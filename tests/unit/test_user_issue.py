import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_user_scenario():
    print("Testing User's Nimoku no Atama Scenario...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # User's Board:
    # 7 . . . . . B . . . (F7 is Black)
    # 6 . . . . B W . . . (E6 is Black, F6 is White)
    # 5 . . . . B W . . . (E5 is Black, F5 is White)
    # White stones: F5, F6. Black hits F7.
    
    history = [
        ["W", "F5"], ["B", "E5"],
        ["W", "F6"], ["B", "E6"],
        ["B", "F7"]  # Last move: Black hits the head
    ]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    
    # Manually check F7, F6, F5 in simulator indices
    # Rank 7 is row 2, Rank 6 is row 3, Rank 5 is row 4. Col F is index 5.
    print(f"F7 stone: {curr_b.get(2, 5)}")
    print(f"F6 stone: {curr_b.get(3, 5)}")
    print(f"F5 stone: {curr_b.get(4, 5)}")
    print(f"F8 (back) stone: {curr_b.get(1, 5)}") # Should be None
    
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Detected IDs: {ids}")
    
    if "nimoku_atama" in ids:
        print("SUCCESS: Nimoku no Atama detected in user scenario.")
    else:
        print("FAILED: Nimoku no Atama NOT detected.")
        # Check Aki-sankaku just in case
        facts = detector.detect_all(curr_b, prev_b, last_c)
        print(f"Report:\n{facts}")

if __name__ == "__main__":
    test_user_scenario()
