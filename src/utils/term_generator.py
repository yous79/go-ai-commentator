import sys
import os

# プロジェクトルートをパスに追加
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from sgfmill import boards
from utils.board_renderer import GoBoardRenderer

class TermGenerator:
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
        return self._save(board, target, f"{'黒' if color=='b' else '白'}のハネ", f"hane_{color}.png", output_dir)

    def generate_atari_basic(self, color='b', output_dir="output_terms"):
        """基本：中央でのアタリ"""
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        board.play(c, c, opp)
        board.play(c+1, c, color); board.play(c-1, c, color)
        target = (c, c+1)
        board.play(*target, color)
        text = f"アタリ (中央): ダメが残り1つ (座標 {self.cols[c-1]}{c+1})"
        return self._save(board, target, text, f"atari_basic_{color}.png", output_dir)

    def generate_atari_edge(self, color='b', output_dir="output_terms"):
        """バリエーション1：1線（端）でのアタリ"""
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        # 1線(端)に相手の石を置く
        board.play(0, 4, opp)
        # 端なので、2方向を塞げばアタリになる
        board.play(0, 3, color)
        target = (1, 4)
        board.play(*target, color)
        text = "アタリ (端): 盤面の端を利用してダメを1つにする"
        return self._save(board, target, text, f"atari_edge_{color}.png", output_dir)

    def generate_atari_group(self, color='b', output_dir="output_terms"):
        """バリエーション2：複数の石（連）へのアタリ"""
        board = boards.Board(self.board_size)
        opp = 'w' if color == 'b' else 'b'
        c = self.board_size // 2
        # 相手の石が2つ並んでいる (4, 4) と (4, 5)
        board.play(c, c, opp)
        board.play(c, c+1, opp)
        
        # 周囲のダメを5箇所埋める (合計6箇所のうち5箇所)
        # (3, 4), (3, 5), (5, 4), (5, 5), (4, 3), (4, 6)
        surrounds = [(c-1, c), (c-1, c+1), (c+1, c), (c+1, c+1), (c, c-1)]
        for r, col_idx in surrounds:
            board.play(r, col_idx, color)
            
        # 最後のダメ (c, c+2) が空いている状態で、
        # アタリを確定させた最後の一手 (c, c-1) を強調表示する
        # ※surroundsの最後 (c, c-1) が target に相当する
        target = (c, c-1)
        
        text = "アタリ (連): 複数の石の共通ダメが残り1つの状態"
        return self._save(board, target, text, f"atari_group_{color}.png", output_dir)

if __name__ == "__main__":
    gen = TermGenerator(9)
    for color in ['b', 'w']:
        gen.generate_tsuke(color)
        gen.generate_nobi(color)
        gen.generate_hane(color)
        gen.generate_atari_basic(color)
        gen.generate_atari_edge(color)
        gen.generate_atari_group(color)
    print(f"Generated Atari patterns in {os.path.abspath('output_terms')}")