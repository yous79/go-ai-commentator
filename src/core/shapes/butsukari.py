from core.shapes.base_shape import BaseShape

class ButsukariDetector(BaseShape):
    key = "butsukari"

    def detect(self, context):
        p = context.last_move
        if not p: return None, []

        color = context.last_color
        opp = self._get_opponent(color)
        messages = []
        found = False

        for neighbor in p.neighbors(context.board_size):
            if self._get_stone(context.curr_board, neighbor) == color:
                diff = p - neighbor 
                if self._get_stone(context.curr_board, p + diff) == opp:
                    messages.append(f"  - 座標 {p.to_gtp()} の着手は、味方に隣接し相手の正面へ突き当たる「ブツカリ」です。")
                    found = True; break

        return "normal" if found else None, list(set(messages))