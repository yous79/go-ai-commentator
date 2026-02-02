from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple, Any
from core.game_board import GameBoard, Color
from core.coordinate_transformer import CoordinateTransformer
from utils.renderer.base import RenderLayer, RenderContext
from utils.renderer.theme import ThemeManager
from utils.renderer.layers import (
    GridLayer, CoordinateLayer, StoneLayer, MarkupLayer, AnalysisLayer, InfoLayer, HeatmapLayer
)

class LayeredBoardRenderer:
    """レイヤー構造を用いて碁盤をレンダリングするメインクラス"""
    
    def __init__(self, board_size=19, image_size=850):
        self.board_size = board_size
        self.image_size = image_size
        self.transformer = CoordinateTransformer(board_size, image_size)
        self.theme_manager = ThemeManager()
        
        # デフォルトレイヤーの構成
        self.layers: List[RenderLayer] = [
            GridLayer(),
            HeatmapLayer(), # Gridの上にヒートマップを表示
            CoordinateLayer(),
            StoneLayer(),
            MarkupLayer(),
            AnalysisLayer(),
            InfoLayer()
        ]
        
        # フォントの初期化
        self._setup_fonts()

    def _setup_fonts(self):
        try:
            self.font = ImageFont.truetype("arial.ttf", 22)
            self.font_small = ImageFont.truetype("arial.ttf", 20)
            self.font_number = ImageFont.truetype("arial.ttf", 18)
        except:
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_number = ImageFont.load_default()

    def set_theme(self, theme_name: str):
        """テーマを切り替える"""
        self.theme_manager.set_theme(theme_name)

    def render(self, board: GameBoard, **kwargs) -> Image.Image:
        """全レイヤーを重ねてレンダリングを実行する"""
        # 碁盤のサイズを渡された盤面に合わせる
        if board.board_size != self.board_size:
            self.board_size = board.board_size
            
        # レンダラーの設定を最新に同期
        self.transformer = CoordinateTransformer(self.board_size, self.image_size)
        
        # レイヤーの表示・非表示切替 (kwargsから削除してContextに渡さないようにする)
        show_heatmap = kwargs.pop('show_heatmap', True)
        for layer in self.layers:
            if isinstance(layer, HeatmapLayer):
                layer.visible = show_heatmap
        
        # フォントサイズを動的に計算 (升目の30%-40%)
        gs = self.transformer.grid_size
        dynamic_size = max(10, int(gs * 0.35))
        try:
             # 再ロードしてサイズ適用
            self.font_number = ImageFont.truetype("arial.ttf", dynamic_size)
        except:
            self.font_number = ImageFont.load_default()
        
        # コンテキストの作成
        ctx = RenderContext(
            board=board,
            transformer=self.transformer,
            image_size=self.image_size,
            board_size=self.board_size,
            theme=self.theme_manager.get_theme(),
            font=self.font,
            font_small=self.font_small,
            font_number=self.font_number,
            **kwargs
        )
        
        # 下部エリアがある場合は高さを調整
        extra_height = 100 if ctx.analysis_text else 0
        img = Image.new("RGBA", (self.image_size, self.image_size + extra_height), (*ctx.theme.board_color, 255))
        ctx.image = img # Set image reference for layers
        draw = ImageDraw.Draw(img)
        
        # 各レイヤーの描画
        for layer in self.layers:
            if layer.visible:
                layer.draw(draw, ctx)
                
        return img.convert("RGB")

    def render_pv(self, board: GameBoard, pv_list: List[str], starting_color: str, title: str = "") -> Image.Image:
        """PV（参考図）をレンダリングする便利なラッパー"""
        # PVを candidates 形式に変換
        mock_candidates = []
        curr_c = Color.from_str(starting_color)
        for i, m in enumerate(pv_list[:10]):
            mock_candidates.append({
                "move": m,
                "winrate": 0.0,
                "color": curr_c
            })
            curr_c = curr_c.opposite()
            
        return self.render(board, analysis_text=title, candidates=mock_candidates, show_numbers=True)
