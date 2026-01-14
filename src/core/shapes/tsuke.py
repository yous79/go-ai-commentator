from core.shapes.base_shape import BaseShape

class TsukeDetector(BaseShape):
    key = "tsuke"

    def detect(self, context):
        p = context.last_move
        if not p: return None, []

        color = context.last_color
        opp = self._get_opponent(color)
        messages = []

        # 1. 自分の石の孤立性
        for neighbor in p.neighbors(context.board_size):
            if self._get_stone(context.curr_board, neighbor) == color:
                return None, []

        # 2. 相手の石への隣接
        tsuke_found = False
        for neighbor in p.neighbors(context.board_size):
            if self._get_stone(context.curr_board, neighbor) == opp:
                is_opp_isolated = True
                for opp_neighbor in neighbor.all_neighbors(context.board_size):
                    if opp_neighbor == p: continue
                    if self._get_stone(context.curr_board, opp_neighbor) == opp:
                        is_opp_isolated = False; break
                
                if is_opp_isolated:
                    messages.append(f"  - 座標 {p.to_gtp()} の着手は、相手の孤立した石 {neighbor.to_gtp()} への「ツケ」です。")
                    tsuke_found = True

        return "normal" if tsuke_found else None, list(set(messages))