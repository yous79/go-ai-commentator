from core.shapes.base_shape import BaseShape

class ButsukariDetector(BaseShape):
    key = "butsukari"

    def detect(self, context):
        if not context.last_move:
            return None, []

        r, c = context.last_move
        color = context.last_color
        opp_color = self._get_opponent(color)
        messages = []
        found = False

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            if self._get_stone(context.curr_board, r - dr, c - dc) == color:
                if self._get_stone(context.curr_board, r + dr, c + dc) == opp_color:
                    messages.append(f"  - 座標 {self._to_coord(r, c)} の着手は、味方に隣接し相手の正面へ突き当たる「ブツカリ」です。")
                    found = True; break

        return "normal" if found else None, list(set(messages))