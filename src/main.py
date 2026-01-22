import tkinter as tk
import sys
import os
import subprocess
import time
import requests
from services.bootstrap_service import BootstrapService

# Add src directory to sys.path to handle modular imports
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from gui.app import GoReplayApp
from utils.logger import logger

# start_api_server function removed, logic moved to BootstrapService

if __name__ == "__main__":
    api_proc = BootstrapService.start_api_server(SRC_DIR)
    
    root = tk.Tk()
    app = GoReplayApp(root, api_proc=api_proc)



    # 検証モードのチェック

    is_verify = "--verify" in sys.argv



    # コマンドライン引数があればSGFを自動ロード

    sgf_to_load = None

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):

        sgf_to_load = sys.argv[1]

    

    if is_verify:
        logger.info("Auto-verification mode enabled.", layer="STARTUP")
        # サーバー起動を待ってから自動検証
        root.after(4000, lambda: app.run_auto_verify("test.sgf"))

    elif sgf_to_load and os.path.exists(sgf_to_load):

        logger.info(f"Auto-loading SGF: {sgf_to_load}", layer="STARTUP")

        root.after(3000, lambda: app.start_analysis(sgf_to_load))

            

    root.mainloop()
