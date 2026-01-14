from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_butsukari():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # 正常なブツカリの検知
    # B Q16 (味方), W Q14 (相手：Q15の正面), B Q15 (最新：正面へぶつかる)
    history = [["B", "Q16"], ["W", "Q14"], ["B", "Q15"]]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Butsukari Scenario IDs: {ids}")
    
    # ノビ（Nobi）での除外テスト
    # B Q16, W R16 (相手：Q15の横), B Q15 (最新：横を這うノビ)
    history_nobi = [["B", "Q16"], ["W", "R16"], ["B", "Q15"]]
    curr_nobi, prev_nobi, last_c = simulator.reconstruct(history_nobi)
    ids_nobi = detector.detect_ids(curr_nobi, prev_nobi, last_c)
    print(f"Nobi Scenario IDs: {ids_nobi}")

    if "butsukari" in ids and "butsukari" not in ids_nobi:
        print("Test SUCCESS: Butsukari detected correctly and Nobi excluded.")
    else:
        print(f"Test FAILED: Butsukari Detected: {'butsukari' in ids}, Nobi Wrongly Detected: {'butsukari' in ids_nobi}")
        sys.exit(1)

if __name__ == "__main__":
    test_butsukari()
