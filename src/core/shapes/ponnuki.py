from core.shapes.base_shape import BaseShape
from core.point import Point

class PonnukiDetector(BaseShape):
    key = "ponnuki"

    def detect(self, context):
        bad_messages = []
        if context.prev_board is None: return None, []
        
        sz = context.board_size
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                old_stone = self._get_stone(context.prev_board, p)
                new_stone = self._get_stone(context.curr_board, p)
                if old_stone in ['b', 'w'] and new_stone == '.':
                    attacker = self._get_opponent(old_stone)
                    if all(self._get_stone(context.curr_board, nb) == attacker for nb in p.neighbors(sz)):
                        bad_messages.append(f"  - 座標 {p.to_gtp()} で「ポン抜き」を許しました。相手に厚みを与える大悪形です。")
        return "bad", list(set(bad_messages))