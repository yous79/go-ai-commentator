import sys
import os

# プロジェクトのルートをパスに追加
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from core.shape_detector import ShapeDetector
from core.coordinate_transformer import CoordinateTransformer

import copy

class InteractiveBoard:
    def __init__(self, size=9):
        self.size = size
        self.board = [['.' for _ in range(size)] for _ in range(size)]
    
    def copy(self):
        new_ib = InteractiveBoard(self.size)
        new_ib.board = copy.deepcopy(self.board)
        return new_ib

    def set_stone(self, coord_str, char):
        indices = CoordinateTransformer.gtp_to_indices_static(coord_str)
        if indices:
            r, c = indices
            if 0 <= r < self.size and 0 <= c < self.size:
                self.board[r][c] = char.lower()
                return True
        return False

    def get(self, r, c):
        if 0 <= r < self.size and 0 <= c < self.size:
            return self.board[r][c]
        return "edge"

    def display(self):
        cols = "ABCDEFGHJKLMNOPQRST"
        print("\n   " + " ".join(cols[:self.size]))
        for r in range(self.size - 1, -1, -1):
            row_str = f"{r+1:2} "
            for c in range(self.size):
                char = self.board[r][c].upper()
                row_str += char + " "
            print(row_str)

def main():
    size = 9
    ib = InteractiveBoard(size)
    detector = ShapeDetector(board_size=size)
    
    prev_ib = None
    last_color = None
    
    print("--- Integrated Shape Logic Interactive Tester (with History) ---")
    print("Commands:")
    print("  B <Coord> : Set Black (e.g. B E5)")
    print("  W <Coord> : Set White (e.g. W F5)")
    print("  . <Coord> : Clear point (e.g. . E5)")
    print("  exit      : Quit")

    while True:
        ib.display()
        # 全ての形状検知を実行（1手前と最後の手番色を渡す）
        facts = detector.detect_all(ib, prev_board=prev_ib, last_move_color=last_color)
        if facts:
            print("\n" + facts)
        else:
            print("\n[No Detection]")

        try:
            line = input("\nInput > ").strip().split()
            if not line: continue
            cmd = line[0].upper()
            if cmd == "EXIT": break
            if len(line) < 2: continue
            
            char = cmd if cmd in ['B', 'W', '.'] else None
            coord = line[1].upper()
            if char:
                # 操作前に現在の盤面を保存
                prev_ib = ib.copy()
                if not ib.set_stone(coord, char):
                    print(f"Invalid Coordinate: {coord}")
                else:
                    # 最後の手番色を記録（'.' の場合は反対の色が抜いたとみなす）
                    if char in ['B', 'W']:
                        last_color = char.lower()
                    else:
                        # 石を消した（抜いた）場合、その地点にいた石の反対の色を手番とする
                        old_stone = prev_ib.get(*CoordinateTransformer.gtp_to_indices_static(coord))
                        if old_stone in ['b', 'w']:
                            last_color = 'w' if old_stone == 'b' else 'b'
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
