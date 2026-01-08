import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import os
import threading
import queue
import json

from config import OUTPUT_BASE_DIR, KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL, load_api_key
from core.game_state import GoGameState
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from services.ai_commentator import GeminiCommentator
from services.analysis_manager import AnalysisManager
from services.report_generator import ReportGenerator
from drivers.katago_driver import KataGoDriver

from gui.board_view import BoardView
from gui.info_view import InfoView

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Analysis Agent (MVC)")
        self.root.geometry("1200x950")

        # Logic & Services
        self.game = GoGameState()
        self.transformer = CoordinateTransformer()
        self.renderer = GoBoardRenderer()
        self.katago_driver = None
        self.gemini = None
        self.analysis_manager = AnalysisManager(queue.Queue())
        self.report_generator = None
        
        self._init_ai()

        # UI State
        self.current_move = 0
        self.image_cache = {}
        self.current_sgf_name = None
        self.image_dir = None
        self.moves_m_b = [None] * 3
        self.moves_m_w = [None] * 3

        self.setup_layout()
        self._start_queue_monitor()
        
        # Global Bindings
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)

    def _init_ai(self):
        api_key = load_api_key()
        if api_key and os.path.exists(KATAGO_EXE):
            try:
                self.katago_driver = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
                self.gemini = GeminiCommentator(api_key, self.katago_driver)
                self.report_generator = ReportGenerator(
                    self.game, self.renderer, self.gemini, self.katago_driver
                )
                print("AI Services Initialized.")
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

        # Top Bar (Progress)
        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_bar = ttk.Progressbar(top_frame, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_status = tk.Label(top_frame, text="Idle", width=30, bg="#ddd")
        self.lbl_status.pack(side=tk.RIGHT, padx=10)

        # Main Paned Window
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")
        
        # Sub-views
        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=600)
        self.board_view.bind_click(self.click_on_board)
        
        callbacks = {
            'comment': self.generate_commentary,
            'report': self.generate_full_report,
            'agent_pv': self.show_agent_pv,
            'show_pv': self.show_pv,
            'goto': self.goto_mistake,
            'pass': self.pass_move,
            'update_display': self.update_display
        }
        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)
        
        # Bottom Bar (Navigation)
        self._setup_bottom_bar()

    def click_on_board(self, event):
        if not self.info_view.edit_mode.get():
            return
        
        # Get board coordinates from pixel click
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            row, col = res
            color = "B" if (self.current_move % 2 == 0) else "W"
            self.play_interactive_move(color, row, col)

    def pass_move(self):
        if not self.info_view.edit_mode.get():
            return
        color = "B" if (self.current_move % 2 == 0) else "W"
        self.play_interactive_move(color, None, None)

    def play_interactive_move(self, color, row, col):
        self.info_view.btn_comment.config(state="disabled", text="Analyzing...")
        
        def run():
            try:
                # 1. Add move to GameState
                success = self.game.add_move(self.current_move, color, row, col)
                if not success:
                    print("DEBUG: Failed to add move to GameState.")
                    return

                new_move_idx = self.current_move + 1
                history = self.game.get_history_up_to(new_move_idx)
                
                # 2. Analyze new situation with KataGo
                res = self.katago_driver.analyze_situation(history, board_size=self.game.board_size)
                
                # 3. Update Analysis Data
                new_data = {
                    "move_number": new_move_idx,
                    "winrate": res.get('current_winrate_black', 0.5), # Driver already standardized this
                    "score": res.get('current_score_lead_black', 0.0),
                    "candidates": []
                }
                # Fix winrate back to hand-over perspective for internal moves if needed
                # (Existing display logic in update_display inverts if current_move % 2 != 0)
                # Let's ensure it matches what analyze_sgf.py produces.
                # KataGo returns next player's winrate. 
                # If we are at move 1 (after B1), it's W's turn. winrate is for W.
                # GoReplayApp.update_display: 
                # wr_black = (1.0 - wr_raw) if (self.current_move % 2 != 0) else wr_raw
                # So if move is 1, it inverts. 
                # Our katago_driver.analyze_situation returns 'current_winrate_black'.
                # To be consistent with 'winrate' in JSON being 'next player', 
                # we need to set it to next player's winrate.
                
                next_player_wr = 1.0 - res.get('current_winrate_black', 0.5) if (new_move_idx % 2 == 0) else res.get('current_winrate_black', 0.5)
                # Wait, if new_move_idx is 1 (after B1), it's W's turn. 
                # Driver returns Black's WR. We want White's WR. So 1 - Black's WR.
                # If move_idx is odd, next is White.
                # Correct logic for 'winrate' key (next player):
                if new_move_idx % 2 != 0: # Next is White
                    new_data["winrate"] = 1.0 - res.get('current_winrate_black', 0.5)
                    new_data["score"] = -res.get('current_score_lead_black', 0.0)
                else: # Next is Black
                    new_data["winrate"] = res.get('current_winrate_black', 0.5)
                    new_data["score"] = res.get('current_score_lead_black', 0.0)

                for c in res.get('top_candidates', []):
                    new_data["candidates"].append({
                        "move": c['move'],
                        "winrate": c.get('winrate_black', 0), # Simplified for candidate
                        "scoreLead": c.get('score_lead_black', 0),
                        "pv": [m.strip() for m in c.get('future_sequence', "").split("->")]
                    })
                
                # Append or replace the future moves
                self.game.moves = self.game.moves[:new_move_idx]
                self.game.moves.append(new_data)
                
                # 4. Generate new board image
                board = self.game.get_board_at(new_move_idx)
                last_move = None
                if row is not None:
                    last_move = (color.lower(), (row, col))
                
                info_text = f"Move {new_move_idx} | Winrate: {res.get('current_winrate_black', 0.5):.1%} | Score: {res.get('current_score_lead_black', 0.0):.1f}"
                img = self.renderer.render(board, last_move=last_move, analysis_text=info_text)
                
                # 5. Store in cache and update UI
                self.image_cache[new_move_idx] = img
                self.root.after(0, lambda: self.show_image(new_move_idx))
                self.root.after(0, lambda: self.lbl_counter.config(text=f"{new_move_idx} / {self.game.total_moves}"))
                self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask KataGo Agent"))
                
            except Exception as e:
                print(f"Error in play_interactive_move: {e}")
                self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask KataGo Agent"))

        threading.Thread(target=run, daemon=True).start()

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
            self.game.load_sgf(path)
            # Sync Transformer & Renderer with new board size
            self.transformer = CoordinateTransformer(board_size=self.game.board_size)
            self.board_view.transformer = self.transformer
            self.renderer = GoBoardRenderer(board_size=self.game.board_size)
            if self.report_generator:
                self.report_generator.renderer = self.renderer
        except Exception as e:
            messagebox.showerror("Error", f"SGFを読み込めません: {e}")
            return

        self.current_sgf_name = os.path.splitext(os.path.basename(path))[0]
        self.image_dir = os.path.join(OUTPUT_BASE_DIR, self.current_sgf_name)
        
        self.lbl_status.config(text="Starting Analysis...")
        self.analysis_manager.start_analysis(path)
        self._monitor_images_on_disk()

    def _start_queue_monitor(self):
        try:
            while True:
                msg, d = self.analysis_manager.queue.get_nowait()
                if msg == "set_max":
                    self.progress_bar.config(maximum=d)
                elif msg == "progress":
                    self.lbl_status.config(text=f"Progress: {d} / {int(self.progress_bar['maximum'])}")
                elif msg == "done" or msg == "skip":
                    self.lbl_status.config(text="Analysis Ready")
                    self._sync_analysis_data()
                elif msg == "error":
                    self.lbl_status.config(text=f"Error: {d[:20]}", fg="red")
        except queue.Empty:
            pass
        self.root.after(100, self._start_queue_monitor)

    def _sync_analysis_data(self):
        p = os.path.join(self.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    d = json.load(f)
                self.game.moves = d if isinstance(d, list) else d.get("moves", [])
                
                # Update Mistake Buttons
                mb, mw = self.game.calculate_mistakes()
                for i in range(3):
                    self._upd_mistake_ui("b", i, mb)
                    self._upd_mistake_ui("w", i, mw)
                
                self.update_display()
            except:
                pass

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
        if len(files) > 0 and not self.image_cache:
            self.show_image(0)
        if self.analysis_manager.analyzing:
            self._sync_analysis_data()
            self.root.after(2000, self._monitor_images_on_disk)

    def show_image(self, n):
        p = os.path.join(self.image_dir, f"move_{n:03d}.png")
        if os.path.exists(p) and n not in self.image_cache:
            self.image_cache[n] = Image.open(p)
        self.current_move = n
        self.update_display()

    def update_display(self):
        if self.current_move not in self.image_cache: return
        
        moves = self.game.moves
        wr_text, sc_text, cands = "--%", "--", []
        if moves and self.current_move < len(moves):
            d = moves[self.current_move]
            wr_raw = d.get('winrate', 0.5)
            wr_black = (1.0 - wr_raw) if (self.current_move % 2 != 0) else wr_raw
            wr_text = f"{wr_black:.1%}"
            sc_text = f"{d.get('score', 0):.1f}"
            cands = d.get('candidates', [])
        
        self.info_view.update_stats(wr_text, sc_text, "")
        self.lbl_counter.config(text=f"{self.current_move} / {self.game.total_moves}")
        
        img = self.image_cache[self.current_move]
        self.board_view.update_board(img, self.info_view.review_mode.get(), cands)

    def generate_commentary(self):
        if not self.gemini: return
        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        self.info_view.set_commentary("Consulting AI...")
        threading.Thread(target=self._run_commentary_task, daemon=True).start()

    def _run_commentary_task(self):
        try:
            h = self.game.get_history_up_to(self.current_move)
            text = self.gemini.generate_commentary(self.current_move, h, self.game.board_size)
            self.root.after(0, lambda: self._update_commentary_ui(text))
        except Exception as e:
            self.root.after(0, lambda: self._update_commentary_ui(f"Error: {e}"))

    def _update_commentary_ui(self, text):
        self.info_view.set_commentary(text)
        self.info_view.btn_comment.config(state="normal", text="Ask KataGo Agent")
        state = "normal" if self.gemini.last_pv else "disabled"
        self.info_view.btn_agent_pv.config(state=state)

    def generate_full_report(self):
        if not self.report_generator: return
        self.info_view.btn_report.config(state="disabled", text="Generating...")
        threading.Thread(target=self._run_report_task, daemon=True).start()

    def _run_report_task(self):
        try:
            self._sync_analysis_data()
            path, err = self.report_generator.generate(self.current_sgf_name, self.image_dir)
            if err:
                self.root.after(0, lambda: messagebox.showinfo("Info", err))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Done", f"Report saved: {path}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.info_view.btn_report.config(state="normal", text="対局レポートを生成"))

    def show_pv(self):
        if self.current_move < len(self.game.moves):
            cands = self.game.moves[self.current_move].get('candidates', [])
            if cands and 'pv' in cands[0]:
                self._show_pv_window("Future Sequence", cands[0]['pv'])
            else:
                messagebox.showinfo("Info", "No variation data.")

    def show_agent_pv(self):
        if self.gemini.last_pv:
            self._show_pv_window("Agent Reference", self.gemini.last_pv)

    def _show_pv_window(self, title, pv_list):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("750x800")
        
        board = self.game.get_board_at(self.current_move)
        start_color = "W" if (self.current_move % 2 != 0) else "B"
        img = self.renderer.render_pv(board, pv_list, start_color, title=title)
        
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img)
        cv = tk.Canvas(top, bg="#333")
        cv.pack(fill=tk.BOTH, expand=True)
        cv.create_image(0, 0, image=photo, anchor=tk.NW)
        cv.image = photo

    def prev_move(self):
        if self.current_move > 0: self.show_image(self.current_move - 1)
    def next_move(self):
        if self.current_move < self.game.total_moves: self.show_image(self.current_move + 1)
    def on_resize(self, event):
        if self.image_cache: self.update_display()
    def goto_mistake(self, color, idx):
        m = self.moves_m_b[idx] if color == "b" else self.moves_m_w[idx]
        if m is not None: self.show_image(m)
