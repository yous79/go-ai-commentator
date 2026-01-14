import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class InfoView(tk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent, bg="#f0f0f0", padx=10, pady=10)
        self.callbacks = callbacks
        self.setup_ui()

    def setup_ui(self):
        # 1. グラフエリア (matplotlib)
        self.fig, self.ax = plt.subplots(figsize=(4, 2.5), dpi=80)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax.set_facecolor('#ffffff')
        self.ax.set_ylim(0, 100)
        self.ax.set_title("Winrate 推移 (%)", fontname="MS Gothic", fontsize=10)
        self.ax.tick_params(axis='both', which='major', labelsize=8)
        
        self.graph_canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.graph_canvas.get_tk_widget().pack(fill=tk.X, pady=(0, 10))
        
        # グラフクリックイベント
        self.fig.canvas.mpl_connect('button_press_event', self._on_graph_click)

        # 2. 基本情報
        info_frame = tk.LabelFrame(self, text="局面解析", bg="#f0f0f0", padx=10, pady=5)
        info_frame.pack(fill=tk.X)
        
        self.lbl_winrate = tk.Label(info_frame, text="黒勝率: --%", font=("Arial", 14, "bold"), bg="#f0f0f0")
        self.lbl_winrate.pack(anchor="w")
        self.lbl_score = tk.Label(info_frame, text="目数差: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(anchor="w")

        # 3. 操作ボタン
        btn_frame = tk.Frame(self, bg="#f0f0f0", pady=10)
        btn_frame.pack(fill=tk.X)
        
        self.btn_comment = tk.Button(btn_frame, text="Ask KataGo Agent", 
                                     command=self.callbacks['comment'], bg="#2196F3", fg="white", height=2)
        self.btn_comment.pack(fill=tk.X, pady=2)
        
        self.btn_show_pv = tk.Button(btn_frame, text="変化図を表示", 
                                     command=self.callbacks['show_pv'])
        self.btn_show_pv.pack(fill=tk.X, pady=2)

        # 4. 失着リスト
        mistake_frame = tk.LabelFrame(self, text="悪手・失着 (勝率下落順)", bg="#f0f0f0", padx=10, pady=5)
        mistake_frame.pack(fill=tk.X, pady=10)
        
        self.mistake_btns = {"b": [], "w": []}
        for color, label in [("b", "黒のミス"), ("w", "白のミス")]:
            tk.Label(mistake_frame, text=label, bg="#f0f0f0", font=("Arial", 9, "bold")).pack(anchor="w")
            for i in range(3):
                btn = tk.Button(mistake_frame, text="-", command=lambda c=color, idx=i: self.callbacks['goto'](c, idx),
                                state="disabled", anchor="w", font=("Consolas", 9))
                btn.pack(fill=tk.X, pady=1)
                self.mistake_btns[color].append(btn)

        # 5. 解説エリア
        comment_frame = tk.LabelFrame(self, text="AI解説", bg="#f0f0f0", padx=10, pady=5)
        comment_frame.pack(fill=tk.BOTH, expand=True)
        
        self.txt_commentary = tk.Text(comment_frame, wrap=tk.WORD, font=("MS Gothic", 10), height=10)
        self.txt_commentary.pack(fill=tk.BOTH, expand=True)

        # 6. モード切替
        mode_frame = tk.Frame(self, bg="#f0f0f0")
        mode_frame.pack(fill=tk.X, pady=5)
        self.review_mode = tk.BooleanVar(value=False) # デフォルトOFF
        tk.Checkbutton(mode_frame, text="候補手の表示", variable=self.review_mode, 
                       command=self.callbacks['update_display'], bg="#f0f0f0").pack(side=tk.LEFT)
        self.edit_mode = tk.BooleanVar(value=False)
        tk.Checkbutton(mode_frame, text="検討（編集）モード", variable=self.edit_mode, bg="#f0f0f0").pack(side=tk.LEFT, padx=10)
        tk.Button(mode_frame, text="Pass", command=self.callbacks['pass']).pack(side=tk.RIGHT)

        self.btn_report = tk.Button(self, text="対局レポートを生成", command=self.callbacks['report'],
                                    bg="#4CAF50", fg="white", pady=5)
        self.btn_report.pack(fill=tk.X, side=tk.BOTTOM)

    def update_stats(self, winrate_text, score_text, info):
        self.lbl_winrate.config(text=f"黒勝率: {winrate_text}")
        self.lbl_score.config(text=f"目数差: {score_text}")

    def update_mistake_button(self, color, idx, text, state):
        self.mistake_btns[color][idx].config(text=text, state=state)

    def set_commentary(self, text):
        self.txt_commentary.delete("1.0", tk.END)
        self.txt_commentary.insert(tk.END, text)

    def update_graph(self, winrates, current_move):
        """勝率推移グラフを更新"""
        self.ax.clear()
        self.ax.set_ylim(0, 100)
        self.ax.set_facecolor('#ffffff')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
        x = list(range(len(winrates)))
        y = [w * 100 for w in winrates]
        
        # メイン曲線
        self.ax.plot(x, y, color='#2196F3', linewidth=2)
        # 50%線
        self.ax.axhline(50, color='red', linewidth=0.8, linestyle='--')
        # 現在位置の強調
        if 0 <= current_move < len(y):
            self.ax.plot(current_move, y[current_move], 'ro', markersize=6)
        
        self.ax.set_title("Winrate 推移 (%)", fontname="MS Gothic", fontsize=10)
        self.fig.tight_layout()
        self.graph_canvas.draw()

    def _on_graph_click(self, event):
        """グラフクリックで該当手番へジャンプ"""
        if event.xdata is not None:
            move_idx = int(round(event.xdata))
            self.callbacks['goto_move'](move_idx)