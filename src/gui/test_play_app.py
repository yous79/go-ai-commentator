import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk
import os

from core.game_state import GoGameState
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from gui.board_view import BoardView

class TestPlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Go Test Play (No Analysis)")
        self.root.geometry("900x950")

        # Core Modules
        self.game = GoGameState()
        self.game.new_game(19) # Default 19x19
        self.transformer = CoordinateTransformer(19)
        self.renderer = GoBoardRenderer(19)

        # UI State
        self.current_move = 0
        self.show_numbers = tk.BooleanVar(value=True)
        self.is_review_mode = tk.BooleanVar(value=False)
        self.current_tool = tk.StringVar(value="stone") # Tool: stone, square, triangle, cross
        
        # Review State
        self.review_stones = [] # List of ((r, c), color, number)

        self.setup_layout()
        
        # Global Bindings
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        
        self.update_display()

    def setup_layout(self):
        # Top Controls
        top_frame = tk.Frame(self.root, bg="#ddd", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(top_frame, text="Board Size:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        for size in [9, 13, 19]:
            btn = tk.Button(top_frame, text=f"{size}x{size}", command=lambda s=size: self.reset_game(s), width=8)
            btn.pack(side=tk.LEFT, padx=5)

        # Tool Selection
        tk.Label(top_frame, text="Tools:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        tools = [("Stone", "stone"), ("□", "square"), ("△", "triangle"), ("×", "cross")]
        for label, mode in tools:
            rb = tk.Radiobutton(top_frame, text=label, variable=self.current_tool, value=mode, 
                                indicatoron=0, width=6, bg="#ccc", selectcolor="#aaa")
            rb.pack(side=tk.LEFT, padx=2)

        # Review Toggle
        self.btn_review = tk.Checkbutton(top_frame, text="Review Mode (1,2,3...)", variable=self.is_review_mode, 
                                         command=self.toggle_review_mode, bg="#ffc107", indicatoron=0, width=18)
        self.btn_review.pack(side=tk.RIGHT, padx=10)

        tk.Checkbutton(top_frame, text="Show Numbers", variable=self.show_numbers, 
                       command=self.update_display, bg="#ddd").pack(side=tk.RIGHT, padx=10)

        # Main Board
        self.board_view = BoardView(self.root, self.transformer)
        self.board_view.pack(fill=tk.BOTH, expand=True)
        self.board_view.bind_click(self.click_on_board)

        # Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#eee", height=60)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_info = tk.Label(bot_frame, text="Move: 0 | Turn: Black", font=("Arial", 12, "bold"), bg="#eee")
        self.lbl_info.pack(pady=10, side=tk.LEFT, padx=20)
        
        tk.Button(bot_frame, text="Clear Review", command=self.clear_review, width=12, bg="#f44336", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="Pass", command=self.pass_move, width=10, bg="#607D8B", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="< Undo", command=self.undo_move, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(bot_frame, text="Save Image", command=self.save_image, width=12, bg="#4CAF50", fg="white").pack(side=tk.RIGHT, padx=20)

    def toggle_review_mode(self):
        if not self.is_review_mode.get():
            if self.review_stones and messagebox.askyesno("Review", "検討手順をクリアしますか？"):
                self.clear_review()
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
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile=f"review_board_{self.current_move}.png",
            title="Save Board Image"
        )
        if file_path:
            try:
                img.save(file_path)
                messagebox.showinfo("Success", f"画像を保存しました:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"保存に失敗しました: {e}")

    def reset_game(self, size):
        if self.game.total_moves > 0 or self.review_stones:
            if not messagebox.askyesno("Reset", "現在の対局を破棄して新しく開始しますか？"):
                return
        
        self.game.new_game(size)
        self.transformer = CoordinateTransformer(size)
        self.board_view.transformer = self.transformer
        self.renderer = GoBoardRenderer(size)
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
                # Review Mode: Add to temporary list with number
                color = "B" if ((self.current_move + len(self.review_stones)) % 2 == 0) else "W"
                # Check if already occupied
                if any(s[0] == (row, col) for s in self.review_stones): return
                
                num = len(self.review_stones) + 1
                self.review_stones.append(((row, col), color, num))
                self.update_display()
                return

            if tool == "stone":
                color = "B" if (self.current_move % 2 == 0) else "W"
                self.play_move(color, row, col)
            else:
                success = self.game.toggle_mark(self.current_move, row, col, tool)
                self.update_display()

    def pass_move(self):
        if self.is_review_mode.get():
            # In review mode, just skip a number? Usually not needed but for consistency:
            color = "B" if ((self.current_move + len(self.review_stones)) % 2 == 0) else "W"
            # We don't add passes to review_stones visualization but we need to flip color
            # For simplicity, review mode assumes consecutive stones
            return

        color = "B" if (self.current_move % 2 == 0) else "W"
        self.play_move(color, None, None)

    def play_move(self, color, row, col):
        success = self.game.add_move(self.current_move, color, row, col)
        if success:
            self.current_move += 1
            self.update_display()

    def undo_move(self):
        if self.is_review_mode.get() and self.review_stones:
            self.review_stones.pop()
            self.update_display()
            return

        if self.current_move > 0:
            self.current_move -= 1
            self.update_display()

    def prev_move(self, event=None):
        if self.current_move > 0:
            self.current_move -= 1
            self.update_display()

    def next_move(self, event=None):
        if self.current_move < self.game.total_moves:
            self.current_move += 1
            self.update_display()

    def update_display(self):
        board = self.game.get_board_at(self.current_move)
        marks = self.game.get_marks_at(self.current_move)
        history = self.game.get_history_up_to(self.current_move)

        turn_idx = self.current_move + (len(self.review_stones) if self.is_review_mode.get() else 0)
        turn_color = "Black" if (turn_idx % 2 == 0) else "White"
        
        info_text = f"Move {self.current_move} | Turn: {turn_color}"
        if self.is_review_mode.get():
            info_text += f" (Review Step: {len(self.review_stones)})"

        img = self.renderer.render(board, last_move=None, analysis_text=info_text, 
                                   history=history, show_numbers=self.show_numbers.get(),
                                   marks=marks, review_stones=self.review_stones)
        
        self.board_view.update_board(img)
        self.lbl_info.config(text=info_text)