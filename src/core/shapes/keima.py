from core.shapes.base_shape import BaseShape

class KeimaDetector(BaseShape):
    key = "keima"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        checked_pairs = set()

        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue

                # 全ての桂馬の跳び（8方向）をチェック
                for dr, dc in [(1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                        if self._get_stone(curr_board, nr, nc) == color:
                            pair = tuple(sorted([(r, c), (nr, nc)]))
                            if pair not in checked_pairs:
                                checked_pairs.add(pair)
                                coords = sorted([self._to_coord(r, c), self._to_coord(nr, nc)])
                                messages.append(f"  - 座標 {coords} に「ケイマ」を検知。柔軟な進出です。")

        return "normal", list(set(messages))