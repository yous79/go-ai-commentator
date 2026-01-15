import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_warikomi_strict():
    print("Testing Strict Warikomi Logic (JSON Engine)...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # シナリオ1: 1石の割り込み (ワリコミ)
    # B D4, B D6 の間に W D5 が割り込んだ
    history_wari1 = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"]
    ]
    curr_w1, prev_w1, last_w1 = simulator.reconstruct(history_wari1)
    ids_w1 = detector.detect_ids(curr_w1, prev_w1, last_w1)
    print(f"Scenario 1 (1-stone): {ids_w1}")

    # シナリオ2: 2石の侵入 (まだ一方が空)
    # B D4, B D6 に対し W D5, W E5 (C5は空)
    history_wari2 = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"], ["B", "A1"], ["W", "E5"]
    ]
    curr_w2, prev_w2, last_w2 = simulator.reconstruct(history_wari2)
    ids_w2 = detector.detect_ids(curr_w2, prev_w2, last_w2)
    print(f"Scenario 2 (2-stone): {ids_w2}")

    # シナリオ3: 3石の壁 (サカレ形) -> ワリコミとしては検知しない
    # B D4, B D6 に対し W D5, W E5, W C5
    history_sakare = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"], ["B", "A1"], ["W", "E5"], ["B", "A2"], ["W", "C5"]
    ]
    curr_s, prev_s, last_s = simulator.reconstruct(history_sakare)
    ids_s = detector.detect_ids(curr_s, prev_s, last_s)
    print(f"Scenario 3 (3-stone Wall - Sakare): {ids_s}")

    success = ("warikomi" in ids_w1 and 
               "warikomi" in ids_w2 and 
               "warikomi" not in ids_s)
    
    if success:
        print("\nALL WARIKOMI STRICT TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should detect 1-stone: {'warikomi' in ids_w1}")
        print(f" - Should detect 2-stone: {'warikomi' in ids_w2}")
        print(f" - Should NOT detect 3-stone (Sakare): {'warikomi' not in ids_s}")

if __name__ == "__main__":
    test_warikomi_strict()
