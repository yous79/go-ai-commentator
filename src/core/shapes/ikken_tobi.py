from core.shapes.base_shape import BaseShape
from core.point import Point

class IkkenTobiDetector(BaseShape):
    key = "ikken_tobi"

    def detect(self, context):
        messages = []
        checked_pairs = set()
        for r in range(context.board_size):
            for c in range(context.board_size):
                p = Point(r, c)
                color = self._get_stone(context.curr_board, p)
                if color not in ['b', 'w']: continue
                for dr, dc in [(0, 2), (2, 0), (0, -2), (-2, 0)]:
                    np = p + (dr, dc)
                    if np.is_valid(context.board_size) and self._get_stone(context.curr_board, np) == color:
                        mid = p + (dr // 2, dc // 2)
                        if self._get_stone(context.curr_board, mid) == '.':
                            pair = tuple(sorted([p, np]))
                            if pair not in checked_pairs:
                                checked_pairs.add(pair)
                                messages.append(f"  - 座標 {sorted([p.to_gtp(), np.to_gtp()])} に「一間トビ」を検知。効率的な進出です。")
        return "normal", list(set(messages))