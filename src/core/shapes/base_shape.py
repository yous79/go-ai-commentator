from abc import ABC, abstractmethod
from core.coordinate_transformer import CoordinateTransformer

class BaseShape(ABC):
    def __init__(self, board_size=19):
        self.board_size = board_size

    @abstractmethod
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        """検知を実行し、(category, message_list) を返す"""
        pass

    def _get_stone(self, board, r, c):
        if 0 <= r < self.board_size and 0 <= c < self.board_size:
            return board.get(r, c)
        return "edge"

    def _to_coord(self, r, c):
        return CoordinateTransformer.indices_to_gtp_static(r, c)

    def _is_connected(self, board, p1, p2, color):
        """BFS（幅優先探索）を使用して、p1 と p2 が同じ色の石で連結されているか判定する"""
        if p1 == p2: return True
        r1, c1 = p1; r2, c2 = p2
        if self._get_stone(board, r1, c1) != color or self._get_stone(board, r2, c2) != color:
            return False

        queue = [p1]
        visited = {p1}
        
        while queue:
            curr_r, curr_c = queue.pop(0)
            if (curr_r, curr_c) == p2:
                return True
            
            # 上下左右および斜め（8近傍）をチェック
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = curr_r + dr, curr_c + dc
                    if (nr, nc) not in visited and self._get_stone(board, nr, nc) == color:
                        visited.add((nr, nc))
                        queue.append((nr, nc))
        
        return False
