from core.shapes.base_shape import BaseShape

class NimokuAtamaDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'
                for dr, dc in [(0, 1), (1, 0)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(curr_board, nr, nc) == color:
                        head_r, head_c = nr + dr, nc + dc
                        if self._get_stone(curr_board, head_r, head_c) == opp:
                            # 支えのチェック
                            if self._get_stone(curr_board, nr, nc+1) == opp or self._get_stone(curr_board, nr, nc-1) == opp or \
                               self._get_stone(curr_board, nr+1, nc) == opp or self._get_stone(curr_board, nr-1, nc) == opp:
                                messages.append(f"  - 石 {[self._to_coord(r,c), self._to_coord(nr,nc)]} が 座標 {self._to_coord(head_r, head_c)} で「二目の頭」をハネられた非常に弱い形になっています。")
        return "bad", messages
