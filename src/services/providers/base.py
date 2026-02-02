from abc import ABC, abstractmethod
from core.inference_fact import FactCollector
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult

class BaseFactProvider(ABC):
    """事実生成プロバイダの抽象基底クラス"""
    
    def __init__(self, board_size: int):
        self.board_size = board_size

    @abstractmethod
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        """解析事実を生成してコレクターに追加する"""
        pass
