from core.shapes.base_shape import BaseShape

class HaneDetector(BaseShape):
    key = "hane"

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

        hane_found = False
        # 2. 最新着手の隣接マスをチェック
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if self._get_stone(curr_board, nr, nc) == opp_color:
                # 相手の石 (nr, nc) を発見。これを含む2x2の領域を確認
                for pr, pc in [(dc, dr), (-dc, -dr)]:
                    c1_r, c1_c = r + pr, c + pc
                    c2_r, c2_c = nr + pr, nc + pc
                    
                    s1 = self._get_stone(curr_board, c1_r, c1_c)
                    s2 = self._get_stone(curr_board, c2_r, c2_c)
                    
                    # ハネの条件: 自分の石が2つ、相手の石が1つ、空点が1つ
                    if (s1 == '.' and s2 == color) or (s1 == color and s2 == '.'):
                        my_coord = self._to_coord(r, c)
                        opp_coord = self._to_coord(nr, nc)
                        messages.append(f"  - 座標 {my_coord} の着手は、相手の石 {opp_coord} を抑える「ハネ」です。")
                        hane_found = True

        return "normal" if hane_found else None, list(set(messages))
