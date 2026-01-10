import subprocess
import os
import json
import sys
import time
import threading

# Add src directory to path to allow importing config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from sgfmill import sgf, boards, common
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
from config import KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL, OUTPUT_BASE_DIR, SRC_DIR

SCRIPT_DIR = SRC_DIR
BASE_OUTPUT_DIR = OUTPUT_BASE_DIR
KATAGO_EXE = KATAGO_EXE
CONFIG = KATAGO_CONFIG
MODEL = KATAGO_MODEL

class BoardRenderer:
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
        
        try: font = ImageFont.truetype("arial.ttf", 22)
        except: font = ImageFont.load_default()

        cols = "ABCDEFGHJKLMNOPQRST"
        for i in range(self.board_size):
            x_pos = self.margin + i * self.grid_size
            y_pos = self.margin + i * self.grid_size
            self._draw_centered_text(draw, x_pos, self.margin - 35, cols[i], font, "black")
            self._draw_centered_text(draw, x_pos, self.margin + (self.board_size-1)*self.grid_size + 35, cols[i], font, "black")
            num_label = str(self.board_size - i)
            self._draw_centered_text(draw, self.margin - 35, y_pos, num_label, font, "black")
            self._draw_centered_text(draw, self.margin + (self.board_size-1)*self.grid_size + 35, y_pos, num_label, font, "black")

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

        draw.rectangle([(0, self.image_size), (self.image_size, self.image_size + 100)], fill=(30, 30, 30))
        self._draw_centered_text(draw, self.image_size // 2, self.image_size + 50, analysis_text, font, "white")
        return img

    def render_pv(self, board, pv_list, starting_color, title=""):
        img = self.render(board, last_move=None, analysis_text=title)
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("arial.ttf", 20)
        except: font = ImageFont.load_default()
        curr_color = starting_color
        for i, m_str in enumerate(pv_list[:10]):
            if not m_str or m_str.lower() == "pass": continue
            col_idx = "ABCDEFGHJKLMNOPQRST".find(m_str[0].upper())
            row_val = int(m_str[1:])
            px, py = self._coord_to_pixel(row_val - 1, col_idx)
            fill = self.color_black if curr_color == "B" else self.color_white
            txt_c = "white" if curr_color == "B" else "black"
            rad = self.grid_size // 2 - 2
            draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill, outline="black")
            self._draw_centered_text(draw, px, py, str(i+1), font, txt_c)
            curr_color = "W" if curr_color == "B" else "B"
        return img

class KataGoEngine:
    def __init__(self, board_size=19):
        self.board_size = board_size
        cmd = [KATAGO_EXE, "analysis", "-config", CONFIG, "-model", MODEL]
        self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        print("Initializing KataGo...", flush=True)
        while True:
            line = self.process.stderr.readline()
            if "Started, ready to begin handling requests" in line:
                print("KataGo is ready.", flush=True)
                break
            if not line and self.process.poll() is not None:
                sys.exit(1)

    def analyze(self, moves, komi=6.5):
        query = {"id": "analysis", "moves": moves, "rules": "japanese", "komi": komi, "boardXSize": self.board_size, "boardYSize": self.board_size, "maxVisits": 500}
        try:
            self.process.stdin.write(json.dumps(query) + "\n")
            self.process.stdin.flush()
            while True:
                line = self.process.stdout.readline()
                if not line: break
                resp = json.loads(line)
                if resp.get("id") == "analysis": return resp
        except: return None

    def close(self):
        self.process.terminate()

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "sample.sgf")
    name = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(BASE_OUTPUT_DIR, name)
    os.makedirs(out, exist_ok=True)
    
    print(f"Loading SGF: {path}", flush=True)
    with open(path, "rb") as f: game = sgf.Sgf_game.from_bytes(f.read())
    board_size = game.get_size()
    
    # Calculate total moves
    total = 0; temp = game.get_root()
    while True:
        try: temp = temp[0]; total += 1
        except: break
    print(f"Total Moves: {total}", flush=True)

    # --- Skip Check ---
    json_path = os.path.join(out, "analysis.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                existing_log = json.load(f)
            # Check if analysis is complete (last move number matches or exceeded)
            if len(existing_log.get("moves", [])) >= total + 1:
                print(f"Analysis for {name} already exists and is complete. Skipping.", flush=True)
                return
        except:
            pass # Continue to analysis if JSON is corrupt
    # --- End Skip Check ---

    engine = KataGoEngine(board_size)
    renderer = BoardRenderer(board_size)
    node = game.get_root(); board = boards.Board(board_size); history = []; m_num = 0
    log = {"board_size": board_size, "moves": []}
    cols = "ABCDEFGHJKLMNOPQRST"
    while True:
        print(f"Analyzing Move {m_num}", flush=True)
        ans = engine.analyze(history)
        info = "No Data"; data = {"move_number": m_num, "winrate": 0.5, "score": 0.0, "candidates": []}
        
        if ans and 'rootInfo' in ans:
            raw_wr = ans['rootInfo'].get('winrate', 0.5)
            raw_sc = ans['rootInfo'].get('scoreLead', 0.0)
            
            # Standardize to Black's perspective
            # m_num 0: next is Black. m_num 1: next is White.
            is_white_next = (m_num % 2 != 0)
            if is_white_next:
                wr_black = 1.0 - raw_wr
                sc_black = -raw_sc
            else:
                wr_black = raw_wr
                sc_black = raw_sc
                
            info = f"Winrate(B): {wr_black:.1%} | Score(B): {sc_black:.1f}"
            data.update({"winrate": wr_black, "score": sc_black})
            
            if 'moveInfos' in ans:
                for c in ans['moveInfos'][:10]:
                    c_wr = c.get('winrate', 0)
                    c_sc = c.get('scoreLead', 0)
                    if is_white_next:
                        c_wr_black = 1.0 - c_wr
                        c_sc_black = -c_sc
                    else:
                        c_wr_black = c_wr
                        c_sc_black = c_sc
                    data["candidates"].append({
                        "move": c['move'], 
                        "winrate": c_wr_black, 
                        "scoreLead": c_sc_black, 
                        "pv": c.get('pv', [])
                    })
        
        log["moves"].append(data)
        with open(os.path.join(out, "analysis.json"), "w") as f: json.dump(log, f, indent=2)
        last = None
        if m_num > 0:
            c, m = node.get_move()
            if m: last = (c, m)
        img = renderer.render(board, last_move=last, analysis_text=f"Move {m_num} | {info}")
        img.save(os.path.join(out, f"move_{m_num:03d}.png"))
        try:
            node = node[0]; m_num += 1; color, m = node.get_move()
            if color:
                if m:
                    board.play(m[0], m[1], color)
                    history.append(["B" if color == 'b' else "W", cols[m[1]] + str(m[0]+1)])
                else: history.append(["B" if color == 'b' else "W", "pass"])
        except: break
    engine.close()
    print(f"Done. Images in {out}", flush=True)

if __name__ == "__main__":
    main()