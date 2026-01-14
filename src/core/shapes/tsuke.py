from core.shapes.base_shape import BaseShape

class TsukeDetector(BaseShape):
    key = "tsuke"

    def detect(self, context):
        if not context.last_move:
            return None, []

        r, c = context.last_move
        color = context.last_color
        opp_color = self._get_opponent(color)
        messages = []

        # 1. 自分の石の孤立性（4近傍に味方なし）
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            if self._get_stone(context.curr_board, r + dr, c + dc) == color:
                return None, []

        # 2. 相手の石への隣接と孤立性の確認
        tsuke_found = False
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if self._get_stone(context.curr_board, nr, nc) == opp_color:
                # 相手の石の周囲8近傍に相手の石がないか（最新着手は除く）
                is_opp_isolated = True
                for ddr in [-1, 0, 1]:
                    for ddc in [-1, 0, 1]:
                        if ddr == 0 and ddc == 0: continue
                        nnr, nnc = nr + ddr, nc + ddc
                        if (nnr, nnc) == (r, c): continue
                        if self._get_stone(context.curr_board, nnr, nnc) == opp_color:
                            is_opp_isolated = False; break
                    if not is_opp_isolated: break
                
                if is_opp_isolated:
                    opp_coord = self._to_coord(nr, nc)
                    messages.append(f"  - 座標 {self._to_coord(r, c)} の着手は、相手の孤立した石 {opp_coord} への「ツケ」です。")
                    tsuke_found = True

        return "normal" if tsuke_found else None, list(set(messages))