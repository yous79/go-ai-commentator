from enum import Enum
from core.point import Point

class RegionType(Enum):
    TOP_LEFT = "左上"
    TOP_RIGHT = "右上"
    BOTTOM_LEFT = "左下"
    BOTTOM_RIGHT = "右下"
    TOP = "上辺"
    BOTTOM = "下辺"
    LEFT = "左辺"
    RIGHT = "右辺"
    CENTER = "中央"

class BoardRegion:
    def __init__(self, board_size=19):
        self._board_size = board_size
        self.regions = {} # Point -> RegionType
        self._init_regions()

    @property
    def board_size(self):
        return self._board_size

    @board_size.setter
    def board_size(self, value):
        if self._board_size != value:
            self._board_size = value
            self.regions = {}
            self._init_regions()

    def _init_regions(self):
        sz = self.board_size
        # 簡易的な3分割ロジック (19路盤基準: 0-5, 6-12, 13-18)
        # 19/3 = 6.33 -> 6, 7, 6
        
        split1 = sz // 3
        split2 = sz - split1
        
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                
                # 行の判定
                if r < split1: r_type = 0 # Top
                elif r < split2: r_type = 1 # Mid
                else: r_type = 2 # Bot
                
                # 列の判定
                if c < split1: c_type = 0 # Left
                elif c < split2: c_type = 1 # Mid
                else: c_type = 2 # Right
                
                # エリアの決定
                if r_type == 0:
                    if c_type == 0: rt = RegionType.TOP_LEFT
                    elif c_type == 1: rt = RegionType.TOP
                    else: rt = RegionType.TOP_RIGHT
                elif r_type == 1:
                    if c_type == 0: rt = RegionType.LEFT
                    elif c_type == 1: rt = RegionType.CENTER
                    else: rt = RegionType.RIGHT
                else:
                    if c_type == 0: rt = RegionType.BOTTOM_LEFT
                    elif c_type == 1: rt = RegionType.BOTTOM
                    else: rt = RegionType.BOTTOM_RIGHT
                
                self.regions[p] = rt

    def get_region(self, p: Point) -> RegionType:
        return self.regions.get(p, RegionType.CENTER)

    def get_points_in_region(self, region: RegionType):
        return [p for p, r in self.regions.items() if r == region]
