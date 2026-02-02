import asyncio
from core.inference_fact import FactCollector, TemporalScope
from core.board_simulator import SimulationContext
from core.shape_detector import ShapeDetector
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class ShapeFactProvider(BaseFactProvider):
    """現局面の幾何学的形状を検知するプロバイダ"""
    
    def __init__(self, board_size: int, detector: ShapeDetector):
        super().__init__(board_size)
        self.detector = detector

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 形状検知はCPU負荷が高いため、必要に応じて thread で実行
        shape_facts = await asyncio.to_thread(self.detector.detect_facts, context, analysis_result=analysis)
        for f in shape_facts:
            f.scope = TemporalScope.IMMEDIATE
            collector.add_fact(f)
