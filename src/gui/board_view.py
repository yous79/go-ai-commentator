import tkinter as tk
from PIL import Image, ImageTk
from utils.event_bus import event_bus, AppEvents

class BoardView(tk.Frame):
    def __init__(self, master, transformer):
        super().__init__(master, bg="#333")
        self.transformer = transformer
        self.canvas = tk.Canvas(self, bg="#333", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # イベント購読
        event_bus.subscribe(AppEvents.BOARD_REDRAW_REQUESTED, self._on_redraw_requested)

    def _on_redraw_requested(self, data):
        """外部（App等）からの再描画要求を処理する"""
        if not data: return
        image = data.get("image")
        show_candidates = data.get("show_candidates", False)
        candidates = data.get("candidates", [])
        
        if image:
            self.update_board(image, show_candidates, candidates)

    def bind_click(self, callback):
        self.canvas.bind("<Button-1>", callback)

    def bind_motion(self, callback):
        self.canvas.bind("<Motion>", callback)

    def update_board(self, image, show_candidates=False, candidates=None, **kwargs):
        self.original_image = image
        self.show_candidates = show_candidates
        self.candidates = candidates if candidates else []
        self.refresh_display()

    def refresh_display(self):
        if not hasattr(self, 'original_image') or self.original_image is None:
            return

        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10: 
            self.after(100, self.refresh_display)
            return

        try:
            # 1. Resize base image to fit canvas
            iw, ih = self.original_image.size
            ratio = min(cw / iw, ch / ih)
            nw, nh = int(iw * ratio), int(ih * ratio)
            
            resized_img = self.original_image.resize((nw, nh), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(resized_img)
        except Exception as e:
            # 画像が不完全な場合は更新をスキップ
            print(f"Skipping display update due to image loading error: {e}")
            return
        
        # 2. Draw on canvas
        self.canvas.delete("all")
        ox, oy = (cw - nw) // 2, (ch - nh) // 2
        self.canvas.create_image(ox, oy, image=self.current_photo, anchor=tk.NW)
        
        # 3. Draw candidates overlay
        if self.show_candidates and self.candidates:
            self._draw_overlays(self.candidates, nw, nh, ox, oy)

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
