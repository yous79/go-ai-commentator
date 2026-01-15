import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageTk
import os
import sys

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
import concurrent.futures

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
        self.is_review_mode = tk.BooleanVar(value=False)
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
        top_frame = tk.Frame(self.root, bg="#ddd", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        # ... (rest of size/tools setup same)
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.pack(fill=tk.BOTH, expand=True)
        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=750)
        self.board_view.bind_click(self.click_on_board)
        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)
        # ... (bottom bar omitted for brevity, logic remains)

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
        # Add review stones to history for commentary
        for (r, c), color, n in self.review_stones:
            h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        def run():
            text = self.gemini.generate_commentary(len(h), h, self.game.board_size)
            self.root.after(0, lambda: self.info_view.set_commentary(text))
            self.root.after(0, lambda: self.info_view.btn_comment.config(state="normal", text="Ask AI Agent"))
        self.executor.submit(run)
        
        # 3. Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#eee", height=60)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_info = tk.Label(bot_frame, text="Move: 0 | Turn: Black", font=("Arial", 12, "bold"), bg="#eee")
        self.lbl_info.pack(pady=10, side=tk.LEFT, padx=20)
        
        self.btn_review = tk.Checkbutton(bot_frame, text="Review Mode", variable=self.is_review_mode, 
                                         command=self.toggle_review_mode, bg="#ffc107", indicatoron=0, width=15)
        self.btn_review.pack(side=tk.RIGHT, padx=10)
        
        tk.Button(bot_frame, text="Clear Review", command=self.clear_review, width=12, bg="#f44336", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="Pass", command=self.pass_move, width=10, bg="#607D8B", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="< Undo", command=self.undo_move, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(bot_frame, text="Save Image", command=self.save_image, width=12, bg="#4CAF50", fg="white").pack(side=tk.RIGHT, padx=20)

    def toggle_review_mode(self):
        if not self.is_review_mode.get():
            if self.review_stones: self.clear_review()
        self.update_display()

    def clear_review(self):
        self.review_stones = []
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

    def reset_game(self, size):
        if self.game.total_moves > 0 and not messagebox.askyesno("Reset", "New Game?"): return
        self.game.new_game(size)
        self.transformer = CoordinateTransformer(size)
        self.board_view.transformer = self.transformer
        self.renderer = GoBoardRenderer(size)
        self.detector = ShapeDetector(size)
        self.current_move = 0
        self.review_stones = []
        self.update_display()

    def click_on_board(self, event):
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            row, col = res
            tool = self.current_tool.get()
            if self.is_review_mode.get() and tool == "stone":
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

    def undo_move(self):
        if self.is_review_mode.get() and self.review_stones:
            self.review_stones.pop(); self.update_display(); return
        if self.current_move > 0:
            self.current_move -= 1; self.update_display()

    def prev_move(self, event=None):
        if self.current_move > 0: self.current_move -= 1; self.update_display()
    def next_move(self, event=None):
        if self.current_move < self.game.total_moves: self.current_move += 1; self.update_display()

    def update_display(self):
        board = self.game.get_board_at(self.current_move)
        history = self.game.get_history_up_to(self.current_move)
        turn_color = "Black" if (self.current_move % 2 == 0) else "White"
        info_text = f"Move {self.current_move} | Turn: {turn_color}"
        
        # 1. Render Board
        img = self.renderer.render(board, last_move=None, analysis_text=info_text, 
                                   history=history, show_numbers=self.show_numbers.get(),
                                   marks=self.game.get_marks_at(self.current_move),
                                   review_stones=self.review_stones)
        self.board_view.update_board(img)
        self.lbl_info.config(text=info_text)

        # 2. Shape Detection (Real-time)
        # Construct combined history for detection including review stones
        combined_h = list(history)
        if self.is_review_mode.get():
            for (r, c), color, n in self.review_stones:
                from core.coordinate_transformer import CoordinateTransformer
                combined_h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        # Use simulator to get clean board states for detector
        try:
            curr_b, prev_b, last_c = self.simulator.reconstruct(combined_h)
            facts = self.detector.detect_all(curr_b, prev_b, last_c)
            self.txt_shapes.delete("1.0", tk.END)
            self.txt_shapes.insert(tk.END, facts if facts else "特筆すべき形状は検出されませんでした。")
        except Exception as e:
            self.txt_shapes.delete("1.0", tk.END)
            self.txt_shapes.insert(tk.END, f"Detection Error: {e}")

