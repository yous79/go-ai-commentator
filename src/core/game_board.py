from enum import Enum
from typing import Optional, List, Tuple, Set, Union
from sgfmill import boards
from core.point import Point
import sys

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
    """sgfmill.boards.Board をラップし、正確なルール判定を提供するクラス"""
    
    def __init__(self, size: int = 19):
        self._board = boards.Board(size)
        self.side = size
        self.ko_point: Optional[Point] = None 

    def get(self, *args) -> Optional[Color]:
        """
        石の色を取得する。
        引数は Point オブジェクト1つ、または row, col の数値2つを受け付ける。
        """
        if len(args) == 1 and isinstance(args[0], Point):
            r, c = args[0].row, args[0].col
        elif len(args) == 2:
            r, c = args[0], args[1]
        else:
            raise TypeError("get() takes 1 Point argument or 2 integer arguments (row, col)")
            
        val = self._board.get(r, c)
        return Color(val) if val else None

    def is_legal(self, pt: Point, color: Union[Color, str]) -> bool:
        """サンドボックス(copy)を用いて着手の合法性を判定する"""
        color_obj = color if isinstance(color, Color) else Color.from_str(color)
        if not color_obj or not pt.is_valid(self.side):
            return False
        
        if self.get(pt):
            return False

        # サンドボックス作成
        test_board = self._board.copy()
        if self.ko_point:
            test_board.ko_point = (self.ko_point.row, self.ko_point.col)
        else:
            test_board.ko_point = None
        
        try:
            test_board.play(pt.row, pt.col, color_obj.value)
            return True
        except ValueError as e:
            reason = str(e).lower()
            sys.stderr.write(f"[BOARD] Reject {pt.to_gtp()}: {reason}\n")
            return False

    def play(self, pt: Point, color: Union[Color, str]) -> List[Point]:
        """石を置き、コウの状態を更新する"""
        color_obj = color if isinstance(color, Color) else Color.from_str(color)
        if not color_obj: return []
        
        if self.ko_point:
            self._board.ko_point = (int(self.ko_point.row), int(self.ko_point.col))
        else:
            self._board.ko_point = None

        try:
            captured_raw = self._board.play(pt.row, pt.col, color_obj.value)
            
            if self._board.ko_point:
                r, c = self._board.ko_point
                self.ko_point = Point(r, c)
            else:
                self.ko_point = None
                
            return [Point(r, c) for r, c in captured_raw] if captured_raw else []
        except Exception as e:
            sys.stderr.write(f"[BOARD] Play Error at {pt.to_gtp()}: {e}\n")
            return []

    def apply_pass(self) -> None:
        """パスによりコウの状態を解除する"""
        self.ko_point = None
        self._board.ko_point = None

    def is_empty(self, pt: Point) -> bool:
        return self.get(pt) is None

    def list_occupied_points(self) -> List[Tuple[Point, Color]]:
        results = []
        for r in range(self.side):
            for c in range(self.side):
                p = Point(r, c)
                color = self.get(p)
                if color:
                    results.append((p, color))
        return results

    def get_group_and_liberties(self, pt: Point) -> Tuple[Set[Point], Set[Point]]:
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

    def copy(self) -> 'GameBoard':
        new_obj = GameBoard(self.side)
        new_obj._board = self._board.copy()
        new_obj.ko_point = self.ko_point
        return new_obj

    @property
    def raw_board(self):
        return self._board
