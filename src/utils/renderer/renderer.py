from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple
from core.game_board import GameBoard, Color
from core.coordinate_transformer import CoordinateTransformer
from utils.renderer.base import RenderLayer, RenderContext
from utils.renderer.layers import (
    GridLayer, CoordinateLayer, StoneLayer, MarkLayer, AnalysisLayer, InfoLayer, COLOR_BG
)

class LayeredBoardRenderer:
    """レイヤー構造を用いて碁盤をレンダリングするメインクラス"""
    
    def __init__(self, board_size=19, image_size=850):
        self.board_size = board_size
        self.image_size = image_size
        self.transformer = CoordinateTransformer(board_size, image_size)
        
        # デフォルトレイヤーの構成
        self.layers: List[RenderLayer] = [
            GridLayer(),
            CoordinateLayer(),
            StoneLayer(),
            MarkLayer(),
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

    def render(self, board: GameBoard, **kwargs) -> Image.Image:
        """全レイヤーを重ねてレンダリングを実行する"""
        # レンダラーの設定を最新に同期
        self.transformer = CoordinateTransformer(self.board_size, self.image_size)
        
        # コンテキストの作成
        ctx = RenderContext(
            board=board,
            transformer=self.transformer,
            image_size=self.image_size,
            board_size=self.board_size,
            font=self.font,
            font_small=self.font_small,
            font_number=self.font_number,
            **kwargs
        )
        
        # 下部エリアがある場合は高さを調整
        extra_height = 100 if ctx.analysis_text else 0
        img = Image.new("RGB", (self.image_size, self.image_size + extra_height), COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # 各レイヤーの描画
        for layer in self.layers:
            if layer.visible:
                layer.draw(draw, ctx)
                
        return img

    def render_pv(self, board: GameBoard, pv_list: List[str], starting_color: str, title: str = "") -> Image.Image:
        """PV（参考図）をレンダリングする便利なラッパー"""
        # 簡易的に candidates 形式に変換して AnalysisLayer に描画させることも可能だが、
        # 既存のロジックとの互換性を重視する場合は、ここに直接書くか、専用レイヤーを作る
        # 今回は互換性重視で、現在の render メソッドをベースに一時的な設定で描画
        
        # PVを candidates 形式に変換
        mock_candidates = []
        curr_c = Color.from_str(starting_color)
        for i, m in enumerate(pv_list[:10]):
            mock_candidates.append({
                "move": m,
                "winrate": 0.0, # PV表示では勝率は重要でない
                "color": curr_c
            })
            curr_c = curr_c.opposite()
            
        return self.render(board, analysis_text=title, candidates=mock_candidates, show_numbers=True)
