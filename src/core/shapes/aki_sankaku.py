from core.shapes.base_shape import BaseShape

class AkiSankakuDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                cells = [(r,c), (r+1,c), (r,c+1), (r+1,c+1)]
                for color in ['b', 'w']:
                    stones = [p for p in cells if self._get_stone(curr_board, *p) == color]
                    empties = [p for p in cells if self._get_stone(curr_board, *p) is None]
                    if len(stones) == 3 and len(empties) == 1:
                        empty = empties[0]
                        diag = (r if empty[0]==r+1 else r+1, c if empty[1]==c+1 else c+1)
                        if self._get_stone(curr_board, *diag) == color:
                            coords = sorted([self._to_coord(*p) for p in stones])
                            messages.append(f"  - 座標 {coords} に「アキ三角」を検知。効率の悪い重い形です。")
        return "bad", messages
