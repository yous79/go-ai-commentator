import subprocess
import os
import json
import sys
import time
import threading
from sgfmill import sgf, boards, common
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "katago", "2023-06-15-windows64+katago")
KATAGO_EXE = os.path.join(BASE_DIR, "katago_opencl", "katago.exe")
CONFIG = os.path.join(BASE_DIR, "katago_configs", "analysis.cfg")
MODEL = os.path.join(BASE_DIR, "weights", "kata20bs530.bin.gz")
BASE_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output_images")

class BoardRenderer:
    def __init__(self, board_size=19, image_size=800):
        self.board_size = board_size
        self.image_size = image_size
        self.margin = 50
        self.grid_size = (self.image_size - 2 * self.margin) // (self.board_size - 1)
        
        self.color_bg = (220, 179, 92)
        self.color_line = (0, 0, 0)
        self.color_black = (0, 0, 0)
        self.color_white = (255, 255, 255)
        self.color_last_move = (255, 0, 0)

    def _get_star_points(self):
        if self.board_size == 19:
            points = [3, 9, 15]
            return [(r, c) for r in points for c in points]
        elif self.board_size == 13:
            points = [3, 9]
            return [(r, c) for r in points for c in points] + [(6,6)]
        elif self.board_size == 9:
            points = [2, 6]
            return [(r, c) for r in points for c in points] + [(4,4)]
        return []

    def _coord_to_pixel(self, row, col):
        visual_row = self.board_size - 1 - row
        x = self.margin + col * self.grid_size
        y = self.margin + visual_row * self.grid_size
        return x, y

    def render(self, board, last_move=None, analysis_text=""):
        img = Image.new("RGB", (self.image_size, self.image_size + 100), self.color_bg)
        draw = ImageDraw.Draw(img)

        # Draw Grid
        for i in range(self.board_size):
            sx, sy = self.margin + i * self.grid_size, self.margin
            ex, ey = sx, self.margin + (self.board_size - 1) * self.grid_size
            draw.line([(sx, sy), (ex, ey)], fill=self.color_line, width=2)
            sx, sy = self.margin, self.margin + i * self.grid_size
            ex, ey = self.margin + (self.board_size - 1) * self.grid_size, sy
            draw.line([(sx, sy), (ex, ey)], fill=self.color_line, width=2)

        for row, col in self._get_star_points():
             x, y = self._coord_to_pixel(row, col)
             draw.ellipse([(x-4, y-4), (x+4, y+4)], fill=self.color_line)

        stone_radius = self.grid_size // 2 - 2
        for row in range(self.board_size):
            for col in range(self.board_size):
                color = board.get(row, col)
                if color:
                    x, y = self._coord_to_pixel(row, col)
                    fill_color = self.color_black if color == 'b' else self.color_white
                    draw.ellipse([(x-stone_radius, y-stone_radius), (x+stone_radius, y+stone_radius)], fill=fill_color, outline=(0,0,0))

        if last_move:
            color, (row, col) = last_move
            x, y = self._coord_to_pixel(row, col)
            m = stone_radius // 2
            draw.rectangle([(x-m, y-m), (x+m, y+m)], fill=self.color_last_move)

        draw.rectangle([(0, self.image_size), (self.image_size, self.image_size + 100)], fill=(30, 30, 30))
        draw.text((20, self.image_size + 30), analysis_text, fill=(255, 255, 255))
        return img

class KataGoEngine:
    def __init__(self, board_size=19):
        self.board_size = board_size
        cmd = [KATAGO_EXE, "analysis", "-config", CONFIG, "-model", MODEL]
        self.process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )
        
        # Wait for "Started" message in stderr
        print("Initializing KataGo engine...", flush=True)
        while True:
            line = self.process.stderr.readline()
            if "Started, ready to begin handling requests" in line:
                print("KataGo is ready.", flush=True)
                break
            if not line and self.process.poll() is not None:
                print("KataGo failed to start.", flush=True)
                sys.exit(1)

    def analyze(self, move_history, komi=6.5):
        query = {
            "id": "analysis",
            "moves": move_history,
            "rules": "japanese",
            "komi": komi,
            "boardXSize": self.board_size,
            "boardYSize": self.board_size,
            "maxVisits": 500
        }

        try:
            self.process.stdin.write(json.dumps(query) + "\n")
            self.process.stdin.flush()

            while True:
                line = self.process.stdout.readline()
                if not line: break
                response = json.loads(line)
                if response.get("id") == "analysis":
                    return response
        except Exception as e:
            print(f"Error: {e}", flush=True)
            return None

    def close(self):
        self.process.terminate()

def main():
    sgf_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "sample.sgf")
    
    sgf_name = os.path.splitext(os.path.basename(sgf_path))[0]
    output_dir = os.path.join(BASE_OUTPUT_DIR, sgf_name)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading SGF: {sgf_path}", flush=True)
    print(f"Output Images to: {output_dir}", flush=True)

    try:
        with open(sgf_path, "rb") as f:
            game = sgf.Sgf_game.from_bytes(f.read())
    except Exception as e:
        print(f"SGF Load Error: {e}", flush=True)
        return

    board_size = game.get_size()
    katago = KataGoEngine(board_size=board_size)
    renderer = BoardRenderer(board_size=board_size)
    
    total_moves = 0
    temp_node = game.get_root()
    while True:
        try:
            temp_node = temp_node[0]
            if temp_node.get_move()[0] is not None:
                total_moves += 1
        except IndexError:
            break
    print(f"Total Moves: {total_moves}", flush=True)

    node = game.get_root()
    board = boards.Board(board_size)
    komi = game.get_komi()
    move_history = [] 
    move_num = 0
    
    analysis_log = {
        "board_size": board_size,
        "moves": []
    }

    while True:
        print(f"Analyzing Move {move_num}", flush=True)
        analysis = katago.analyze(move_history, komi)
        
        info = "No Data"
        current_data = {
            "move_number": move_num,
            "winrate": 0.0,
            "score": 0.0,
            "candidates": []
        }

        if analysis and 'rootInfo' in analysis:
            wr, sc = analysis['rootInfo'].get('winrate', 0), analysis['rootInfo'].get('scoreLead', 0)
            info = f"Winrate: {wr:.1%} | Score: {sc:.1f}"
            current_data["winrate"] = wr
            current_data["score"] = sc
            if 'moveInfos' in analysis:
                for cand in analysis['moveInfos'][:10]:
                    current_data["candidates"].append({
                        "move": cand['move'],
                        "winrate": cand.get('winrate', 0),
                        "scoreLead": cand.get('scoreLead', 0),
                        "visits": cand.get('visits', 0)
                    })
        
        analysis_log["moves"].append(current_data)
        json_path = os.path.join(output_dir, "analysis.json")
        try:
            with open(json_path, "w") as f:
                json.dump(analysis_log, f, indent=2)
        except: pass

        last_move = None
        if move_num > 0:
            c, m = node.get_move()
            if m: last_move = (c, m)

        img = renderer.render(board, last_move=last_move, analysis_text=f"Move {move_num} | {info}")
        img.save(os.path.join(output_dir, f"move_{move_num:03d}.png"))

        try:
            node = node[0]
            move_num += 1
            color, move = node.get_move()
            if color:
                if move:
                    board.play(move[0], move[1], color)
                    coord = "ABCDEFGHJKLMNOPQRST"[move[1]] + str(move[0] + 1)
                    move_history.append(["B" if color == "b" else "W", coord])
                else:
                    move_history.append(["B" if color == "b" else "W", "pass"])
        except IndexError:
            break

    katago.close()
    print(f"\nDone. {move_num+1} images and analysis.json saved to {output_dir}", flush=True)

if __name__ == "__main__":
    main()