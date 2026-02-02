from core.inference_fact import FactCollector, FactCategory, TemporalScope, KoMetadata
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from .base import BaseFactProvider

class KoFactProvider(BaseFactProvider):
    """コウの発生や解消を検知するプロバイダ"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 1. コウの発生（今打たれた手によって石が1つ取られた）
        if context.captured_points and len(context.captured_points) == 1:
            cap_pt = context.captured_points[0]
            msg = f"最新の着手によって {cap_pt.to_gtp()} の石が取られました。コウの争いが始まる可能性があります。"
            collector.add(FactCategory.STRATEGY, msg, severity=4, metadata=KoMetadata(type="ko_initiation", point=cap_pt.to_gtp()), scope=TemporalScope.IMMEDIATE)
