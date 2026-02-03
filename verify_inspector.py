import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from core.game_board import GameBoard, Color
from core.point import Point
from core.inference_fact import FactCollector, FactCategory, TemporalScope
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult, MoveCandidate
from services.providers.strategy import StrategicFactProvider
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_config import AnalysisConfig
from utils.logger import logger

# setup_logger() called implicitly on import

async def run_verification():
    print("=== Starting Logic Inspector Verification ===")
    
    # Setup Board with a "marginal" status group
    # Black stone at 3,3. Ownership 0.88.
    # Default Atsumi Threshold is 0.90. -> Should NOT be Atsumi.
    # If we lower threshold to 0.85 -> Should BE Atsumi.
    
    board = GameBoard(19)
    board.play(Point(2, 2), Color.BLACK) # 3-3 point
    
    # Mock Analysis Result
    ownership = [0.0] * 361
    ownership[40] = 0.88 # Top-Left?
    ownership[306] = 0.88 # Bottom-Left? (16*19+2)
    
    analysis = AnalysisResult(
        winrate=0.5,
        score_lead=0.0,
        candidates=[],
        ownership=ownership,
        influence=None
    )
    
    analyzer = StabilityAnalyzer()
    provider = StrategicFactProvider(19, analyzer)
    
    # 1. Test with Default Threshold (0.90)
    print("\n--- Test 1: Default Threshold (0.90) ---")
    
    # Mock Context
    prev_board = board # Just use same board for simplicity
    ctx = SimulationContext(
        board=board,
        prev_board=prev_board,
        history=[["b", "C3"]],
        last_move=Point(2,2), # Just played
        last_color=Color.BLACK,
        prev_analysis=analysis, # Use mock analysis
    )
    
    collector = FactCollector()
    await provider.provide_facts(collector, ctx, analysis)
    
    atsumi_facts = [f for f in collector.facts if "厚み" in f.description]
    print(f"Facts found (Default): {len(atsumi_facts)}")
    for f in atsumi_facts: print(f" - {f.description}")
    
    # Expected: 0 facts (0.88 < 0.90) or maybe some if logic differs.
    # StabilityAnalyzer: 0.88 -> "strong" (>=0.8)
    # StrategicFactProvider: if strong, check if val < ATSUMI_THRESHOLD (0.90).
    # 0.88 < 0.90 -> Continue (Skip). So 0 facts expected.
    
    if len(atsumi_facts) == 0:
        print("SUCCESS: No Atsumi detected with 0.88 ownership (Threshold 0.90)")
    else:
        print("FAILURE: Atsumi detected unexpectedly")

    # 2. Test with Lower Threshold (0.80)
    print("\n--- Test 2: Lower Threshold (0.80) ---")
    AnalysisConfig.set_param("ATSUMI_THRESHOLD", 0.80)
    
    # analysis.ownership is already set
    
    # Debug: Check StabilityAnalyzer output
    # Need to pass ownership directly
    results = analyzer.analyze(prev_board, ownership, None)
    for grp in results:
        print(f"Debug Group: {grp.stones}, Status: {grp.status}, Stability: {grp.stability}")
    
    collector2 = FactCollector()
    await provider.provide_facts(collector2, ctx, analysis)
    
    atsumi_facts2 = [f for f in collector2.facts if "厚み" in f.description]
    print(f"Facts found (Lowered): {len(atsumi_facts2)}")
    
    # Expected: Should be detected now?
    # Logic: if current_val (0.88) < 0.80 -> Continue.
    # 0.88 >= 0.80 -> Proceed.
    # But wait, logic also checks distance to last move etc.
    # "is_near" check: last_move is (2,2). Stone is (2,2). dist=0.
    # Group is own color.
    # Message: "警告：重複 ... 自身の厚みに近すぎます" (Overconcentration)
    # This fact should be generated if it passes threshold check.
    
    if len(atsumi_facts2) > 0:
        print("SUCCESS: Atsumi detected with 0.88 ownership (Threshold 0.80)")
        for f in atsumi_facts2: print(f" - {f.description}")
    else:
        print("FAILURE: Atsumi NOT detected even with lower threshold")
        
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(run_verification())
