from core.shapes.base_shape import BaseShape

class TsukeDetector(BaseShape):
    key = "tsuke"

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

        # 2. 自分の石の孤立性（上下左右4近傍に自分の石がない）
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if self._get_stone(curr_board, nr, nc) == color:
                return None, [] # 自分の石が隣接していればツケではない

        # 3. 相手の石への隣接と孤立性の確認
        tsuke_found = False
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if self._get_stone(curr_board, nr, nc) == opp_color:
                # 相手の石(nr, nc)の孤立性（周囲8近傍に相手の石がない）をチェック
                is_opp_isolated = True
                for ddr in [-1, 0, 1]:
                    for ddc in [-1, 0, 1]:
                        if ddr == 0 and ddc == 0: continue
                        nnr, nnc = nr + ddr, nc + ddc
                        # (r, c) は最新の着手位置なので、それ以外の周囲に相手の石がないか確認
                        if (nnr, nnc) == (r, c): continue
                        if self._get_stone(curr_board, nnr, nnc) == opp_color:
                            is_opp_isolated = False
                            break
                    if not is_opp_isolated: break
                
                if is_opp_isolated:
                    opp_coord = self._to_coord(nr, nc)
                    my_coord = self._to_coord(r, c)
                    messages.append(f"  - 座標 {my_coord} の着手は、相手の孤立した石 {opp_coord} への「ツケ」です。")
                    tsuke_found = True

        return "normal" if tsuke_found else None, list(set(messages))
