import tkinter as tk
import sys
import os

# Add src directory to sys.path
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from gui.test_play_app import TestPlayApp

if __name__ == "__main__":
    root = tk.Tk()
    app = TestPlayApp(root)
    root.mainloop()
