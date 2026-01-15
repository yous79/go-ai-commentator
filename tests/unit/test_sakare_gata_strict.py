import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_sakare_gata_perfect():
    print("Testing Perfect Sakare-gata Logic (3-stone wall for Ikken-tobi)...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # シナリオ1: 2石の壁（C5が空いている） -> サカレ形ではない
    # B D4, B D6 に対し W D5, W E5 のみ
    history_incomplete = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"], ["B", "A1"], ["W", "E5"]
    ]
    curr_i, prev_i, last_i = simulator.reconstruct(history_incomplete)
    ids_i = detector.detect_ids(curr_i, prev_i, last_i)
    print(f"Scenario 1 (2-stone wall): {ids_i}")

    # シナリオ2: 3石の壁（C5, D5, E5） -> 完璧なサカレ形
    history_perfect = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"], ["B", "A1"], ["W", "E5"], ["B", "A2"], ["W", "C5"]
    ]
    curr_p, prev_p, last_p = simulator.reconstruct(history_perfect)
    ids_p = detector.detect_ids(curr_p, prev_p, last_p)
    print(f"Scenario 2 (3-stone wall): {ids_p}")

    success = ("sakare_gata" not in ids_i and 
               "sakare_gata" in ids_p)
    
    if success:
        print("\nALL PERFECT SAKARE-GATA TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should NOT detect 2-stone wall: {'sakare_gata' not in ids_i}")
        print(f" - Should detect 3-stone wall: {'sakare_gata' in ids_p}")

if __name__ == "__main__":
    test_perfect_sakare_gata() if False else test_sakare_gata_perfect()
