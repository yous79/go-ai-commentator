import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

import asyncio
from core.game_board import GameBoard, Color
from core.point import Point
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from core.inference_fact import FactCollector, AtsumiMetadata, MoyoMetadata
from core.stability_analyzer import StabilityAnalyzer
from services.fact_providers import StrategicFactProvider, InfluenceFactProvider
from core.board_region import RegionType

async def test_atsumi():
    print("--- Testing Atsumi Detection ---")
    board_size = 9
    board = GameBoard(board_size)
    
    # Create a strong black group in center
    stones = [(4,4), (4,5), (5,4), (5,5)]
    for r, c in stones:
        # Use underlying byte array or public method?
        # GameBoard has play(point, color).
        board.play(Point(r, c), Color.BLACK)
        
    # Fake Analysis
    ownership = [0.0] * (board_size * board_size)
    for r, c in stones:
        idx = r * board_size + c
        ownership[idx] = 1.0 # Strong ownership

    # Influence: High positive around center
    influence = [0.0] * (board_size * board_size)
    for r in range(board_size):
        for c in range(board_size):
            if 2 <= r <= 7 and 2 <= c <= 7:
                influence[r*board_size + c] = 2.0
                
    analysis = AnalysisResult(
        winrate=0.5,
        score_lead=0.0,
        ownership=ownership,
        influence=influence,
        candidates=[]
    )
    
    context = SimulationContext(
        board=board, 
        history=[], 
        captured_points=[],
        prev_board=board, # dummy
        last_move=None,
        last_color=Color.WHITE, # dummy
        board_size=board_size
    )
    collector = FactCollector()
    analyzer = StabilityAnalyzer(board_size)
    
    provider = StrategicFactProvider(board_size, analyzer)
    await provider.provide_facts(collector, context, analysis)
    
    atsumi_found = False
    for fact in collector.facts:
        print(f"[{fact.category.name}] {fact.description}")
        if isinstance(fact.metadata, AtsumiMetadata):
            print(f"  Atsumi Found! Strength: {fact.metadata.strength}, Inf: {fact.metadata.influence_power:.2f}")
            atsumi_found = True
            
    if not atsumi_found:
        print("FAIL: No Atsumi detected.")

async def test_moyo():
    print("\n--- Testing Moyo Detection ---")
    board_size = 9
    board = GameBoard(board_size)
    context = SimulationContext(
        board=board, 
        history=[], 
        captured_points=[],
        prev_board=board,
        last_move=None,
        last_color=Color.WHITE,
        board_size=board_size
    )
    
    ownership = [0.0] * (board_size * board_size)
    influence = [0.0] * (board_size * board_size)
    
    # Set top-right corner area as Moyo (Size 16)
    moyo_points = []
    for r in range(4):
        for c in range(5, 9):
            idx = r * board_size + c
            ownership[idx] = 0.6
            influence[idx] = 1.0
            moyo_points.append((r,c))
            
    analysis = AnalysisResult(
        winrate=0.5,
        score_lead=0.0,
        ownership=ownership,
        influence=influence,
        candidates=[]
    )
    
    collector = FactCollector()
    
    class MockRegion:
        def get_region(self, p):
            return RegionType.CENTER
            
    provider = InfluenceFactProvider(board_size, MockRegion())
    await provider.provide_facts(collector, context, analysis)
    
    moyo_found = False
    for fact in collector.facts:
        if isinstance(fact.metadata, MoyoMetadata):
            print(f"[{fact.category.name}] {fact.description}")
            print(f"  Moyo Found! Label: {fact.metadata.label}, Size: {fact.metadata.size}, Pot: {fact.metadata.potential:.2f}")
            moyo_found = True
            
    if not moyo_found:
        print("FAIL: No Moyo detected.")

if __name__ == "__main__":
    asyncio.run(test_atsumi())
    asyncio.run(test_moyo())
