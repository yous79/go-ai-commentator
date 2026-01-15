import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_sakare_gata_strict():
    print("Testing New Strict Sakare-gata Logic (JSON Engine)...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # シナリオ1: 1石の割り込み (ワリコミ) -> サカレ形として検知されてはならない
    # B D4, B D6 の間に W D5 が割り込んだだけ
    history_wari = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"]
    ]
    curr_w, prev_w, last_w = simulator.reconstruct(history_wari)
    ids_w = detector.detect_ids(curr_w, prev_w, last_w)
    print(f"Scenario 1 (1-stone Split/Wari): {ids_w}")

    # シナリオ2: 2石による分断の完了 -> サカレ形として検知されるべき
    # B D4, B D6 に対し W D5 があり、さらに W E5 が打たれて「裂いた」
    history_sakare = [
        ["B", "D4"], ["B", "D6"], ["W", "D5"], ["B", "A1"], ["W", "E5"]
    ]
    curr_s, prev_s, last_s = simulator.reconstruct(history_sakare)
    ids_s = detector.detect_ids(curr_s, prev_s, last_s)
    print(f"Scenario 2 (2-stone Strict Sakare): {ids_s}")

    # シナリオ3: ケイマのサカレ形
    # B D4, B E6 に対し W E5, W D5 が並んで分断
    history_keima = [
        ["B", "D4"], ["B", "E6"], ["W", "E5"], ["B", "A1"], ["W", "D5"]
    ]
    curr_k, prev_k, last_k = simulator.reconstruct(history_keima)
    ids_k = detector.detect_ids(curr_k, prev_k, last_k)
    print(f"Scenario 3 (Keima Strict Sakare): {ids_k}")

    success = ("sakare_gata" not in ids_w and 
               "sakare_gata" in ids_s and 
               "sakare_gata" in ids_k)
    
    if success:
        print("\nALL SAKARE-GATA STRICT TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should NOT detect 1-stone: {'sakare_gata' not in ids_w}")
        print(f" - Should detect Ikken-tobi split: {'sakare_gata' in ids_s}")
        print(f" - Should detect Keima split: {'sakare_gata' in ids_k}")

if __name__ == "__main__":
    test_sakare_gata_strict()