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
from google import genai
from google.genai import types
from sgfmill import sgf
from katago_driver import KataGoDriver

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYZE_SCRIPT = os.path.join(SCRIPT_DIR, "analyze_sgf.py")
OUTPUT_BASE_DIR = os.path.join(SCRIPT_DIR, "output_images")

# KataGo Paths
BASE_DIR = os.path.join(SCRIPT_DIR, "katago", "2023-06-15-windows64+katago")
KATAGO_EXE = os.path.join(BASE_DIR, "katago_opencl", "katago.exe")
CONFIG = os.path.join(BASE_DIR, "katago_configs", "analysis.cfg")
MODEL = os.path.join(BASE_DIR, "weights", "kata20bs530.bin.gz")

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Replay & Analysis (Latest SDK)")
        self.root.geometry("1100x900")

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
        self.review_mode = tk.BooleanVar(value=False)
        self.gemini_client = None
        self.katago_agent = None 
        self.agent_last_pv = None # To store PV from the last agent analysis
        
        self.setup_gemini()
        self.setup_layout()
        
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        
        self.check_queue()

    def setup_gemini(self):
        key_path = os.path.join(SCRIPT_DIR, "api_key.txt")
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    api_key = f.read().strip()
                
                # New SDK Client
                self.gemini_client = genai.Client(api_key=api_key)
                
                # Initialize KataGo Driver
                self.katago_agent = KataGoDriver(KATAGO_EXE, CONFIG, MODEL)
                
                print("DEBUG: Gemini Client (New SDK) configured.")
            except Exception as e:
                print(f"Gemini Init Error: {e}")

    # Tool definition for new SDK
    def consult_katago_tool(self, moves_list: list[list[str]]):
        """
        Consults the KataGo Go engine to analyze the current board position.

        Args:
            moves_list: A list of moves played so far. Each move is a list containing two strings: the color ("B" or "W") and the coordinate (e.g. "Q16").
        """
        # Get actual board size from the loaded game data
        board_size = self.analysis_data.get("board_size", 19)
        print(f"DEBUG: Tool called for {board_size}x{board_size} board.")
        result = self.katago_agent.analyze_situation(moves_list, board_size=board_size)
        
        # CAPTURE PV IMMEDIATELY HERE
        if 'top_candidates' in result and len(result['top_candidates']) > 0:
            pv = result['top_candidates'][0].get('future_sequence', "")
            if pv:
                self.agent_last_pv = [m.strip() for m in pv.split("->")]
                print(f"DEBUG: PV captured inside tool: {self.agent_last_pv}")
        
        return result

    def setup_layout(self):
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)
        self.root.columnconfigure(0, weight=1)

        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open SGF...", command=self.open_sgf)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # Top
        top_frame = tk.Frame(self.root, pady=5, bg="#ddd")
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(top_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_progress_text = tk.Label(top_frame, text="Idle", width=25, anchor="w", bg="#ddd")
        self.lbl_progress_text.pack(side=tk.RIGHT, padx=10)

        # Middle
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")

        self.board_frame = tk.Frame(self.paned, bg="#333")
        self.paned.add(self.board_frame, width=550)
        self.canvas = tk.Canvas(self.board_frame, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.info_frame = tk.Frame(self.paned, bg="#f0f0f0", width=550)
        self.paned.add(self.info_frame)

        tk.Label(self.info_frame, text="Analysis Info", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        self.lbl_data_status = tk.Label(self.info_frame, text="Data: Not Loaded", fg="red", bg="#f0f0f0")
        self.lbl_data_status.pack(pady=2)
        self.lbl_winrate = tk.Label(self.info_frame, text="Winrate: --%", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w", padx=20)
        self.lbl_score = tk.Label(self.info_frame, text="Score: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w", padx=20)

        tk.Checkbutton(self.info_frame, text="Review Mode (Show Candidates)", variable=self.review_mode, command=self.update_display, font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        
        tk.Button(self.info_frame, text="Show Future Sequence (PV)", command=self.show_pv, bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(pady=5, fill=tk.X, padx=10)

        # Commentary
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=5)
        tk.Label(self.info_frame, text="AI Commentary (New SDK Agent)", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=2)
        
        self.btn_comment = tk.Button(self.info_frame, text="Ask KataGo Agent", command=self.generate_commentary, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_comment.pack(pady=5, fill=tk.X, padx=10)
        
        self.btn_full_report = tk.Button(self.info_frame, text="対局レポートを生成 (Markdown)", command=self.generate_full_report, bg="#9C27B0", fg="white", font=("Arial", 10, "bold"))
        self.btn_full_report.pack(pady=5, fill=tk.X, padx=10)
        
        comm_container = tk.Frame(self.info_frame, bg="#f0f0f0")
        comm_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
        comm_scroll = tk.Scrollbar(comm_container)
        comm_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_commentary = tk.Text(comm_container, height=12, width=30, wrap=tk.WORD, font=("Arial", 10), yscrollcommand=comm_scroll.set)
        self.txt_commentary.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        comm_scroll.config(command=self.txt_commentary.yview)

        self.btn_agent_pv = tk.Button(self.info_frame, text="エージェントの想定図を表示", command=self.show_agent_pv, state="disabled", bg="#FF9800", fg="white", font=("Arial", 10, "bold"))
        self.btn_agent_pv.pack(pady=5, fill=tk.X, padx=10)

        # Mistakes (Bottom of Right Panel)
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self.info_frame, text="Top 3 Mistakes", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        self.mistakes_frame = tk.Frame(self.info_frame, bg="#f0f0f0")
        self.mistakes_frame.pack(fill=tk.X, padx=5, pady=5)
        self.mistakes_frame.columnconfigure(0, weight=1); self.mistakes_frame.columnconfigure(1, weight=1)
        tk.Label(self.mistakes_frame, text="Black", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=0, column=0)
        tk.Label(self.mistakes_frame, text="White", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=0, column=1)
        self.btn_mistakes_b = []; self.btn_mistakes_w = []
        for i in range(3):
            b = tk.Button(self.mistakes_frame, text="-", command=lambda x=i: self.goto_mistake("b", x), bg="#ffcccc", font=("Arial", 9))
            b.grid(row=i+1, column=0, sticky="ew", padx=2, pady=2); self.btn_mistakes_b.append(b)
            w = tk.Button(self.mistakes_frame, text="-", command=lambda x=i: self.goto_mistake("w", x), bg="#ffcccc", font=("Arial", 9))
            w.grid(row=i+1, column=1, sticky="ew", padx=2, pady=2); self.btn_mistakes_w.append(w)
        self.mistake_moves_b = [None]*3; self.mistake_moves_w = [None]*3

        # Bottom
        self.bottom_frame = tk.Frame(self.root, pady=10, bg="#e0e0e0", height=60)
        self.bottom_frame.grid(row=2, column=0, sticky="ew"); self.bottom_frame.grid_propagate(False)
        self.bottom_frame.columnconfigure(0, weight=1); self.bottom_frame.columnconfigure(1, weight=0)
        self.bottom_frame.columnconfigure(2, weight=0); self.bottom_frame.columnconfigure(3, weight=0)
        self.bottom_frame.columnconfigure(4, weight=1)
        tk.Button(self.bottom_frame, text="< Prev", command=self.prev_move, width=15).grid(row=0, column=1, padx=10)
        self.lbl_counter = tk.Label(self.bottom_frame, text="0 / 0", font=("Arial", 12, "bold"), bg="#e0e0e0")
        self.lbl_counter.grid(row=0, column=2, padx=20)
        tk.Button(self.bottom_frame, text="Next >", command=self.next_move, width=15).grid(row=0, column=3, padx=10)

    def open_sgf(self):
        p = filedialog.askopenfilename(initialdir=SCRIPT_DIR, filetypes=[("SGF Files", "*.sgf")])
        if p: self.current_sgf_path = p; self.start_analysis(p)

    def start_analysis(self, sgf_path):
        self.current_move = 0; self.image_cache = {}; self.analysis_data = {"board_size": 19, "moves": []}
        self.analyzing = True; self.current_sgf_name = os.path.splitext(os.path.basename(sgf_path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name); self.progress_var.set(0)
        self.lbl_data_status.config(text="Data: Initializing...", fg="orange")
        self.txt_commentary.delete(1.0, tk.END); self.txt_commentary.insert(tk.END, "Analyzing...")
        if self.process and self.process.poll() is None: self.process.terminate()
        threading.Thread(target=self.run_analysis_script, args=(sgf_path,), daemon=True).start()
        self.monitor_images()

    def run_analysis_script(self, sgf_path):
        env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"; env["PYTHONIOENCODING"] = "utf-8"
        cmd = ["python", "-u", ANALYZE_SCRIPT, sgf_path]
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Use PIPE for both stdout and stderr separately
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, bufsize=1, startupinfo=startupinfo,
                                          encoding='utf-8', errors='replace', env=env)
            
            # Read stdout in a loop
            while True:
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None: break
                    continue
                line = line.strip()
                if not line: continue
                
                print(f"SCRIPT_OUT: {line}") # Console debug
                
                if line.startswith("Total Moves:"):
                    self.queue.put(("set_max", int(line.split(":")[1].strip())))
                elif line.startswith("Analyzing Move"):
                    try: self.queue.put(("progress", int(line.split("Move")[1].strip())))
                    except: pass
            
            # Process finished. Check return code and stderr.
            ret = self.process.poll()
            stderr_output = self.process.stderr.read()
            
            if stderr_output:
                print(f"SCRIPT_ERR: {stderr_output}")
                self.queue.put(("error", stderr_output))
            
            if ret != 0:
                self.queue.put(("error", f"Process exited with code {ret}"))
            else:
                self.analyzing = False
                self.queue.put(("done", None))
                
        except Exception as e:
            self.queue.put(("error", str(e)))
            self.analyzing = False

    def check_queue(self):
        try:
            while True:
                msg, data = self.queue.get_nowait()
                if msg == "set_max": self.progress_bar.config(maximum=data); self.lbl_progress_text.config(text=f"Analyzing... (Total: {data})")
                elif msg == "progress": self.progress_var.set(data); self.lbl_progress_text.config(text=f"Analyzing: {data} / {int(self.progress_bar['maximum'])}")
                elif msg == "done": self.lbl_progress_text.config(text="Analysis Complete"); self.progress_var.set(self.progress_bar['maximum']); self.load_analysis_data()
                elif msg == "error": self.lbl_progress_text.config(text=f"Error: {data[:20]}...", fg="red")
        except queue.Empty: pass
        self.root.after(100, self.check_queue)

    def load_analysis_data(self):
        json_path = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f: 
                    d = json.load(f)
                    self.analysis_data = {"board_size": 19, "moves": d} if isinstance(d, list) else d
                self.lbl_data_status.config(text=f"Data: Loaded ({len(self.analysis_data.get('moves', []))} moves)", fg="green"); self.calculate_mistakes()
            except: self.lbl_data_status.config(text="Data: Error Loading", fg="red")

    def calculate_mistakes(self):
        moves = self.analysis_data.get("moves", [])
        if len(moves) < 2: return
        drops_b, drops_w = [], []
        for i in range(1, len(moves)):
            prev, curr = moves[i-1], moves[i]
            drop = prev.get('winrate', 0.5) - (1.0 - curr.get('winrate', 0.5))
            if drop > 0.001:
                if i % 2 != 0: drops_b.append((drop, i))
                else: drops_w.append((drop, i))
        drops_b.sort(key=lambda x: x[0], reverse=True); drops_w.sort(key=lambda x: x[0], reverse=True)
        for idx in range(3):
            self._update_m_btn(self.btn_mistakes_b[idx], self.mistake_moves_b, idx, drops_b)
            self._update_m_btn(self.btn_mistakes_w[idx], self.mistake_moves_w, idx, drops_w)

    def _update_m_btn(self, btn, store, idx, drops):
        if idx < len(drops): drop, m = drops[idx]; store[idx] = m; btn.config(text=f"#{m}: -{drop:.1%}", state="normal")
        else: store[idx] = None; btn.config(text="-", state="disabled")

    def goto_mistake(self, color, idx):
        m = self.mistake_moves_b[idx] if color == "b" else self.mistake_moves_w[idx]
        if m is not None: self.show_image(m)

    def monitor_images(self):
        if not self.image_dir: return
        files = sorted(glob.glob(os.path.join(self.image_dir, "move_*.png"))); self.total_moves_in_dir = len(files)
        self.lbl_counter.config(text=f"{self.current_move} / {max(0, self.total_moves_in_dir - 1)}")
        if self.analyzing: self.load_analysis_data()
        if self.total_moves_in_dir > 0 and not self.image_cache: self.show_image(0)
        if self.total_moves_in_dir > 0 and len(self.canvas.find_all()) == 0: self.show_image(self.current_move)
        if self.analyzing: self.root.after(2000, self.monitor_images)

    def gtp_to_coords(self, gtp_vertex):
        if not gtp_vertex or gtp_vertex.lower() == "pass": return None
        cols = "ABCDEFGHJKLMNOPQRST"; col = cols.find(gtp_vertex[0].upper())
        if col == -1: return None
        try: row = int(gtp_vertex[1:]) - 1
        except: return None
        return row, col

    def get_canvas_coords(self, r, c):
        sz = self.analysis_data.get("board_size", 19); m, b = 50, 800
        step = (b - 2 * m) / (sz - 1); vr = sz - 1 - r
        return (m + c * step) / b, (m + vr * step) / b

    def show_image(self, move_num):
        path = os.path.join(self.image_dir, f"move_{move_num:03d}.png")
        if os.path.exists(path) and move_num not in self.image_cache:
            try: self.image_cache[move_num] = Image.open(path)
            except: return
        self.current_move = move_num; self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache: return
        winrate, score, candidates = "--%", "--", []
        moves = self.analysis_data.get("moves", [])
        if moves and self.current_move < len(moves):
            d = moves[self.current_move]; winrate, score, candidates = f"{d.get('winrate', 0):.1%}", f"{d.get('score', 0):.1f}", d.get('candidates', [])
        self.lbl_winrate.config(text=f"Winrate: {winrate}"); self.lbl_score.config(text=f"Score: {score}"); self.lbl_counter.config(text=f"{self.current_move} / {max(0, self.total_moves_in_dir - 1)}")
        canvas_w, canvas_h = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        orig = self.image_cache[self.current_move]; iw, ih = orig.size
        ratio = min(canvas_w / iw, canvas_h / ih); nw, nh = int(iw * ratio), int(ih * ratio)
        resized = orig.resize((nw, nh), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(resized)
        self.canvas.delete("all"); cx, cy = canvas_w // 2, canvas_h // 2; self.canvas.create_image(cx, cy, image=photo, anchor=tk.CENTER); self.canvas.image = photo
        if self.review_mode.get() and candidates:
            ox, oy = cx - nw // 2, cy - nh // 2; br = 800 / 900
            for i, cand in enumerate(candidates[:3]):
                coords = self.gtp_to_coords(cand['move'])
                if coords:
                    nx, ny = self.get_canvas_coords(coords[0], coords[1]); fx, fy = ox + nw * nx, oy + (nh * br) * ny
                    rad = (nw / 19) * 0.6; color = "#00ff00" if i == 0 else "#00aaff"
                    self.canvas.create_oval(fx-rad, fy-rad, fx+rad, fy+rad, outline=color, width=3, fill=color, tags="overlay")
                    self.canvas.create_text(fx, fy, text=f"{cand['winrate']:.0%}", fill="black", font=("Arial", int(rad), "bold"), tags="overlay")

    def _draw_centered_text(self, draw, x, y, text, font, fill):
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            w, h = right - left, bottom - top
            draw.text((x - w / 2, y - h / 2 - top), text, font=font, fill=fill)
        except AttributeError:
            w, h = draw.textsize(text, font=font)
            draw.text((x - w / 2, y - h / 2), text, font=font, fill=fill)

    def show_agent_pv(self):
        if self.agent_last_pv: self._render_pv_window("Agent's Reference Diagram", self.agent_last_pv)

    def _render_pv_window(self, title, pv_list):
        idx = self.current_move
        sz = self.analysis_data.get("board_size", 19)
        
        top = tk.Toplevel(self.root); top.title(f"{title} (Move {idx})"); top.geometry("700x750")
        cv = tk.Canvas(top, bg="#333"); cv.pack(fill=tk.BOTH, expand=True)
        
        if idx not in self.image_cache: return
        base = self.image_cache[idx].copy(); draw = ImageDraw.Draw(base)
        
        # Geometry: Match analyze_sgf.py 850px image, 70px margin
        m, b_w = 70, 850
        # Dynamic step calculation based on actual board size
        step = (b_w - 2 * m) / (sz - 1)
        
        # Coordinates (Draw only for the current board size)
        try: coord_font = ImageFont.truetype("arial.ttf", 20)
        except: coord_font = ImageFont.load_default()
        cols = "ABCDEFGHJKLMNOPQRST"
        
        for i in range(sz):
            x = m + i * step
            y = m + i * step
            # Letters
            self._draw_centered_text(draw, x, m - 35, cols[i], coord_font, "black")
            self._draw_centered_text(draw, x, m + (sz-1)*step + 35, cols[i], coord_font, "black")
            # Numbers
            self._draw_centered_text(draw, m - 35, y, str(sz - i), coord_font, "black")
            self._draw_centered_text(draw, m + (sz-1)*step + 35, y, str(sz - i), coord_font, "black")

        color = "W" if (idx % 2 != 0) else "B"
        for i, m_str in enumerate(pv_list[:10]): # Limit to 10 moves
            coords = self.gtp_to_coords(m_str)
            if coords:
                r, c = coords
                # Correct placement calculation for any board size
                px, py = m + c * step, m + (sz - 1 - r) * step
                
                fill, txt_c = ("white", "black") if color == "W" else ("black", "white")
                rad = step * 0.45; draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill, outline=txt_c)
                
                f_sz = int(rad * 1.1) if len(str(i+1)) == 1 else int(rad * 0.9)
                try: font = ImageFont.truetype("arial.ttf", f_sz)
                except: font = ImageFont.load_default()
                self._draw_centered_text(draw, px, py, str(i+1), font, txt_c)
                color = "B" if color == "W" else "W"
        photo = ImageTk.PhotoImage(base); cv.create_image(0, 0, image=photo, anchor=tk.NW, tags="pv_img"); cv.image = photo
        def on_res(e):
            if e.width < 100: return
            res = base.resize((e.width, e.height), Image.Resampling.LANCZOS); p = ImageTk.PhotoImage(res); cv.delete("pv_img"); cv.create_image(0, 0, image=p, anchor=tk.NW, tags="pv_img"); cv.image = p
        cv.bind("<Configure>", on_res)

    def show_pv(self):
        idx = self.current_move; moves = self.analysis_data.get("moves", [])
        if idx >= len(moves): return
        data = moves[idx]; cands = data.get('candidates', [])
        if not cands or 'pv' not in cands[0]: messagebox.showinfo("Info", "No variation data."); return
        self._render_pv_window("Future Sequence", cands[0]['pv'])

    def next_move(self):
        if self.image_dir and self.current_move < self.total_moves_in_dir - 1: self.show_image(self.current_move + 1)
    def prev_move(self):
        if self.image_dir and self.current_move > 0: self.show_image(self.current_move - 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()

    def generate_commentary(self):
        if not self.gemini_client: messagebox.showwarning("API Key", "API key missing."); return
        if not self.current_sgf_path: return
        self.btn_comment.config(state="disabled", text="Agent Thinking...")
        self.txt_commentary.delete(1.0, tk.END); self.txt_commentary.insert(tk.END, "Consulting KataGo via New SDK...\n")
        threading.Thread(target=self._run_agent_task, args=(self.current_move,), daemon=True).start()

    def _run_agent_task(self, move_idx):
        try:
            with open(self.current_sgf_path, "rb") as f: game = sgf.Sgf_game.from_bytes(f.read())
            board_size = game.get_size()
            history = []; node = game.get_root(); count = 0
            while count < move_idx:
                try:
                    node = node[0]; count += 1; color, move = node.get_move()
                    if color:
                        if move: history.append(["B" if color == "b" else "W", "ABCDEFGHJKLMNOPQRST"[move[1]] + str(move[0] + 1)])
                        else: history.append(["B" if color == "b" else "W", "pass"])
                except IndexError: break
            
            # Initial Prompt with Board Size
            initial_prompt = f"I am at move {move_idx} of a {board_size}x{board_size} Go game. History: {history}. Use 'consult_katago_tool' to analyze this exact position."
            
            # Prepare contents for chat-like interaction
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=initial_prompt)])]
            
            config = types.GenerateContentConfig(
                tools=[self.consult_katago_tool],
                system_instruction=f"あなたはプロの囲碁棋士です。現在は {board_size}路盤の対局を解説しています。盤面の状況を正確に把握するために、必ず 'consult_katago_tool' を使用して分析データを取得してください。{board_size}路盤特有の戦略を踏まえて、日本語で論理的な解説を作成してください。自分の推測だけで答えてはいけません。"
            )

            print("DEBUG: Agent sending initial request...")
            # Turn 1: Send prompt
            response = self.gemini_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=contents,
                config=config
            )

            # Handle Tool Calls (Simple Loop)
            final_text = "解析結果を取得できませんでした。"
            
            # Loop to handle function calls (max 5 turns)
            for turn in range(5):
                print(f"DEBUG: Agent Turn {turn+1} response check...")
                
                # If we have text, we are done
                if response.text:
                    final_text = response.text
                    print(f"DEBUG: Agent produced text: {final_text[:50]}...")
                    if not response.function_calls:
                        break
                
                # Check for function calls
                if response.function_calls:
                    print(f"DEBUG: Agent calling tool (Turn {turn+1})")
                    contents.append(response.candidates[0].content)
                    
                    tool_outputs = []
                    for call in response.function_calls:
                        if call.name == "consult_katago_tool":
                            moves_arg = call.args.get('moves_list')
                            print(f"DEBUG: Consulting KataGo with moves: {moves_arg}")
                            result = self.consult_katago_tool(moves_arg)
                            
                            # CAPTURE PV FOR BUTTON
                            if 'top_candidates' in result and len(result['top_candidates']) > 0:
                                best = result['top_candidates'][0]
                                pv = best.get('future_sequence', "")
                                print(f"DEBUG: Found best candidate: {best.get('move')} with PV: {pv}")
                                if pv:
                                    # Split "Q16 -> D4" into ["Q16", "D4"]
                                    self.agent_last_pv = [m.strip() for m in pv.split("->")]
                                    print(f"DEBUG: Stored PV list for visualization: {self.agent_last_pv}")
                            else:
                                print("DEBUG: Tool result contained no candidates.")
                            
                            tool_outputs.append(types.Part.from_function_response(
                                name=call.name,
                                response={'result': result}
                            ))
                    
                    if tool_outputs:
                        contents.append(types.Content(role="user", parts=tool_outputs))
                        response = self.gemini_client.models.generate_content(
                            model='gemini-3-flash-preview',
                            contents=contents,
                            config=config
                        )
                    else:
                        break
                else:
                    break


            self.root.after(0, lambda: self.update_commentary_ui(final_text))
            
        except Exception as e:
            err = str(e)
            print(f"Agent Loop Error: {err}")
            self.root.after(0, lambda: self.update_commentary_ui(f"Agent Error: {err}"))

    def generate_full_report(self):
        if not self.gemini_client or not self.current_sgf_path:
            messagebox.showwarning("Error", "SGFをロードし、Geminiを設定してください。")
            return

        self.btn_full_report.config(state="disabled", text="Generating Report...")
        threading.Thread(target=self._run_report_task, daemon=True).start()

    def _run_report_task(self):
        try:
            # 1. Gather mistakes
            self.load_analysis_data()
            moves = self.analysis_data.get("moves", [])
            if not moves: return

            drops = []
            for i in range(1, len(moves)):
                drop = moves[i-1].get('winrate', 0.5) - (1.0 - moves[i].get('winrate', 0.5))
                if drop > 0.05: drops.append((drop, i))
            
            # Top 3 for each color
            drops_b = sorted([d for d in drops if d[1] % 2 != 0], key=lambda x: x[0], reverse=True)[:3]
            drops_w = sorted([d for d in drops if d[1] % 2 == 0], key=lambda x: x[0], reverse=True)[:3]
            all_mistakes = sorted(drops_b + drops_w, key=lambda x: x[1])

            report_md = f"# 対局レポート: {self.current_sgf_name}\n\n"
            report_md += f"生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            report_md += "## 悪手分析 (Top Mistakes)\n\n"

            # Create report directory
            report_dir = os.path.join(self.image_dir, "report")
            os.makedirs(report_dir, exist_ok=True)

            # Reconstruct board state for each mistake
            with open(self.current_sgf_path, "rb") as f: game = sgf.Sgf_game.from_bytes(f.read())
            board_size = game.get_size()
            from analyze_sgf import BoardRenderer, boards # Import from analyze_sgf
            renderer = BoardRenderer(board_size)

            for drop, m_idx in all_mistakes:
                # Get moves up to m_idx
                history = []; node = game.get_root(); temp_board = boards.Board(board_size)
                for _ in range(m_idx - 1):
                    node = node[0]; c, m = node.get_move()
                    if c:
                        if m: temp_board.play(m[0], m[1], c); history.append(["B" if c == 'b' else "W", "ABCDEFGHJKLMNOPQRST"[m[1]] + str(m[0] + 1)])
                        else: history.append(["B" if c == 'b' else "W", "pass"])
                
                # Get PV for this state
                print(f"DEBUG: Analyzing mistake at move {m_idx}...")
                result = self.katago_agent.analyze_situation(history, board_size=board_size)
                
                if 'top_candidates' in result and result['top_candidates']:
                    best = result['top_candidates'][0]
                    pv_str = best.get('future_sequence', "")
                    pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
                    
                    # Save reference diagram
                    color = "W" if (m_idx % 2 == 0) else "B"
                    pv_img = renderer.render_pv(temp_board, pv_list, color, title=f"Move {m_idx} Ref (Winrate Drop: {drop:.1%})")
                    img_filename = f"mistake_{m_idx:03d}_pv.png"
                    pv_img.save(os.path.join(report_dir, img_filename))

                    # Ask Gemini for commentary (Individual Mistake)
                    print(f"DEBUG: Requesting individual commentary for move {m_idx}...")
                    m_player = "黒" if m_idx % 2 != 0 else "白"
                    prompt = f"""
囲碁インストラクターとして、以下の局面の悪手分析を論理的に解説してください。
対象：強くなりたい大人の級位者

【データ】
- 手数: {m_idx}手目 ({m_player}番)
- 勝率下落: -{drop:.1%}
- AI推奨手: {best['move']}
- AIの読み筋: {pv_str}

【指示】
1. なぜ実戦の手が「疑問手」とされたのか、石の強弱や地の効率の観点から説明してください。
2. AIの推奨手「{best['move']}」にはどのような狙い（攻め、守り、根拠の確保など）がありますか？
3. 簡潔に150文字〜200文字程度で、丁寧かつ論理的な口調でお願いします。
"""
                    resp = self.gemini_client.models.generate_content(
                        model='gemini-3-flash-preview', 
                        contents=prompt
                    )
                    
                    report_md += f"### 手数 {m_idx} ({m_player}番)\n"
                    report_md += f"- **勝率下落**: -{drop:.1%}\n"
                    report_md += f"- **AI推奨**: {best['move']}\n\n"
                    report_md += f"![参考図]({img_filename})\n\n"
                    report_md += f"**解説**: {resp.text}\n\n"
                    report_md += "---\n\n"

            # --- Generate Overall Summary ---
            print("DEBUG: Generating Game Summary...")
            
            # Create a summary prompt with winrate flow
            # Sample critical points
            flow_data = []
            step = max(1, len(moves) // 10)
            for i in range(0, len(moves), step):
                m = moves[i]
                flow_data.append(f"手数{i}: 黒勝率 {m.get('winrate', 0.5):.1%}")
            
            summary_prompt = f"""
あなたは経験豊富な囲碁インストラクターです。この対局の「黒番（プレイヤー）」に向けた、上達のための詳細な総評を作成してください。
対象は、論理的な解説を好む大人の級位者です。子供向けの表現は避け、専門的かつ教育的な視点から記述してください。

【対局データ】
- 総手数: {len(moves)}手
- 碁盤サイズ: {self.analysis_data.get('board_size', 19)}路盤
- 黒番の勝率推移:
{chr(10).join(flow_data)}

【黒番の主な失着（勝負所）】
{chr(10).join([f"手数{m}: -{d:.1%}" for d, m in all_mistakes if m % 2 != 0][:5])}

【記述に関する厳格なルール】
1. **前置きは不要**: 「お疲れ様でした」「対局を振り返ります」などの挨拶や導入は一切省き、いきなりポイントの解説から始めてください。
2. **黒番目線**: 常に黒番の立場に立ち、黒の構想や判断の是非について論じてください。
3. **3つのポイント**: 解説を以下の3項目に整理し、見出し（###）を立てて記述してください。
    - **ポイント1：布石・序盤の構想と大局観**
      （序盤の石の方向性や勢力の築き方がどうだったか、大局的な視点から評価してください）
    - **ポイント2：中盤の攻防と勝負の分かれ目**
      （リストにある具体的な失着を取り上げ、その時どのような理屈で悪手となったのか、理詰めで解説してください）
    - **ポイント3：実力向上のための具体的な課題**
      （今回の対局から見える改善点について、次の一局から直ちに意識すべき技術的課題を提示してください）
4. **文字数**: 600文字〜1000文字。
5. **トーン**: 抽象的な表現を避け、「厚みが働いていない」「根拠を奪うべきだった」など、囲碁の理論に基づいた論理的なトーンで統一してください。
"""
            
            try:
                summary_resp = self.gemini_client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=summary_prompt
                )
                report_md += "## 総評 (Game Summary)\n\n"
                report_md += f"{summary_resp.text}\n\n"
            except Exception as e:
                print(f"Summary Error: {e}")
                report_md += "\n(総評の生成に失敗しました)\n"

            # Save Markdown
            with open(os.path.join(report_dir, "report.md"), "w", encoding="utf-8") as f:
                report_md = report_md.replace("\n", "\n") # Normalize
                f.write(report_md)

            print(f"Report generated in {report_dir}")
            self.root.after(0, lambda: messagebox.showinfo("Done", f"レポートを生成しました:\n{report_dir}"))
            
        except Exception as e:
            print(f"Report Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"レポート生成に失敗しました: {e}"))
        finally:
            self.root.after(0, lambda: self.btn_full_report.config(state="normal", text="対局レポートを生成 (Markdown)"))

    def update_commentary_ui(self, text):
        if text is None: text = ""
        text = str(text)
        self.txt_commentary.delete(1.0, tk.END); self.txt_commentary.insert(tk.END, text)
        self.btn_comment.config(state="normal", text="Ask KataGo Agent")
        
        # Explicitly enable/disable the Agent PV button
        if self.agent_last_pv:
            print(f"DEBUG: Enabling Agent PV button with {len(self.agent_last_pv)} moves.")
            self.btn_agent_pv.config(state="normal")
        else:
            print("DEBUG: Agent PV button remains disabled (no data).")
            self.btn_agent_pv.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk(); app = GoReplayApp(root); root.mainloop()