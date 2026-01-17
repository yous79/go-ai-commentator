from typing import Tuple
from PIL import ImageDraw
from core.point import Point
from core.game_board import Color
from core.coordinate_transformer import CoordinateTransformer
from utils.renderer.base import RenderLayer, RenderContext

# Constants
COLOR_BG = (220, 179, 92)
COLOR_LINE = (0, 0, 0)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)

class GridLayer(RenderLayer):
    """背景と罫線、星を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        # Background is already filled by the base image creation, but we can enforce it here if needed
        # draw.rectangle([(0,0), (ctx.image_size, ctx.image_size)], fill=COLOR_BG)
        
        m = ctx.transformer.margin
        sz = ctx.board_size
        gs = ctx.transformer.grid_size
        
        # Lines
        for i in range(sz):
            x, y = m + i * gs, m + i * gs
            draw.line([(x, m), (x, m + (sz-1)*gs)], fill=COLOR_LINE, width=2)
            draw.line([(m, y), (m + (sz-1)*gs, y)], fill=COLOR_LINE, width=2)

        # Star Points
        stars = self._get_star_points(sz)
        for r, c in stars:
            px, py = ctx.transformer.indices_to_pixel(r, c)
            draw.ellipse([px-4, py-4, px+4, py+4], fill=COLOR_LINE)

    def _get_star_points(self, size):
        if size == 19: return [(r, c) for r in [3, 9, 15] for c in [3, 9, 15]]
        elif size == 13: return [(r, c) for r in [3, 9] for c in [3, 9]] + [(6, 6)]
        elif size == 9: return [(r, c) for r in [2, 6] for c in [2, 6]] + [(4, 4)]
        return []

class CoordinateLayer(RenderLayer):
    """座標の文字(A-T, 1-19)を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        m = ctx.transformer.margin
        sz = ctx.board_size
        gs = ctx.transformer.grid_size
        cols = "ABCDEFGHJKLMNOPQRST"
        
        for i in range(sz):
            x, y = m + i * gs, m + i * gs
            # Top/Bottom Cols
            self._draw_centered_text(draw, x, m - 30, cols[i], ctx.font, "black")
            self._draw_centered_text(draw, x, m + (sz-1)*gs + 30, cols[i], ctx.font, "black")
            # Left/Right Rows
            self._draw_centered_text(draw, m - 30, y, str(sz - i), ctx.font, "black")
            self._draw_centered_text(draw, m + (sz-1)*gs + 30, y, str(sz - i), ctx.font, "black")

class StoneLayer(RenderLayer):
    """盤上の石と手数を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        gs = ctx.transformer.grid_size
        rad = gs // 2 - 2
        sz = ctx.board_size
        
        # History map for numbers
        stone_to_num = {}
        if ctx.history and ctx.show_numbers:
            for i, mv in enumerate(ctx.history):
                idx = CoordinateTransformer.gtp_to_indices_static(mv[1])
                if idx: stone_to_num[idx] = i + 1

        # 1. Existing Stones
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                color = ctx.board.get(p)
                if color:
                    self._draw_stone(draw, ctx, r, c, color, rad, stone_to_num.get((r, c)))

        # 2. Review Stones
        if ctx.review_stones:
            for (r, c), color_str, num in ctx.review_stones:
                color = Color.from_str(color_str)
                self._draw_stone(draw, ctx, r, c, color, rad, num, outline="red", width=2)

    def _draw_stone(self, draw, ctx, r, c, color: Color, rad, number=None, outline="black", width=1):
        px, py = ctx.transformer.indices_to_pixel(r, c)
        fill_c = COLOR_BLACK if color == Color.BLACK else COLOR_WHITE
        draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_c, outline=outline, width=width)
        
        if number is not None:
            num_c = "white" if color == Color.BLACK else "black"
            num_s = str(number)
            # Adjust font size
            f_sz = int(rad * 1.2) if len(num_s) <= 2 else int(rad * 0.9)
            # For simplicity, using ctx.font_number (or dynamic if possible, but keep simple for now)
            self._draw_centered_text(draw, px, py, num_s, ctx.font_number, num_c)

class MarkLayer(RenderLayer):
    """△□×のマークを描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.marks: return
        gs = ctx.transformer.grid_size
        rad = gs // 2 - 2
        
        for prop, shape in [("SQ", "square"), ("TR", "triangle"), ("MA", "cross")]:
            points = ctx.marks.get(prop, [])
            for r, c in points:
                px, py = ctx.transformer.indices_to_pixel(r, c)
                p = Point(r, c)
                stone_color = ctx.board.get(p)
                
                # Check review stones if empty
                if not stone_color and ctx.review_stones:
                    for (rr, cc), col, n in ctx.review_stones:
                        if rr == r and cc == c: 
                            stone_color = Color.from_str(col)
                            break
                
                mark_color = "white" if stone_color == Color.BLACK else "black"
                self._draw_mark(draw, px, py, shape, rad, mark_color)

    def _draw_mark(self, draw, px, py, shape, rad, color):
        size = int(rad * 0.6)
        w = 5
        if shape == "square":
            rect = [(px-size, py-size), (px+size, py-size), (px+size, py+size), (px-size, py+size), (px-size, py-size)]
            draw.line(rect, fill=color, width=w, joint="round")
        elif shape == "triangle":
            pts = [(px, py-int(size*1.2)), (px-size, py+int(size*0.8)), (px+size, py+int(size*0.8)), (px, py-int(size*1.2))]
            draw.line(pts, fill=color, width=w, joint="round")
        elif shape == "cross":
            draw.line([px-size, py-size, px+size, py+size], fill=color, width=w)
            draw.line([px+size, py-size, px-size, py+size], fill=color, width=w)

class AnalysisLayer(RenderLayer):
    """AIの候補手を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.candidates: return
        
        # Scaling factor for text overlay (roughly same as original)
        # Using a fixed logic or simpler approach here
        
        for i, c in enumerate(ctx.candidates[:3]): # Top 3
            move_str = c.get('move')
            idx_pair = ctx.transformer.gtp_to_indices(move_str)
            if not idx_pair: continue
            
            px, py = ctx.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
            
            gs = ctx.transformer.grid_size
            rad = gs // 2 - 2
            
            color = "#00ff00" if i == 0 else "#00aaff"
            draw.ellipse([px-rad, py-rad, px+rad, py+rad], outline=color, width=3)
            
            wr = c.get('winrate_black', c.get('winrate', 0))
            if isinstance(wr, float):
                txt = f"{wr:.0%}"
                self._draw_centered_text(draw, px, py, txt, ctx.font_number, "blue")

class InfoLayer(RenderLayer):
    """下部の情報テキストを描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if ctx.analysis_text:
            # Draw bottom area
            draw.rectangle([(0, ctx.image_size), (ctx.image_size, ctx.image_size + 100)], fill=(30, 30, 30))
            self._draw_centered_text(draw, ctx.image_size // 2, ctx.image_size + 50, ctx.analysis_text, ctx.font, "white")
