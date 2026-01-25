from PIL import ImageDraw
from core.point import Point
from core.game_board import Color
from utils.renderer.base import RenderLayer, RenderContext

class MarkupLayer(RenderLayer):
    """△□×のマークを描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.marks: return
        t = ctx.theme
        gs = ctx.transformer.grid_size
        rad = gs // 2 - 2
        
        for prop, shape in [("SQ", "square"), ("TR", "triangle"), ("MA", "cross")]:
            points = ctx.marks.get(prop, [])
            for r, c in points:
                px, py = ctx.transformer.indices_to_pixel(r, c)
                p = Point(r, c)
                
                # 下にある石の色を確認して markup 色を決定
                stone_color = ctx.board.get(p)
                if not stone_color and ctx.review_stones:
                    for (rr, cc), col, n in ctx.review_stones:
                        if rr == r and cc == c: 
                            stone_color = Color.from_str(col)
                            break
                
                # V2: テーマに基づくマーク色決定
                mark_color = t.markup_color_dark if stone_color == Color.BLACK else t.markup_color_light
                self._draw_mark(draw, px, py, shape, rad, mark_color, t.mark_thickness)

    def _draw_mark(self, draw, px, py, shape, rad, color, thickness):
        size = int(rad * 0.6)
        w = thickness
        if shape == "square":
            rect = [(px-size, py-size), (px+size, py-size), (px+size, py+size), (px-size, py+size), (px-size, py-size)]
            draw.line(rect, fill=color, width=w, joint="round")
        elif shape == "triangle":
            pts = [(px, py-int(size*1.2)), (px-size, py+int(size*0.8)), (px+size, py+int(size*0.8)), (px, py-int(size*1.2))]
            draw.line(pts, fill=color, width=w, joint="round")
        elif shape == "cross":
            draw.line([px-size, py-size, px+size, py+size], fill=color, width=w)
            draw.line([px+size, py-size, px-size, py+size], fill=color, width=w)
