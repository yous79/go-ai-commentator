import sys
import os

# プロジェクトルートをパスに追加
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from sgfmill import boards
from utils.board_renderer import GoBoardRenderer

class TermGenerator:
    """囲碁用語に基づいて盤面画像を生成するクラス"""
    
    def __init__(self, board_size=9, image_size=500):
        self.board_size = board_size
        self.renderer = GoBoardRenderer(board_size, image_size=image_size)
        self.cols = "ABCDEFGHJKLMNOPQRST"

    def _save(self, board, target_pos, text, filename, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        marks = {"SQ": [target_pos] if target_pos else []}
        img = self.renderer.render(board, analysis_text=text, marks=marks)
        path = os.path.join(output_dir, filename)
        img.save(path)
        return path

    def generate_tsuke(self, color='b', output_dir="output_terms"):
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        board.play(c, c, opp)
        target = (c, c + 1)
        board.play(*target, color)
        return self._save(board, target, f"{'黒' if color=='b' else '白'}のツケ", f"tsuke_{color}.png", output_dir)

    def generate_nobi(self, color='b', output_dir="output_terms"):
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        board.play(c, c, color)
        board.play(c + 1, c, opp)
        target = (c, c + 1)
        board.play(*target, color)
        return self._save(board, target, f"{'黒' if color=='b' else '白'}のノビ", f"nobi_{color}.png", output_dir)

    def generate_hane(self, color='b', output_dir="output_terms"):
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        board.play(c, c, color)
        board.play(c, c + 1, opp)
        target = (c + 1, c + 1)
        board.play(*target, color)
        return self._save(board, target, f"{'黒' if color=='b' else 'white' if color=='w' else ''}のハネ", f"hane_{color}.png", output_dir)

    def generate_atari_basic(self, color='b', output_dir="output_terms"):
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        board.play(c, c, opp)
        board.play(c+1, c, color); board.play(c-1, c, color)
        target = (c, c+1)
        board.play(*target, color)
        text = f"アタリ (中央): ダメが残り1つ"
        return self._save(board, target, text, f"atari_basic_{color}.png", output_dir)

    def generate_nimoku_no_atama(self, color='b', output_dir="output_terms"):
        """
        二目の頭をハネる: 互いに2石ずつ競り合っている状態から相手の頭を抑える
        """
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        
        # 相手の2石を並べる (D4, D5相当)
        board.play(c-1, c, opp)
        board.play(c, c, opp)
        
        # 自分の支えとなる2石を並べる (E4, E5相当)
        board.play(c-1, c+1, color)
        board.play(c, c+1, color)
        
        # 相手の「頭」をハネる決定打 (D6相当)
        target = (c+1, c)
        board.play(*target, color)
        
        c_name = "黒" if color == 'b' else "白"
        text = f"{c_name}が「二目の頭」をハネた形"
        return self._save(board, target, text, f"nimoku_no_atama_{color}.png", output_dir)

if __name__ == "__main__":
    gen = TermGenerator(9)
    for color in ['b', 'w']:
        gen.generate_tsuke(color)
        gen.generate_nobi(color)
        gen.generate_hane(color)
        gen.generate_atari_basic(color)
        gen.generate_nimoku_no_atama(color)
    print(f"Generated accurate 'Nimoku no Atama' in {os.path.abspath('output_terms')}")