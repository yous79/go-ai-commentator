from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext

class CoordinateLayer(RenderLayer):
    """座標の文字(A-T, 1-19)を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        t = ctx.theme
        m = ctx.transformer.margin
        sz = ctx.board_size
        gs = ctx.transformer.grid_size
        cols = "ABCDEFGHJKLMNOPQRST"
        
        for i in range(sz):
            x, y = m + i * gs, m + i * gs
            # Top/Bottom Cols
            self._draw_centered_text(draw, x, m - 30, cols[i], ctx.font, t.label_color)
            self._draw_centered_text(draw, x, m + (sz-1)*gs + 30, cols[i], ctx.font, t.label_color)
            # Left/Right Rows
            self._draw_centered_text(draw, m - 30, y, str(sz - i), ctx.font, t.label_color)
            self._draw_centered_text(draw, m + (sz-1)*gs + 30, y, str(sz - i), ctx.font, t.label_color)
