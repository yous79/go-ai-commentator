import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import os
import time
import queue
import json
import concurrent.futures
import requests
import subprocess
import sys
import traceback

from config import OUTPUT_BASE_DIR, load_api_key, SRC_DIR
from core.game_state import GoGameState
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from services.ai_commentator import GeminiCommentator
from services.analysis_manager import AnalysisManager
from services.report_generator import ReportGenerator

from gui.board_view import BoardView
from gui.info_view import InfoView

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Analysis Agent (MVC)")
        self.root.geometry("1200x950")

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self.game = GoGameState()
        self.transformer = CoordinateTransformer()
        self.renderer = GoBoardRenderer()
        self.gemini = None
        
        self._init_ai()
        
        self.analysis_manager = AnalysisManager(queue.Queue(), self.renderer)
        self.report_generator = None
        
        if self.gemini:
            self.report_generator = ReportGenerator(self.game, self.renderer, self.gemini)

        self.current_move = 0
        self.image_cache = {}
        self.current_sgf_name = None
        self.image_dir = None
        self.moves_m_b = [None] * 3
        self.moves_m_w = [None] * 3

        self.setup_layout()
        self._start_queue_monitor()
        
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_ai(self):
        api_key = load_api_key()
        if api_key:
            try:
                self._ensure_api_server()
                self.gemini = GeminiCommentator(api_key)
                print("AI Services (Pure API Mode) Initialized.")
            except Exception as e:
                print(f"AI Init Failed: {e}")
                traceback.print_exc()

    def _ensure_api_server(self):
        try:
            requests.get("http://127.0.0.1:8000/health", timeout=1)
            return
        except:
            print("Starting KataGo API Service...")
            api_script = os.path.join(SRC_DIR, "katago_api.py")
            log_file = os.path.join(SRC_DIR, "api_server.log")
            with open(log_file, "a") as f:
                subprocess.Popen([sys.executable, api_script], stdout=f, stderr=f,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for _ in range(10):
                try:
                    time.sleep(1)
                    requests.get("http://127.0.0.1:8000/health", timeout=1)
                    return
                except: pass

    def setup_layout(self):
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open SGF...", command=self.open_sgf)
        filemenu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_bar = ttk.Progressbar(top_frame, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_status = tk.Label(top_frame, text="Idle", width=30, bg="#ddd")
        self.lbl_status.pack(side=tk.RIGHT, padx=10)

        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")
        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=600)
        self.board_view.bind_click(self.click_on_board)
        
        callbacks = {'comment': self.generate_commentary, 'report': self.generate_full_report,
                     'agent_pv': self.show_agent_pv, 'show_pv': self.show_pv, 'goto': self.goto_mistake,
                     'pass': self.pass_move, 'update_display': self.update_display}
        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)
        self._setup_bottom_bar()

    def _setup_bottom_bar(self):
        bot = tk.Frame(self.root, bg="#e0e0e0", height=60)
        bot.grid(row=2, column=0, sticky="ew")
        bot.grid_propagate(False)
        bot.columnconfigure(0, weight=1); bot.columnconfigure(4, weight=1)
        tk.Button(bot, text="< Prev", command=self.prev_move, width=15).grid(row=0, column=1, padx=10, pady=10)
        self.lbl_counter = tk.Label(bot, text="0 / 0", font=("Arial", 12, "bold"), bg="#e0e0e0")
        self.lbl_counter.grid(row=0, column=2, padx=20)
        tk.Button(bot, text="Next >", command=self.next_move, width=15).grid(row=0, column=3, padx=10, pady=10)

    def open_sgf(self):
        p = filedialog.askopenfilename(filetypes=[("SGF Files", "*.sgf")])
        if p: self.start_analysis(p)

    def start_analysis(self, path):
        self.current_move = 0
        self.image_cache = {}
        try:
            self.game.load_sgf(path)
            self.transformer = CoordinateTransformer(board_size=self.game.board_size)
            self.board_view.transformer = self.transformer
            self.renderer = GoBoardRenderer(board_size=self.game.board_size)
            self.analysis_manager.renderer = self.renderer
        except Exception as e:
            messagebox.showerror("Error", f"SGFを読み込めません: {e}"); return

        self.current_sgf_name = os.path.splitext(os.path.basename(path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name)
        
        # Update renderer for report generator
        if self.report_generator:
            self.report_generator.renderer = self.renderer
            
        self.lbl_status.config(text="Starting Analysis...")
        self.analysis_manager.start_analysis(path)
        self._monitor_images_on_disk()

    def _start_queue_monitor(self):
        try:
            while True:
                msg, d = self.analysis_manager.app_queue.get_nowait()
                if msg == "set_max": self.progress_bar.config(maximum=d)
                elif msg == "progress": self.lbl_status.config(text=f"Progress: {d} / {int(self.progress_bar['maximum'])}")
                elif msg == "done" or msg == "skip":
                    self.lbl_status.config(text="Analysis Ready")
                    self._sync_analysis_data()
        except queue.Empty: pass
        self.root.after(100, self._start_queue_monitor)

    def _sync_analysis_data(self):
        if not self.image_dir: return
        p = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
                self.game.moves = d.get("moves", [])
                mb, mw = self.game.calculate_mistakes()
                for i in range(3):
                    self._upd_mistake_ui("b", i, mb); self._upd_mistake_ui("w", i, mw)
                self.update_display()
            except (PermissionError, json.JSONDecodeError): pass
            except Exception as e:
                print(f"Sync Error: {e}")
                traceback.print_exc()

    def _upd_mistake_ui(self, color, idx, mistakes):
        store = self.moves_m_b if color == "b" else self.moves_m_w
        if idx < len(mistakes):
            sc_drop, wr_drop, m = mistakes[idx]
            if wr_drop > 0 or sc_drop > 0:
                store[idx] = m
                text = f"#{m}: -{wr_drop:.1%} / -{sc_drop:.1f}"
                self.info_view.update_mistake_button(color, idx, text, "normal")
                return
        store[idx] = None
        self.info_view.update_mistake_button(color, idx, "-", "disabled")

    def _monitor_images_on_disk(self):
        if not self.image_dir: return
        import glob
        files = glob.glob(os.path.join(self.image_dir, "move_*.png"))
        if len(files) > 0 and not self.image_cache: self.show_image(0)
        if self.analysis_manager.analyzing:
            self._sync_analysis_data()
            self.root.after(2000, self._monitor_images_on_disk)

    def show_image(self, n):
        if not self.image_dir: return
        p = os.path.join(self.image_dir, f"move_{n:03d}.png")
        if os.path.exists(p) and n not in self.image_cache:
            try: self.image_cache[n] = Image.open(p)
            except: return
        self.current_move = n
        self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache: return
        moves = self.game.moves
        wr_text, sc_text, cands = "--%", "--", []
        if moves and self.current_move < len(moves):
            d = moves[self.current_move]
            # 両方のキー名をチェック
            wr_val = d.get('winrate', d.get('winrate_black', 0.5))
            sc_val = d.get('score', d.get('score_lead_black', 0.0))
            wr_text = f"{wr_val:.1%}"
            sc_text = f"{sc_val:.1f}"
            cands = d.get('candidates', [])
        self.info_view.update_stats(wr_text, sc_text, "")
        self.lbl_counter.config(text=f"{self.current_move} / {self.game.total_moves}")
        img = self.image_cache[self.current_move]
        self.board_view.update_board(img, self.info_view.review_mode.get(), cands)

    def generate_commentary(self):
        if not self.gemini: return
        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        self.info_view.set_commentary("Consulting AI...")
        self.executor.submit(self._run_commentary_task)

    def _run_commentary_task(self):
        try:
            h = self.game.get_history_up_to(self.current_move)
            text = self.gemini.generate_commentary(self.current_move, h, self.game.board_size)
            self.root.after(0, lambda: self._update_commentary_ui(text))
        except Exception as e:
            traceback.print_exc()
            err_msg = f"Error: {e}"
            self.root.after(0, lambda: self._update_commentary_ui(err_msg))

    def _update_commentary_ui(self, text):
        self.info_view.set_commentary(text)
        self.info_view.txt_commentary.config(fg="red" if "【エラー】" in text or "ERROR" in text else "black")
        self.info_view.btn_comment.config(state="normal", text="Ask KataGo Agent")
        self.info_view.btn_agent_pv.config(state="normal" if self.gemini.last_pv else "disabled")

    def generate_full_report(self):
        if not self.report_generator: return
        self.info_view.btn_report.config(state="disabled", text="Generating...")
        self.executor.submit(self._run_report_task)

    def _run_report_task(self):
        try:
            self.root.after(0, lambda: self._sync_analysis_data())
            path, err = self.report_generator.generate(self.current_sgf_name, self.image_dir)
            if err:
                self.root.after(0, lambda: messagebox.showinfo("Info", err))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Done", f"PDFレポートを生成しました:\n{path}"))
        except Exception as e:
            traceback.print_exc()
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", err_msg))
        finally:
            self.root.after(0, lambda: self.info_view.btn_report.config(state="normal", text="対局レポートを生成"))

    def show_pv(self):
        if self.current_move < len(self.game.moves):
            cands = self.game.moves[self.current_move].get('candidates', [])
            if cands and 'pv' in cands[0]: self._show_pv_window("Future Sequence", cands[0]['pv'])
            else: messagebox.showinfo("Info", "No variation data.")

    def show_agent_pv(self):
        if self.gemini.last_pv: self._show_pv_window("Agent Reference", self.gemini.last_pv)

    def _show_pv_window(self, title, pv_list):
        top = tk.Toplevel(self.root); top.title(title); top.geometry("750x800")
        board = self.game.get_board_at(self.current_move)
        start_color = "W" if (self.current_move % 2 != 0) else "B"
        img = self.renderer.render(board, pv_list=pv_list, start_color=start_color, title=title)
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img)
        cv = tk.Canvas(top, bg="#333"); cv.pack(fill=tk.BOTH, expand=True)
        cv.create_image(0, 0, image=photo, anchor=tk.NW); cv.image = photo

    def click_on_board(self, event):
        if not self.info_view.edit_mode.get(): return
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            color = "B" if (self.current_move % 2 == 0) else "W"
            self.play_interactive_move(color, res[0], res[1])

    def pass_move(self):
        if not self.info_view.edit_mode.get(): return
        color = "B" if (self.current_move % 2 == 0) else "W"
        self.play_interactive_move(color, None, None)

    def play_interactive_move(self, color, row, col):
        self.info_view.btn_comment.config(state="disabled", text="Analyzing...")
        def run():
            try:
                if not self.game.add_move(self.current_move, color, row, col): return
                new_move_idx = self.current_move + 1
                history = self.game.get_history_up_to(new_move_idx)
                resp = requests.post("http://127.0.0.1:8000/analyze", json={"history": history, "board_size": self.game.board_size}, timeout=30)
                res = resp.json()
                new_data = {"move_number": new_move_idx, "winrate": res.get('winrate_black', 0.5), "score": res.get('score_lead_black', 0.0), "candidates": []}
                for c in res.get('top_candidates', []):
                    new_data["candidates"].append({"move": c['move'], "winrate": c.get('winrate_black', 0), "scoreLead": c.get('score_lead_black', 0),
                                                   "pv": [m.strip() for m in c.get('future_sequence', "").split("->")]})
                self.game.moves = self.game.moves[:new_move_idx]
                self.game.moves.append(new_data)
                board = self.game.get_board_at(new_move_idx)
                last_move = (color.lower(), (row, col)) if row is not None else None
                img = self.renderer.render(board, last_move=last_move, analysis_text=f"Move {new_move_idx} | Winrate(B): {new_data['winrate']:.1%} | Score(B): {new_data['score']:.1f}")
                self.image_cache[new_move_idx] = img
                self.root.after(0, lambda: self.show_image(new_move_idx))
                self.root.after(0, lambda: self.lbl_counter.config(text=f"{new_move_idx} / {self.game.total_moves}"))
            except Exception as e:
                print(f"Error in interactive move: {e}")
                traceback.print_exc()
            finally: self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask KataGo Agent"))
        self.executor.submit(run)

    def prev_move(self):
        if self.current_move > 0: self.show_image(self.current_move - 1)
    def next_move(self):
        if self.current_move < self.game.total_moves: self.show_image(self.current_move + 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()
    def goto_mistake(self, color, idx):
        m = self.moves_m_b[idx] if color == "b" else self.moves_m_w[idx]
        if m is not None: self.show_image(m)
    def on_close(self):
        self.analysis_manager.stop_analysis()
        self.executor.shutdown(wait=False)
        self.root.destroy()