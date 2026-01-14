import sys
import os
import unittest

# プロジェクトのルートをパスに追加
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.shape_detector import ShapeDetector

class MockBoard:
    """テスト用の軽量盤面オブジェクト"""
    def __init__(self, board_map, size=9):
        self.board_map = board_map
        self.size = size
    def get(self, r, c):
        return self.board_map.get((r, c), '.')

def parse_board(board_str):
    """アスキー文字列を座標マップに変換"""
    if not board_str: return {}, 0
    lines = [l.strip() for l in board_str.strip().split('\n') if l.strip()]
    if not lines: return {}, 0
    
    height = len(lines)
    # 各行の要素数を取得し、最大の幅を決定
    max_width = 0
    for line in lines:
        max_width = max(max_width, len(line.split()))
    
    # 盤面サイズは縦横の大きい方に合わせる（19x19等に対応するため）
    size = max(height, max_width)
    
    board_map = {}
    for r_idx, line in enumerate(lines):
        # アスキー上の最上行(r_idx=0) は、碁盤の最大行(height-1)
        r = (height - 1) - r_idx
        chars = line.split()
        for c, char in enumerate(chars):
            if char.upper() in ['B', 'W']:
                board_map[(r, c)] = char.lower()
    return board_map, size

class TestShapeDetection(unittest.TestCase):
    def check(self, board_str, expected_hit, msg_fragment="", prev_board_str=None):
        """共通の検証ロジック"""
        board_map, size = parse_board(board_str)
        curr_board = MockBoard(board_map, size=size)
        
        prev_board = None
        if prev_board_str:
            p_map, p_size = parse_board(prev_board_str)
            prev_board = MockBoard(p_map, size=max(size, p_size))

        detector = ShapeDetector(board_size=size)
        facts = detector.detect_all(curr_board, prev_board=prev_board)
        
        actual_hit = (msg_fragment in facts) if msg_fragment else (len(facts) > 0)
        
        if actual_hit != expected_hit:
            print(f"\n[FAIL] Scenario: {msg_fragment}")
            print(f"Board (Size {size}):\n{board_str}")
            print(f"Detected Facts: {facts}")
            
        self.assertEqual(actual_hit, expected_hit)

    def test_nimoku_atama_basic(self):
        """基本的な二目の頭 (正解)"""
        # B石が (1,1),(2,1) にあり、W石が (1,2),(2,2) に並走、
        # さらに Wが (3,1) でハネている。 (0,1) は空。
        self.check("""
            . W . .
            . B W .
            . B W .
            . . . .
        """, True, "二目の頭")

    def test_aki_sankaku_basic(self):
        """基本的なアキ三角 (正解)"""
        self.check("""
            . B B
            . B .
            . . .
        """, True, "アキ三角")

    def test_ponnuki_basic(self):
        """ポン抜き (正解)"""
        prev = """
            . B .
            B W B
            . B .
        """
        curr = """
            . B .
            B . B
            . B .
        """
        self.check(curr, True, "ポン抜き", prev_board_str=prev)

    # --- サカレ形 (Sakare Gata) ---

    def test_sakare_gata_ikken_basic(self):
        """一間トビのサカレ"""
        self.check("""
            . . . . .
            . B W B .
            . . W . .
            . . . . .
        """, True, "サカレ形")

    def test_sakare_gata_keima_basic(self):
        """ケイマのサカレ"""
        # B:(1,2) と B:(3,1) のケイマに対し、
        # 白が継ぎ目の (2,2) と (2,1) を完全に分断しているケース
        self.check("""
            . . . . .
            . . . . .
            . B W . .
            . W W . .
            . . B . .
            . . . . .
        """, True, "サカレ形")

    def test_sakare_gata_exclusion_connected(self):
        """割り込まれているが、他で連絡している場合は除外"""
        # B石が (1,1) と (1,3) にあり、白が (1,2) を突き抜けているが、
        # B石が (0,1),(0,2),(0,3) を通って連絡しているケース
        self.check("""
            . B W B .
            . B B B .
            . . . . .
        """, False, "サカレ形")

if __name__ == "__main__":
    unittest.main()
