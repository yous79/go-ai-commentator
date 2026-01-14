from core.shapes.base_shape import BaseShape

class KeimaDetector(BaseShape):
    key = "keima"

    def detect(self, context):
        messages = []
        checked_pairs = set()
        for r in range(context.board_size):
            for c in range(context.board_size):
                color = self._get_stone(context.curr_board, r, c)
                if color not in ['b', 'w']: continue
                for dr, dc in [(1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < context.board_size and 0 <= nc < context.board_size:
                        if self._get_stone(context.curr_board, nr, nc) == color:
                            pair = tuple(sorted([(r, c), (nr, nc)]))
                            if pair not in checked_pairs:
                                checked_pairs.add(pair)
                                messages.append(f"  - 座標 {sorted([self._to_coord(r, c), self._to_coord(nr, nc)])} に「ケイマ」を検知。柔軟な進出です。")
        return "normal", list(set(messages))
