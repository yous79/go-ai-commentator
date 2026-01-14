from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_hane():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # 1. 正常なハネの検知 (B Q16, W Q17, B R17)
    # R17 は Q16 と斜め、かつ相手の Q17 に隣接
    history_hane = [["B", "Q16"], ["W", "Q17"], ["B", "R17"]]
    curr_hane, prev_hane, last_c = simulator.reconstruct(history_hane)
    ids_hane = detector.detect_ids(curr_hane, prev_hane, last_c)
    print(f"Hane Scenario IDs: {ids_hane}")
    if "hane" not in ids_hane:
        print("Test FAILED: Standard hane not detected.")
        sys.exit(1)

    # 2. 切り違い（Kirichigai）での除外テスト
    # Q16(B), Q17(W), R17(B) の後に R16(W) を打つ
    history_kiri = [["B", "Q16"], ["W", "Q17"], ["B", "R17"], ["W", "R16"]]
    curr_kiri, prev_kiri, last_c = simulator.reconstruct(history_kiri)
    ids_kiri = detector.detect_ids(curr_kiri, prev_kiri, last_c)
    print(f"Kirichigai Scenario IDs: {ids_kiri}")
    
    if "hane" not in ids_kiri:
        print("Test SUCCESS: Hane detected correctly and Kirichigai excluded.")
    else:
        print("Test FAILED: Hane logic too broad (detected Kirichigai as hane).")
        # ただし、R16から見て別の場所でハネが成立している可能性もあるため、
        # 厳密には R16 周辺のメッセージを確認すべきだが、ここでは簡易判定
        # 実際には R16 は Q16 を「ハネ」ているように見える（2x2に石3つ）
        # R16(W), Q16(B), Q17(W) の3つ＋ R17(B) = 4つ。空点がないので除外されるはず。
        sys.exit(1)

if __name__ == "__main__":
    test_hane()
