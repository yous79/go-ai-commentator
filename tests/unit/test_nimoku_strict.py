import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_nimoku_atama_strict():
    print("Testing Strict Nimoku no Atama Logic...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # シナリオ1: 承認された正常パターン (F7:B, F6-F5:W, E6-E5:B)
    history_ok = [
        ["W", "F5"], ["B", "E5"],
        ["W", "F6"], ["B", "E6"],
        ["B", "F7"]
    ]
    curr_ok, prev_ok, last_ok = simulator.reconstruct(history_ok)
    ids_ok = detector.detect_ids(curr_ok, prev_ok, last_ok)
    print(f"Scenario 1 (Valid): {ids_ok}")

    # シナリオ2: 側面石がないパターン (F7:B, F6-F5:W)
    history_no_side = [
        ["W", "F5"], ["B", "A1"], # A1は関係ない場所
        ["W", "F6"], ["B", "A2"],
        ["B", "F7"]
    ]
    curr_ns, prev_ns, last_ns = simulator.reconstruct(history_no_side)
    ids_ns = detector.detect_ids(curr_ns, prev_ns, last_ns)
    print(f"Scenario 2 (No Side Stones): {ids_ns}")

    # シナリオ3: 三目あるパターン (F7:B, F6-F5-F4:W, E6-E5-E4:B)
    history_three = [
        ["W", "F4"], ["B", "E4"],
        ["W", "F5"], ["B", "E5"],
        ["W", "F6"], ["B", "E6"],
        ["B", "F7"]
    ]
    curr_3, prev_3, last_3 = simulator.reconstruct(history_three)
    ids_3 = detector.detect_ids(curr_3, prev_3, last_3)
    print(f"Scenario 3 (Three Stones): {ids_3}")

    success = ("nimoku_atama" in ids_ok and 
               "nimoku_atama" not in ids_ns and 
               "nimoku_atama" not in ids_3)
    
    if success:
        print("\nALL STRICT TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should be detected: {'nimoku_atama' in ids_ok}")
        print(f" - Should NOT be detected (No Side): {'nimoku_atama' not in ids_ns}")
        print(f" - Should NOT be detected (Three): {'nimoku_atama' not in ids_3}")

if __name__ == "__main__":
    test_nimoku_atama_strict()
