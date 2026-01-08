import tkinter as tk
from PIL import Image, ImageTk

class BoardView(tk.Frame):
    def __init__(self, master, transformer):
        super().__init__(master, bg="#333")
        self.transformer = transformer
        self.canvas = tk.Canvas(self, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.current_photo = None

    def bind_click(self, callback):
        self.canvas.bind("<Button-1>", callback)

    def update_board(self, pil_image, review_mode=False, candidates=None):
        cw, ch = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        
        # PIL image already has the status bar (e.g., 850x950)
        img_w, img_h = pil_image.size
        
        # Resize image to fit canvas while preserving aspect ratio
        ratio = min(cw / img_w, ch / img_h)
        nw, nh = int(img_w * ratio), int(img_h * ratio)
        res = pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
        
        self.current_photo = ImageTk.PhotoImage(res)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.current_photo, anchor=tk.CENTER)
        
        if review_mode and candidates:
            # Overlays need to know the board-only area (excluding status bar)
            ox, oy = (cw - nw)//2, (ch - nh)//2
            self._draw_overlays(candidates, nw, nh, ox, oy)

    def _draw_overlays(self, candidates, nw, nh, ox, oy):
        # Re-use coordinate conversion from transformer
        br = 850 / 950 # Aspect adjustment
        for i, c in enumerate(candidates[:3]):
            move_str = c['move']
            idx_pair = self.transformer.gtp_to_indices(move_str)
            if not idx_pair: continue
            
            # Use transformer to get normalized coordinates
            px, py = self.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
            
            # Scale to current canvas size
            fx = ox + (px / self.transformer.image_size) * nw
            fy = oy + (py / self.transformer.image_size) * (nh * br)
            
            rad = (nw / self.transformer.board_size) * 0.6
            color = "#00ff00" if i == 0 else "#00aaff"
            self.canvas.create_oval(fx-rad, fy-rad, fx+rad, fy+rad, fill=color, outline=color, tags="overlay")
            
            # Winrate text
            wr = c.get('winrate_black', c.get('winrate', 0))
            self.canvas.create_text(fx, fy, text=f"{wr:.0%}", fill="black", 
                                   font=("Arial", int(rad), "bold"), tags="overlay")
