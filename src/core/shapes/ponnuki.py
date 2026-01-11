from core.shapes.base_shape import BaseShape

class PonnukiDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        bad_messages = []
        normal_messages = []
        if not prev_board or not last_move_color:
            return "normal", []

        for check_color in ['b', 'w']:
            opp = 'w' if check_color == 'b' else 'b'
            for r in range(self.board_size):
                for c in range(self.board_size):
                    if prev_board.get(r,c) == opp and curr_board.get(r,c) is None:
                        surround = 0
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            if self._get_stone(curr_board, r+dr, c+dc) == check_color:
                                surround += 1
                        if surround == 4:
                            coord = self._to_coord(r,c)
                            if check_color == last_move_color:
                                normal_messages.append(f"  - 座標 {coord} で鮮やかな「ポン抜き」をしました。非常に効率の良い厚みです。")
                            else:
                                bad_messages.append(f"  - 座標 {coord} で相手に「ポン抜き」を許しました。極めて深刻な悪形です。")
        return "mixed", (bad_messages, normal_messages)
