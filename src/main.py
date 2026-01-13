import tkinter as tk
import sys
import os
import subprocess
import time
import requests
from utils.process_manager import kill_process_on_port, kill_legacy_katago

# Add src directory to sys.path to handle modular imports
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from gui.app import GoReplayApp

def start_api_server():
    """APIサーバーをクリーンな状態で自動起動し、準備ができるまで待機する"""
    print("--- System Startup: Initializing Intelligence Infrastructure ---")
    kill_process_on_port(8000)
    kill_legacy_katago()
    
    api_script = os.path.join(SRC_DIR, "katago_api.py")
    log_file_path = os.path.join(SRC_DIR, "api_server.log")
    
    # サーバーをバックグラウンド起動
    print(f"Launching API Server: {api_script}")
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen([sys.executable, api_script], 
                                stdout=log_file, stderr=log_file, 
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    
    # サーバーの準備ができるまで待機
    for i in range(20):
        try:
            resp = requests.get("http://127.0.0.1:8000/health", timeout=1)
            if resp.status_code == 200:
                print("API Server is Ready.")
                return proc
        except:
            time.sleep(1)
            if i % 5 == 0: print(f"Waiting for API server to initialize... ({i}s)")
            
    print("Warning: API Server startup timed out. Proceeding anyway...")
    return proc

if __name__ == "__main__":
    api_proc = start_api_server()
    
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