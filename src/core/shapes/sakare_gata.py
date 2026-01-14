from core.shapes.base_shape import BaseShape

class SakareGataDetector(BaseShape):
    key = "sakare_gata"

    def detect(self, context):
        messages = []
        checked_pairs = set()
        for r in range(context.board_size):
            for c in range(context.board_size):
                color = self._get_stone(context.curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = self._get_opponent(color)
                for dr, dc in [(0, 2), (2, 0), (1, 2), (1, -2), (2, 1), (2, -1)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(context.curr_board, nr, nc) == color:
                        mid_r, mid_c = (r + nr) // 2, (c + nc) // 2
                        if self._is_connected(context.curr_board, (r, c), (nr, nc), color): continue
                        if self._get_stone(context.curr_board, mid_r, mid_c) == opp:
                            pair = tuple(sorted([(r, c), (nr, nc)]))
                            if pair not in checked_pairs:
                                checked_pairs.add(pair)
                                messages.append(f"  - 座標 {sorted([self._to_coord(r, c), self._to_coord(nr, nc)])} が「サカレ形」に分断されました。")
        return "bad", list(set(messages))
