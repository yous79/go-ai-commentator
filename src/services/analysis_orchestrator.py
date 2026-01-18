from typing import List
from core.board_simulator import BoardSimulator, SimulationContext
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from core.inference_fact import InferenceFact, FactCategory, FactCollector
from core.analysis_dto import AnalysisResult
from core.board_region import BoardRegion, RegionType
from services.api_client import api_client
from utils.logger import logger

class AnalysisOrchestrator:
    """KataGo, ShapeDetector, StabilityAnalyzer を統合し、整理された『事実セット』を構築する責任を持つ"""

    def __init__(self, board_size=19):
        self.board_size = board_size
        self.simulator = BoardSimulator(board_size)
        self.detector = ShapeDetector(board_size)
        self.stability_analyzer = StabilityAnalyzer(board_size)
        self.board_region = BoardRegion(board_size)

    def analyze_full(self, history, board_size=None) -> FactCollector:
        """全ての解析を実行し、トリアージ済みの FactCollector を返す"""
        bs = board_size or self.board_size
        collector = FactCollector()
        
        logger.info(f"Full Analysis Orchestration Start (History len: {len(history)})", layer="ORCHESTRATOR")

        # 1. KataGo 基本解析
        ana_data = api_client.analyze_move(history, bs, include_pv=True)
        if not ana_data:
            collector.add(FactCategory.STRATEGY, "APIサーバーから解析データを取得できませんでした。", severity=5)
            return collector

        # 2. コンテキスト復元
        curr_ctx = self.simulator.reconstruct_to_context(history, bs)

        # 3. 形状検知 (現在)
        shape_facts = self.detector.detect_facts(curr_ctx.board, curr_ctx.prev_board, analysis_result=ana_data)
        for f in shape_facts: collector.facts.append(f)

        # 4. 緊急度 & 未来予測
        urgency_data = api_client.analyze_urgency(history, bs)
        if urgency_data:
            u_severity = 5 if urgency_data['is_critical'] else 2
            u_desc = f"この局面の緊急度は {urgency_data['urgency']:.1f}目 です。{'一手の緩みも許されない急場です。' if urgency_data['is_critical'] else '比較的平穏な局面です。'}"
            collector.add(FactCategory.URGENCY, u_desc, u_severity, urgency_data)
            
            # 未来の悪形警告
            thr_pv = urgency_data.get('opponent_pv')
            if thr_pv:
                thr_seq = ["pass"] + thr_pv
                future_ctx = self.simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=urgency_data['next_player'])
                future_shape_facts = self.detector.detect_facts(future_ctx.board, future_ctx.prev_board)
                for f in future_shape_facts:
                    if f.severity >= 4:
                        f.description = f"放置すると {f.description} という悪形が発生する恐れがあります。"
                        collector.facts.append(f)

        # 5. 安定度分析
        ownership = ana_data.ownership
        if ownership:
            stability_facts = self.stability_analyzer.analyze_to_facts(curr_ctx.board, ownership)
            for f in stability_facts: collector.facts.append(f)

        # 6. 影響力（勢力）分析 [NEW]
        influence = ana_data.influence
        if influence:
            inf_facts = self._analyze_influence(influence, ownership)
            for f in inf_facts: collector.facts.append(f)

        # 7. 基本統計
        wr = ana_data.winrate
        sl = ana_data.score_lead
        collector.add(FactCategory.STRATEGY, f"現在の勝率(黒): {ana_data.winrate_label}, 目数差: {sl:.1f}目", severity=3)

        # 8. 解析データ自体の保持（後続のPV表示などのため）
        collector.raw_analysis = ana_data 
        collector.context = curr_ctx

        return collector

    def _analyze_influence(self, influence: List[float], ownership: List[float]) -> List[InferenceFact]:
        """影響力データを解析し、エリアごとの情勢（地 vs 勢力）を抽出する"""
        facts = []
        
        # 1. エリア別統計の算出
        region_stats = {rt: {"own": 0.0, "inf": 0.0, "count": 0} for rt in RegionType}
        
        for i in range(len(influence)):
            r = i // self.board_size
            c = i % self.board_size
            
            # Pointオブジェクトを介さずに、座標から直接リージョンを取得する簡易ロジック
            # BoardRegion.get_region は Point を要求するため、ここだけ少し工夫が必要
            # 今回は BoardRegion の内部ロジックを再利用するため、簡易Pointを作るか、
            # BoardRegionに (r,c) を受け取るメソッドがあればよいが、
            # 既存の Point クラスを使うのが最も安全
            from core.point import Point
            pt = Point(r, c)
            rt = self.board_region.get_region(pt)
            
            own = ownership[i] if ownership else 0
            inf = influence[i]
            
            region_stats[rt]["own"] += own
            region_stats[rt]["inf"] += inf
            region_stats[rt]["count"] += 1

        # 2. エリアごとの評価と事実生成
        for rt, stats in region_stats.items():
            count = stats["count"]
            if count == 0: continue
            
            avg_own = stats["own"] / count
            avg_inf = stats["inf"] / count
            
            # 閾値設定
            TERRITORY_THRES = 0.4
            INFLUENCE_THRES = 0.3
            
            # 状態判定
            status_own = "中立"
            if avg_own > TERRITORY_THRES: status_own = "黒地"
            elif avg_own < -TERRITORY_THRES: status_own = "白地"
            
            status_inf = "互角"
            if avg_inf > INFLUENCE_THRES: status_inf = "黒勢力"
            elif avg_inf < -INFLUENCE_THRES: status_inf = "白勢力"
            
            # 特徴的な乖離を検知
            msg = ""
            if status_own == "黒地" and status_inf == "白勢力":
                msg = f"{rt.value}は黒の実利ですが、白の厚みが勝り、薄い状態です。"
            elif status_own == "白地" and status_inf == "黒勢力":
                msg = f"{rt.value}は白の実利ですが、黒の厚みが勝り、薄い状態です。"
            elif status_own == "中立":
                if status_inf == "黒勢力":
                    msg = f"{rt.value}は黒の有望な模様（勢力圏）となっています。"
                elif status_inf == "白勢力":
                    msg = f"{rt.value}は白の有望な模様（勢力圏）となっています。"
            
            if msg:
                facts.append(InferenceFact(FactCategory.STRATEGY, msg, severity=3))

        return facts
