import asyncio
from core.inference_fact import FactCollector, TemporalScope
from core.board_simulator import SimulationContext
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class StabilityFactProvider(BaseFactProvider):
    """石の安定度（生存確率）を解析するプロバイダ"""
    
    def __init__(self, board_size: int, stability_analyzer: StabilityAnalyzer):
        super().__init__(board_size)
        self.analyzer = stability_analyzer

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if analysis.ownership:
            # uncertainty map might be None if engine doesn't support it
            uncertainty_map = getattr(analysis, 'uncertainty', None)
            stability_facts = await asyncio.to_thread(self.analyzer.analyze_to_facts, context.board, analysis.ownership, uncertainty_map)
            for f in stability_facts:
                f.scope = TemporalScope.EXISTING
                collector.add_fact(f)
