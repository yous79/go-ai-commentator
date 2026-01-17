from typing import List
from core.board_simulator import BoardSimulator, SimulationContext
from core.inference_fact import InferenceFact, FactCategory, FactCollector
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from services.api_client import api_client
from utils.logger import logger

class AnalysisOrchestrator:
    """KataGo, ShapeDetector, StabilityAnalyzer を統合し、整理された『事実セット』を構築する責任を持つ"""

    def __init__(self, board_size=19):
        self.board_size = board_size
        self.simulator = BoardSimulator(board_size)
        self.detector = ShapeDetector(board_size)
        self.stability_analyzer = StabilityAnalyzer(board_size)

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
        """影響力データを解析し、模様や勢力の事実を抽出する"""
        facts = []
        bs = self.board_size
        
        black_total = sum(v for v in influence if v > 0)
        white_total = sum(abs(v) for v in influence if v < 0)
        
        # 勢力バランスの判定
        balance_ratio = black_total / (white_total + 0.1)
        if balance_ratio > 1.5:
            facts.append(InferenceFact(FactCategory.STRATEGY, "黒が盤面全体の勢力（厚み）で圧倒しています。", severity=3))
        elif balance_ratio < 0.6:
            facts.append(InferenceFact(FactCategory.STRATEGY, "白が盤面全体の勢力（厚み）で圧倒しています。", severity=3))

        # 模様（Moyo）の特定: 影響力は強いが、まだ地として確定していない領域
        moyo_count_b = 0
        moyo_count_w = 0
        for i in range(len(influence)):
            inf = influence[i]
            own = ownership[i] if ownership else 0
            
            # 黒の模様: 影響力 > 0.5 かつ 所有権 < 0.5
            if inf > 0.5 and own < 0.5:
                moyo_count_b += 1
            # 白の模様: 影響力 < -0.5 かつ 所有権 > -0.5
            elif inf < -0.5 and own > -0.5:
                moyo_count_w += 1
        
        if moyo_count_b > bs * 2:
            facts.append(InferenceFact(FactCategory.STRATEGY, f"黒には将来の地になり得る巨大な模様（約{moyo_count_b}目分）が存在します。", severity=4))
        if moyo_count_w > bs * 2:
            facts.append(InferenceFact(FactCategory.STRATEGY, f"白には将来の地になり得る巨大な模様（約{moyo_count_w}目分）が存在します。", severity=4))
            
        return facts
