from abc import ABC, abstractmethod
from typing import Optional, Union, Tuple, List, Set
from core.coordinate_transformer import CoordinateTransformer
from core.point import Point
from core.game_board import GameBoard, Color

class BaseShape(ABC):
    def __init__(self, board_size=19):
        self.board_size = board_size

    @abstractmethod
    def detect(self, context):
        """検知を実行し、(category, message_list) を返す"""
        pass

    def _get_stone(self, board: GameBoard, r, c=None) -> str:
        """座標(r, c) または Pointオブジェクトから石の色を1文字で返す ('.', 'b', 'w', 'edge')"""
        if c is None:
            if isinstance(r, Point):
                pt = r
            elif hasattr(r, 'row'): # Duck typing for Point-like
                pt = Point(r.row, r.col)
            elif isinstance(r, (tuple, list)):
                pt = Point(r[0], r[1])
            else:
                return "edge"
        else:
            pt = Point(r, c)
        
        if pt.is_valid(self.board_size):
            res = board.get(pt)
            if res == Color.BLACK: return 'b'
            if res == Color.WHITE: return 'w'
            return '.'
        return "edge"

    def _to_coord(self, r, c):
        return CoordinateTransformer.indices_to_gtp_static(r, c)

    def _get_opponent(self, color: Union[Color, str, None]) -> str:
        """相手の色を1文字で返す ('b' or 'w')"""
        if color is None: return '.'
        
        # Colorオブジェクトの場合
        if isinstance(color, Color):
            return color.opposite().value
            
        # 文字列の場合
        c = str(color).lower()
        if c in ['b', 'black', '黒']: return 'w'
        if c in ['w', 'white', '白']: return 'b'
        return '.'

    def _is_connected(self, board: GameBoard, p1, p2, color: str):
        """BFS（幅優先探索）を使用して、p1 と p2 が同じ色の石で連結されているか判定する"""
        if isinstance(p1, (tuple, list)): p1 = Point(p1[0], p1[1])
        if isinstance(p2, (tuple, list)): p2 = Point(p2[0], p2[1])
        
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
