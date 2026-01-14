from typing import NamedTuple, Iterator, Tuple, Optional

class Point(NamedTuple):
    row: int
    col: int

    def __add__(self, other: Tuple[int, int]) -> 'Point':
        return Point(self.row + other[0], self.col + other[1])

    def __sub__(self, other: Tuple[int, int]) -> 'Point':
        return Point(self.row - other[0], self.col - other[1])

    def is_valid(self, size: int) -> bool:
        """盤面内に収まっているか判定"""
        return 0 <= self.row < size and 0 <= self.col < size

    def neighbors(self, size: int) -> Iterator['Point']:
        """有効な隣接4近傍を返す"""
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            p = self + (dr, dc)
            if p.is_valid(size):
                yield p

    def all_neighbors(self, size: int) -> Iterator['Point']:
        """有効な8近傍（斜め含む）を返す"""
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                p = self + (dr, dc)
                if p.is_valid(size):
                    yield p

    @classmethod
    def from_gtp(cls, gtp_str: str) -> Optional['Point']:
        """GTP座標文字列（Q16等）からPointを生成"""
        from core.coordinate_transformer import CoordinateTransformer
        res = CoordinateTransformer.gtp_to_indices_static(gtp_str)
        return cls(res[0], res[1]) if res else None

    def to_gtp(self) -> str:
        """GTP座標文字列に変換"""
        from core.coordinate_transformer import CoordinateTransformer
        return CoordinateTransformer.indices_to_gtp_static(self.row, self.col)
