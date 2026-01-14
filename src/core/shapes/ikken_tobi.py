from core.shapes.base_shape import BaseShape

class IkkenTobiDetector(BaseShape):
    key = "ikken_tobi"

    def detect(self, context):
        messages = []
        checked_pairs = set()
        for r in range(context.board_size):
            for c in range(context.board_size):
                color = self._get_stone(context.curr_board, r, c)
                if color not in ['b', 'w']: continue
                for dr, dc in [(0, 2), (0, -2), (2, 0), (-2, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < context.board_size and 0 <= nc < context.board_size:
                        if self._get_stone(context.curr_board, nr, nc) == color:
                            mid_r, mid_c = r + dr // 2, c + dc // 2
                            if self._get_stone(context.curr_board, mid_r, mid_c) == '.':
                                pair = tuple(sorted([(r, c), (nr, nc)]))
                                if pair not in checked_pairs:
                                    checked_pairs.add(pair)
                                    messages.append(f"  - 座標 {sorted([self._to_coord(r, c), self._to_coord(nr, nc)])} に「一間トビ」を検知。効率的な進出です。")
        return "normal", list(set(messages))
