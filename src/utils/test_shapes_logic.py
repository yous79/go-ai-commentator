import sys
import os

# プロジェクトのルートをパスに追加
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from core.shapes.nimoku_atama import NimokuAtamaDetector

class MockBoard:
    """テスト用の軽量盤面オブジェクト"""
    def __init__(self, board_map, size=9):
        self.board_map = board_map
        self.size = size
    def get(self, r, c):
        return self.board_map.get((r, c), '.')

def run_test(name, board_str, expected_hit):
    """
    board_str: 文字列形式の盤面 ( . = 空, B = 黒, W = 白 )
    """
    print(f"Testing: {name}")
    lines = [l.strip() for l in board_str.strip().split('\n')]
    board_map = {}
    size = len(lines)
    for r_idx, line in enumerate(reversed(lines)): # 下から上へ
        chars = line.split()
        for c_idx, char in enumerate(chars):
            if char != '.':
                board_map[(r_idx, c_idx)] = char.lower()
    
    # 盤面の可視化（デバッグ用）
    cols = "ABCDEFGHJ"
    for r in range(size - 1, -1, -1):
        row_str = f"{r+1} "
        for c in range(size):
            row_str += board_map.get((r, c), '.').upper() + " "
        print(row_str)
    print("  " + " ".join(cols[:size]))

    board = MockBoard(board_map, size=size)
    detector = NimokuAtamaDetector(board_size=size)
    
    # 判定実行
    cat, messages = detector.detect(board)
    actual_hit = (cat == "bad")
    
    status = "PASS" if actual_hit == expected_hit else "FAIL"
    print(f"[{status}] {name}")
    if actual_hit != expected_hit:
        print(f"  Expected Hit: {expected_hit}, Actual: {actual_hit}")
        if messages:
            for m in messages: print(f"    Message: {m}")

if __name__ == "__main__":
    print("--- Starting Nimoku no Atama Logic Unit Tests ---\n")

    # 1. 基本的な正解ケース (白の二目の頭を黒がハネている)
    # E4, E5 が白。 F4, F5 が黒。 黒が E6 を叩く。 D6 は空点。
    run_test("Basic Success", """
        . . . . . . 
        . . W B . . 
        . . W B . . 
        . . . . . . 
    """, True)

    # 2. 除外ケース: 三目並び (自軍が3つ並んでいる)
    run_test("Exclude: Three Stones", """
        . . . . . . 
        . . W B . . 
        . . W B . . 
        . . W . . . 
        . . . . . . 
    """, False)

    # 3. 除外ケース: 並走不足 (相手が1つしかいない)
    run_test("Exclude: Single Opponent", """
        . . . . . . 
        . . W B . . 
        . . W . . . 
        . . . . . . 
    """, False)

    # 4. 除外ケース: 相互ハネ / 切り違い (反対側も埋まっている)
    # E6 を黒が叩き、同時に D6 に白（または黒）がいて空点ではない状態
    run_test("Exclude: Mutual Hane (Occupied Side)", """
        . . B B . . 
        . . W B . . 
        . . W B . . 
        . . . . . . 
    """, False)

    # 5. 反対方向からのハネ (正常検知)
    run_test("Success: Other Side Hane", """
        . . . . . . 
        . B W . . . 
        . B W . . . 
        . . . . . . 
    """, True)

    print("\n--- Tests Completed ---")
