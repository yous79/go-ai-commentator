import tkinter as tk
import sys
import os

# src 内部に配置されるため、同一ディレクトリのモジュールとしてインポート
from services.bootstrap_service import BootstrapService
from gui.test_play_app import TestPlayApp
from utils.logger import logger

# src 内部に配置されるため、同一ディレクトリを SRC_DIR とする
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    api_proc = BootstrapService.start_api_server(SRC_DIR)
    
    logger.info("Launching Test Play App from src directory", layer="STARTUP")
    root = tk.Tk()
    app = TestPlayApp(root, api_proc=api_proc)
    root.mainloop()
