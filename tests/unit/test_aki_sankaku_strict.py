import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator

def test_aki_sankaku_strict():
    print("Testing Strict Aki-sankaku Logic...")
    detector = ShapeDetector(board_size=9)
    simulator = BoardSimulator(board_size=9)
    
    # シナリオ1: 正常パターン (L字型の3石 + 角が空)
    # D4, E4 に黒石があり、E5 に黒が打たれる。D5 は空点。
    history_ok = [
        ["B", "D4"], ["W", "A1"],
        ["B", "E4"], ["W", "A2"],
        ["B", "E5"] # 角のD5は空点のはず
    ]
    ctx_ok = simulator.reconstruct_to_context(history_ok)
    curr_ok, prev_ok = ctx_ok.board, ctx_ok.prev_board
    ids_ok = detector.detect_ids(curr_ok, prev_ok)
    print(f"Scenario 1 (Valid Aki-sankaku): {ids_ok}")

    # シナリオ2: 角に自分の石がある（アキ三角ではない）
    # D4, E4, D5 に石がある状態で E5 に打つ（またはその逆）
    history_full_self = [
        ["B", "D4"], ["W", "A1"],
        ["B", "E4"], ["W", "A2"],
        ["B", "D5"], ["W", "A3"],
        ["B", "E5"] # すでにD5に石があるのでアキ三角ではない
    ]
    ctx_fs = simulator.reconstruct_to_context(history_full_self)
    curr_fs, prev_fs = ctx_fs.board, ctx_fs.prev_board
    ids_fs = detector.detect_ids(curr_fs, prev_fs)
    print(f"Scenario 2 (Corner occupied by Self): {ids_fs}")

    # シナリオ3: 角に相手の石がある（アキ三角ではない）
    history_full_opp = [
        ["B", "D4"], ["W", "D5"], # 相手が角を占めている
        ["B", "E4"], ["W", "A1"],
        ["B", "E5"]
    ]
    ctx_fo = simulator.reconstruct_to_context(history_full_opp)
    curr_fo, prev_fo = ctx_fo.board, ctx_fo.prev_board
    ids_fo = detector.detect_ids(curr_fo, prev_fo)
    print(f"Scenario 4 (Corner occupied by Opponent): {ids_fo}")

    success = ("aki_sankaku" in ids_ok and 
               "aki_sankaku" not in ids_fs and 
               "aki_sankaku" not in ids_fo)
    
    if success:
        print("\nALL AKI-SANKAKU STRICT TESTS PASSED!")
    else:
        print("\nTEST FAILED:")
        print(f" - Should be detected: {'aki_sankaku' in ids_ok}")
        print(f" - Should NOT be detected (Self in corner): {'aki_sankaku' not in ids_fs}")
        print(f" - Should NOT be detected (Opp in corner): {'aki_sankaku' not in ids_fo}")

if __name__ == "__main__":
    test_aki_sankaku_strict()
