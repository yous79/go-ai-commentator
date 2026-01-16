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
        ownership = ana_data.get('ownership')
        if ownership:
            stability_facts = self.stability_analyzer.analyze_to_facts(curr_ctx.board, ownership)
            for f in stability_facts: collector.facts.append(f)

        # 6. 基本統計
        wr = ana_data.get('winrate_black', 0.5)
        sl = ana_data.get('score_lead_black', 0.0)
        collector.add(FactCategory.STRATEGY, f"現在の勝率(黒): {wr:.1%}, 目数差: {sl:.1f}目", severity=3)

        # 7. 解析データ自体の保持（後続のPV表示などのため）
        collector.raw_analysis = ana_data 
        collector.context = curr_ctx

        return collector
