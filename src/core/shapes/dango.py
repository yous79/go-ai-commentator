from core.shapes.base_shape import BaseShape
from core.point import Point

class DangoDetector(BaseShape):
    key = "dango"

    def detect(self, context):
        messages = []
        for r in range(context.board_size - 1):
            for c in range(context.board_size - 1):
                p = Point(r, c)
                cells = [p, p + (1, 0), p + (0, 1), p + (1, 1)]
                for color in ['b', 'w']:
                    if all(self._get_stone(context.curr_board, cp) == color for cp in cells):
                        coords = sorted([cp.to_gtp() for cp in cells])
                        messages.append(f"  - 座標 {coords} に「団子石」を検知。効率が非常に悪いです。")
        return "bad" if messages else None, list(set(messages))