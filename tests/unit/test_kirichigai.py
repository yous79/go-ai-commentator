from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_kirichigai():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # シナリオ: 切り違い
    # B Q16, W Q17, B R17, W R16
    history = [["B", "Q16"], ["W", "Q17"], ["B", "R17"], ["W", "R16"]]
    
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    report = detector.detect_all(curr_b, prev_b, last_c)
    
    print(f"Detected IDs: {ids}")
    print(f"Report:\n{report}")
    
    if "kirichigai" in ids:
        print("Test SUCCESS: kirichigai detected.")
    else:
        print("Test FAILED: kirichigai not detected.")
        sys.exit(1)

if __name__ == "__main__":
    test_kirichigai()

