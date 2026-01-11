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
        r1, c1 = p1; r2, c2 = p2
        if abs(r1-r2) + abs(c1-c2) == 1: return True
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr==0 and dc==0: continue
                mr, mc = r1+dr, c1+dc
                if self._get_stone(board, mr, mc) == color:
                    if abs(mr-r2)<=1 and abs(mc-c2)<=1: return True
        return False
