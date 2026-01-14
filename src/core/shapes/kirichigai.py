from core.shapes.base_shape import BaseShape

class KirichigaiDetector(BaseShape):
    key = "kirichigai"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        if prev_board is None:
            return None, []

        messages = []
        # 1. 最新の着手座標を特定
        last_move = None
        for r in range(self.board_size):
            for c in range(self.board_size):
                if curr_board.get(r, c) and not prev_board.get(r, c):
                    last_move = (r, c)
                    break
            if last_move: break

        if not last_move:
            return None, []

        r, c = last_move
        color = self._get_stone(curr_board, r, c)
        opp_color = self._get_opponent(color)

        found = False
        # 2. 最新着手を含む4つの2x2領域をチェック
        for dr in [-1, 0]:
            for dc in [-1, 0]:
                top, left = r + dr, c + dc
                if not (0 <= top < self.board_size - 1 and 0 <= left < self.board_size - 1):
                    continue
                
                # 2x2のセルの石を取得
                s11 = self._get_stone(curr_board, top, left)
                s12 = self._get_stone(curr_board, top, left + 1)
                s21 = self._get_stone(curr_board, top + 1, left)
                s22 = self._get_stone(curr_board, top + 1, left + 1)
                
                # 切り違いのパターンチェック (X字型)
                is_pattern_a = (s11 == color and s22 == color and s12 == opp_color and s21 == opp_color)
                is_pattern_b = (s11 == opp_color and s22 == opp_color and s12 == color and s21 == color)
                
                if is_pattern_a or is_pattern_b:
                    my_coord = self._to_coord(r, c)
                    messages.append(f"  - 座標 {my_coord} の着手により、激しい「切り違い」が発生しました。")
                    found = True

        return "normal" if found else None, list(set(messages))
