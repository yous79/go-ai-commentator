from core.shapes.base_shape import BaseShape

class KirichigaiDetector(BaseShape):
    key = "kirichigai"

    def detect(self, context):
        if not context.last_move:
            return None, []

        r, c = context.last_move
        color = context.last_color
        opp_color = self._get_opponent(color)
        messages = []
        found = False

        for dr in [-1, 0]:
            for dc in [-1, 0]:
                top, left = r + dr, c + dc
                if not (0 <= top < context.board_size - 1 and 0 <= left < context.board_size - 1):
                    continue
                s11, s12 = self._get_stone(context.curr_board, top, left), self._get_stone(context.curr_board, top, left + 1)
                s21, s22 = self._get_stone(context.curr_board, top + 1, left), self._get_stone(context.curr_board, top + 1, left + 1)
                if (s11 == color and s22 == color and s12 == opp_color and s21 == opp_color) or \
                   (s11 == opp_color and s22 == opp_color and s12 == color and s21 == color):
                    messages.append(f"  - 座標 {self._to_coord(r, c)} の着手により、激しい「切り違い」が発生しました。")
                    found = True

        return "normal" if found else None, list(set(messages))