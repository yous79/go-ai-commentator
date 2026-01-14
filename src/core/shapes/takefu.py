from core.shapes.base_shape import BaseShape

class TakefuDetector(BaseShape):
    key = "takefu"

    def detect(self, context):
        messages = []
        # 垂直方向のタケフ (2x3の範囲)
        for r in range(context.board_size - 1):
            for c in range(context.board_size - 2):
                for color in ['b', 'w']:
                    if (self._get_stone(context.curr_board, r, c) == color and 
                        self._get_stone(context.curr_board, r+1, c) == color and
                        self._get_stone(context.curr_board, r, c+2) == color and
                        self._get_stone(context.curr_board, r+1, c+2) == color):
                        
                        # 間が相手の石で完全に分断されていないこと
                        opp = self._get_opponent(color)
                        if self._get_stone(context.curr_board, r, c+1) != opp and \
                           self._get_stone(context.curr_board, r+1, c+1) != opp:
                            coords = sorted([self._to_coord(r, c), self._to_coord(r+1, c), 
                                             self._to_coord(r, c+2), self._to_coord(r+1, c+2)])
                            messages.append(f"  - 座標 {coords} に「タケフ」を検知。強固な連絡です。")

        # 水平方向のタケフ (3x2の範囲)
        for r in range(context.board_size - 2):
            for c in range(context.board_size - 1):
                for color in ['b', 'w']:
                    if (self._get_stone(context.curr_board, r, c) == color and 
                        self._get_stone(context.curr_board, r, c+1) == color and
                        self._get_stone(context.curr_board, r+2, c) == color and
                        self._get_stone(context.curr_board, r+2, c+1) == color):
                        
                        opp = self._get_opponent(color)
                        if self._get_stone(context.curr_board, r+1, c) != opp and \
                           self._get_stone(context.curr_board, r+1, c+1) != opp:
                            coords = sorted([self._to_coord(r, c), self._to_coord(r, c+1), 
                                             self._to_coord(r+2, c), self._to_coord(r+2, c+1)])
                            messages.append(f"  - 座標 {coords} に「タケフ」を検知。強固な連絡です。")

        return "normal", list(set(messages))
