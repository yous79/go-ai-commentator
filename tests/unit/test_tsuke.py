from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_tsuke():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # シナリオ:
    # 1. 白が D4 に孤立して置かれる
    # 2. 黒が D5 にツケる (D5 の上下左右に黒石なし、D4 は孤立)
    history = [["W", "D4"], ["B", "Q16"], ["W", "Q17"], ["B", "D5"]]
    
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    report = detector.detect_all(curr_b, prev_b, last_c)
    
    print(f"Detected IDs: {ids}")
    print(f"Report:\n{report}")
    
    if "tsuke" in ids:
        print("Test SUCCESS: tsuke detected.")
    else:
        print("Test FAILED: tsuke not detected.")
        sys.exit(1)

if __name__ == "__main__":
    test_tsuke()
