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
        comm_f.pack(fill=tk.BOTH, expand=False, padx=10) # Changed expand=True to False
        scr = tk.Scrollbar(comm_f)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_commentary = tk.Text(comm_f, height=8, wrap=tk.WORD, yscrollcommand=scr.set) # Slightly reduced height
        self.txt_commentary.pack(fill=tk.BOTH, expand=True)
        scr.config(command=self.txt_commentary.yview)
        
        self.btn_agent_pv = tk.Button(self.info_frame, text="エージェントの想定図を表示", command=self.show_agent_pv, state="disabled", bg="#FF9800", fg="white")
        self.btn_agent_pv.pack(pady=5, fill=tk.X, padx=20)
        self.btn_report = tk.Button(self.info_frame, text="対局レポートを生成", command=self.generate_full_report, bg="#9C27B0", fg="white")
        self.btn_report.pack(pady=5, fill=tk.X, padx=20)
        
        # Mistakes Section
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self.info_frame, text="Mistakes (Winrate Drop > 5%)", font=("Arial", 10, "bold"), bg="#f0f0f0").pack()
        
        m_frame = tk.Frame(self.info_frame, bg="#eee", bd=1, relief=tk.RIDGE)
        m_frame.pack(fill=tk.X, padx=10, pady=5)
        m_frame.columnconfigure(0, weight=1)
        m_frame.columnconfigure(1, weight=1)
        
        tk.Label(m_frame, text="Black", font=("Arial", 9, "bold"), bg="#333", fg="white").grid(row=0, column=0, sticky="ew")
        tk.Label(m_frame, text="White", font=("Arial", 9, "bold"), bg="#eee", fg="#333").grid(row=0, column=1, sticky="ew")
        
        self.btn_m_b = []
        self.btn_m_w = []
        for i in range(3):
            b = tk.Button(m_frame, text="-", command=lambda x=i: self.goto_mistake("b", x), bg="#ffcccc", font=("Arial", 8))
            b.grid(row=i+1, column=0, sticky="ew", padx=2, pady=1)
            self.btn_m_b.append(b)
            w = tk.Button(m_frame, text="-", command=lambda x=i: self.goto_mistake("w", x), bg="#ffcccc", font=("Arial", 8))
            w.grid(row=i+1, column=1, sticky="ew", padx=2, pady=1)
            self.btn_m_w.append(w)
        
        # Ensure m_frame itself is visible
        m_frame.pack(fill=tk.X, padx=5, pady=5)
        
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
        print(f"DEBUG: Starting background analysis script for: {path}")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # Also set PYTHONPATH to include src
        env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
        
        cmd = ["python", "-u", ANALYZE_SCRIPT, path]
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                bufsize=1, 
                env=env,
                encoding='utf-8',
                errors='replace'
            )
            while True:
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                print(f"ANALYZE_LOG: {line.strip()}") # Print log to console
                if "Total Moves:" in line:
                    self.queue.put(("set_max", int(line.split(":")[1])))
                if "Analyzing Move" in line:
                    self.queue.put(("progress", int(line.split("Move")[1])))
            
            # Check for errors in stderr
            stderr_out = self.process.stderr.read()
            if stderr_out:
                print(f"DEBUG ERROR from analyze_sgf: {stderr_out}")

            self.analyzing = False
            self.queue.put(("done", None))
        except Exception as e:
            print(f"DEBUG ERROR in run_analysis_script: {e}")
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

    def _upd_m_btn(self, btn, store, idx, mistakes):
        if idx < len(mistakes):
            sc_drop, wr_drop, m = mistakes[idx]
            if wr_drop > 0 or sc_drop > 0: # Show if either drop is positive
                store[idx] = m
                btn.config(text=f"#{m}: -{wr_drop:.1%} / -{sc_drop:.1f}目", state="normal")
                return
        
        # Default placeholder
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

    def generate_full_report(self):
        if not self.gemini or not self.game.sgf_path: return
        self.btn_report.config(state="disabled", text="Generating...")
        threading.Thread(target=self._run_report_task, daemon=True).start()

    def _run_report_task(self):
        import traceback
        print("DEBUG: Report generation started...")
        try:
            # 0. データのロードを確認
            self.load_analysis_data()
            print(f"DEBUG: Loaded {len(self.game.moves)} moves for analysis.")

            # 1. データの準備
            mb, mw = self.game.calculate_mistakes()
            print(f"DEBUG: Calculated mistakes - Black: {len(mb)}, White: {len(mw)}")
            
            if not mb:
                print("DEBUG: No significant mistakes found for Black.")
                self.root.after(0, lambda: messagebox.showinfo("Info", "黒番に顕著な悪手が見つかりませんでした。"))
                return

            # 黒番のミス上位3つのみをピックアップ
            all_m = sorted(mb, key=lambda x:x[0], reverse=True)[:3]
            all_m = sorted(all_m, key=lambda x:x[1]) # 手数順に並べ替え
            print(f"DEBUG: Targeting {len(all_m)} mistake points for Black's report.")

            r_dir = os.path.join(self.image_dir, "report")
            os.makedirs(r_dir, exist_ok=True)
            
            r_md = f"# 対局レポート (黒番視点): {self.current_sgf_name}\n\n"
            kn = self.gemini._load_knowledge() # AI Engineから知識ベースを取得
            print("DEBUG: Knowledge base loaded.")

            # 2. 各悪手の解析と画像生成
            from google.genai import types
            for i, (sc_drop, wr_drop, m_idx) in enumerate(all_m):
                print(f"DEBUG: Analyzing Black mistake {i+1}/{len(all_m)} (Move {m_idx}, score drop {sc_drop:.1f}, winrate drop {wr_drop:.1%})...")
                history = self.game.get_history_up_to(m_idx - 1)
                board = self.game.get_board_at(m_idx - 1)
                
                # KataGoで最善手を取得
                res = self.katago_driver.analyze_situation(history, board_size=self.game.board_size)
                if 'top_candidates' in res and res['top_candidates']:
                    best = res['top_candidates'][0]
                    pv_str = best.get('future_sequence', "")
                    pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
                    
                    # 変化図画像を保存
                    p_img = self.renderer.render_pv(board, pv_list, "B", title=f"Move {m_idx} Ref (-{wr_drop:.1%} / -{sc_drop:.1f}pts)")
                    f_name = f"mistake_{m_idx:03d}_pv.png"
                    p_img.save(os.path.join(r_dir, f_name))
                    print(f"DEBUG: Image saved: {f_name}")
                    
                    # Geminiによる個別解説生成
                    prompt = (
                        f"あなたはプロ棋士。手数: {m_idx}, プレイヤー: 黒, 勝率下落: {wr_drop:.1%}, 目数下落: {sc_drop:.1f}目, "
                        f"AI推奨: {best['move']}, 変化図: {pv_str}。\n"
                        f"知識ベース: {kn}\n"
                        f"黒番のプレイヤーに対して、この手がなぜ悪手なのか論理的に解説してください。\n"
                        f"※知識ベースの用語（サカレ形など）は、この局面や変化図に実際にその形が現れている場合のみ使用してください。関係のない用語を無理に使うことは禁止します。"
                    )
                    
                    print(f"DEBUG: Requesting Gemini commentary for move {m_idx}...")
                    resp = self.gemini.client.models.generate_content(
                        model='gemini-3-flash-preview', 
                        contents=prompt,
                        config=types.GenerateContentConfig(system_instruction="プロの囲碁インストラクターとして解説せよ。用語の乱用を避け、事実に基づいた論理的な解説を行うこと。")
                    )
                    print(f"DEBUG: Commentary received for move {m_idx}.")
                    
                    r_md += f"### 手数 {m_idx} (黒番のミス)\n- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n- **AI推奨**: {best['move']}\n\n![参考図]({f_name})\n\n**解説**: {resp.text}\n\n---\n\n"

            # 3. 総評の生成
            print("DEBUG: Generating Black-focused summary...")
            sum_p = (
                f"囲碁インストラクターとして、黒番を打った大人級位者への総評（600-1000文字）を書いてください。"
                f"対局全体を振り返り、黒番のプレイヤーが今後改善すべき点をアドバイスしてください。\n"
                f"※知識ベース({kn})の用語は、対局の内容に合致する場合のみ言及してください。無理に用語を当てはめる必要はありません。"
                f"データ(黒のミス): {all_m}"
            )
            sum_resp = self.gemini.client.models.generate_content(model='gemini-3-flash-preview', contents=sum_p)
            r_md += f"## 黒番への総評\n\n{sum_resp.text}\n"
            
            # 4. ファイル保存
            report_path = os.path.join(r_dir, "report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(r_md)
            
            print(f"DEBUG: Report finished! Saved to {report_path}")
            self.root.after(0, lambda: messagebox.showinfo("Done", f"レポートを保存しました: {report_path}"))
        except Exception as e:
            print("DEBUG: Error occurred in _run_report_task!")
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_report.config(state="normal", text="対局レポートを生成"))
