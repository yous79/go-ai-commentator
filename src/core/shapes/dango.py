from core.shapes.base_shape import BaseShape

class DangoDetector(BaseShape):
    key = "dango"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        # 2x2の領域をスキャン
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                cells = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                
                for color in ['b', 'w']:
                    stones = [p for p in cells if self._get_stone(curr_board, p[0], p[1]) == color]
                    
                    # 4つすべてが同じ色の石であれば団子石
                    if len(stones) == 4:
                        coords = sorted([self._to_coord(p[0], p[1]) for p in stones])
                        messages.append(f"  - 座標 {coords} に「団子石」を検知。凝り形で効率が非常に悪いです。")
        
        # 重複検知を避けるためユニーク化
        return "bad" if messages else None, list(set(messages))