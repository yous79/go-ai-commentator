from abc import ABC, abstractmethod
from core.coordinate_transformer import CoordinateTransformer

class BaseShape(ABC):
    def __init__(self, board_size=19):
        self.board_size = board_size

    @abstractmethod
    def detect(self, context):
        """検知を実行し、(category, message_list) を返す"""
        pass

    def _get_stone(self, board, r, c=None):
        if c is None:
            if hasattr(r, 'row'): # Point object
                r, c = r.row, r.col
            elif isinstance(r, (tuple, list)):
                r, c = r[0], r[1]
        
        if 0 <= r < self.board_size and 0 <= c < self.board_size:
            res = board.get(r, c)
            if res is None: return '.'
            return res.lower()
        return "edge"

    def _to_coord(self, r, c):
        return CoordinateTransformer.indices_to_gtp_static(r, c)

    def _get_opponent(self, color):
        if not color: return '.'
        c = color.lower()
        if c == 'b': return 'w'
        if c == 'w': return 'b'
        return '.'

    def _is_connected(self, board, p1, p2, color):
        """BFS（幅優先探索）を使用して、p1 と p2 が同じ色の石で連結されているか判定する"""
        from core.point import Point
        p1 = Point(p1[0], p1[1]) if isinstance(p1, tuple) else p1
        p2 = Point(p2[0], p2[1]) if isinstance(p2, tuple) else p2
        
        if p1 == p2: return True
        if self._get_stone(board, p1) != color or self._get_stone(board, p2) != color:
            return False

        queue = [p1]
        visited = {p1}
        
        while queue:
            curr = queue.pop(0)
            if curr == p2:
                return True
            
            for neighbor in curr.all_neighbors(self.board_size):
                if neighbor not in visited and self._get_stone(board, neighbor) == color:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return False