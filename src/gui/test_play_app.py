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

        self.setup_layout()
        self.update_display()

    def setup_layout(self):
        # Top Controls
        top_frame = tk.Frame(self.root, bg="#ddd", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(top_frame, text="Board Size:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        for size in [9, 13, 19]:
            btn = tk.Button(top_frame, text=f"{size}x{size}", command=lambda s=size: self.reset_game(s), width=8)
            btn.pack(side=tk.LEFT, padx=5)

        # Main Board
        self.board_view = BoardView(self.root, self.transformer)
        self.board_view.pack(fill=tk.BOTH, expand=True)
        self.board_view.bind_click(self.click_on_board)

        # Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#eee", height=60)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_info = tk.Label(bot_frame, text="Move: 0 | Turn: Black", font=("Arial", 12, "bold"), bg="#eee")
        self.lbl_info.pack(pady=10, side=tk.LEFT, padx=20)
        
        tk.Button(bot_frame, text="Pass", command=self.pass_move, width=10, bg="#607D8B", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="< Undo", command=self.undo_move, width=10).pack(side=tk.RIGHT, padx=5)

    def reset_game(self, size):
        if self.game.total_moves > 0:
            if not messagebox.askyesno("Reset", "現在の対局を破棄して新しく開始しますか？"):
                return
        
        self.game.new_game(size)
        self.transformer = CoordinateTransformer(size)
        self.board_view.transformer = self.transformer
        self.renderer = GoBoardRenderer(size)
        self.current_move = 0
        self.update_display()

    def click_on_board(self, event):
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch)
        if res:
            row, col = res
            color = "B" if (self.current_move % 2 == 0) else "W"
            self.play_move(color, row, col)

    def pass_move(self):
        color = "B" if (self.current_move % 2 == 0) else "W"
        self.play_move(color, None, None)

    def play_move(self, color, row, col):
        # Add to SGF tree
        success = self.game.add_move(self.current_move, color, row, col)
        if success:
            self.current_move += 1
            self.update_display()

    def undo_move(self):
        if self.current_move > 0:
            self.current_move -= 1
            # Note: For simplicity, we just stay at the previous node.
            # In a full app, we might want to prune the branch.
            self.update_display()

    def update_display(self):
        # 1. Get Board State
        board = self.game.get_board_at(self.current_move)
        
        # 2. Get Last Move for highlight
        last_move = None
        history = self.game.get_history_up_to(self.current_move)
        if history:
            last_m_data = history[-1]
            color_str, gtp = last_m_data[0], last_m_data[1]
            indices = self.transformer.gtp_to_indices(gtp)
            if indices:
                last_move = (color_str.lower(), indices)

        # 3. Render Image
        turn_color = "Black" if (self.current_move % 2 == 0) else "White"
        info_text = f"Move {self.current_move} | Turn: {turn_color}"
        img = self.renderer.render(board, last_move=last_move, analysis_text=info_text)
        
        # 4. Update View
        self.board_view.update_board(img)
        self.lbl_info.config(text=info_text)
