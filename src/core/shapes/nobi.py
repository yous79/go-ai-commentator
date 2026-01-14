from core.shapes.base_shape import BaseShape

class NobiDetector(BaseShape):
    key = "nobi"

    def detect(self, context):
        p = context.last_move
        if not p: return None, []

        color = context.last_color
        opp = self._get_opponent(color)
        messages = []
        nobi_found = False

        for neighbor in p.neighbors(context.board_size):
            if self._get_stone(context.curr_board, neighbor) == color:
                diff = p - neighbor 
                if self._get_stone(context.curr_board, p + diff) == opp: continue
                side_v = (diff.col, diff.row)
                for mult in [1, -1]:
                    v = (side_v[0] * mult, side_v[1] * mult)
                    if self._get_stone(context.curr_board, p + v) == opp or \
                       self._get_stone(context.curr_board, neighbor + v) == opp:
                        messages.append(f"  - 座標 {p.to_gtp()} の着手は、味方 {neighbor.to_gtp()} に沿って伸びる「ノビ」です。")
                        nobi_found = True; break
                if nobi_found: break

        return "normal" if nobi_found else None, list(set(messages))