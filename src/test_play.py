import tkinter as tk
import sys
import os

# src 内部に配置されるため、同一ディレクトリのモジュールとしてインポート
from gui.test_play_app import TestPlayApp
from utils.logger import logger

if __name__ == "__main__":
    logger.info("Launching Test Play App from src directory", layer="STARTUP")
    root = tk.Tk()
    app = TestPlayApp(root)
    root.mainloop()
