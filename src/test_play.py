import tkinter as tk
import sys
import os

# src 内部に配置されるため、同一ディレクトリのモジュールとしてインポート
from gui.test_play_app import TestPlayApp
from utils.logger import logger
from main import start_api_server

if __name__ == "__main__":
    api_proc = start_api_server()
    
    logger.info("Launching Test Play App from src directory", layer="STARTUP")
    root = tk.Tk()
    app = TestPlayApp(root, api_proc=api_proc)
    root.mainloop()
