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
from utils.logger import logger

def start_api_server():
    """APIサーバーをクリーンな状態で自動起動し、準備ができるまで待機する"""
    logger.info("System Startup: Initializing Intelligence Infrastructure", layer="STARTUP")
    kill_process_on_port(8000)
    kill_legacy_katago()
    
    api_script = os.path.join(SRC_DIR, "katago_api.py")
    log_file_path = os.path.join(SRC_DIR, "api_server.log")
    
    # サーバーをバックグラウンド起動
    logger.info(f"Launching API Server: {api_script}", layer="STARTUP")
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen([sys.executable, api_script], 
                                stdout=log_file, stderr=log_file, 
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    
    # サーバーの準備ができるまで待機
    for i in range(20):
        try:
            resp = requests.get("http://127.0.0.1:8000/health", timeout=1)
            if resp.status_code == 200:
                logger.info("API Server is Ready.", layer="STARTUP")
                return proc
        except:
            time.sleep(1)
            if i % 5 == 0: logger.info(f"Waiting for API server to initialize... ({i}s)", layer="STARTUP")
            
    logger.warning("API Server startup timed out. Proceeding anyway...", layer="STARTUP")
    return proc

if __name__ == "__main__":

    api_proc = start_api_server()

    

    root = tk.Tk()

    app = GoReplayApp(root)



    # 検証モードのチェック

    is_verify = "--verify" in sys.argv



    # コマンドライン引数があればSGFを自動ロード

    sgf_to_load = None

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):

        sgf_to_load = sys.argv[1]

    

    if is_verify:

        logger.info("Auto-verification mode enabled.", layer="STARTUP")

        # サーバー起動を待ってから検証開始

        root.after(4000, lambda: app.run_auto_verify("test.sgf"))

    elif sgf_to_load and os.path.exists(sgf_to_load):

        logger.info(f"Auto-loading SGF: {sgf_to_load}", layer="STARTUP")

        root.after(3000, lambda: app.start_analysis(sgf_to_load))

            

    root.mainloop()
