from PIL import ImageDraw
from core.point import Point
from core.game_board import Color
from core.coordinate_transformer import CoordinateTransformer
from utils.renderer.base import RenderLayer, RenderContext

class StoneLayer(RenderLayer):
    """盤上の石と手数を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        t = ctx.theme
        gs = ctx.transformer.grid_size
        rad = gs // 2 - 2
        sz = ctx.board_size
        
        # 1. 現在の盤面から石の分布を把握
        current_stones = {}
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                color = ctx.board.get(p)
                if color:
                    current_stones[(r, c)] = color

        # 2. 手数番号のマップ作成 (現在の盤面に存在する石のみ)
        stone_to_num = {}
        if ctx.history and ctx.show_numbers:
            for i, mv in enumerate(ctx.history):
                idx = CoordinateTransformer.gtp_to_indices_static(mv[1])
                # 盤面に石が存在し、かつ色が一致する場合のみ番号を表示
                if idx in current_stones:
                    stone_to_num[idx] = i + 1

        # 3. 石の描画
        for (r, c), color in current_stones.items():
            self._draw_stone(draw, ctx, r, c, color, rad, stone_to_num.get((r, c)))

        # 4. 検討用の石（Review Stones）の描画
        if ctx.review_stones:
            for (r, c), color_str, num in ctx.review_stones:
                color = Color.from_str(color_str)
                # 検討用の石はテーマに関わらず目立つように（必要ならテーマ化）
                self._draw_stone(draw, ctx, r, c, color, rad, num, outline="red", width=2)

    def _draw_stone(self, draw, ctx, r, c, color: Color, rad, number=None, outline=None, width=1):
        t = ctx.theme
        px, py = ctx.transformer.indices_to_pixel(r, c)
        
        # V2: テーマ色を使用
        fill_c = t.black_stone_color if color == Color.BLACK else t.white_stone_color
        stroke_c = outline or t.stone_outline_color
        
        draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_c, outline=stroke_c, width=width)
        
        if number is not None:
            # V2: コントラストを考慮した番号色
            num_c = t.white_stone_color if color == Color.BLACK else t.black_stone_color
            num_s = str(number)
            self._draw_centered_text(draw, px, py, num_s, ctx.font_number, num_c)
