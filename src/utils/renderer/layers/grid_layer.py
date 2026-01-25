from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext

class GridLayer(RenderLayer):
    """背景と罫線、星を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        t = ctx.theme
        m = ctx.transformer.margin
        sz = ctx.board_size
        gs = ctx.transformer.grid_size
        
        # Lines
        for i in range(sz):
            x, y = m + i * gs, m + i * gs
            # V2: テーマの線色と太さを反映
            draw.line([(x, m), (x, m + (sz-1)*gs)], fill=t.line_color, width=2)
            draw.line([(m, y), (m + (sz-1)*gs, y)], fill=t.line_color, width=2)

        # Star Points
        stars = self._get_star_points(sz)
        for r, c in stars:
            px, py = ctx.transformer.indices_to_pixel(r, c)
            # V2: 星の色をテーマから取得
            draw.ellipse([px-4, py-4, px+4, py+4], fill=t.star_color)

    def _get_star_points(self, size):
        if size == 19: return [(r, c) for r in [3, 9, 15] for c in [3, 9, 15]]
        elif size == 13: return [(r, c) for r in [3, 9] for c in [3, 9]] + [(6, 6)]
        elif size == 9: return [(r, c) for r in [2, 6] for c in [2, 6]] + [(4, 4)]
        return []
