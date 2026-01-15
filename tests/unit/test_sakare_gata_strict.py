import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_sakare_gata_strict():
    print("Testing Strict Sakare-gata Logic...")
    detector = ShapeDetector(board_size=19)
    simulator = BoardSimulator(board_size=19)
    
    # シナリオ1: 一間トビが完全に分断された（サカレ形）
    # B D4, B D6 の間に W D5 が割り込んだ
    history_split = [
        ["B", "D4"], ["W", "D5"], ["B", "D6"]
    ]
    curr_s, prev_s, last_s = simulator.reconstruct(history_split)
    ids_s = detector.detect_ids(curr_s, prev_s, last_s)
    print(f"Scenario 1 (Split Ikken-tobi): {ids_s}")

    # シナリオ2: 分断されているが、遠くでつながっている（サカレ形ではない）
    # D4, D6 の間に D5 があるが、C4, C5, C6 を通じて B がつながっている
    history_connected = [
        ["B", "D4"], ["W", "D5"], ["B", "D6"],
        ["B", "C4"], ["W", "A1"], ["B", "C5"], ["W", "A2"], ["B", "C6"]
    ]
    curr_c, prev_c, last_c = simulator.reconstruct(history_connected)
    ids_c = detector.detect_ids(curr_c, prev_c, last_c)
    print(f"Scenario 2 (Split but Connected via C-line): {ids_c}")

    # シナリオ3: ケイマの突き出し（サカレ形）
    # B D4, B E6 の間に W E5 (またはD5) が割り込み、連絡がない
    history_keima = [
        ["B", "D4"], ["W", "E5"], ["B", "E6"]
    ]
    curr_k, prev_k, last_k = simulator.reconstruct(history_keima)
    ids_k = detector.detect_ids(curr_k, prev_k, last_k)
    print(f"Scenario 3 (Split Keima): {ids_k}")

    success = ("sakare_gata" in ids_s and 
               "sakare_gata" not in ids_c and 
               "sakare_gata" in ids_k)
    
    if success:
        print("\nALL SAKARE-GATA STRICT TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should be detected (Split): {'sakare_gata' in ids_s}")
        print(f" - Should NOT be detected (Connected): {'sakare_gata' not in ids_c}")
        print(f" - Should be detected (Keima): {'sakare_gata' in ids_k}")

if __name__ == "__main__":
    test_sakare_gata_strict()
