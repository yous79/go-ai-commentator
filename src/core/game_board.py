from enum import Enum
from typing import Optional, List, Tuple, Set
from sgfmill import boards
from core.point import Point

class Color(Enum):
    BLACK = 'b'
    WHITE = 'w'

    @property
    def label(self) -> str:
        return "黒" if self == Color.BLACK else "白"

    @property
    def key(self) -> str:
        return "black" if self == Color.BLACK else "white"

    def opposite(self) -> 'Color':
        return Color.WHITE if self == Color.BLACK else Color.BLACK

    @classmethod
    def from_str(cls, s: str) -> Optional['Color']:
        if not s: return None
        s = s.lower()
        if s in ['b', 'black', '黒']: return cls.BLACK
        if s in ['w', 'white', '白']: return cls.WHITE
        return None

class GameBoard:
    """sgfmill.boards.Board をラップし、Pointベースの操作を提供するクラス"""
    
    def __init__(self, size: int = 19):
        self._board = boards.Board(size)
        self.side = size

    def get(self, pt: Point) -> Optional[Color]:
        """指定した座標の石の色を返す"""
        val = self._board.get(pt.row, pt.col)
        return Color(val) if val else None

    def play(self, pt: Point, color: Color) -> None:
        """指定した座標に石を置く（アゲハマ処理はsgfmillが担当）"""
        self._board.play(pt.row, pt.col, color.value)

    def is_empty(self, pt: Point) -> bool:
        return self.get(pt) is None

    def list_occupied_points(self) -> List[Tuple[Point, Color]]:
        """盤上のすべての石とその座標を返す"""
        results = []
        for r in range(self.side):
            for c in range(self.side):
                p = Point(r, c)
                color = self.get(p)
                if color:
                    results.append((p, color))
        return results

    def get_group_and_liberties(self, pt: Point) -> Tuple[Set[Point], Set[Point]]:
        """指定した座標の石を含むグループとその呼吸点を返す"""
        color = self.get(pt)
        if not color:
            return set(), set()
        
        group = {pt}
        liberties = set()
        queue = [pt]
        
        while queue:
            curr = queue.pop(0)
            for neighbor in curr.neighbors(self.side):
                n_color = self.get(neighbor)
                if n_color == color:
                    if neighbor not in group:
                        group.add(neighbor)
                        queue.append(neighbor)
                elif n_color is None:
                    liberties.add(neighbor)
        
        return group, liberties

    @property
    def raw_board(self):
        """互換性のために生のsgfmillボードを返す"""
        return self._board
