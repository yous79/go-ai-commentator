import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from core.game_board import GameBoard, Color
from core.point import Point
from core.inference_fact import FactCollector
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult, MoveCandidate
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_config import AnalysisConfig
from services.providers.strategy import StrategicFactProvider

async def main():
    print("=== Starting Scrap Stone Logic v2 Verification ===")
    
    # Setup
    analyzer = StabilityAnalyzer(19)
    provider = StrategicFactProvider(19, analyzer)
    
    # 1. 盤面準備: 黒石一つ (C3)
    board = GameBoard(19)
    # 3-3 point pt(2,2)
    board.play(Point(2, 2), Color.BLACK) # C3
    
    # 前回の盤面（C3がある状態）
    prev_board = board
    
    # 2. 前回の解析状況 (Ownership)
    # C3を「死に体(Critical)」にする
    # 3-3 point index = 2*19 + 2 = 40 (Top-Down index for KataGo)
    ownership = [0.0] * 361
    ownership[40] = 0.1 # Very weak (Critical threshold is 0.2)
    ownership[306] = 0.1 # Bottom-up symmetric for safety
    
    prev_analysis = AnalysisResult(
        winrate=0.5,
        score_lead=0.0,
        ownership=ownership
    )
    
    # --- Test Case 1: カス石救済（損失あり） ---
    print("\n--- Test 1: Saving Critical Stone with High Loss ---")
    
    # 次の手: D3 (C3の隣) に黒が打つ
    move = Point(2, 3) # D3
    last_color = Color.BLACK
    
    # 現在の解析結果
    # 最善手は別の場所とする
    candidates = [
        MoveCandidate(move="Q16", winrate=0.5, score_lead=10.0), # Best
        MoveCandidate(move="D17", winrate=0.3, score_lead=5.0)    # D3 is move(2,3) -> D17 in top-down index if flipped? 
                                                                # Point(2,3) to GTP is "D3". Let's use GTP.
    ]
    # Update current candidate move to match last_move.to_gtp()
    candidates[1] = MoveCandidate(move=move.to_gtp(), winrate=0.3, score_lead=5.0)
    
    analysis = AnalysisResult(
        winrate=0.3,
        score_lead=5.0,
        candidates=candidates,
        ownership=ownership # Simplified
    )
    
    context = SimulationContext(
        board=board,
        prev_board=prev_board,
        history=[],
        last_move=move,
        last_color=last_color,
        prev_analysis=prev_analysis
    )
    
    collector = FactCollector()
    await provider.provide_facts(collector, context, analysis)
    
    print(f"Facts found (Test 1): {len(collector.facts)}")
    for f in collector.facts:
        print(f" - {f.description}")
        if "救済不要" in f.description:
            print("SUCCESS: 'Kasu-ishi' warning detected.")
    
    # --- Test Case 2: 活用（損失なし） ---
    print("\n--- Test 2: Touching Critical Stone with Low Loss (Best Move) ---")
    
    # 最善手を D3 にする
    candidates_low_loss = [
        MoveCandidate(move=move.to_gtp(), winrate=0.5, score_lead=10.0)
    ]
    
    analysis_low_loss = AnalysisResult(
        winrate=0.5,
        score_lead=10.0,
        candidates=candidates_low_loss,
        ownership=ownership
    )
    
    collector_low = FactCollector()
    await provider.provide_facts(collector_low, context, analysis_low_loss)
    
    print(f"Facts found (Test 2): {len(collector_low.facts)}")
    for f in collector_low.facts:
        print(f" - {f.description}")
        if "活用" in f.description:
            print("SUCCESS: 'Utilization' message detected instead of warning.")
    
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
