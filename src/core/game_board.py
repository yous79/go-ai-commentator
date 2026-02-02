from enum import Enum
from typing import Optional, List, Tuple, Set, Union
from sgfmill import boards
from core.point import Point
import sys
from utils.logger import logger

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
        
        # 詳細ログ
        ko_str = f", Ko: {self.ko_point.to_gtp()}" if self.ko_point else ""
        logger.debug(f"[BOARD] Validating Move -> Color: {color_obj.label}({color_obj.value}), Point: {pt.to_gtp()}{ko_str}")

        # 1. 座標の重複チェック
        if self.get(pt):
            logger.warning(f"[BOARD] Result: ILLEGAL | Reason: OCCUPIED at {pt.to_gtp()}")
            return False

        # 2. コウのチェック
        if self.ko_point and pt == self.ko_point:
            logger.warning(f"[BOARD] Result: ILLEGAL | Reason: KO at {pt.to_gtp()}")
            return False

        # 3. 自殺手のチェック（実際に置いてみる）
        test_board = self._board.copy()
        try:
            # play() は石が打ち抜かれるリストを返す（Noneを返す可能性も考慮）
            captured = test_board.play(pt.row, pt.col, color_obj.value)
            
            # 石が盤面に残っているか確認（自殺手なら打ち抜かれて消えているはず）
            if test_board.get(pt.row, pt.col) is None:
                lib_info = []
                for n in pt.neighbors(self.side):
                    n_val = self.get(n)
                    n_color = n_val.label if n_val else "空"
                    lib_info.append(f"{n.to_gtp()}:{n_color}")
                sys.stderr.write(f"[BOARD] Result: ILLEGAL | Reason: SUICIDE at {pt.to_gtp()} (Neighbors: {', '.join(lib_info)})\n")
                sys.stderr.flush()
                return False
            
            logger.debug(f"[BOARD] Result: LEGAL for {pt.to_gtp()}")
            return True
        except ValueError as e:
            # sgfmillが投げるその他のエラー
            logger.error(f"[BOARD] Result: ILLEGAL | Reason: SGFMILL REJECT ({e})")
            return False

    def play(self, pt: Point, color: Union[Color, str]) -> List[Point]:
        """石を置き、コウの状態を更新する"""
        color_obj = color if isinstance(color, Color) else Color.from_str(color)
        if not color_obj: return []
        
        try:
            # 1. 石を置く
            captured_raw = self._board.play(pt.row, pt.col, color_obj.value)
            
            # captured_raw の形式を正規化 (単一タプルまたはリストに対応)
            captured_pts = []
            if captured_raw:
                if isinstance(captured_raw, tuple) and len(captured_raw) == 2 and isinstance(captured_raw[0], int):
                    items = [captured_raw]
                else:
                    items = captured_raw
                
                for item in items:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        captured_pts.append(Point(item[0], item[1]))

            # 2. コウの判定
            old_ko = self.ko_point
            self.ko_point = None
            if old_ko:
                logger.debug(f"[BOARD] Ko Point Cleared (was {old_ko.to_gtp()})")
            
            if len(captured_pts) == 1:
                group, liberties = self.get_group_and_liberties(pt)
                if len(group) == 1 and len(liberties) == 1:
                    if captured_pts[0] in liberties:
                        self.ko_point = captured_pts[0]
                        logger.info(f"[BOARD] New KO established at {self.ko_point.to_gtp()}")
            
            return captured_pts
        except Exception as e:
            logger.error(f"[BOARD] Play Error at {pt.to_gtp()}: {e}")
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
    def board_size(self):
        return self.side

    @property
    def raw_board(self):
        return self._board
