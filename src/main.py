import tkinter as tk
import sys
import os

# Add src directory to sys.path to handle modular imports
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from gui.app import GoReplayApp

if __name__ == "__main__":
    root = tk.Tk()
    app = GoReplayApp(root)

    # コマンドライン引数があればSGFを自動ロード
    if len(sys.argv) > 1:
        sgf_path = sys.argv[1]
        if os.path.exists(sgf_path):
            print(f"Auto-loading SGF: {sgf_path}")
            # APIサーバーの起動時間を考慮して3秒待つ
            root.after(3000, lambda: app.start_analysis(sgf_path))
            
            # テスト用：解析が進んだら自動で手番を進める (第2引数がある場合)
            if len(sys.argv) > 2:
                def auto_step():
                    if app.current_move < app.game.total_moves:
                        app.next_move()
                        print(f"DEBUG TEST: Auto-stepped to move {app.current_move}")
                    root.after(2000, auto_step)
                root.after(10000, auto_step)
            
    root.mainloop()