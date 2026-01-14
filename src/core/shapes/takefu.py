from core.shapes.base_shape import BaseShape
from core.point import Point

class TakefuDetector(BaseShape):
    key = "takefu"

    def detect(self, context):
        messages = []
        sz = context.board_size
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                color = self._get_stone(context.curr_board, p)
                if color not in ['b', 'w']: continue
                opp = self._get_opponent(color)
                # 垂直タケフ
                if (self._get_stone(context.curr_board, p + (1, 0)) == color and 
                    self._get_stone(context.curr_board, p + (0, 2)) == color and
                    self._get_stone(context.curr_board, p + (1, 2)) == color):
                    if self._get_stone(context.curr_board, p + (0, 1)) != opp and \
                       self._get_stone(context.curr_board, p + (1, 1)) != opp:
                        coords = sorted([p.to_gtp(), (p+(1,0)).to_gtp(), (p+(0,2)).to_gtp(), (p+(1,2)).to_gtp()])
                        messages.append(f"  - 座標 {coords} に「タケフ」を検知。強固な連絡です。")
                # 水平タケフ
                if (self._get_stone(context.curr_board, p + (0, 1)) == color and 
                    self._get_stone(context.curr_board, p + (2, 0)) == color and
                    self._get_stone(context.curr_board, p + (2, 1)) == color):
                    if self._get_stone(context.curr_board, p + (1, 0)) != opp and \
                       self._get_stone(context.curr_board, p + (1, 1)) != opp:
                        coords = sorted([p.to_gtp(), (p+(0,1)).to_gtp(), (p+(2,0)).to_gtp(), (p+(2,1)).to_gtp()])
                        messages.append(f"  - 座標 {coords} に「タケフ」を検知。強固な連絡です。")
        return "normal", list(set(messages))