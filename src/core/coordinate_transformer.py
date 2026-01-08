class CoordinateTransformer:
    def __init__(self, board_size=19, image_size=850, margin=70):
        self.board_size = board_size
        self.image_size = image_size
        self.margin = margin
        self.grid_size = (self.image_size - 2 * self.margin) // (self.board_size - 1)

    def gtp_to_indices(self, vertex):
        """GTP形式 (Q16など) を (row, col) インデックスに変換"""
        if not vertex or vertex.lower() == "pass":
            return None
        col_str = vertex[0].upper()
        cols = "ABCDEFGHJKLMNOPQRST"
        col = cols.find(col_str)
        try:
            row = int(vertex[1:]) - 1
            return row, col
        except:
            return None

    def indices_to_gtp(self, row, col):
        """(row, col) インデックスを GTP形式 (Q16など) に変換"""
        cols = "ABCDEFGHJKLMNOPQRST"
        if 0 <= col < len(cols):
            return f"{cols[col]}{row + 1}"
        return "pass"

    def indices_to_pixel(self, row, col):
        """(row, col) インデックスを画像上の (x, y) ピクセル座標に変換"""
        visual_row = self.board_size - 1 - row
        x = self.margin + col * self.grid_size
        y = self.margin + visual_row * self.grid_size
        return x, y

    def pixel_to_indices(self, x, y, canvas_width, canvas_height):
        """キャンバス上のクリック位置を (row, col) インデックスに変換"""
        # 画像の実サイズは (850, 950) なので、高さを補正して比率を計算
        actual_height = self.image_size + 100
        ratio = min(canvas_width / self.image_size, canvas_height / actual_height)
        
        ox = (canvas_width - self.image_size * ratio) // 2
        oy = (canvas_height - actual_height * ratio) // 2
        
        rel_x = (x - ox) / ratio
        rel_y = (y - oy) / ratio
        
        # 碁盤領域 (850x850) の中での相対位置で判定
        col = round((rel_x - self.margin) / self.grid_size)
        visual_row = round((rel_y - self.margin) / self.grid_size)
        row = self.board_size - 1 - visual_row
        
        if 0 <= col < self.board_size and 0 <= row < self.board_size:
            return row, col
        return None
