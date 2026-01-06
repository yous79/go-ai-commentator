import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import sys
import threading
import subprocess
import time
import glob
import queue
import json
import traceback
from google import genai
from google.genai import types
from sgfmill import sgf
from katago_driver import KataGoDriver

# --- Configuration (Gemini.md Rev. 3.0 compliant) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYZE_SCRIPT = os.path.join(SCRIPT_DIR, "analyze_sgf.py")
OUTPUT_BASE_DIR = os.path.join(SCRIPT_DIR, "output_images")

BASE_DIR = os.path.join(SCRIPT_DIR, "katago", "2023-06-15-windows64+katago")
KATAGO_EXE = os.path.join(BASE_DIR, "katago_opencl", "katago.exe")
CONFIG = os.path.join(BASE_DIR, "katago_configs", "analysis.cfg")
MODEL = os.path.join(BASE_DIR, "weights", "kata20bs530.bin.gz")

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Analysis Agent")
        self.root.geometry("1200x950")

        # Variables
        self.current_move = 0
        self.total_moves_in_dir = 0
        self.image_cache = {}
        self.analysis_data = {"board_size": 19, "moves": []}
        self.current_sgf_name = None
        self.current_sgf_path = None
        self.image_dir = None
        self.analyzing = False
        self.process = None
        self.queue = queue.Queue()
        
        # State
        self.review_mode = tk.BooleanVar(value=False)
        self.edit_mode = tk.BooleanVar(value=False)
        self.agent_last_pv = None
        
        # AI
        self.gemini_client = None
        self.katago_agent = None 
        
        self.setup_gemini()
        self.setup_layout()
        
        # Bind events
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.click_on_board)
        
        self.check_queue()

    def setup_gemini(self):
        key_path = os.path.join(SCRIPT_DIR, "api_key.txt")
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    api_key = f.read().strip()
                self.gemini_client = genai.Client(api_key=api_key)
                self.katago_agent = KataGoDriver(KATAGO_EXE, CONFIG, MODEL)
                print("DEBUG: Gemini and KataGo initialized.")
            except Exception as e:
                print(f"DEBUG Gemini Init Error: {e}")

    def consult_katago_tool(self, moves_list: list[list[str]]):
        """Tool for Gemini Agent"""
        board_size = self.analysis_data.get("board_size", 19)
        print(f"DEBUG TOOL: Consulting KataGo for {board_size}x{board_size} board...")
        try:
            result = self.katago_agent.analyze_situation(moves_list, board_size=board_size)
            
            # Standardize winrate to Black perspective
            num_moves = len(moves_list)
            if num_moves % 2 != 0:
                raw_wr = result.get('current_winrate_black', 0.5)
                result['current_winrate_black'] = 1.0 - raw_wr
                if 'top_candidates' in result:
                    for cand in result['top_candidates']:
                        cand['winrate'] = 1.0 - cand.get('winrate', 0.5)

            # Capture PV
            if 'top_candidates' in result and result['top_candidates']:
                pv_str = result['top_candidates'][0].get('future_sequence', "")
                if pv_str:
                    self.agent_last_pv = [m.strip() for m in pv_str.split("->")]
                    print(f"DEBUG TOOL: Captured PV list: {self.agent_last_pv}")
            return result
        except Exception as e:
            print(f"DEBUG TOOL ERROR: {e}")
            return {"error": str(e)}

    def load_knowledge_base(self):
        kn_text = ""
        kn_dir = os.path.join(SCRIPT_DIR, "knowledge")
        if os.path.exists(kn_dir):
            subfolders = sorted(os.listdir(kn_dir))
            for subdir in subfolders:
                sub_path = os.path.join(kn_dir, subdir)
                if os.path.isdir(sub_path):
                    term = subdir.split("_")[-1]
                    kn_text += f"\n### 用語: {term}\n"
                    txt_files = glob.glob(os.path.join(sub_path, "*.txt"))
                    for f_name in txt_files:
                        try:
                            with open(f_name, "r", encoding="utf-8") as f:
                                kn_text += f"- {f.read().strip()}\n"
                        except:
                            pass
        return kn_text

    def setup_layout(self):
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        
        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open SGF...", command=self.open_sgf)
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # Top
        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_bar = ttk.Progressbar(top_frame, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_status = tk.Label(top_frame, text="Idle", width=30, bg="#ddd")
        self.lbl_status.pack(side=tk.RIGHT, padx=10)

        # Middle
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")
        
        self.board_frame = tk.Frame(self.paned, bg="#333")
        self.paned.add(self.board_frame, width=600)
        self.canvas = tk.Canvas(self.board_frame, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.info_frame = tk.Frame(self.paned, bg="#f0f0f0", width=600)
        self.paned.add(self.info_frame)

        # Labels
        tk.Label(self.info_frame, text="Analysis Info", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        self.lbl_winrate = tk.Label(self.info_frame, text="Winrate (Black): --%", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w", padx=20)
        self.lbl_score = tk.Label(self.info_frame, text="Score: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w", padx=20)

        # Toggles
        tk.Checkbutton(self.info_frame, text="Review Mode", variable=self.review_mode, command=self.update_display, bg="#f0f0f0").pack()
        tk.Checkbutton(self.info_frame, text="Edit Mode", variable=self.edit_mode, bg="#f0f0f0").pack()
        
        # Buttons
        tk.Button(self.info_frame, text="Show Future Sequence (PV)", command=self.show_pv, bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(pady=5, fill=tk.X, padx=20)

        # Agent Area
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=5)
        tk.Label(self.info_frame, text="AI Commentary (Agent)", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=2)
        self.btn_comment = tk.Button(self.info_frame, text="Ask KataGo Agent", command=self.generate_commentary, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_comment.pack(pady=5, fill=tk.X, padx=20)
        
        comm_f = tk.Frame(self.info_frame, bg="#f0f0f0")
        comm_f.pack(fill=tk.BOTH, expand=True, padx=10)
        scr = tk.Scrollbar(comm_f)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_commentary = tk.Text(comm_f, height=10, wrap=tk.WORD, yscrollcommand=scr.set)
        self.txt_commentary.pack(fill=tk.BOTH, expand=True)
        scr.config(command=self.txt_commentary.yview)
        
        self.btn_agent_pv = tk.Button(self.info_frame, text="エージェントの想定図を表示", command=self.show_agent_pv, state="disabled", bg="#FF9800", fg="white")
        self.btn_agent_pv.pack(pady=5, fill=tk.X, padx=20)
        self.btn_report = tk.Button(self.info_frame, text="対局レポートを生成", command=self.generate_full_report, bg="#9C27B0", fg="white")
        self.btn_report.pack(pady=5, fill=tk.X, padx=20)

        # Mistakes
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=5)
        m_frame = tk.Frame(self.info_frame, bg="#f0f0f0")
        m_frame.pack(fill=tk.X, padx=5)
        m_frame.columnconfigure(0, weight=1)
        m_frame.columnconfigure(1, weight=1)
        tk.Label(m_frame, text="Black", font=("Arial", 9, "bold"), bg="#f0f0f0").grid(row=0, column=0)
        tk.Label(m_frame, text="White", font=("Arial", 9, "bold"), bg="#f0f0f0").grid(row=0, column=1)
        
        self.btn_m_b = []
        self.btn_m_w = []
        for i in range(3):
            b = tk.Button(m_frame, text="-", command=lambda x=i: self.goto_mistake("b", x), bg="#ffcccc", font=("Arial", 8))
            b.grid(row=i+1, column=0, sticky="ew", padx=2, pady=1)
            self.btn_m_b.append(b)
            
            w = tk.Button(m_frame, text="-", command=lambda x=i: self.goto_mistake("w", x), bg="#ffcccc", font=("Arial", 8))
            w.grid(row=i+1, column=1, sticky="ew", padx=2, pady=1)
            self.btn_m_w.append(w)
            
        self.moves_m_b = [None]*3
        self.moves_m_w = [None]*3

        # Bottom
        bot = tk.Frame(self.root, bg="#e0e0e0", height=60)
        bot.grid(row=2, column=0, sticky="ew")
        bot.grid_propagate(False)
        bot.columnconfigure(0, weight=1)
        bot.columnconfigure(4, weight=1)
        tk.Button(bot, text="< Prev", command=self.prev_move, width=15).grid(row=0, column=1, padx=10, pady=10)
        self.lbl_counter = tk.Label(bot, text="0 / 0", font=("Arial", 12, "bold"), bg="#e0e0e0")
        self.lbl_counter.grid(row=0, column=2, padx=20)
        tk.Button(bot, text="Next >", command=self.next_move, width=15).grid(row=0, column=3, padx=10, pady=10)

    def open_sgf(self):
        p = filedialog.askopenfilename(filetypes=[("SGF Files", "*.sgf")])
        if p:
            self.current_sgf_path = p
            self.start_analysis(p)

    def start_analysis(self, path):
        self.current_move = 0
        self.image_cache = {}
        self.analysis_data = {"board_size": 19, "moves": []}
        self.analyzing = True
        self.current_sgf_name = os.path.splitext(os.path.basename(path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name)
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
        threading.Thread(target=self.run_analysis_script, args=(path,), daemon=True).start()
        self.monitor_images()

    def run_analysis_script(self, path):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = ["python", "-u", ANALYZE_SCRIPT, path]
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
            while True:
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                if "Total Moves:" in line:
                    self.queue.put(("set_max", int(line.split(":")[1])))
                if "Analyzing Move" in line:
                    self.queue.put(("progress", int(line.split("Move")[1])))
            self.analyzing = False
            self.queue.put(("done", None))
        except:
            self.analyzing = False

    def check_queue(self):
        try:
            while True:
                msg, d = self.queue.get_nowait()
                if msg == "set_max":
                    self.progress_bar.config(maximum=d)
                    self.lbl_status.config(text=f"Analyzing... (Total: {d})")
                elif msg == "progress":
                    self.lbl_status.config(text=f"Progress: {d} / {int(self.progress_bar['maximum'])}")
                elif msg == "done":
                    self.lbl_status.config(text="Analysis Complete")
                    self.load_analysis_data()
                elif msg == "error":
                    self.lbl_status.config(text=f"Error: {d[:20]}", fg="red")
        except:
            pass
        self.root.after(100, self.check_queue)

    def load_analysis_data(self):
        p = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    d = json.load(f)
                if isinstance(d, list):
                    self.analysis_data = {"board_size": 19, "moves": d}
                else:
                    self.analysis_data = d
                self.calculate_mistakes()
                self.update_display()
            except:
                pass

    def calculate_mistakes(self):
        moves = self.analysis_data.get("moves", [])
        if len(moves) < 2:
            return
        db, dw = [], []
        for i in range(1, len(moves)):
            prev = moves[i-1]
            curr = moves[i]
            drop = prev.get('winrate', 0.5) - (1.0 - curr.get('winrate', 0.5))
            if drop > 0.01:
                if i % 2 != 0:
                    db.append((drop, i))
                else:
                    dw.append((drop, i))
        db.sort(key=lambda x: x[0], reverse=True)
        dw.sort(key=lambda x: x[0], reverse=True)
        for i in range(3):
            self._upd_m_btn(self.btn_m_b[i], self.moves_m_b, i, db)
            self._upd_m_btn(self.btn_m_w[i], self.moves_m_w, i, dw)

    def _upd_m_btn(self, btn, store, idx, drops):
        if idx < len(drops):
            drop, m = drops[idx]
            store[idx] = m
            btn.config(text=f"#{m}: -{drop:.1%}", state="normal")
        else:
            store[idx] = None
            btn.config(text="-", state="disabled")

    def goto_mistake(self, c, i):
        m = self.moves_m_b[i] if c == "b" else self.moves_m_w[i]
        if m:
            self.show_image(m)

    def monitor_images(self):
        if not self.image_dir:
            return
        files = glob.glob(os.path.join(self.image_dir, "move_*.png"))
        self.total_moves_in_dir = len(files)
        if self.total_moves_in_dir > 0 and not self.image_cache:
            self.show_image(0)
        if self.analyzing:
            self.load_analysis_data()
            self.root.after(2000, self.monitor_images)

    def gtp_to_coords(self, v):
        if not v or v.lower() == "pass":
            return None
        col = "ABCDEFGHJKLMNOPQRST".find(v[0].upper())
        try:
            return int(v[1:]) - 1, col
        except:
            return None

    def get_canvas_coords(self, r, c):
        sz = self.analysis_data.get("board_size", 19)
        m, b = 70, 850
        step = (b - 2 * m) / (sz - 1)
        vr = sz - 1 - r
        return (m + c * step) / b, (m + vr * step) / b

    def show_image(self, n):
        p = os.path.join(self.image_dir, f"move_{n:03d}.png")
        if os.path.exists(p) and n not in self.image_cache:
            self.image_cache[n] = Image.open(p)
        self.current_move = n
        self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache:
            return
        moves = self.analysis_data.get("moves", [])
        wr_d, sc, cands = "--%", "--", []
        if moves and self.current_move < len(moves):
            d = moves[self.current_move]
            wr_raw = d.get('winrate', 0.5)
            wr_black = (1.0 - wr_raw) if (self.current_move % 2 != 0) else wr_raw
            wr_d = f"{wr_black:.1%}"
            sc = f"{d.get('score', 0):.1f}"
            cands = d.get('candidates', [])
        
        self.lbl_winrate.config(text=f"Winrate (Black): {wr_d}")
        self.lbl_score.config(text=f"Score: {sc}")
        self.lbl_counter.config(text=f"{self.current_move} / {self.total_moves_in_dir - 1}")
        
        cw, ch = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        img = self.image_cache[self.current_move]
        ratio = min(cw / img.size[0], ch / img.size[1])
        nw, nh = int(img.size[0] * ratio), int(img.size[1] * ratio)
        ox, oy = (cw - nw)//2, (ch - nh)//2
        
        res = img.resize((nw, nh), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(res)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo
        
        if self.review_mode.get() and cands:
            br = 850 / 950
            for i, c in enumerate(cands[:3]):
                co = self.gtp_to_coords(c['move'])
                if co:
                    nx, ny = self.get_canvas_coords(co[0], co[1])
                    fx, fy = ox + nw * nx, oy + (nh * br) * ny
                    rad = (nw / 19) * 0.6
                    color = "#00ff00" if i == 0 else "#00aaff"
                    self.canvas.create_oval(fx-rad, fy-rad, fx+rad, fy+rad, fill=color, outline=color, tags="overlay")
                    self.canvas.create_text(fx, fy, text=f"{c['winrate']:.0%}", fill="black", font=("Arial", int(rad), "bold"), tags="overlay")

    def _draw_centered_text(self, draw, x, y, text, font, fill):
        try:
            l, t, r, b = draw.textbbox((0, 0), text, font=font)
            w, h = r - l, b - t
            draw.text((x - w/2, y - h/2 - t), text, font=font, fill=fill)
        except:
            try:
                w, h = draw.textsize(text, font=font)
                draw.text((x - w/2, y - h/2), text, font=font, fill=fill)
            except:
                draw.text((x, y), text, font=font, fill=fill)

    def _render_pv_window(self, title, pv_list):
        idx = self.current_move
        sz = self.analysis_data.get("board_size", 19)
        top = tk.Toplevel(self.root)
        top.title(f"{title} (Move {idx})")
        top.geometry("750x800")
        cv = tk.Canvas(top, bg="#333")
        cv.pack(fill=tk.BOTH, expand=True)
        
        if idx not in self.image_cache:
            return
        base = self.image_cache[idx].copy()
        draw = ImageDraw.Draw(base)
        m, b_w = 70, 850
        step = (b_w - 2 * m) / (sz - 1)
        
        try:
            f = ImageFont.truetype("arial.ttf", 20)
        except:
            f = ImageFont.load_default()
            
        cols = "ABCDEFGHJKLMNOPQRST"
        for i in range(sz):
            x = m + i * step
            y = m + i * step
            self._draw_centered_text(draw, x, m-35, cols[i], f, "black")
            self._draw_centered_text(draw, x, m+(sz-1)*step+35, cols[i], f, "black")
            self._draw_centered_text(draw, m-35, y, str(sz-i), f, "black")
            self._draw_centered_text(draw, m+(sz-1)*step+35, y, str(sz-i), f, "black")
            
        color = "W" if (idx % 2 != 0) else "B"
        for i, m_str in enumerate(pv_list[:10]):
            co = self.gtp_to_coords(m_str)
            if co:
                px, py = m + co[1] * step, m + (sz - 1 - co[0]) * step
                fill, txt_c = ("white", "black") if color == "W" else ("black", "white")
                rad = step * 0.45
                draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill, outline=txt_c)
                num = str(i + 1)
                f_sz = int(rad * 1.1) if len(num) == 1 else int(rad * 0.9)
                try:
                    fn = ImageFont.truetype("arial.ttf", f_sz)
                except:
                    fn = ImageFont.load_default()
                self._draw_centered_text(draw, px, py, num, fn, txt_c)
                color = "B" if color == "W" else "W"
                
        photo = ImageTk.PhotoImage(base)
        cv.create_image(0, 0, image=photo, anchor=tk.NW, tags="pv_img")
        cv.image = photo
        
        def on_res(e):
            if e.width < 100: return
            res = base.resize((e.width, e.height), Image.Resampling.LANCZOS)
            p = ImageTk.PhotoImage(res)
            cv.delete("pv_img")
            cv.create_image(0, 0, image=p, anchor=tk.NW, tags="pv_img")
            cv.image = p
        cv.bind("<Configure>", on_res)

    def show_pv(self):
        idx = self.current_move
        moves = self.analysis_data.get("moves", [])
        if idx < len(moves):
            d = moves[idx]
            cands = d.get('candidates', [])
            if cands and 'pv' in cands[0]:
                self._render_pv_window("Future Sequence", cands[0]['pv'])
            else:
                messagebox.showinfo("Info", "No variation data.")

    def show_agent_pv(self):
        if self.agent_last_pv:
            self._render_pv_window("Agent Reference", self.agent_last_pv)

    def click_on_board(self, event):
        if not self.edit_mode.get() or not self.current_sgf_path: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        img = self.image_cache.get(self.current_move)
        if not img: return
        ratio = min(cw/img.size[0], ch/img.size[1])
        nw, nh = int(img.size[0]*ratio), int(img.size[1]*ratio)
        ox, oy = (cw-nw)//2, (ch-nh)//2
        m, b_size, sz = 70, 850, self.analysis_data.get("board_size", 19)
        step = (b_size-2*m)/(sz-1)
        rel_x, rel_y = (event.x - ox) / ratio, (event.y - oy) / ratio
        col = round((rel_x - m) / step)
        row_idx = round((rel_y - m) / step)
        row = sz - 1 - row_idx
        if 0 <= col < sz and 0 <= row < sz:
            coord = "ABCDEFGHJKLMNOPQRST"[col] + str(row+1)
            color = "B" if (self.current_move % 2 == 0) else "W"
            self.play_interactive_move(color, coord)

    def play_interactive_move(self, color, coord):
        self.btn_comment.config(state="disabled", text="Analyzing...")
        def run():
            try:
                with open(self.current_sgf_path, "rb") as f:
                    game = sgf.Sgf_game.from_bytes(f.read())
                h = []
                node = game.get_root()
                count = 0
                while count < self.current_move:
                    try:
                        node = node[0]
                        count += 1
                        c, m = node.get_move()
                        if c:
                            if m:
                                h.append(["B" if c == 'b' else "W", "ABCDEFGHJKLMNOPQRST"[m[1]] + str(m[0]+1)])
                            else:
                                h.append(["B" if c == 'b' else "W", "pass"])
                    except:
                        break
                h.append([color, coord])
                sz = self.analysis_data.get("board_size", 19)
                res = self.katago_agent.analyze_situation(h, board_size=sz)
                new_idx = self.current_move + 1
                new_data = {
                    "move_number": new_idx,
                    "winrate": res.get('current_winrate_black', 0.5),
                    "score": res.get('current_score_lead_black', 0.0),
                    "candidates": []
                }
                for c in res.get('top_candidates', []):
                    new_data["candidates"].append({
                        "move": c['move'],
                        "winrate": c.get('winrate', 0),
                        "scoreLead": c.get('score_lead', 0),
                        "pv": [m.strip() for m in c.get('future_sequence', "").split("->")]
                    })
                self.analysis_data["moves"] = self.analysis_data["moves"][:new_idx]
                self.analysis_data["moves"].append(new_data)
                
                base = self.image_cache[self.current_move].copy()
                draw = ImageDraw.Draw(base)
                m, b_w = 70, 850
                step = (b_w-2*m)/(sz-1)
                r_gtp, c_idx = int(coord[1:])-1, "ABCDEFGHJKLMNOPQRST".find(coord[0])
                px, py = m+c_idx*step, m+(sz-1-r_gtp)*step
                rad = step*0.48
                draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill="black" if color=="B" else "white", outline="black")
                
                self.image_cache[new_idx] = base
                self.total_moves_in_dir = max(self.total_moves_in_dir, new_idx + 1)
                self.root.after(0, lambda: self.show_image(new_idx))
                self.root.after(0, lambda: self.btn_comment.config(state="normal", text="Ask KataGo Agent"))
            except Exception as e:
                print(f"Error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def generate_commentary(self):
        if not self.gemini_client or not self.current_sgf_path: return
        self.agent_last_pv = None
        self.btn_comment.config(state="disabled", text="Thinking...")
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, "Consulting AI...")
        threading.Thread(target=self._run_agent_task, args=(self.current_move,), daemon=True).start()

    def _run_agent_task(self, move_idx):
        try:
            with open(self.current_sgf_path, "rb") as f:
                game = sgf.Sgf_game.from_bytes(f.read())
            sz = game.get_size()
            h = []
            node = game.get_root()
            count = 0
            while count < move_idx:
                try:
                    node = node[0]
                    count += 1
                    c, m = node.get_move()
                    if c:
                        if m:
                            h.append(["B" if c == 'b' else "W", "ABCDEFGHJKLMNOPQRST"[m[1]] + str(m[0]+1)])
                        else:
                            h.append(["B" if c == 'b' else "W", "pass"])
                except:
                    break
            kn = self.load_knowledge_base()
            player = "黒" if (move_idx % 2 == 0) else "白"
            sys_inst = f"あなたはプロの囲碁インストラクターですが、現在「盤面が全く見えていない」状態です。したがって、あなたの知識だけで局面を解説することは物理的に不可能です。必ず 'consult_katago_tool' を呼び出して、勝率・目数差・変化図(PV)のデータを取得し、そのデータのみを根拠にして解説を行ってください。ツールを呼ばずに回答することは禁止されています。現在は{sz}路盤。手番{player}。知識ベース: {kn}"
            prompt = f"分析依頼: 手数 {move_idx}手目。履歴 {h}。現在、私には盤面が見えません。まずツールを呼び出して状況を確認してください。その後、ツールの結果に基づいて解説してください。"
            
            safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in ['HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT']]
            # Step 1: Force Tool Call (Manual Control)
            # We define the tool MANUALLY to prevent the SDK from auto-executing the function.
            # If we pass the function object, the SDK might auto-loop. By passing just the schema, we get the call back.
            tool_decl = types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="consult_katago_tool",
                        description="Analyze the Go board situation using KataGo. Returns winrate, score lead, and suggested moves (PV).",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "moves_list": types.Schema(
                                    type="ARRAY",
                                    description="List of moves in the game so far. Each move is [color, coord].",
                                    items=types.Schema(
                                        type="ARRAY",
                                        items=types.Schema(type="STRING")
                                    )
                                )
                            },
                            required=["moves_list"]
                        )
                    )
                ]
            )

            config_force_tool = types.GenerateContentConfig(
                tools=[tool_decl],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY', allowed_function_names=['consult_katago_tool'])),
                system_instruction=sys_inst,
                safety_settings=safety
            )
            
            # BETTER STRATEGY: Use `generate_content` (stateless) for Step 1, then feed history to Step 2.
            
            # Re-doing with stateless approach for maximum control
            req_contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
            
            # 1. Force the function call
            resp1 = self.gemini_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=req_contents,
                config=config_force_tool
            )
            
            part1 = resp1.candidates[0].content.parts[0]
            
            # Check if we got a function call
            if not part1.function_call:
                 raise Exception("Model failed to call tool despite mode='ANY'.")
            
            fc = part1.function_call
            print(f"DEBUG: Manual Tool Execution for {fc.name}")
            
            # 2. Execute the tool
            # Parse arguments (they are usually a dict or object)
            args = fc.args
            moves_arg = args.get('moves_list') # match parameter name in consult_katago_tool
            
            # Run the actual python function
            tool_result_data = self.consult_katago_tool(moves_arg)
            
            # Create the FunctionResponse part
            # The SDK expects a specific structure for tool responses.
            # We need to match the id of the function call if present, though often implicit in simple flows.
            # The google-genai SDK uses 'function_response' part type.
            
            tool_response_part = types.Part(
                function_response=types.FunctionResponse(
                    name='consult_katago_tool',
                    response={'result': tool_result_data} # generic dict wrapper
                )
            )
            
            # Update history: User Prompt -> Model FunctionCall -> User FunctionResponse
            req_contents.append(types.Content(role="model", parts=[part1]))
            req_contents.append(types.Content(role="user", parts=[tool_response_part]))
            
            # 3. Generate Explanation (Mode = NONE or AUTO, but we have the data now)
            # We relax the constraint so it can talk.
            config_talk = types.GenerateContentConfig(
                system_instruction=sys_inst,
                safety_settings=safety
                # No tools needed here, or tools with mode='NONE', to prevent further calls
            )
            
            resp2 = self.gemini_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=req_contents,
                config=config_talk
            )
            
            final_text = resp2.text if resp2.text else "解説生成エラー"
            self.root.after(0, lambda: self.update_commentary_ui(final_text))
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.root.after(0, lambda: self.update_commentary_ui(f"Error: {err_msg}"))

    def update_commentary_ui(self, text):
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, str(text))
        self.btn_comment.config(state="normal", text="Ask KataGo Agent")
        if self.agent_last_pv:
            self.btn_agent_pv.config(state="normal")

    def generate_full_report(self):
        if not self.gemini_client or not self.current_sgf_path: return
        self.btn_report.config(state="disabled", text="Generating...")
        threading.Thread(target=self._run_report_task, daemon=True).start()

    def _run_report_task(self):
        try:
            self.load_analysis_data()
            moves = self.analysis_data.get("moves", [])
            if not moves: return
            
            drops = []
            for i in range(1, len(moves)):
                prev, curr = moves[i-1], moves[i]
                d = prev.get('winrate', 0.5) - (1.0 - curr.get('winrate', 0.5))
                if d > 0.05: drops.append((d, i))
            
            all_m = sorted([d for d in drops if d[1]%2!=0], key=lambda x:x[0], reverse=True)[:3] + \
                    sorted([d for d in drops if d[1]%2==0], key=lambda x:x[0], reverse=True)[:3]
            all_m = sorted(all_m, key=lambda x:x[1])
            
            r_dir = os.path.join(self.image_dir, "report")
            os.makedirs(r_dir, exist_ok=True)
            
            r_md = f"# 対局レポート: {self.current_sgf_name}\n\n"
            
            with open(self.current_sgf_path, "rb") as f:
                game = sgf.Sgf_game.from_bytes(f.read())
            sz = game.get_size()
            
            from analyze_sgf import BoardRenderer, boards
            renderer = BoardRenderer(sz)
            
            for drop, m_idx in all_m:
                history = []
                node = game.get_root()
                tb = boards.Board(sz)
                for _ in range(m_idx - 1):
                    node = node[0]
                    c, m = node.get_move()
                    if c:
                        if m:
                            tb.play(m[0], m[1], c)
                            history.append(["B" if c == 'b' else "W", "ABCDEFGHJKLMNOPQRST"[m[1]] + str(m[0] + 1)])
                        else:
                            history.append(["B" if c == 'b' else "W", "pass"])
                
                res = self.katago_agent.analyze_situation(history, board_size=sz)
                if 'top_candidates' in res and res['top_candidates']:
                    best = res['top_candidates'][0]
                    pv_str = best.get('future_sequence', "")
                    pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
                    p_img = renderer.render_pv(tb, pv_list, "W" if (m_idx % 2 == 0) else "B", title=f"Move {m_idx} Ref (-{drop:.1%})")
                    f_name = f"mistake_{m_idx:03d}_pv.png"
                    p_img.save(os.path.join(r_dir, f_name))
                    
                    prompt = f"手数: {m_idx}, プレイヤー: {'黒' if m_idx%2!=0 else '白'}, 勝率下落: {drop:.1%}, AI推奨: {best['move']}, 変化図: {pv_str}. なぜ悪手か論理的に解説せよ."
                    resp = self.gemini_client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
                    r_md += f"### 手数 {m_idx} ({'黒' if m_idx%2!=0 else '白'}番)\n- **勝率下落**: -{drop:.1%}\n- **AI推奨**: {best['move']}\n\n![参考図]({f_name})\n\n**解説**: {resp.text}\n\n---\n\n"
            
            sum_p = f"囲碁インストラクター。大人級位者への総評（600-1000文字）。データ: {all_m}"
            sum_resp = self.gemini_client.models.generate_content(model='gemini-3-flash-preview', contents=sum_p)
            r_md += f"## 総評\n\n{sum_resp.text}\n"
            
            with open(os.path.join(r_dir, "report.md"), "w", encoding="utf-8") as f:
                f.write(r_md)
            
            self.root.after(0, lambda: messagebox.showinfo("Done", f"Report saved in {r_dir}"))
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", err_msg))
        finally:
            self.root.after(0, lambda: self.btn_report.config(state="normal", text="対局レポートを生成"))

    def prev_move(self):
        if self.current_move > 0: self.show_image(self.current_move - 1)
    def next_move(self):
        if self.image_dir and self.current_move < self.total_moves_in_dir - 1: self.show_image(self.current_move + 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()

if __name__ == "__main__":
    root = tk.Tk()
    app = GoReplayApp(root)
    root.mainloop()