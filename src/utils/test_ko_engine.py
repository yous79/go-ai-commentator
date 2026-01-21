from core.game_board import GameBoard, Point, Color

def test_ko_logic():
    board = GameBoard(19)
    # コウの形を作る (黒が白を取れる状態)
    #   . W .
    # W B W .
    #   B . .
    board.play(Point(1, 1), "B")
    board.play(Point(2, 0), "B") # ダミー
    
    board.play(Point(0, 1), "W")
    board.play(Point(1, 0), "W")
    board.play(Point(1, 2), "W")
    # ここで黒が L10 (1, 1) にあり、白が囲んでいる。黒の呼吸点は (2, 1) のみ。
    
    # 黒が L11 (2, 1) に打つ（コウの開始）
    print("--- Testing Ko flow ---")
    board.play(Point(2, 1), "B") # 準備
    
    # 白が (1, 1) を取る
    captured = board.play(Point(1, 1), "W")
    print(f"White captures Black stone at: {[p.to_gtp() for p in captured]}")
    print(f"Ko point set at: {board.ko_point.to_gtp() if board.ko_point else 'None'}")
    
    # 即座に黒が (2, 1) を取り返そうとする (拒否されるべき)
    is_legal = board.is_legal(Point(2, 1), "B")
    print(f"Black immediate re-take is legal: {is_legal}")
    
    # パスをする
    board.apply_pass()
    print("Black passes.")
    
    # 再度取り返そうとする (許可されるべき)
    is_legal = board.is_legal(Point(2, 1), "B")
    print(f"Black re-take after pass is legal: {is_legal}")

if __name__ == "__main__":
    test_ko_logic()
