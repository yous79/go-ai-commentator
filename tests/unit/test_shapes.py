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
    size = len(lines)
    board_map = {}
    for r_idx, line in enumerate(lines):
        r = (size - 1) - r_idx
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
            p_map, _ = parse_board(prev_board_str)
            prev_board = MockBoard(p_map, size=size)

        detector = ShapeDetector(board_size=size)
        # last_move_color は PonnukiDetector のために必要なら適宜設定
        facts = detector.detect_all(curr_board, prev_board=prev_board)
        
        actual_hit = (msg_fragment in facts) if msg_fragment else (len(facts) > 0)
        
        if actual_hit != expected_hit:
            print(f"\n[FAIL] Scenario: {msg_fragment}")
            print(f"Board:\n{board_str}")
            print(f"Detected Facts: {facts}")
            
        self.assertEqual(actual_hit, expected_hit)

    def test_nimoku_atama_basic(self):
        """基本的な二目の頭（正解）"""
        self.check("""
            . . . . .
            . . B . .
            . B W . .
            . B W . .
            . . . . .
        """, True, "二目の頭")

    def test_nimoku_atama_exclusion_mutual(self):
        """相互ハネ（切り違い）は除外されるべき"""
        self.check("""
            . . . . .
            . W B . .
            . B W . .
            . B W . .
            . . . . .
        """, False, "二目の頭")

    def test_nimoku_atama_exclusion_isolation(self):
        """叩いている石の隣に味方がいる場合は除外（連絡あり）"""
        self.check("""
            . . . . .
            . . B B .
            . B W . .
            . B W . .
            . . . . .
        """, False, "二目の頭")

    def test_aki_sankaku_basic(self):
        """基本的なアキ三角（正解）"""
        self.check("""
            . . .
            . B B
            . B .
            . . .
        """, True, "アキ三角")

    def test_aki_sankaku_exclusion_full(self):
        """4点目が埋まっている場合はアキ三角ではない"""
        self.check("""
            . . .
            . B B
            . B W
            . . .
        """, False, "アキ三角")

    def test_ponnuki_basic(self):
        """石を抜いた直後のポン抜き（正解）"""
        prev = """
            . . . . .
            . . B . .
            . B W B .
            . . B . .
            . . . . .
        """
        curr = """
            . . . . .
            . . B . .
            . B . B .
            . . B . .
            . . . . .
        """
        self.check(curr, True, "ポン抜き", prev_board_str=prev)

    def test_ponnuki_exclusion_diagonal(self):
        """斜めに余計な石がある場合は除外（純粋性チェック）"""
        prev = """
            . . . . .
            . . B . .
            . B W B .
            . B B . .
            . . . . .
        """
        curr = """
            . . . . .
            . . B . .
            . B . B .
            . B B . .
            . . . . .
        """
        self.check(curr, False, "ポン抜き", prev_board_str=prev)

if __name__ == "__main__":
    unittest.main()
