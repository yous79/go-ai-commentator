import asyncio
from core.inference_fact import FactCollector, TemporalScope
from core.board_simulator import SimulationContext
from core.shape_detector import ShapeDetector
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class ShapeFactProvider(BaseFactProvider):
    """現局面の幾何学的形状を検知するプロバイダ"""
    
    def __init__(self, board_size: int, detector: ShapeDetector, simulator: SimulationContext = None):
        super().__init__(board_size)
        self.detector = detector
        # simulator check is handled in provide_facts as it might be passed dynamically or initialized differently
        # However, for typing we can hint it. But AnalysisOrchestrator passes it.
        # Let's assume it's passed in __init__ for clean DI
        self.simulator = simulator

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 1. 最新手（実戦）の形状検知
        shape_facts = await asyncio.to_thread(self.detector.detect_facts, context, analysis_result=analysis)
        for f in shape_facts:
            f.scope = TemporalScope.IMMEDIATE
            collector.add_fact(f)

        if not self.simulator or not analysis.candidates:
            return

        # 2. 推奨手（Candidates）の形状予測
        # 上位3手について形状を先読みする
        top_candidates = analysis.candidates[:3]
        
        # 予測処理は重くなる可能性があるため、別スレッド推奨だが、
        # ここではループ回数が少ないため直接実行する（またはまとめてawait asyncio.to_thread）
        
        for cand in top_candidates:
            move_str = cand.move
            if move_str == "pass": continue
            
            # シミュレーション：この候補手を打った後の仮想盤面
            # 注: simulator.simulate_sequence は新しい Context を返す
            try:
                pred_ctx = await asyncio.to_thread(self.simulator.simulate_sequence, context, [move_str])
                
                # その着手地点に発生する事実を検知
                pred_facts = await asyncio.to_thread(self.detector.detect_facts_at, pred_ctx, pred_ctx.last_move)
                
                for f in pred_facts:
                    # 予測スコープに設定
                    f.scope = TemporalScope.PREDICTED
                    
                    # メッセージを「もし〜なら」形式に加工
                    # 既に description には "アキ三角を検知しました" などが入っている
                    original_desc = f.description.replace("検知しました。", "").replace("検知しました", "")
                    f.description = f"推奨手[{move_str}]を選択すると、{original_desc}となります。"
                    
                    # 既存の事実と重複しないように登録
                    collector.add_fact(f)
                    
            except Exception as e:
                pass
