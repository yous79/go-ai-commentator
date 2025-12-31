import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import sys
import threading
import subprocess
import time
import glob
import queue
import json

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYZE_SCRIPT = os.path.join(SCRIPT_DIR, "analyze_sgf.py")
OUTPUT_BASE_DIR = os.path.join(SCRIPT_DIR, "output_images")

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Replay & Analysis")
        self.root.geometry("1100x900")

        # Variables
        self.current_move = 0
        self.total_moves_in_dir = 0
        self.image_cache = {}
        self.analysis_data = {"board_size": 19, "moves": []}
        self.current_sgf_name = None
        self.image_dir = None
        self.analyzing = False
        self.process = None
        self.queue = queue.Queue()
        self.review_mode = tk.BooleanVar(value=False)

        # UI Layout setup
        self.setup_layout()
        
        # Key bindings
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        
        self.check_queue()

    def setup_layout(self):
        # Configure Grid Weights for Root
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)
        self.root.columnconfigure(0, weight=1)

        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open SGF...", command=self.open_sgf)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # --- Row 0: Top Frame (Progress) ---
        top_frame = tk.Frame(self.root, pady=5, bg="#ddd")
        top_frame.grid(row=0, column=0, sticky="ew")
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(top_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.lbl_progress_text = tk.Label(top_frame, text="Idle", width=25, anchor="w", bg="#ddd")
        self.lbl_progress_text.pack(side=tk.RIGHT, padx=10)

        # --- Row 1: Middle Frame (PanedWindow) ---
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.grid(row=1, column=0, sticky="nsew")

        # Left: Board
        self.board_frame = tk.Frame(self.paned, bg="#333")
        self.paned.add(self.board_frame, minsize=400)
        
        self.canvas = tk.Canvas(self.board_frame, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Right: Info & Commentary
        self.info_frame = tk.Frame(self.paned, bg="#f0f0f0", width=350)
        self.paned.add(self.info_frame, minsize=300)

        # Info Section
        tk.Label(self.info_frame, text="Analysis Info", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        
        self.lbl_data_status = tk.Label(self.info_frame, text="Data: Not Loaded", fg="red", bg="#f0f0f0")
        self.lbl_data_status.pack(pady=2)

        self.lbl_winrate = tk.Label(self.info_frame, text="Winrate: --%", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w", padx=20)
        self.lbl_score = tk.Label(self.info_frame, text="Score: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w", padx=20)

        chk = tk.Checkbutton(self.info_frame, text="Review Mode (Show Candidates)", 
                        variable=self.review_mode, command=self.update_display,
                        font=("Arial", 10, "bold"), bg="#f0f0f0")
        chk.pack(pady=10)

        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self.info_frame, text="AI Commentary", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)

        tk.Button(self.info_frame, text="Generate Commentary (Gemini)", command=self.generate_commentary, bg="#4CAF50", fg="white").pack(pady=5)
        self.txt_commentary = tk.Text(self.info_frame, height=10, width=30, wrap=tk.WORD, font=("Arial", 10))
        self.txt_commentary.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Mistakes Section
        tk.Frame(self.info_frame, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self.info_frame, text="Top 3 Mistakes", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        self.mistakes_frame = tk.Frame(self.info_frame, bg="#f0f0f0")
        self.mistakes_frame.pack(fill=tk.X, padx=5)
        
        # Grid layout for mistakes: Left (Black), Right (White)
        self.mistakes_frame.columnconfigure(0, weight=1)
        self.mistakes_frame.columnconfigure(1, weight=1)

        # Headers
        tk.Label(self.mistakes_frame, text="Black", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=0, column=0)
        tk.Label(self.mistakes_frame, text="White", font=("Arial", 10, "bold"), bg="#f0f0f0").grid(row=0, column=1)

        self.btn_mistakes_b = []
        self.btn_mistakes_w = []
        
        for i in range(3):
            # Black buttons
            btn_b = tk.Button(self.mistakes_frame, text="-", command=lambda x=i: self.goto_mistake("b", x), bg="#ffcccc", font=("Arial", 9))
            btn_b.grid(row=i+1, column=0, sticky="ew", padx=2, pady=2)
            self.btn_mistakes_b.append(btn_b)
            
            # White buttons
            btn_w = tk.Button(self.mistakes_frame, text="-", command=lambda x=i: self.goto_mistake("w", x), bg="#ffcccc", font=("Arial", 9))
            btn_w.grid(row=i+1, column=1, sticky="ew", padx=2, pady=2)
            self.btn_mistakes_w.append(btn_w)
        
        self.mistake_moves_b = [None] * 3
        self.mistake_moves_w = [None] * 3

        # --- Row 2: Bottom Frame (Controls) ---
        self.bottom_frame = tk.Frame(self.root, pady=15, bg="#e0e0e0", height=60)
        self.bottom_frame.grid(row=2, column=0, sticky="ew")
        self.bottom_frame.grid_propagate(False)

        btn_prev = tk.Button(self.bottom_frame, text="< Prev", command=self.prev_move, width=15)
        btn_prev.pack(side=tk.LEFT, padx=20)

        self.lbl_counter = tk.Label(self.bottom_frame, text="0 / 0", font=("Arial", 12, "bold"), bg="#e0e0e0")
        self.lbl_counter.pack(side=tk.LEFT, expand=True)

        btn_next = tk.Button(self.bottom_frame, text="Next >", command=self.next_move, width=15)
        btn_next.pack(side=tk.RIGHT, padx=20)

    def goto_mistake(self, color, idx):
        move = None
        if color == "b":
            move = self.mistake_moves_b[idx]
        else:
            move = self.mistake_moves_w[idx]
            
        if move is not None:
            self.show_image(move)

    def calculate_mistakes(self):
        moves = self.analysis_data.get("moves", [])
        if len(moves) < 2: return
        
        drops_b = []
        drops_w = []
        
        # Calculate drop for each move starting from 1
        for i in range(1, len(moves)):
            prev = moves[i-1]
            curr = moves[i]
            
            w_prev = prev.get('winrate', 0.5)
            w_curr = curr.get('winrate', 0.5)
            
            # Drop calculation assumes winrate is "Side to Move"
            drop = w_prev - (1.0 - w_curr)
            
            if drop > 0.001: # Threshold
                # Odd moves = Black (1, 3, 5...), Even moves = White (2, 4, 6...)
                if i % 2 != 0:
                    drops_b.append((drop, i))
                else:
                    drops_w.append((drop, i))
        
        # Sort desc
        drops_b.sort(key=lambda x: x[0], reverse=True)
        drops_w.sort(key=lambda x: x[0], reverse=True)
        
        # Update UI Black
        for idx in range(3):
            btn = self.btn_mistakes_b[idx]
            if idx < len(drops_b):
                drop, move_num = drops_b[idx]
                self.mistake_moves_b[idx] = move_num
                btn.config(text=f"#{move_num}: -{drop:.1%}", state="normal")
            else:
                self.mistake_moves_b[idx] = None
                btn.config(text="-", state="disabled")

        # Update UI White
        for idx in range(3):
            btn = self.btn_mistakes_w[idx]
            if idx < len(drops_w):
                drop, move_num = drops_w[idx]
                self.mistake_moves_w[idx] = move_num
                btn.config(text=f"#{move_num}: -{drop:.1%}", state="normal")
            else:
                self.mistake_moves_w[idx] = None
                btn.config(text="-", state="disabled")

    def open_sgf(self):
        file_path = filedialog.askopenfilename(initialdir=SCRIPT_DIR, filetypes=[("SGF Files", "*.sgf")])
        if not file_path: return
        self.start_analysis(file_path)

    def start_analysis(self, sgf_path):
        self.current_move = 0
        self.image_cache = {}
        self.analysis_data = {"board_size": 19, "moves": []}
        self.analyzing = True
        self.current_sgf_name = os.path.splitext(os.path.basename(sgf_path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name)
        self.progress_var.set(0)
        self.lbl_data_status.config(text="Data: Initializing...", fg="orange")
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, "Analyzing... Commentary will be available later.")
        
        if self.process and self.process.poll() is None:
            self.process.terminate()

        threading.Thread(target=self.run_analysis_script, args=(sgf_path,), daemon=True).start()
        self.monitor_images()

    def run_analysis_script(self, sgf_path):
        env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = ["python", "-u", ANALYZE_SCRIPT, sgf_path]
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, bufsize=1, startupinfo=startupinfo,
                                          encoding='utf-8', errors='replace', env=env)
            while True:
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None: break
                    continue
                line = line.strip()
                if line.startswith("Total Moves:"):
                    self.queue.put(("set_max", int(line.split(":")[1].strip())))
                elif line.startswith("Analyzing Move"):
                    try:
                        self.queue.put(("progress", int(line.split("Move")[1].strip())))
                    except: pass
                elif any(x in line for x in ["Error", "Traceback", "Exception"]):
                    self.queue.put(("error", line))

            self.analyzing = False
            self.queue.put(("done", None))
        except Exception as e:
            self.queue.put(("error", str(e)))
            self.analyzing = False

    def check_queue(self):
        try:
            while True:
                msg, data = self.queue.get_nowait()
                if msg == "set_max":
                    self.progress_bar.config(maximum=data)
                    self.lbl_progress_text.config(text=f"Analyzing... (Total: {data})")
                elif msg == "progress":
                    self.progress_var.set(data)
                    self.lbl_progress_text.config(text=f"Analyzing: {data} / {int(self.progress_bar['maximum'])}")
                elif msg == "done":
                    self.lbl_progress_text.config(text="Analysis Complete")
                    self.progress_var.set(self.progress_bar['maximum'])
                    self.load_analysis_data()
                elif msg == "error":
                    self.lbl_progress_text.config(text=f"Error: {data[:20]}...", fg="red")
        except queue.Empty: pass
        self.root.after(100, self.check_queue)

    def load_analysis_data(self):
        json_path = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f: 
                    data = json.load(f)
                    if isinstance(data, list): self.analysis_data = {"board_size": 19, "moves": data}
                    else: self.analysis_data = data
                count = len(self.analysis_data.get("moves", []))
                self.lbl_data_status.config(text=f"Data: Loaded ({count} moves)", fg="green")
                self.calculate_mistakes()
            except: 
                self.lbl_data_status.config(text="Data: Error Loading", fg="red")

    def monitor_images(self):
        if not self.image_dir: return
        files = sorted(glob.glob(os.path.join(self.image_dir, "move_*.png")))
        self.total_moves_in_dir = len(files)
        self.lbl_counter.config(text=f"{self.current_move} / {max(0, self.total_moves_in_dir - 1)}")
        if self.analyzing: self.load_analysis_data()
        if self.total_moves_in_dir > 0 and not self.image_cache: self.show_image(0)
        if self.total_moves_in_dir > 0 and len(self.canvas.find_all()) == 0: self.show_image(self.current_move)
        if self.analyzing: self.root.after(2000, self.monitor_images)

    def gtp_to_coords(self, gtp_vertex):
        if gtp_vertex == "pass": return None
        col_map = "ABCDEFGHJKLMNOPQRST"
        col = col_map.find(gtp_vertex[0].upper())
        row = int(gtp_vertex[1:]) - 1
        return row, col

    def get_canvas_coords(self, row_idx, col_idx):
        board_size = self.analysis_data.get("board_size", 19)
        margin, base_size = 50, 800
        step = (base_size - 2 * margin) / (board_size - 1)
        visual_row = board_size - 1 - row_idx
        return (margin + col_idx * step) / base_size, (margin + visual_row * step) / base_size

    def show_image(self, move_num):
        path = os.path.join(self.image_dir, f"move_{move_num:03d}.png")
        if os.path.exists(path) and move_num not in self.image_cache:
            try: self.image_cache[move_num] = Image.open(path)
            except: return
        self.current_move = move_num
        self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache: return
        
        winrate, score, candidates = "--%", "--", []
        moves_data = self.analysis_data.get("moves", [])
        if moves_data and self.current_move < len(moves_data):
            d = moves_data[self.current_move]
            winrate = f"{d.get('winrate', 0):.1%}"
            score = f"{d.get('score', 0):.1f}"
            candidates = d.get('candidates', [])
        
        self.lbl_winrate.config(text=f"Winrate: {winrate}")
        self.lbl_score.config(text=f"Score: {score}")
        self.lbl_counter.config(text=f"{self.current_move} / {max(0, self.total_moves_in_dir - 1)}")

        canvas_w = max(self.canvas.winfo_width(), 100)
        canvas_h = max(self.canvas.winfo_height(), 100)
        original_img = self.image_cache[self.current_move]
        img_w, img_h = original_img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h)
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        
        resized_img = original_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized_img)
        self.canvas.delete("all")
        cx, cy = canvas_w // 2, canvas_h // 2
        self.canvas.create_image(cx, cy, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo

        if self.review_mode.get() and candidates:
            off_x, off_y = cx - new_w // 2, cy - new_h // 2
            board_ratio = 800 / 900
            best_cand = candidates[0]
            coords = self.gtp_to_coords(best_cand['move'])
            if coords:
                nx, ny = self.get_canvas_coords(coords[0], coords[1])
                fx, fy = off_x + new_w * nx, off_y + (new_h * board_ratio) * ny
                rad = (new_w / 19) * 0.6
                self.canvas.create_oval(fx-rad, fy-rad, fx+rad, fy+rad, outline="#00ff00", width=2, fill="#00ff00", tags="overlay")
                wr_text = f"{best_cand['winrate']:.0%}"
                font_size = int(rad * 1.0)
                self.canvas.create_text(fx, fy, text=wr_text, fill="black", font=("Arial", font_size, "bold"), tags="overlay")

    def next_move(self):
        if self.image_dir and self.current_move < self.total_moves_in_dir - 1: self.show_image(self.current_move + 1)
    def prev_move(self):
        if self.image_dir and self.current_move > 0: self.show_image(self.current_move - 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()
    def generate_commentary(self):
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, f"Move {self.current_move} Analysis:\n\nMock Gemini: ここでの白のツケは鋭い一手です。黒は受け方に苦慮します。")

if __name__ == "__main__":
    root = tk.Tk(); app = GoReplayApp(root); root.mainloop()