from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any, Tuple
from PIL import ImageDraw, ImageFont
from core.game_board import GameBoard
from core.coordinate_transformer import CoordinateTransformer
from utils.renderer.theme import RenderTheme, CLASSIC_THEME

@dataclass
class RenderContext:
    """描画に必要な全情報を保持するコンテキスト"""
    board: GameBoard
    transformer: CoordinateTransformer
    image_size: int
    board_size: int
    theme: RenderTheme = CLASSIC_THEME
    
    # Optional Data
    history: List[List[str]] = field(default_factory=list)
    last_move: Optional[Any] = None # Point or None
    analysis_text: str = ""
    show_numbers: bool = False
    marks: Optional[dict] = None
    review_stones: Optional[List[Tuple]] = None
    candidates: Optional[List[dict]] = None
    
    # Resources (Fonts)
    font: Any = None
    font_small: Any = None
    font_number: Any = None

class RenderLayer(ABC):
    """描画レイヤーの基底クラス"""
    
    def __init__(self):
        self.visible = True

    @abstractmethod
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        """
        draw: PIL ImageDraw object
        ctx: RenderContext containing all game state
        """
        pass

    def _draw_centered_text(self, draw, x, y, text, font, fill):
        """Utility for centered text"""
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            w, h = right - left, bottom - top
            draw.text((x - w / 2, y - h / 2 - top), text, font=font, fill=fill)
        except:
            # Fallback for older Pillow
            w, h = 20, 20
            draw.text((x - w / 2, y - h / 2), text, font=font, fill=fill)
