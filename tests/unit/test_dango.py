from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

# srcディレクトリをパスに追加
sys.path.append(os.path.join(os.getcwd(), "src"))

def test_detect_dango():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # 確実な団子石 (D4, D5, E4, E5)
    history = [["B", "D4"], ["W", "Q16"], ["B", "D5"], ["W", "Q17"], ["B", "E4"], ["W", "R16"], ["B", "E5"]]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Detected IDs: {ids}")
    
    report = detector.detect_all(curr_b, prev_b, last_c)
    print(f"Report:\n{report}")

    if "dango" in ids:
        print("Test SUCCESS: dango detected by ID.")
    else:
        print("Test FAILED: dango not detected.")
        sys.exit(1)

if __name__ == "__main__":
    test_detect_dango()

