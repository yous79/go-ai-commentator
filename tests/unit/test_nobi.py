from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_nobi():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # 正常なノビの検知
    # B Q16 (味方), W R16 (相手：横にいる), B Q15 (最新：下へノビ)
    history = [["B", "Q16"], ["W", "R16"], ["B", "Q15"]]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Nobi Scenario IDs: {ids}")
    
    # ブツカリ（Butsukari）での除外テスト
    # B Q16, W Q14 (相手：Q15の正面), B Q15 (最新：ブツカリ)
    history_butsu = [["B", "Q16"], ["W", "Q14"], ["B", "Q15"]]
    curr_butsu, prev_butsu, last_c = simulator.reconstruct(history_butsu)
    ids_butsu = detector.detect_ids(curr_butsu, prev_butsu, last_c)
    print(f"Butsukari Scenario IDs: {ids_butsu}")

    if "nobi" in ids and "nobi" not in ids_butsu:
        print("Test SUCCESS: Nobi detected correctly and Butsukari excluded.")
    else:
        print(f"Test FAILED: Nobi Detected: {'nobi' in ids}, Butsukari Wrongly Detected: {'nobi' in ids_butsu}")
        sys.exit(1)

if __name__ == "__main__":
    test_nobi()
