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
    root.mainloop()