from typing import List, Optional
from core.board_simulator import BoardSimulator, SimulationContext
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from core.inference_fact import InferenceFact, FactCategory, FactCollector, TemporalScope
from core.analysis_dto import AnalysisResult
from core.board_region import BoardRegion, RegionType
from services.api_client import api_client
from utils.logger import logger
from services.fact_providers import (
    ShapeFactProvider, 
    StabilityFactProvider, 
    EndgameFactProvider, 
    InfluenceFactProvider,
    KoFactProvider,
    UrgencyFactProvider,
    BaseFactProvider,
    BasicStatsFactProvider
)

class AnalysisOrchestrator:
    """事実生成プロバイダを統括し、整理された『事実セット』を構築する責任を持つ"""

    def __init__(self, board_size=19):
        self.board_size = board_size
        self.simulator = BoardSimulator(board_size)
        self.detector = ShapeDetector(board_size)
        self.stability_analyzer = StabilityAnalyzer(board_size)
        self.board_region = BoardRegion(board_size)
        
        # プロバイダの登録
        self.providers: List[BaseFactProvider] = [
            BasicStatsFactProvider(board_size),
            ShapeFactProvider(board_size, self.detector),
            UrgencyFactProvider(board_size, self.simulator, self.detector),
            StabilityFactProvider(board_size, self.stability_analyzer),
            EndgameFactProvider(board_size),
            InfluenceFactProvider(board_size, self.board_region),
            KoFactProvider(board_size)
        ]

    async def analyze_full(self, history, board_size=None) -> FactCollector:
        """全ての解析事実を収集し、トリアージ済みの FactCollector を返す (非同期並列版)"""
        import asyncio
        bs = board_size or self.board_size
        collector = FactCollector()
        
        logger.info(f"Full Analysis Orchestration Start (History len: {len(history)})", layer="ORCHESTRATOR")

        # 1. KataGo 基本解析
        # ネットワークIOを含むため、別スレッドで実行
        ana_data = await asyncio.to_thread(api_client.analyze_move, history, bs, include_pv=True)
        if not ana_data:
            collector.add(FactCategory.STRATEGY, "APIサーバーから解析データを取得できませんでした。", severity=5)
            return collector

        # 2. 盤面コンテキストの復元 (CPU負荷あり)
        curr_ctx = await asyncio.to_thread(self.simulator.reconstruct_to_context, history, bs)

        # 3. 各プロバイダによる事実生成の並列実行
        tasks = []
        for provider in self.providers:
            provider.board_size = bs
            tasks.append(provider.provide_facts(collector, curr_ctx, ana_data))
        
        await asyncio.gather(*tasks)

        # 5. ルール適合性チェック (デバッグ用)
        if curr_ctx.last_move:
            if not curr_ctx.board.is_legal(curr_ctx.last_move, curr_ctx.last_color):
                logger.warning(f"Analyzed move {curr_ctx.last_move.to_gtp()} is considered ILLEGAL by local rule engine.", layer="ORCHESTRATOR")

        # 6. 後続処理用のデータ保持
        collector.raw_analysis = ana_data 
        collector.context = curr_ctx

        return collector
