import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import queue
import json
import threading
import concurrent.futures
import traceback
import sys
import config

from config import OUTPUT_BASE_DIR, load_api_key
from core.game_state import GoGameState
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from services.ai_commentator import GeminiCommentator
from services.analysis_manager import AnalysisManager
from services.report_generator import ReportGenerator
from services.term_visualizer import TermVisualizer
from core.knowledge_manager import KnowledgeManager
from core.board_simulator import BoardSimulator
from config import KNOWLEDGE_DIR

from gui.board_view import BoardView
from gui.info_view import InfoView
from gui.controller import AppController

class GoReplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go AI Commentator (Rev 33.0 MVC)")
        self.root.geometry("1200x950")

        # Core Engine & State
        self.game = GoGameState()
        self.controller = AppController(self.game)
        self.transformer = CoordinateTransformer()
        self.renderer = GoBoardRenderer()
        self.visualizer = TermVisualizer()
        self.simulator = BoardSimulator() # シミュレーターを保持
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.gemini = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        
        self._init_ai()
        
        self.analysis_manager = AnalysisManager(queue.Queue(), self.renderer)
        self.report_generator = None
        if self.gemini:
            self.report_generator = ReportGenerator(self.game, self.renderer, self.gemini)

        # UI State
        self.moves_m_b = [None] * 3
        self.moves_m_w = [None] * 3

        # Callbacks including Dictionary logic
        callbacks = {
            'comment': self.generate_commentary, 
            'report': self.generate_full_report,
            'show_pv': self.show_pv, 
            'goto': self.goto_mistake,
            'pass': self.pass_move, 
            'update_display': self.update_display,
            'goto_move': self.show_image,
            'on_term_select': self.on_term_select,
            'visualize_term': self.visualize_term,
            'on_level_change': self.on_level_change
        }

        self.setup_layout(callbacks)
        self._load_dictionary_terms()
        self._start_queue_monitor()
        
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_ai(self):
        api_key = load_api_key()
        if api_key:
            if self.controller.api_client.health_check():
                self.gemini = GeminiCommentator(api_key)
                print("AI Services Initialized.")

    def setup_layout(self, callbacks):
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
        
        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)
        self._setup_bottom_bar()

    def _load_dictionary_terms(self):
        """知識ベースから用語一覧をロードしてUIにセットする"""
        terms = []
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                terms.append(item.title)
        self.info_view.set_terms_list(sorted(terms))

    def on_term_select(self, term_title):
        """用語が選択された際の詳細表示ロジック"""
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    desc = getattr(item, 'full_content', "詳細な解説はありません。")
                    meta = item.metadata
                    header = f"【{item.title}】\n"
                    if "importance" in meta: header += f"重要度: {'★' * meta['importance']}\n"
                    if "description" in meta: header += f"概要: {meta['description']}\n"
                    
                    full_text = f"{header}\n--- 解説 ---\n{desc}"
                    self.info_view.set_term_details(full_text)
                    return

    def visualize_term(self, term_title):
        """選択された用語の具体例画像を生成・表示する"""
        term_id = None
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    term_id = item.id
                    break
        
        if term_id:
            path, err = self.visualizer.visualize(term_id)
            if path:
                self._show_image_popup(term_title, path)
            else:
                messagebox.showerror("Error", f"画像の生成に失敗しました: {err}")

    def _show_image_popup(self, title, image_path):
        """画像を別ウィンドウで表示する"""
        from PIL import Image, ImageTk
        top = tk.Toplevel(self.root)
        top.title(f"Diagram: {title}")
        
        try:
            img = Image.open(image_path)
            img.thumbnail((600, 600))
            photo = ImageTk.PhotoImage(img)
            
            lbl = tk.Label(top, image=photo)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)
            
            tk.Button(top, text="Close", command=top.destroy).pack(pady=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open diagram: {e}")


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
        try:
            self.game.load_sgf(path)
            # Update dependencies
            self.transformer = CoordinateTransformer(board_size=self.game.board_size)
            self.board_view.transformer = self.transformer
            self.renderer = GoBoardRenderer(board_size=self.game.board_size)
            self.analysis_manager.renderer = self.renderer
            
            # Controller setup
            name = os.path.splitext(os.path.basename(path))[0]
            self.controller.current_sgf_name = name
            self.controller.set_image_dir(os.path.join(OUTPUT_BASE_DIR, name))
            self.controller.jump_to_move(0)
            
            if self.report_generator:
                self.report_generator.renderer = self.renderer
                
            self.lbl_status.config(text="Starting Analysis...")
            self.analysis_manager.start_analysis(path)
            self._monitor_images_on_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start analysis: {e}")

    def _start_queue_monitor(self):
        try:
            while True:
                msg, d = self.analysis_manager.app_queue.get_nowait()
                if msg == "set_max": self.progress_bar.config(maximum=d)
                elif msg == "progress":
                    self.lbl_status.config(text=f"Progress: {d} / {int(self.progress_bar['maximum'])}")
                elif msg == "done" or msg == "skip":
                    self.lbl_status.config(text="Analysis Ready")
                    self._sync_analysis_data()
        except queue.Empty: pass
        self.root.after(100, self._start_queue_monitor)

    def _sync_analysis_data(self):
        if not self.controller.image_dir: return
        p = os.path.join(self.controller.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
                self.game.moves = d.get("moves", [])
                mb, mw = self.game.calculate_mistakes()
                for i in range(3):
                    self._upd_mistake_ui("b", i, mb); self._upd_mistake_ui("w", i, mw)
                self.update_display()
            except: pass

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
        if not self.controller.image_dir: return
        import glob
        files = glob.glob(os.path.join(self.controller.image_dir, "move_*.png"))
        if len(files) > 0 and not self.controller.image_cache: self.show_image(0)
        if self.analysis_manager.analyzing:
            self._sync_analysis_data()
            self.root.after(2000, self._monitor_images_on_disk)

    def show_image(self, n):
        if self.controller.jump_to_move(n):
            self.update_display()

    def update_display(self):
        img = self.controller.get_current_image()
        if not img: return
        
        moves = self.game.moves
        wr_text, sc_text, cands = "--%", "--", []
        curr = self.controller.current_move
        
        if moves and curr < len(moves):
            d = moves[curr]
            if d:
                wr_text = f"{d.get('winrate_black', 0.5):.1%}"
                sc_text = f"{d.get('score_lead_black', 0.0):.1f}"
                cands = d.get('candidates', [])
        
        self.info_view.update_stats(wr_text, sc_text, "")
        self.lbl_counter.config(text=f"{curr} / {self.game.total_moves}")
        
        if moves:
            wrs = [m.get('winrate_black', 0.5) if m else 0.5 for m in moves]
            self.info_view.update_graph(wrs, curr)

        self.board_view.update_board(img, self.info_view.review_mode.get(), cands)

    def generate_commentary(self):
        if not self.gemini: return
        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        self.executor.submit(self._run_commentary_task)

    def _run_commentary_task(self):
        try:
            curr = self.controller.current_move
            h = self.game.get_history_up_to(curr)
            
            # 1. 解説生成
            text = self.gemini.generate_commentary(curr, h, self.game.board_size)
            
            # 2. 緊急度解析
            urgency_data = self.controller.api_client.analyze_urgency(h, self.game.board_size)
            
            rec_path = None
            thr_path = None
            
            if urgency_data:
                # SimulationContextの構築
                curr_ctx = self.simulator.reconstruct_to_context(h, self.game.board_size)
                
                # 成功図（最善進行）の生成
                best_pv = urgency_data.get("best_pv", [])
                if best_pv:
                    rec_ctx = self.simulator.simulate_sequence(curr_ctx, best_pv)
                    rec_path, _ = self.visualizer.visualize_context(rec_ctx, title="AI Recommended Success Plan")
                
                # 失敗図（放置被害）の生成 - 緊急時のみ
                if urgency_data.get("is_critical"):
                    opp_pv = urgency_data.get("opponent_pv", [])
                    if opp_pv:
                        thr_seq = ["pass"] + opp_pv
                        thr_ctx = self.simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=urgency_data['next_player'])
                        title = f"Future Threat Diagram (Potential Loss: {urgency_data['urgency']:.1f})"
                        thr_path, _ = self.visualizer.visualize_context(thr_ctx, title=title)

            # 3. UIへの反映（非同期）
            self.root.after(0, lambda: self._update_commentary_ui(text))
            
            if rec_path:
                self.root.after(0, lambda: self._show_image_popup("AI Recommended Plan", rec_path))
            
            if thr_path:
                # 少し遅らせて表示
                self.root.after(200, lambda: self._show_image_popup("WARNING: Future Threat", thr_path))
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            err_msg = str(e)
            self.root.after(0, lambda: self._update_commentary_ui(f"Error: {err_msg}"))

    def _update_commentary_ui(self, text):
        self.info_view.set_commentary(text)
        self.info_view.btn_comment.config(state="normal", text="Ask AI Agent")

    def generate_full_report(self):
        if not self.report_generator: return
        self.info_view.btn_report.config(state="disabled", text="Generating...")
        self.executor.submit(self._run_report_task)

    def _run_report_task(self):
        try:
            path, err = self.report_generator.generate(self.controller.current_sgf_name, self.controller.image_dir)
            msg = err if err else f"PDFレポートを生成しました:\n{path}"
            self.root.after(0, lambda: messagebox.showinfo("Done", msg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.info_view.btn_report.config(state="normal", text="対局レポートを生成"))

    def show_pv(self):
        curr = self.controller.current_move
        if curr < len(self.game.moves):
            d = self.game.moves[curr]
            if d:
                cands = d.get('candidates', []) or d.get('top_candidates', [])
                if cands and 'pv' in cands[0]:
                    self._show_pv_window("Variation", cands[0]['pv'])

    def _show_pv_window(self, title, pv_list):
        top = tk.Toplevel(self.root); top.title(title)
        curr = self.controller.current_move
        board = self.game.get_board_at(curr)
        start_color = "W" if (curr % 2 != 0) else "B"
        img = self.renderer.render_pv(board, pv_list, starting_color=start_color, title=title)
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img)
        cv = tk.Canvas(top, bg="#333", width=img.width, height=img.height)
        cv.pack(fill=tk.BOTH, expand=True)
        cv.create_image(0, 0, image=photo, anchor=tk.NW); cv.image = photo

    def click_on_board(self, event):
        if not self.info_view.edit_mode.get(): return
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            color = "B" if (self.controller.current_move % 2 == 0) else "W"
            self.play_interactive_move(color, res[0], res[1])

    def pass_move(self):
        if not self.info_view.edit_mode.get(): return
        color = "B" if (self.controller.current_move % 2 == 0) else "W"
        self.play_interactive_move(color, None, None)

    def play_interactive_move(self, color, row, col):
        self.info_view.btn_comment.config(state="disabled", text="Analyzing...")
        def run():
            try:
                curr = self.controller.current_move
                if not self.game.add_move(curr, color, row, col): return
                new_idx = curr + 1
                history = self.game.get_history_up_to(new_idx)
                res = self.controller.api_client.analyze_move(history, self.game.board_size)
                if res:
                    new_data = {"winrate_black": res.get('winrate_black', 0.5), "score_lead_black": res.get('score_lead_black', 0.0), "candidates": []}
                    self.game.moves = self.game.moves[:new_idx]
                    self.game.moves.append(new_data)
                    self.root.after(0, lambda: self.show_image(new_idx))
            except Exception as e: print(f"Interactive Move Error: {e}")
            finally: self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask AI Agent"))
        self.executor.submit(run)

    def prev_move(self):
        if self.controller.prev_move(): self.update_display()
    def next_move(self):
        if self.controller.next_move(): self.update_display()
    def on_resize(self, event):
        if self.controller.image_cache: self.update_display()
        def goto_mistake(self, color, idx):
            m = self.moves_m_b[idx] if color == "b" else self.moves_m_w[idx]
            if m is not None: self.show_image(m)
    
            def on_level_change(self, new_level):
    
                """解説ターゲットレベルを動的に変更する"""
    
                config.TARGET_LEVEL = new_level
    
                print(f"Commentary Mode changed to: {new_level}")
    
        
    
            def on_close(self):
    
                self.analysis_manager.stop_analysis()
    
                self.executor.shutdown(wait=False)
    
                self.root.destroy()
    
        
