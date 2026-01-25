import tkinter as tk
from tkinter import ttk

class Launcher(tk.Frame):
    def __init__(self, master, switch_callback):
        super().__init__(master, bg="#333")
        self.switch_callback = switch_callback
        self.pack(fill=tk.BOTH, expand=True)

        self._setup_ui()

    def _setup_ui(self):
        # Center container
        container = tk.Frame(self, bg="#333")
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Title
        tk.Label(container, text="Go AI Commentator", font=("Helvetica", 24, "bold"), 
                 bg="#333", fg="white").pack(pady=(0, 20))
        
        tk.Label(container, text="Select Mode", font=("Helvetica", 12), 
                 bg="#333", fg="#ccc").pack(pady=(0, 20))

        # Buttons
        style = ttk.Style()
        style.configure("Launcher.TButton", font=("Helvetica", 14), padding=10)

        btn_replay = ttk.Button(container, text="📂 SGF Analysis / Replay", 
                                command=lambda: self.switch_callback("replay"), style="Launcher.TButton")
        btn_replay.pack(fill=tk.X, pady=10)

        btn_test = ttk.Button(container, text="♟️ Test Play / Practice", 
                              command=lambda: self.switch_callback("test_play"), style="Launcher.TButton")
        btn_test.pack(fill=tk.X, pady=10)
