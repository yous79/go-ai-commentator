from PIL import Image, ImageDraw, ImageFont
import os
from core.coordinate_transformer import CoordinateTransformer

class GoBoardRenderer:
    def __init__(self, board_size=19, image_size=850):
        self.board_size = board_size
        self.image_size = image_size
        self.transformer = CoordinateTransformer(board_size, image_size)
        
        self.color_bg = (220, 179, 92) 
        self.color_line = (0, 0, 0)
        self.color_black = (0, 0, 0)
        self.color_white = (255, 255, 255)
        self.color_last_move = (255, 0, 0)

        try:
            self.font = ImageFont.truetype("arial.ttf", 22)
            self.font_small = ImageFont.truetype("arial.ttf", 20)
            self.font_number = ImageFont.truetype("arial.ttf", 18)
        except:
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_number = ImageFont.load_default()

    def _draw_centered_text(self, draw, x, y, text, font, fill):
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            w, h = right - left, bottom - top
            draw.text((x - w / 2, y - h / 2 - top), text, font=font, fill=fill)
        except:
            w, h = draw.textsize(text, font=font)
            draw.text((x - w / 2, y - h / 2), text, font=font, fill=fill)

    def render(self, board, last_move=None, analysis_text="", history=None, show_numbers=False, marks=None):
        img = Image.new("RGB", (self.image_size, self.image_size + 100), self.color_bg)
        draw = ImageDraw.Draw(img)
        
        # 1. Grid
        m = self.transformer.margin
        sz = self.board_size
        gs = self.transformer.grid_size
        cols = "ABCDEFGHJKLMNOPQRST"
        for i in range(sz):
            x, y = m + i * gs, m + i * gs
            draw.line([(x, m), (x, m + (sz-1)*gs)], fill=self.color_line, width=2)
            draw.line([(m, y), (m + (sz-1)*gs, y)], fill=self.color_line, width=2)
            self._draw_centered_text(draw, x, m - 35, cols[i], self.font, "black")
            self._draw_centered_text(draw, x, m + (sz-1)*gs + 35, cols[i], self.font, "black")
            self._draw_centered_text(draw, m - 35, y, str(sz - i), self.font, "black")
            self._draw_centered_text(draw, m + (sz-1)*gs + 35, y, str(sz - i), self.font, "black")

        for r, c in self._get_star_points():
            px, py = self.transformer.indices_to_pixel(r, c)
            draw.ellipse([px-4, py-4, px+4, py+4], fill=self.color_line)

        # 2. Stones & Numbers
        stone_to_num = {}
        if history and show_numbers:
            for i, mv in enumerate(history):
                idx = self.transformer.gtp_to_indices(mv[1])
                if idx: stone_to_num[idx] = i + 1

        rad = gs // 2 - 2
        for r in range(sz):
            for c in range(sz):
                color = board.get(r, c)
                if color:
                    px, py = self.transformer.indices_to_pixel(r, c)
                    fill_c = self.color_black if color == 'b' else self.color_white
                    draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_c, outline="black")
                    if show_numbers and (r, c) in stone_to_num:
                        num_c = "white" if color == 'b' else "black"
                        num_s = str(stone_to_num[(r, c)])
                        f_sz = int(rad * 1.2) if len(num_s) <= 2 else int(rad * 0.9)
                        try: fn = ImageFont.truetype("arial.ttf", f_sz)
                        except: fn = self.font_number
                        self._draw_centered_text(draw, px, py, num_s, fn, num_c)

        # 3. Marks
        if marks:
            for prop, shape in [("SQ", "square"), ("TR", "triangle"), ("MA", "cross")]:
                points = marks.get(prop, [])
                for r, c in points:
                    px, py = self.transformer.indices_to_pixel(r, c)
                    stone_color = board.get(r, c)
                    mark_color = "white" if stone_color == 'b' else "black"
                    size = int(rad * 0.6)
                    w = 5
                    
                    if shape == "square":
                        rect = [(px-size, py-size), (px+size, py-size), (px+size, py+size), (px-size, py+size), (px-size, py-size)]
                        draw.line(rect, fill=mark_color, width=w, joint="round")
                    elif shape == "triangle":
                        pts = [(px, py-int(size*1.2)), (px-size, py+int(size*0.8)), (px+size, py+int(size*0.8)), (px, py-int(size*1.2))]
                        draw.line(pts, fill=mark_color, width=w, joint="round")
                    elif shape == "cross":
                        draw.line([px-size, py-size, px+size, py+size], fill=mark_color, width=w)
                        draw.line([px+size, py-size, px-size, py+size], fill=mark_color, width=w)

        # Analysis text (bottom bar)
        if analysis_text:
            draw.rectangle([(0, self.image_size), (self.image_size, self.image_size + 100)], fill=(30, 30, 30))
            self._draw_centered_text(draw, self.image_size // 2, self.image_size + 50, analysis_text, self.font, "white")
        
        return img

    def _get_star_points(self):
        if self.board_size == 19: return [(r, c) for r in [3, 9, 15] for c in [3, 9, 15]]
        elif self.board_size == 13: return [(r, c) for r in [3, 9] for c in [3, 9]] + [(6, 6)]
        elif self.board_size == 9: return [(r, c) for r in [2, 6] for c in [2, 6]] + [(4, 4)]
        return []

    def render_pv(self, board, pv_list, starting_color, title=""):
        img = self.render(board, last_move=None, analysis_text=title)
        draw = ImageDraw.Draw(img)
        curr_color = starting_color
        for i, m_str in enumerate(pv_list[:10]):
            idx_pair = self.transformer.gtp_to_indices(m_str)
            if idx_pair:
                px, py = self.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
                fill = self.color_black if curr_color == "B" else self.color_white
                txt_c = "white" if curr_color == "B" else "black"
                draw.ellipse([px-15, py-15, px+15, py+15], fill=fill, outline="black")
                self._draw_centered_text(draw, px, py, str(i+1), self.font_small, txt_c)
                curr_color = "W" if curr_color == "B" else "B"
        return img