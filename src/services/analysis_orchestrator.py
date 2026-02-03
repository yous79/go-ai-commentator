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
    BasicStatsFactProvider,
    StrategicFactProvider,
    MoveQualityFactProvider
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
            ShapeFactProvider(board_size, self.detector, self.simulator),
            UrgencyFactProvider(board_size, self.simulator, self.detector),
            StabilityFactProvider(board_size, self.stability_analyzer),
            StrategicFactProvider(board_size, self.stability_analyzer),
            MoveQualityFactProvider(board_size),
            EndgameFactProvider(board_size),
            InfluenceFactProvider(board_size, self.board_region),
            KoFactProvider(board_size)
        ]

    async def analyze_full(self, history, board_size=None, prev_analysis: Optional[AnalysisResult] = None) -> FactCollector:
        """全ての解析事実を収集し、トリアージ済みの FactCollector を返す (非同期並列版)"""
        import asyncio
        bs = board_size or self.board_size
        collector = FactCollector()
        
        logger.info(f"Full Analysis Orchestration Start (History len: {len(history)})", layer="ORCHESTRATOR")

        # 1. KataGo 基本解析
        logger.debug("Step 1: KataGo Base Analysis started...", layer="ORCHESTRATOR")
        import time
        t0 = time.time()
        ana_data = await asyncio.to_thread(api_client.analyze_move, history, bs, include_pv=True)
        logger.debug(f"Step 1 finished in {time.time()-t0:.2f}s", layer="ORCHESTRATOR")
        
        if not ana_data:
            collector.add(FactCategory.STRATEGY, "APIサーバーから解析データを取得できませんでした。", severity=5)
            return collector

        # 2. 盤面コンテキストの復元
        logger.debug("Step 2: Reconstructing Board Context...", layer="ORCHESTRATOR")
        t0 = time.time()
        curr_ctx = await asyncio.to_thread(self.simulator.reconstruct_to_context, history, bs)
        curr_ctx.prev_analysis = prev_analysis
        logger.debug(f"Step 2 finished in {time.time()-t0:.2f}s", layer="ORCHESTRATOR")

        # 3. 各プロバイダによる事実生成の並列実行
        logger.debug("Step 3: Fact Generation (Parallel) started...", layer="ORCHESTRATOR")
        
        # 解析対象のサイズを内部コンポーネントに同期
        self.simulator.board_size = bs
        self.detector.board_size = bs
        self.stability_analyzer.board_size = bs
        self.board_region.board_size = bs

        t0 = time.time()
        tasks = []
        for provider in self.providers:
            provider.board_size = bs
            tasks.append(provider.provide_facts(collector, curr_ctx, ana_data))
        
        # タイムアウトを設定して実行 (個別のプロバイダの遅延が全体を止めないようにする)
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=45.0)
        except asyncio.TimeoutError:
            logger.error("Fact generation timed out!", layer="ORCHESTRATOR")
            collector.add(FactCategory.STRATEGY, "一部の解析（緊急度など）が制限時間内に完了しませんでした。", severity=3)
        
        logger.debug(f"Step 3 finished in {time.time()-t0:.2f}s", layer="ORCHESTRATOR")

        # 6. 後続処理用のデータ保持
        collector.raw_analysis = ana_data 
        collector.context = curr_ctx

        return collector
