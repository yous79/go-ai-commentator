from pydantic import BaseModel, Field
from typing import List, Optional

class Move(BaseModel):
    """囲碁の一手を表す構造化データ"""
    color: str = Field(..., pattern="^[BWbw]$", description="石の色 ('B' または 'W')")
    coord: str = Field(..., description="GTP形式の座標 (例: 'D4', 'Q16', 'pass')")

    def to_list(self) -> List[str]:
        """既存の [['B', 'D4'], ...] 形式に変換する"""
        return [self.color.upper(), self.coord.upper()]

class AnalysisParams(BaseModel):
    """解析リクエストのパラメータ"""
    history: List[Move] = Field(..., description="着手履歴のリスト")
    board_size: int = Field(default=19, ge=9, le=19, description="盤面サイズ (9, 13, 19)")
