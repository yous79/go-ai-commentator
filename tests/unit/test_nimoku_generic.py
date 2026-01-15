import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_nimoku_atama_generic():
    print("Testing Nimoku no Atama (Generic Engine)...")
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # B D4, B E4 (黒の二目) -> W F4 (白が頭を叩く)
    # これにより、F4(last)に対して E4(1,0), D4(2,0) が相手の石になる
    history = [["B", "D4"], ["B", "E4"], ["W", "F4"]]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Detected IDs: {ids}")
    
    if "nimoku_atama" in ids:
        print("SUCCESS: Nimoku no Atama detected by generic engine.")
    else:
        print("FAILED: Nimoku no Atama NOT detected.")
        # デバッグ用に全出力を確認
        facts = detector.detect_all(curr_b, prev_b, last_c)
        print(f"Full Detection Report:\n{facts}")

if __name__ == "__main__":
    test_nimoku_atama_generic()
