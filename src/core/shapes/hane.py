from core.shapes.base_shape import BaseShape

class HaneDetector(BaseShape):
    key = "hane"

    def detect(self, context):
        p = context.last_move
        if not p: return None, []

        color = context.last_color
        opp = self._get_opponent(color)
        messages = []
        hane_found = False

        for neighbor in p.neighbors(context.board_size):
            if self._get_stone(context.curr_board, neighbor) == opp:
                diff = neighbor - p 
                for side_v in [(diff.col, diff.row), (-diff.col, -diff.row)]:
                    s1_p, s2_p = p + side_v, neighbor + side_v
                    s1, s2 = self._get_stone(context.curr_board, s1_p), self._get_stone(context.curr_board, s2_p)
                    if (s1 == '.' and s2 == color) or (s1 == color and s2 == '.'):
                        messages.append(f"  - 座標 {p.to_gtp()} の着手は、相手の石 {neighbor.to_gtp()} を抑える「ハネ」です。")
                        hane_found = True

        return "normal" if hane_found else None, list(set(messages))