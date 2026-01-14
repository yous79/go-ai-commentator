from core.shapes.base_shape import BaseShape

class AkiSankakuDetector(BaseShape):
    key = "aki_sankaku"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        # 2x2の領域をスキャン
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                cells = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                
                for color in ['b', 'w']:
                    stones = [p for p in cells if self._get_stone(curr_board, p[0], p[1]) == color]
                    # 空点判定を '.' に修正
                    empties = [p for p in cells if self._get_stone(curr_board, p[0], p[1]) == '.']
                    
                    if len(stones) == 3 and len(empties) == 1:
                        # 3つの石がL字型（三角形）であることを確認
                        # （対角線の位置にある石が欠けていれば三角形）
                        coords = sorted([self._to_coord(p[0], p[1]) for p in stones])
                        messages.append(f"  - 座標 {coords} に「アキ三角」を検知。効率の悪い重複した形です。")
        
        # 重複検知（隣り合う2x2窓での重複）を避けるためユニーク化
        return "bad" if messages else None, list(set(messages))
