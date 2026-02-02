from core.inference_fact import FactCollector, FactCategory, TemporalScope
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class BasicStatsFactProvider(BaseFactProvider):
    """勝率や目数差などの基本統計情報を提供"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        sl = analysis.score_lead
        collector.add(
            FactCategory.STRATEGY, 
            f"現在の勝率(黒): {analysis.winrate_label}, 目数差: {sl:.1f}目", 
            severity=3, 
            scope=TemporalScope.EXISTING
        )
