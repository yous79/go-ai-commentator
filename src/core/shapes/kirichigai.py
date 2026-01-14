from core.shapes.base_shape import BaseShape

class KirichigaiDetector(BaseShape):
    key = "kirichigai"

    def detect(self, context):
        p = context.last_move
        if not p: return None, []

        color = context.last_color
        opp = self._get_opponent(color)
        messages = []
        found = False

        for dr in [-1, 0]:
            for dc in [-1, 0]:
                origin = p + (dr, dc)
                s11 = self._get_stone(context.curr_board, origin)
                s12 = self._get_stone(context.curr_board, origin + (0, 1))
                s21 = self._get_stone(context.curr_board, origin + (1, 0))
                s22 = self._get_stone(context.curr_board, origin + (1, 1))
                
                if (s11 == color and s22 == color and s12 == opp and s21 == opp) or \
                   (s11 == opp and s22 == opp and s12 == color and s21 == color):
                    messages.append(f"  - 座標 {p.to_gtp()} の着手により、激しい「切り違い」が発生しました。")
                    found = True

        return "normal" if found else None, list(set(messages))