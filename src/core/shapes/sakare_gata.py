from core.shapes.base_shape import BaseShape
from core.point import Point

class SakareGataDetector(BaseShape):
    key = "sakare_gata"

    def detect(self, context):
        messages = []
        checked_pairs = set()
        sz = context.board_size
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                color = self._get_stone(context.curr_board, p)
                if color not in ['b', 'w']: continue
                opp = self._get_opponent(color)
                for dr, dc in [(0, 2), (2, 0), (1, 2), (1, -2), (2, 1), (2, -1)]:
                    np = p + (dr, dc)
                    if self._get_stone(context.curr_board, np) == color:
                        mid = Point((p.row + np.row) // 2, (p.col + np.col) // 2)
                        if self._is_connected(context.curr_board, p, np, color): continue
                        if self._get_stone(context.curr_board, mid) == opp:
                            pair = tuple(sorted([p, np]))
                            if pair not in checked_pairs:
                                checked_pairs.add(pair)
                                messages.append(f"  - 座標 {sorted([p.to_gtp(), np.to_gtp()])} が「サカレ形」に分断されました。")
        return "bad", list(set(messages))