from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from core.inference_fact import (
    InferenceFact, FactCategory, FactCollector, TemporalScope, 
    BaseFactMetadata, GamePhaseMetadata, KoMetadata, UrgencyMetadata, ShapeMetadata
)
from core.board_simulator import SimulationContext, BoardSimulator
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_dto import AnalysisResult
from core.board_region import BoardRegion, RegionType
from services.api_client import api_client
from utils.logger import logger

class BaseFactProvider(ABC):
    """事実生成プロバイダの抽象基底クラス"""
    
    def __init__(self, board_size: int):
        self.board_size = board_size

    @abstractmethod
    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        """解析事実を生成してコレクターに追加する"""
        pass

class ShapeFactProvider(BaseFactProvider):
    """現局面の幾何学的形状を検知するプロバイダ"""
    
    def __init__(self, board_size: int, detector: ShapeDetector):
        super().__init__(board_size)
        self.detector = detector

    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        shape_facts = self.detector.detect_facts(context, analysis_result=analysis)
        for f in shape_facts:
            f.scope = TemporalScope.IMMEDIATE
            collector.facts.append(f)

class StabilityFactProvider(BaseFactProvider):
    """石の安定度（生存確率）を解析するプロバイダ"""
    
    def __init__(self, board_size: int, stability_analyzer: StabilityAnalyzer):
        super().__init__(board_size)
        self.analyzer = stability_analyzer

    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if analysis.ownership:
            # uncertainty map might be None if engine doesn't support it
            uncertainty_map = getattr(analysis, 'uncertainty', None)
            stability_facts = self.analyzer.analyze_to_facts(context.board, analysis.ownership, uncertainty_map)
            for f in stability_facts:
                f.scope = TemporalScope.EXISTING
                collector.facts.append(f)

class EndgameFactProvider(BaseFactProvider):
    """局面が終盤（ヨセ）に入ったかを判定するプロバイダ"""
    
    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.ownership:
            return
            
        SETTLED_THRESHOLD = 0.9
        settled_points = sum(1 for val in analysis.ownership if abs(val) > SETTLED_THRESHOLD)
        settlement_ratio = settled_points / len(analysis.ownership)
        
        if settlement_ratio > 0.85:
            collector.add(
                FactCategory.STRATEGY, 
                "【局面ステータス】終盤（ヨセ）に入りました。細かな得失と正確な計算が重要です。", 
                severity=2, 
                metadata=GamePhaseMetadata(phase="endgame"), 
                scope=TemporalScope.EXISTING
            )

class InfluenceFactProvider(BaseFactProvider):
    """エリアごとの勢力バランスを分析するプロバイダ"""
    
    def __init__(self, board_size: int, board_region: BoardRegion):
        super().__init__(board_size)
        self.board_region = board_region

    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.influence:
            return
            
        region_stats = {rt: {"own": 0.0, "inf": 0.0, "count": 0} for rt in RegionType}
        from core.point import Point
        
        for i, inf_val in enumerate(analysis.influence):
            r, c = i // self.board_size, i % self.board_size
            rt = self.board_region.get_region(Point(r, c))
            own = analysis.ownership[i] if analysis.ownership else 0
            
            region_stats[rt]["own"] += own
            region_stats[rt]["inf"] += inf_val
            region_stats[rt]["count"] += 1

        for rt, stats in region_stats.items():
            if stats["count"] == 0: continue
            avg_own, avg_inf = stats["own"] / stats["count"], stats["inf"] / stats["count"]
            
            msg = self._judge_influence(rt, avg_own, avg_inf)
            if msg:
                collector.add(FactCategory.STRATEGY, msg, severity=3, scope=TemporalScope.EXISTING)

    def _judge_influence(self, rt: RegionType, avg_own: float, avg_inf: float) -> str:
        TERRITORY_THRES, INFLUENCE_THRES = 0.4, 0.3
        
        status_own = "中立"
        if avg_own > TERRITORY_THRES: status_own = "黒地"
        elif avg_own < -TERRITORY_THRES: status_own = "白地"
        
        status_inf = "互角"
        if avg_inf > INFLUENCE_THRES: status_inf = "黒勢力"
        elif avg_inf < -INFLUENCE_THRES: status_inf = "白勢力"
        
        if status_own == "黒地" and status_inf == "白勢力":
            return f"{rt.value}は黒の実利ですが、白の厚みが勝り、薄い状態です。"
        elif status_own == "白地" and status_inf == "黒勢力":
            return f"{rt.value}は白の実利ですが、黒の厚みが勝り、薄い状態です。"
        elif status_own == "中立":
            if status_inf == "黒勢力": return f"{rt.value}は黒の有望な模様（勢力圏）となっています。"
            elif status_inf == "白勢力": return f"{rt.value}は白の有望な模様（勢力圏）となっています。"
        return ""

class UrgencyFactProvider(BaseFactProvider):
    """着手の緊急度および将来の悪形予測を行うプロバイダ"""
    
    def __init__(self, board_size: int, simulator: BoardSimulator, detector: ShapeDetector):
        super().__init__(board_size)
        self.simulator = simulator
        self.detector = detector

    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        history = context.history
        bs = self.board_size
        
        urgency_data = api_client.analyze_urgency(history, bs)
        if urgency_data:
            u_severity = 5 if urgency_data['is_critical'] else 2
            u_desc = f"この局面の緊急度は {urgency_data['urgency']:.1f}目 です。{'一手の緩みも許されない急場です。' if urgency_data['is_critical'] else '比較的平穏な局面です。'}"
            
            meta = UrgencyMetadata(
                urgency=urgency_data['urgency'],
                is_critical=urgency_data['is_critical'],
                next_player=urgency_data['next_player']
            )
            collector.add(FactCategory.URGENCY, u_desc, u_severity, meta, scope=TemporalScope.EXISTING)
            
            # 未来の悪形警告
            thr_pv = urgency_data.get('opponent_pv')
            if thr_pv:
                thr_seq = ["pass"] + thr_pv
                future_ctx = self.simulator.simulate_sequence(context, thr_seq, starting_color=urgency_data['next_player'])
                future_shape_facts = self.detector.detect_facts(future_ctx)
                for f in future_shape_facts:
                    if f.severity >= 4:
                        f.description = f"放置すると {f.description} という悪形が発生する恐れがあります。"
                        f.scope = TemporalScope.PREDICTED
                        collector.facts.append(f)

class KoFactProvider(BaseFactProvider):
    """コウの発生や解消を検知するプロバイダ"""
    
    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 1. コウの発生（今打たれた手によって石が1つ取られた）
        if context.captured_points and len(context.captured_points) == 1:
            cap_pt = context.captured_points[0]
            msg = f"最新の着手によって {cap_pt.to_gtp()} の石が取られました。コウの争いが始まる可能性があります。"
            collector.add(FactCategory.STRATEGY, msg, severity=4, metadata=KoMetadata(type="ko_initiation", point=cap_pt.to_gtp()), scope=TemporalScope.IMMEDIATE)

class BasicStatsFactProvider(BaseFactProvider):
    """勝率や目数差などの基本統計情報を提供"""
    
    def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        sl = analysis.score_lead
        collector.add(
            FactCategory.STRATEGY, 
            f"現在の勝率(黒): {analysis.winrate_label}, 目数差: {sl:.1f}目", 
            severity=3, 
            scope=TemporalScope.EXISTING
        )
