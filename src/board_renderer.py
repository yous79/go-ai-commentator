from PIL import Image, ImageDraw, ImageFont
import os

class GoBoardRenderer:
    def __init__(self, board_size=19, image_size=850):
        self.board_size = board_size
        self.image_size = image_size
        self.margin = 70 
        self.grid_size = (self.image_size - 2 * self.margin) // (self.board_size - 1)
        
        self.color_bg = (220, 179, 92) 
        self.color_line = (0, 0, 0)
        self.color_black = (0, 0, 0)
        self.color_white = (255, 255, 255)
        self.color_last_move = (255, 0, 0)

        try:
            self.font = ImageFont.truetype("arial.ttf", 22)
            self.font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def _get_star_points(self):
        if self.board_size == 19:
            p = [3, 9, 15]
            return [(r, c) for r in p for c in p]
        elif self.board_size == 13:
            p = [3, 9]
            return [(r, c) for r in p for c in p] + [(6, 6)]
        elif self.board_size == 9:
            p = [2, 6]
            return [(r, c) for r in p for c in p] + [(4, 4)]
        return []

    def _coord_to_pixel(self, row, col):
        visual_row = self.board_size - 1 - row
        x = self.margin + col * self.grid_size
        y = self.margin + visual_row * self.grid_size
        return x, y

    def _draw_centered_text(self, draw, x, y, text, font, fill):
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            w, h = right - left, bottom - top
            draw.text((x - w / 2, y - h / 2 - top), text, font=font, fill=fill)
        except AttributeError:
            w, h = draw.textsize(text, font=font)
            draw.text((x - w / 2, y - h / 2), text, font=font, fill=fill)

    def render(self, board, last_move=None, analysis_text=""):
        img = Image.new("RGB", (self.image_size, self.image_size + 100), self.color_bg)
        draw = ImageDraw.Draw(img)
        
        cols = "ABCDEFGHJKLMNOPQRST"
        for i in range(self.board_size):
            x_pos = self.margin + i * self.grid_size
            y_pos = self.margin + i * self.grid_size
            self._draw_centered_text(draw, x_pos, self.margin - 35, cols[i], self.font, "black")
            self._draw_centered_text(draw, x_pos, self.margin + (self.board_size-1)*self.grid_size + 35, cols[i], self.font, "black")
            num_label = str(self.board_size - i)
            self._draw_centered_text(draw, self.margin - 35, y_pos, num_label, self.font, "black")
            self._draw_centered_text(draw, self.margin + (self.board_size-1)*self.grid_size + 35, y_pos, num_label, self.font, "black")

            sx, sy = self.margin + i * self.grid_size, self.margin
            ex, ey = sx, self.margin + (self.board_size - 1) * self.grid_size
            draw.line([(sx, sy), (ex, ey)], fill=self.color_line, width=2)
            sx, sy = self.margin, self.margin + i * self.grid_size
            ex, ey = self.margin + (self.board_size - 1) * self.grid_size, sy
            draw.line([(sx, sy), (ex, ey)], fill=self.color_line, width=2)

        for r, c in self._get_star_points():
            px, py = self._coord_to_pixel(r, c)
            draw.ellipse([px-4, py-4, px+4, py+4], fill=self.color_line)

        rad = self.grid_size // 2 - 2
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = board.get(r, c)
                if color:
                    px, py = self._coord_to_pixel(r, c)
                    fill_c = self.color_black if color == 'b' else self.color_white
                    draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_c, outline="black")

        if last_move:
            c, (r, col) = last_move
            px, py = self._coord_to_pixel(r, col)
            m = rad // 2
            draw.rectangle([px-m, py-m, px+m, py+m], fill=self.color_last_move)

        if analysis_text:
            draw.rectangle([(0, self.image_size), (self.image_size, self.image_size + 100)], fill=(30, 30, 30))
            self._draw_centered_text(draw, self.image_size // 2, self.image_size + 50, analysis_text, self.font, "white")
        
        return img

    def render_pv(self, board, pv_list, starting_color, title=""):
        img = self.render(board, last_move=None, analysis_text=title)
        draw = ImageDraw.Draw(img)
        
        curr_color = starting_color
        for i, m_str in enumerate(pv_list[:10]):
            if not m_str or m_str.lower() == "pass": continue
            col_idx = "ABCDEFGHJKLMNOPQRST".find(m_str[0].upper())
            try:
                row_val = int(m_str[1:])
            except:
                continue
                
            px, py = self._coord_to_pixel(row_val - 1, col_idx)
            fill = self.color_black if curr_color == "B" else self.color_white
            txt_c = "white" if curr_color == "B" else "black"
            rad = self.grid_size // 2 - 2
            draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill, outline="black")
            self._draw_centered_text(draw, px, py, str(i+1), self.font_small, txt_c)
            curr_color = "W" if curr_color == "B" else "B"
        return img
