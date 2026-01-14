from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "src"))

def test_new_shapes():
    detector = ShapeDetector()
    simulator = BoardSimulator()
    
    # テスト局面
    history = [
        ["B", "D4"], ["W", "Q16"], ["B", "E5"], # コスミ
        ["W", "Q17"], ["B", "G4"], ["W", "R16"], ["B", "G5"], # タケフ準備
        ["W", "R17"], ["B", "J4"], ["W", "S16"], ["B", "J5"], # タケフ完成
        ["W", "S17"], ["B", "D10"], ["W", "A1"], ["B", "D12"], # 一間トビ
        ["W", "A2"], ["B", "G10"], ["W", "A3"], ["B", "H12"]  # ケイマ
    ]
    curr_b, prev_b, last_c = simulator.reconstruct(history)
    
    # 一間トビの中間点 D11 を調査
    # D11 は GTP座標で D=3, 11=10 (r=10, c=3)
    mid_stone = curr_b.get(10, 3)
    print(f"DEBUG: Stone at D11 (10, 3) is '{mid_stone}'")
    
    ids = detector.detect_ids(curr_b, prev_b, last_c)
    print(f"Detected IDs: {ids}")
    
    expected = ["kosumi", "takefu", "ikken_tobi", "keima"]
    for ex in expected:
        if ex in ids:
            print(f"Check SUCCESS: {ex} detected.")
        else:
            print(f"Check FAILED: {ex} not detected.")

if __name__ == "__main__":
    test_new_shapes()