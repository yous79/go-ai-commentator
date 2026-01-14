from core.shapes.base_shape import BaseShape

class ButsukariDetector(BaseShape):
    key = "butsukari"

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
        # 2. 隣接する味方の石 M を探し、進行方向を特定
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            mr, mc = r - dr, c - dc
            if self._get_stone(curr_board, mr, mc) == color:
                # 進行方向 (dr, dc)
                # 3. 正面に相手の石がいるか確認
                fr, fc = r + dr, c + dc
                if self._get_stone(curr_board, fr, fc) == opp_color:
                    my_coord = self._to_coord(r, c)
                    ally_coord = self._to_coord(mr, mc)
                    opp_coord = self._to_coord(fr, fc)
                    messages.append(f"  - 座標 {my_coord} の着手は、味方 {ally_coord} から相手 {opp_coord} の正面へ突き当たる「ブツカリ」です。")
                    found = True
                    break

        return "normal" if found else None, list(set(messages))
