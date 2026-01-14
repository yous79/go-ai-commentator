from core.shapes.base_shape import BaseShape

class PonnukiDetector(BaseShape):
    key = "ponnuki"

    def detect(self, context):
        bad_messages = []
        if context.prev_board is None: return None, []
        
        for r in range(context.board_size):
            for c in range(context.board_size):
                old_stone = self._get_stone(context.prev_board, r, c)
                new_stone = self._get_stone(context.curr_board, r, c)
                if old_stone in ['b', 'w'] and new_stone == '.':
                    attacker = 'w' if old_stone == 'b' else 'b'
                    is_ponnuki = True
                    for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        if self._get_stone(context.curr_board, r + dr, c + dc) != attacker:
                            is_ponnuki = False; break
                    if is_ponnuki:
                        bad_messages.append(f"  - 座標 {self._to_coord(r, c)} で「ポン抜き」を許しました。相手に厚みを与える大悪形です。")
        return "bad", list(set(bad_messages))