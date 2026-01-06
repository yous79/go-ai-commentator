import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import threading
import queue
import subprocess
import json

from config import SRC_DIR, OUTPUT_BASE_DIR, KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL, API_KEY_PATH, load_api_key
from game_state import GoGameState
from board_renderer import GoBoardRenderer
from ai_engine import GeminiCommentator
from katago_driver import KataGoDriver
from analyze_sgf import BoardRenderer as ReportRenderer

# For subprocess call, we point to analyze_sgf.py in the same src directory
ANALYZE_SCRIPT = os.path.join(SRC_DIR, "analyze_sgf.py")

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Analysis Agent (Refactored)")
        self.root.geometry("1200x950")

        # Logic Modules
        self.game = GoGameState()
        self.renderer = GoBoardRenderer()
        self.katago_driver = None
        self.gemini = None
        
        self._init_ai()

        # UI State
        self.current_move = 0
        self.image_cache = {}
        self.analyzing = False
        self.process = None
        self.queue = queue.Queue()
        self.review_mode = tk.BooleanVar(value=False)
        self.edit_mode = tk.BooleanVar(value=False)
        self.current_sgf_name = None
        self.image_dir = None

        self.setup_layout()
        self.check_queue()
        
        # Bindings
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.click_on_board)

    def _init_ai(self):
        api_key = load_api_key()
        if api_key and os.path.exists(KATAGO_EXE):
            try:
                self.katago_driver = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
                self.gemini = GeminiCommentator(api_key, self.katago_driver)
                print("AI Modules Initialized.")
            except Exception as e:
                print(f"AI Init Failed: {e}")

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

        # Top Bar
        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_bar = ttk.Progressbar(top_frame, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_status = tk.Label(top_frame, text="Idle", width=30, bg="#ddd")
        self.lbl_status.pack(side=tk.RIGHT, padx=10)

        # Paned Window
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")
        
        # Board Area
        self.board_frame = tk.Frame(self.paned, bg="#333")
        self.paned.add(self.board_frame, width=600)
        self.canvas = tk.Canvas(self.board_frame, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Info Area
        self.info_frame = tk.Frame(self.paned, bg="#f0f0f0", width=600)
        self.paned.add(self.info_frame)
        
        self._setup_info_panel()
        self._setup_bottom_bar()

    def _setup_info_panel(self):
        tk.Label(self.info_frame, text="Analysis Info", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        self.lbl_winrate = tk.Label(self.info_frame, text="Winrate (Black): --%", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w", padx=20)
        self.lbl_score = tk.Label(self.info_frame, text="Score: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w", padx=20)

        tk.Checkbutton(self.info_frame, text="Review Mode", variable=self.review_mode, command=self.update_display, bg="#f0f0f0").pack()
        tk.Checkbutton(self.info_frame, text="Edit Mode", variable=self.edit_mode, bg="#f0f0f0").pack()
        
        tk.Button(self.info_frame, text="Show Future Sequence (PV)", command=self.show_pv, bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(pady=5, fill=tk.X, padx=20)

        # AI Section
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=5)
        tk.Label(self.info_frame, text="AI Commentary", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=2)
        
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

    def _setup_bottom_bar(self):
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
            self.start_analysis(p)

    def start_analysis(self, path):
        self.current_move = 0
        self.image_cache = {}
        try:
            self.game.load_sgf(path) # Use new GameState logic
            # Re-initialize renderer with correct board size
            self.renderer = GoBoardRenderer(board_size=self.game.board_size)
        except Exception as e:
            messagebox.showerror("Error", f"SGFを読み込めません: {e}")
            print(f"SGF Load Error: {e}")
            return

        self.current_sgf_name = os.path.splitext(os.path.basename(path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name)
        
        if self.process:
            try: self.process.terminate()
            except: pass
            
        self.analyzing = True
        # Reuse existing analyze_sgf.py for background image generation
        # Ideally, this should also be moved to a thread calling GameState + Renderer, 
        # but for now we keep the subprocess to avoid main thread blocking.
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
                    if self.process.poll() is not None: break
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
        # We load json from disk because the background process writes it.
        # Ideally, GameState should handle this sync.
        p = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    d = json.load(f)
                if isinstance(d, list):
                    self.game.moves = d
                else:
                    self.game.moves = d.get("moves", [])
                
                # Use GameState to calculate mistakes
                mb, mw = self.game.calculate_mistakes()
                
                # Update UI buttons
                for i in range(3):
                    self._upd_m_btn(self.btn_m_b[i], self.moves_m_b, i, mb)
                    self._upd_m_btn(self.btn_m_w[i], self.moves_m_w, i, mw)
                
                self.update_display()
            except:
                pass

    def _upd_m_btn(self, btn, store, idx, drops):
        if idx < len(drops):
            drop, m = drops[idx]
            store[idx] = m
            btn.config(text=f"#{m}: -{drop:.1%}", state="normal")
        else:
            store[idx] = None
            btn.config(text="-", state="disabled")

    def monitor_images(self):
        if not self.image_dir: return
        import glob
        files = glob.glob(os.path.join(self.image_dir, "move_*.png"))
        if len(files) > 0 and not self.image_cache:
            self.show_image(0)
        if self.analyzing:
            self.load_analysis_data()
            self.root.after(2000, self.monitor_images)

    def show_image(self, n):
        p = os.path.join(self.image_dir, f"move_{n:03d}.png")
        if os.path.exists(p) and n not in self.image_cache:
            self.image_cache[n] = Image.open(p)
        self.current_move = n
        self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache: return
        
        # Logic to get info
        moves = self.game.moves
        wr_d, sc, cands = "--%", "--", []
        if moves and self.current_move < len(moves):
            d = moves[self.current_move]
            # Adjust perspective logic if needed, similar to before
            wr_raw = d.get('winrate', 0.5)
            wr_black = (1.0 - wr_raw) if (self.current_move % 2 != 0) else wr_raw
            wr_d = f"{wr_black:.1%}"
            sc = f"{d.get('score', 0):.1f}"
            cands = d.get('candidates', [])
        
        self.lbl_winrate.config(text=f"Winrate (Black): {wr_d}")
        self.lbl_score.config(text=f"Score: {sc}")
        self.lbl_counter.config(text=f"{self.current_move} / {self.game.total_moves}")
        
        # Draw Board Image
        cw, ch = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        img = self.image_cache[self.current_move]
        ratio = min(cw / img.size[0], ch / img.size[1])
        nw, nh = int(img.size[0] * ratio), int(img.size[1] * ratio)
        
        res = img.resize((nw, nh), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(res)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo
        
        # Draw Overlays
        if self.review_mode.get() and cands:
            # We need coordinate conversion logic here.
            # For simplicity, reusing the old logic but should be in Renderer ideally
            ox, oy = (cw - nw)//2, (ch - nh)//2
            self._draw_overlays(cands, nw, nh, ox, oy)

    def _draw_overlays(self, cands, nw, nh, ox, oy):
        br = 850 / 950 # Aspect ratio fix from original code?
        sz = self.game.board_size
        m, b_size = 70, 850
        step = (b_size - 2*m) / (sz-1)
        
        for i, c in enumerate(cands[:3]):
            move_str = c['move']
            if not move_str or move_str.lower()=="pass": continue
            col = "ABCDEFGHJKLMNOPQRST".find(move_str[0].upper())
            try: row = int(move_str[1:]) - 1
            except: continue
            
            # Coord to normalized
            vr = sz - 1 - row
            nx = (m + col * step) / b_size
            ny = (m + vr * step) / b_size
            
            fx, fy = ox + nw * nx, oy + (nh * br) * ny
            rad = (nw / 19) * 0.6
            color = "#00ff00" if i == 0 else "#00aaff"
            self.canvas.create_oval(fx-rad, fy-rad, fx+rad, fy+rad, fill=color, outline=color, tags="overlay")
            self.canvas.create_text(fx, fy, text=f"{c.get('winrate',0):.0%}", fill="black", font=("Arial", int(rad), "bold"), tags="overlay")

    def generate_commentary(self):
        if not self.gemini: return
        self.btn_comment.config(state="disabled", text="Thinking...")
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, "Consulting AI...")
        threading.Thread(target=self._run_agent_task, daemon=True).start()

    def _run_agent_task(self):
        try:
            # Get history from GameState
            h = self.game.get_history_up_to(self.current_move)
            
            # Delegate to AI Engine
            text = self.gemini.generate_commentary(self.current_move, h, self.game.board_size)
            
            self.root.after(0, lambda: self._update_comment_ui(text))
        except Exception as e:
            self.root.after(0, lambda: self._update_comment_ui(f"Error: {e}"))

    def _update_comment_ui(self, text):
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, text)
        self.btn_comment.config(state="normal", text="Ask KataGo Agent")
        
        if self.gemini.last_pv:
            self.btn_agent_pv.config(state="normal")
        else:
            self.btn_agent_pv.config(state="disabled")

    def show_agent_pv(self):
        if self.gemini and self.gemini.last_pv:
            self._show_pv_window("Agent Reference", self.gemini.last_pv)

    def show_pv(self):
        moves = self.game.moves
        if self.current_move < len(moves):
            d = moves[self.current_move]
            cands = d.get('candidates', [])
            if cands and 'pv' in cands[0]:
                self._show_pv_window("Future Sequence", cands[0]['pv'])
            else:
                messagebox.showinfo("Info", "No variation data.")

    def _show_pv_window(self, title, pv_list):
        top = tk.Toplevel(self.root)
        top.title(f"{title}")
        top.geometry("750x800")
        cv = tk.Canvas(top, bg="#333")
        cv.pack(fill=tk.BOTH, expand=True)
        
        # Use Renderer to generate PV image
        board = self.game.get_board_at(self.current_move)
        start_color = "W" if (self.current_move % 2 != 0) else "B"
        
        # Need to convert pv_list (strings) to something Renderer might need? 
        # Renderer.render_pv takes string list directly.
        
        img = self.renderer.render_pv(board, pv_list, start_color, title=title)
        
        photo = ImageTk.PhotoImage(img)
        cv.create_image(0, 0, image=photo, anchor=tk.NW, tags="pv_img")
        cv.image = photo # Keep ref

    def prev_move(self):
        if self.current_move > 0: self.show_image(self.current_move - 1)
    def next_move(self):
        if self.current_move < self.game.total_moves - 1: self.show_image(self.current_move + 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()
    
    # Placeholder for interactive clicks - implementation similar to original but using GameState
    def click_on_board(self, event):
        pass # To be reimplemented cleanly
    def goto_mistake(self, c, i):
        m = self.moves_m_b[i] if c == "b" else self.moves_m_w[i]
        if m: self.show_image(m)
