from core.shapes.base_shape import BaseShape

class NobiDetector(BaseShape):
    key = "nobi"

    def detect(self, context):
        if not context.last_move:
            return None, []

        r, c = context.last_move
        color = context.last_color
        opp_color = self._get_opponent(color)
        messages = []
        nobi_found = False

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            mr, mc = r - dr, c - dc
            if self._get_stone(context.curr_board, mr, mc) == color:
                # 正面の確認
                if self._get_stone(context.curr_board, r + dr, c + dc) == opp_color:
                    continue 
                # 横での接触確認
                sides = [(dc, dr), (-dc, -dr)]
                is_contact = False
                for sr, sc in sides:
                    if self._get_stone(context.curr_board, r + sr, c + sc) == opp_color or \
                       self._get_stone(context.curr_board, mr + sr, mc + sc) == opp_color:
                        is_contact = True; break
                
                if is_contact:
                    messages.append(f"  - 座標 {self._to_coord(r, c)} の着手は、味方の石 {self._to_coord(mr, mc)} に沿って真っ直ぐ伸びる「ノビ」です。")
                    nobi_found = True; break

        return "normal" if nobi_found else None, list(set(messages))