from core.shapes.base_shape import BaseShape

class NobiDetector(BaseShape):
    key = "nobi"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        if prev_board is None:
            return None, []

        messages = []
        # 1. 最新の着手座標を特定
        last_move = None
        for r in range(self.board_size):
            for c in range(self.board_size):
                if curr_board.get(r, c) and not prev_board.get(r, c):
                    last_move = (r, c)
                    break
            if last_move: break

        if not last_move:
            return None, []

        r, c = last_move
        color = self._get_stone(curr_board, r, c)
        opp_color = self._get_opponent(color)

        nobi_found = False
        # 2. 隣接する味方の石 M を探し、進行方向を特定
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            mr, mc = r - dr, c - dc # 味方の石の推定位置
            if self._get_stone(curr_board, mr, mc) == color:
                # 進行方向は (dr, dc)
                
                # 3. 正面の確認（進行方向の先が相手の石でないこと）
                fr, fc = r + dr, c + dc
                if self._get_stone(curr_board, fr, fc) == opp_color:
                    continue # 正面が相手なら「ブツカリ」

                # 4. 横での接触確認（M または P の側面に相手の石がいるか）
                sides = [(dc, dr), (-dc, -dr)]
                is_contact = False
                for sr, sc in sides:
                    if self._get_stone(curr_board, r + sr, c + sc) == opp_color:
                        is_contact = True; break
                    if self._get_stone(curr_board, mr + sr, mc + sc) == opp_color:
                        is_contact = True; break
                
                if is_contact:
                    my_coord = self._to_coord(r, c)
                    ally_coord = self._to_coord(mr, mc)
                    messages.append(f"  - 座標 {my_coord} の着手は、味方の石 {ally_coord} に沿って真っ直ぐ伸びる「ノビ」です。")
                    nobi_found = True
                    break

        return "normal" if nobi_found else None, list(set(messages))
