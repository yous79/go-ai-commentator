from core.shapes.base_shape import BaseShape
from core.point import Point

class AkiSankakuDetector(BaseShape):
    key = "aki_sankaku"

    def detect(self, context):
        messages = []
        for r in range(context.board_size - 1):
            for c in range(context.board_size - 1):
                p = Point(r, c)
                cells = [p, p + (1, 0), p + (0, 1), p + (1, 1)]
                for color in ['b', 'w']:
                    stones = [cp for cp in cells if self._get_stone(context.curr_board, cp) == color]
                    empties = [cp for cp in cells if self._get_stone(context.curr_board, cp) == '.']
                    if len(stones) == 3 and len(empties) == 1:
                        coords = sorted([cp.to_gtp() for cp in stones])
                        messages.append(f"  - 座標 {coords} に「アキ三角」を検知。効率の悪い形です。")
        return "bad" if messages else None, list(set(messages))