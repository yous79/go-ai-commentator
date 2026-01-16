import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageTk
import os
import sys
import concurrent.futures

from core.game_state import GoGameState
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from gui.board_view import BoardView
from gui.info_view import InfoView
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
from core.knowledge_manager import KnowledgeManager
from services.term_visualizer import TermVisualizer
from config import KNOWLEDGE_DIR, load_api_key
from services.ai_commentator import GeminiCommentator
from gui.controller import AppController

class TestPlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go Test Play & Shape Detection Debugger (Rev 26.0)")
        self.root.geometry("1200x950")

        # Core Modules
        self.game = GoGameState()
        self.game.new_game(19)
        self.controller = AppController(self.game)
        self.transformer = CoordinateTransformer(19)
        self.renderer = GoBoardRenderer(19)
        self.detector = ShapeDetector(19)
        self.simulator = BoardSimulator()
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.visualizer = TermVisualizer()
        self.gemini = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # UI State
        self.current_move = 0
        self.show_numbers = tk.BooleanVar(value=True)
        self.current_tool = tk.StringVar(value="stone")
        self.review_stones = []

        self._init_ai()

        callbacks = {
            'comment': self.generate_commentary,
            'report': lambda: messagebox.showinfo("Info", "Report not supported in debug mode"),
            'show_pv': lambda: None,
            'goto': lambda c, i: None,
            'pass': self.pass_move,
            'update_display': self.update_display,
            'on_term_select': self.on_term_select,
            'visualize_term': self.visualize_term
        }

        self.setup_layout(callbacks)
        self._load_dictionary_terms()
        self.update_display()

    def _init_ai(self):
        api_key = load_api_key()
        if api_key:
            self.gemini = GeminiCommentator(api_key)

    def setup_layout(self, callbacks):
        # 1. Top Frame
        top_frame = tk.Frame(self.root, bg="#ddd", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(top_frame, text="Board Size:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        for size in [9, 13, 19]:
            btn = tk.Button(top_frame, text=f"{size}x{size}", command=lambda s=size: self.reset_game(s), width=8)
            btn.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="Tools:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        tools = [("Stone", "stone"), ("□", "square"), ("△", "triangle"), ("×", "cross")]
        for label, mode in tools:
            rb = tk.Radiobutton(top_frame, text=label, variable=self.current_tool, value=mode, 
                                indicatoron=0, width=6, bg="#ccc", selectcolor="#aaa")
            rb.pack(side=tk.LEFT, padx=2)

        tk.Checkbutton(top_frame, text="Show Numbers", variable=self.show_numbers, 
                       command=self.update_display, bg="#ddd").pack(side=tk.RIGHT, padx=10)

        # 2. Main Content
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=750)
        self.board_view.bind_click(self.click_on_board)

        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)

        # 3. Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#eee", height=60)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        tk.Button(bot_frame, text="Clear Review", command=self.clear_review, width=12, bg="#f44336", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="Pass", command=self.pass_move, width=10, bg="#607D8B", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="< Undo", command=self.undo_move, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(bot_frame, text="Save Image", command=self.save_image, width=12, bg="#4CAF50", fg="white").pack(side=tk.RIGHT, padx=20)

    def _load_dictionary_terms(self):
        terms = []
        for cat in self.knowledge_manager.index.values():
            for item in cat.values(): terms.append(item.title)
        self.info_view.set_terms_list(sorted(terms))

    def on_term_select(self, term_title):
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    desc = getattr(item, 'full_content', "")
                    self.info_view.set_term_details(f"【{item.title}】\n\n{desc}")
                    return

    def visualize_term(self, term_title):
        term_id = None
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title: term_id = item.id; break
        if term_id:
            path, err = self.visualizer.visualize(term_id)
            if path: self._show_image_popup(term_title, path)

    def _show_image_popup(self, title, image_path):
        from PIL import Image, ImageTk
        top = tk.Toplevel(self.root); top.title(f"Example: {title}")
        img = Image.open(image_path); img.thumbnail((600, 600))
        photo = ImageTk.PhotoImage(img); lbl = tk.Label(top, image=photo); lbl.image = photo; lbl.pack(padx=10, pady=10)

    def generate_commentary(self):
        if not self.gemini: return
        h = list(self.game.get_history_up_to(self.current_move))
        for (r, c), color, n in self.review_stones:
            h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        def run():
            try:
                # 1. AI解説生成
                text = self.gemini.generate_commentary(len(h), h, self.game.board_size)
                
                # 2. 緊急度チェックと参考図生成
                from services.api_client import api_client
                urgency_data = api_client.analyze_urgency(h, self.game.board_size)
                
                rec_path = None
                thr_path = None
                
                if urgency_data:
                    # 手番の決定
                    last_color = h[-1][0] if h else "W"
                    next_color = "W" if last_color == "B" else "B"

                    # 推奨図
                    best_pv = urgency_data.get("best_pv", [])
                    if best_pv:
                        rec_path, _ = self.visualizer.visualize_sequence(h, best_pv, title="Recommended Plan", 
                                                                         board_size=self.game.board_size,
                                                                         starting_color=next_color)
                    
                    # 失敗図
                    if urgency_data.get("is_critical"):
                        opp_pv = urgency_data.get("opponent_pv", [])
                        if opp_pv:
                            thr_seq = ["pass"] + opp_pv
                            title = f"Future Threat (Loss: {urgency_data['urgency']:.1f})"
                            thr_path, _ = self.visualizer.visualize_sequence(h, thr_seq, title=title, 
                                                                             board_size=self.game.board_size,
                                                                             starting_color=next_color)

                self.root.after(0, lambda: self.info_view.set_commentary(text))
                if rec_path:
                    self.root.after(0, lambda: self._show_image_popup("AI Recommended Plan", rec_path))
                if thr_path:
                    self.root.after(200, lambda: self._show_image_popup("WARNING: Future Threat", thr_path))
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_msg = str(e)
                self.root.after(0, lambda: self.info_view.set_commentary(f"Error: {err_msg}"))
            finally:
                self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask AI Agent"))
        self.executor.submit(run)

    def reset_game(self, size):
        self.game.new_game(size)
        self.transformer = CoordinateTransformer(size)
        self.board_view.transformer = self.transformer
        self.renderer = GoBoardRenderer(size)
        self.detector = ShapeDetector(size)
        self.current_move = 0
        self.review_stones = []
        self.update_display()

    def clear_review(self):
        self.review_stones = []
        self.update_display()

    def undo_move(self):
        if self.info_view.edit_mode.get() and self.review_stones:
            self.review_stones.pop(); self.update_display(); return
        if self.current_move > 0:
            self.current_move -= 1; self.update_display()

    def prev_move(self, event=None):
        if self.current_move > 0: self.current_move -= 1; self.update_display()
    def next_move(self, event=None):
        if self.current_move < self.game.total_moves: self.current_move += 1; self.update_display()

    def click_on_board(self, event):
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            row, col = res
            tool = self.current_tool.get()
            if self.info_view.edit_mode.get() and tool == "stone":
                color = "B" if ((self.current_move + len(self.review_stones)) % 2 == 0) else "W"
                if not any(s[0] == (row, col) for s in self.review_stones):
                    self.review_stones.append(((row, col), color, len(self.review_stones) + 1))
                    self.update_display()
                return
            if tool == "stone":
                color = "B" if (self.current_move % 2 == 0) else "W"
                if self.game.add_move(self.current_move, color, row, col):
                    self.current_move += 1
                    self.update_display()
            else:
                self.game.toggle_mark(self.current_move, row, col, tool)
                self.update_display()

    def pass_move(self):
        color = "B" if (self.current_move % 2 == 0) else "W"
        if self.game.add_move(self.current_move, color, None, None):
            self.current_move += 1
            self.update_display()

    def save_image(self):
        from tkinter import filedialog
        board = self.game.get_board_at(self.current_move)
        history = self.game.get_history_up_to(self.current_move)
        img = self.renderer.render(board, last_move=None, analysis_text="", 
                                   history=history, show_numbers=self.show_numbers.get(),
                                   marks=self.game.get_marks_at(self.current_move),
                                   review_stones=self.review_stones)
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path: img.save(file_path)

    def update_display(self):
        board = self.game.get_board_at(self.current_move)
        history = self.game.get_history_up_to(self.current_move)
        turn_color = "Black" if (self.current_move % 2 == 0) else "White"
        info_text = f"Move {self.current_move} | Turn: {turn_color}"
        
        img = self.renderer.render(board, last_move=None, analysis_text=info_text, 
                                   history=history, show_numbers=self.show_numbers.get(),
                                   marks=self.game.get_marks_at(self.current_move),
                                   review_stones=self.review_stones)
        self.board_view.update_board(img)

        combined_h = list(history)
        if self.info_view.edit_mode.get():
            for (r, c), color, n in self.review_stones:
                combined_h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        try:
            curr_b, prev_b, last_c = self.simulator.reconstruct(combined_h)
            facts = self.detector.detect_all(curr_b, prev_b, last_c)
            self.info_view.set_facts(facts)
        except Exception as e:
            self.info_view.set_facts(f"Detection Error: {e}")