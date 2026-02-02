from core.inference_fact import FactCollector, FactCategory, TemporalScope, GamePhaseMetadata
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class EndgameFactProvider(BaseFactProvider):
    """局面が終盤（ヨセ）に入ったかを判定するプロバイダ"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
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
