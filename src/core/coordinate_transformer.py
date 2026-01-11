class CoordinateTransformer:
    # 共通の列定義 (Iを除去)
    COLS = "ABCDEFGHJKLMNOPQRST"

    def __init__(self, board_size=19, image_size=850, margin=70):
        self.board_size = board_size
        self.image_size = image_size
        self.margin = margin
        self.grid_size = (self.image_size - 2 * self.margin) // (self.board_size - 1)

    @staticmethod
    def gtp_to_indices_static(vertex):
        """GTP形式 (Q16など) を (row, col) インデックスに変換 (static)"""
        if not vertex or vertex.lower() == "pass":
            return None
        col_str = vertex[0].upper()
        col = CoordinateTransformer.COLS.find(col_str)
        try:
            row = int(vertex[1:]) - 1
            if col == -1: return None
            return row, col
        except:
            return None

    @staticmethod
    def indices_to_gtp_static(row, col):
        """(row, col) インデックスを GTP形式 (Q16など) に変換 (static)"""
        if 0 <= col < len(CoordinateTransformer.COLS):
            return f"{CoordinateTransformer.COLS[col]}{row + 1}"
        return "pass"

    def gtp_to_indices(self, vertex):
        return self.gtp_to_indices_static(vertex)

    def indices_to_gtp(self, row, col):
        return self.indices_to_gtp_static(row, col)

    def indices_to_pixel(self, row, col):
        """(row, col) インデックスを画像上の (x, y) ピクセル座標に変換"""
        visual_row = self.board_size - 1 - row
        x = self.margin + col * self.grid_size
        y = self.margin + visual_row * self.grid_size
        return x, y

    def pixel_to_indices(self, x, y, canvas_width, canvas_height):
        """キャンバス上のクリック位置を (row, col) インデックスに変換"""
        actual_height = self.image_size + 100
        ratio = min(canvas_width / self.image_size, canvas_height / actual_height)
        
        ox = (canvas_width - self.image_size * ratio) // 2
        oy = (canvas_height - actual_height * ratio) // 2
        
        rel_x = (x - ox) / ratio
        rel_y = (y - oy) / ratio
        
        col = round((rel_x - self.margin) / self.grid_size)
        visual_row = round((rel_y - self.margin) / self.grid_size)
        row = self.board_size - 1 - visual_row
        
        if 0 <= col < self.board_size and 0 <= row < self.board_size:
            return row, col
        return None