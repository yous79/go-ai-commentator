from core.shapes.base_shape import BaseShape

class HaneDetector(BaseShape):
    key = "hane"

    def detect(self, context):
        if not context.last_move:
            return None, []

        r, c = context.last_move
        color = context.last_color
        opp_color = self._get_opponent(color)
        messages = []
        hane_found = False

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if self._get_stone(context.curr_board, nr, nc) == opp_color:
                for pr, pc in [(dc, dr), (-dc, -dr)]:
                    s1 = self._get_stone(context.curr_board, r + pr, c + pc)
                    s2 = self._get_stone(context.curr_board, nr + pr, nc + pc)
                    if (s1 == '.' and s2 == color) or (s1 == color and s2 == '.'):
                        messages.append(f"  - 座標 {self._to_coord(r, c)} の着手は、相手の石 {self._to_coord(nr, nc)} を抑える「ハネ」です。")
                        hane_found = True

        return "normal" if hane_found else None, list(set(messages))