import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.game_state import GoGameState

def test_mistake_calculation():
    print("--- Testing Mistake Calculation Logic ---")
    gs = GoGameState()
    
    # Mock moves with analysis data
    # Move 0: Root (WR 50%)
    # Move 1: Black (WR drops to 30%) -> Mistake!
    # Move 2: White (WR back to 50% for Black, meaning WR drops for White) -> Mistake!
    gs.moves = [
        {"winrate": 0.5, "score": 0.0}, # 0
        {"winrate": 0.3, "score": -5.0}, # 1 (Black mistake: -20% / -5.0)
        {"winrate": 0.6, "score": 2.0},  # 2 (White mistake: Black +30% / +7.0)
    ]
    
    mb, mw = gs.calculate_mistakes()
    
    print(f"Black mistakes: {mb}")
    print(f"White mistakes: {mw}")
    
    # Verification
    # Black move 1: after(0.3) - before(0.5) = -0.2 (drop 0.2)
    # White move 2: before(0.3) - after(0.6) = -0.3 (actually after - before in logic)
    # White logic: sc_after(2.0) - sc_before(-5.0) = 7.0, wr_after(0.6) - wr_before(0.3) = 0.3
    
    assert mb[0][1] == 0.2
    assert mw[0][1] == 0.3
    print("SUCCESS: Mistake calculation logic is correct.")

if __name__ == "__main__":
    test_mistake_calculation()
