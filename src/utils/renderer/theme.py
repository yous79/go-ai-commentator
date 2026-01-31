from dataclasses import dataclass, field
from typing import Tuple, Dict, Any

@dataclass
class RenderTheme:
    """描画スタイルを定義するデータクラス"""
    name: str
    board_color: Tuple[int, int, int]
    line_color: Tuple[int, int, int]
    star_color: Tuple[int, int, int]
    label_color: Tuple[int, int, int]
    
    # 石のスタイル
    black_stone_color: Tuple[int, int, int] = (10, 10, 10)
    white_stone_color: Tuple[int, int, int] = (245, 245, 245)
    stone_outline_color: Tuple[int, int, int] = (0, 0, 0)
    
    # 注釈スタイル
    mark_thickness: int = 5
    markup_color_dark: str = "white"   # 黒石上のマーク色
    markup_color_light: str = "black"  # 白石・盤上のマーク色
    
    # ヒートマップ用 (黒地色, 白地色) - RGBAのRGB部分のみ
    heatmap_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((0, 0, 0), (255, 255, 255))
    
    # フォントサイズ倍率
    font_scale: float = 1.0

# プリセットテーマ
CLASSIC_THEME = RenderTheme(
    name="Classic Wood",
    board_color=(220, 179, 92),
    line_color=(0, 0, 0),
    star_color=(0, 0, 0),
    label_color=(0, 0, 0),
    heatmap_colors=((0, 0, 255), (255, 0, 0)) # Classic: 青/赤
)

MODERN_DARK_THEME = RenderTheme(
    name="Modern Dark",
    board_color=(40, 44, 52),
    line_color=(171, 178, 191),
    star_color=(171, 178, 191),
    label_color=(171, 178, 191),
    white_stone_color=(200, 200, 200),
    markup_color_dark="cyan",
    markup_color_light="orange",
    heatmap_colors=((100, 149, 237), (255, 99, 71)) # Dark: CornflowerBlue / Tomato
)

class ThemeManager:
    """テーマの管理と切り替えを統括するクラス"""
    def __init__(self):
        self._themes = {
            "classic": CLASSIC_THEME,
            "dark": MODERN_DARK_THEME
        }
        self._current_theme = "classic"

    def get_theme(self, name: str = None) -> RenderTheme:
        return self._themes.get(name or self._current_theme, CLASSIC_THEME)

    def set_theme(self, name: str):
        if name in self._themes:
            self._current_theme = name

    @property
    def available_themes(self):
        return list(self._themes.keys())
