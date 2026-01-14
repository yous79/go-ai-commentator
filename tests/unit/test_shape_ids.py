from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

# srcディレクトリをパスに追加
sys.path.append(os.path.join(os.getcwd(), "src"))

def test_detect_ids():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # 確実なアキ三角 (D4, D5, E4)
    history = [["B", "D4"], ["W", "Q16"], ["B", "D5"], ["W", "Q17"], ["B", "E4"]]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Detected IDs: {ids}")
    if "aki_sankaku" in ids:
        print("Test SUCCESS: aki_sankaku detected by ID.")
    else:
        # レポートも確認してみる
        report = detector.detect_all(curr_b, prev_b, last_c)
        print(f"Report: {report}")
        print("Test FAILED: aki_sankaku not detected.")
        sys.exit(1)

if __name__ == "__main__":
    test_detect_ids()
