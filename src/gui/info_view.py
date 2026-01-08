import tkinter as tk

class InfoView(tk.Frame):
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0", width=600)
        self.callbacks = callbacks # dict of functions: {'comment': ..., 'report': ..., 'pv': ..., 'goto': ...}
        
        self.review_mode = tk.BooleanVar(value=False)
        self.edit_mode = tk.BooleanVar(value=False)
        
        self._setup_ui()

    def _setup_ui(self):
        tk.Label(self, text="Analysis Info", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        
        self.lbl_winrate = tk.Label(self, text="Winrate (Black): --%", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w", padx=20)
        
        self.lbl_score = tk.Label(self, text="Score: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w", padx=20)

        tk.Checkbutton(self, text="Review Mode", variable=self.review_mode, 
                       command=self.callbacks.get('update_display'), bg="#f0f0f0").pack()
        tk.Checkbutton(self, text="Edit Mode", variable=self.edit_mode, bg="#f0f0f0").pack()
        
        tk.Button(self, text="Show Future Sequence (PV)", 
                  command=self.callbacks.get('show_pv'), bg="#2196F3", fg="white", 
                  font=("Arial", 10, "bold")).pack(pady=5, fill=tk.X, padx=20)

        self.btn_pass = tk.Button(self, text="Pass (Edit Mode)", 
                                  command=self.callbacks.get('pass'), 
                                  bg="#607D8B", fg="white", font=("Arial", 10, "bold"))
        self.btn_pass.pack(pady=5, fill=tk.X, padx=20)

        # AI Section
        tk.Frame(self, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self, text="AI Commentary", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=2)
        
        self.btn_comment = tk.Button(self, text="Ask KataGo Agent", 
                                     command=self.callbacks.get('comment'), 
                                     bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_comment.pack(pady=5, fill=tk.X, padx=20)
        
        comm_f = tk.Frame(self, bg="#f0f0f0")
        comm_f.pack(fill=tk.BOTH, expand=False, padx=10)
        scr = tk.Scrollbar(comm_f)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_commentary = tk.Text(comm_f, height=8, wrap=tk.WORD, yscrollcommand=scr.set)
        self.txt_commentary.pack(fill=tk.BOTH, expand=True)
        scr.config(command=self.txt_commentary.yview)
        
        self.btn_agent_pv = tk.Button(self, text="エージェントの想定図を表示", 
                                      command=self.callbacks.get('agent_pv'), 
                                      state="disabled", bg="#FF9800", fg="white")
        self.btn_agent_pv.pack(pady=5, fill=tk.X, padx=20)
        
        self.btn_report = tk.Button(self, text="対局レポートを生成", 
                                    command=self.callbacks.get('report'), 
                                    bg="#9C27B0", fg="white")
        self.btn_report.pack(pady=5, fill=tk.X, padx=20)
        
        # Mistakes Section
        tk.Frame(self, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self, text="Mistakes (Winrate Drop)", font=("Arial", 10, "bold"), bg="#f0f0f0").pack()
        
        m_frame = tk.Frame(self, bg="#eee", bd=1, relief=tk.RIDGE)
        m_frame.pack(fill=tk.X, padx=10, pady=5)
        m_frame.columnconfigure(0, weight=1)
        m_frame.columnconfigure(1, weight=1)
        
        tk.Label(m_frame, text="Black", font=("Arial", 9, "bold"), bg="#333", fg="white").grid(row=0, column=0, sticky="ew")
        tk.Label(m_frame, text="White", font=("Arial", 9, "bold"), bg="#eee", fg="#333").grid(row=0, column=1, sticky="ew")
        
        self.btn_m_b = []
        self.btn_m_w = []
        for i in range(3):
            b = tk.Button(m_frame, text="-", command=lambda x=i: self.callbacks.get('goto')("b", x), 
                          bg="#ffcccc", font=("Arial", 8))
            b.grid(row=i+1, column=0, sticky="ew", padx=2, pady=1)
            self.btn_m_b.append(b)
            
            w = tk.Button(m_frame, text="-", command=lambda x=i: self.callbacks.get('goto')("w", x), 
                          bg="#ffcccc", font=("Arial", 8))
            w.grid(row=i+1, column=1, sticky="ew", padx=2, pady=1)
            self.btn_m_w.append(w)

    def update_stats(self, wr_text, sc_text, move_count_text):
        self.lbl_winrate.config(text=f"Winrate (Black): {wr_text}")
        self.lbl_score.config(text=f"Score: {sc_text}")

    def update_mistake_button(self, color, idx, text, state):
        btns = self.btn_m_b if color == "b" else self.btn_m_w
        btns[idx].config(text=text, state=state)

    def set_commentary(self, text):
        self.txt_commentary.delete(1.0, tk.END)
        self.txt_commentary.insert(tk.END, text)
