import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from config import TARGET_LEVEL
from utils.event_bus import event_bus, AppEvents

class AnalysisTab(tk.Frame):
    """解析データ、グラフ、AI解説、悪手一覧を表示するタブ"""
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0")
        self.callbacks = callbacks
        self._setup_ui()
        
        # イベント購読の開始
        event_bus.subscribe(AppEvents.STATE_UPDATED, self._on_state_updated)

    def _on_state_updated(self, data):
        """解析データが更新された際の処理"""
        # data: {"winrate_text": str, "score_text": str, "winrate_history": list, "current_move": int}
        if not data: return
        
        self.update_stats(data.get("winrate_text", "--%"), data.get("score_text", "--"))
        
        wr_history = data.get("winrate_history")
        if wr_history:
            self.update_graph(wr_history, data.get("current_move", 0))

    def _setup_level_selector(self, parent):
        level_frame = tk.Frame(parent, bg="#f0f0f0")
        level_frame.pack(pady=5)
        tk.Label(level_frame, text="解説モード:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.combo_level = ttk.Combobox(level_frame, values=["1桁級（中級者）", "2桁級（初心者）"], state="readonly", width=15)
        init_val = "1桁級（中級者）" if TARGET_LEVEL == "intermediate" else "2桁級（初心者）"
        self.combo_level.set(init_val)
        self.combo_level.pack(side=tk.LEFT)
        self.combo_level.bind("<<ComboboxSelected>>", self._on_level_changed)

    def _setup_ui(self):
        # Stats Area
        self.lbl_winrate = tk.Label(self, text="Winrate (B): --%", font=("Arial", 14), bg="#f0f0f0")
        self.lbl_winrate.pack(pady=5)
        self.lbl_score = tk.Label(self, text="Score Lead: --", font=("Arial", 12), bg="#f0f0f0")
        self.lbl_score.pack(pady=5)
        
        # Graph Area
        self.fig, self.ax = plt.subplots(figsize=(4, 2), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_graph.get_tk_widget().pack(fill=tk.X, padx=10)
        
        # Skill Level Selector
        self._setup_level_selector(self)

        # Action Buttons
        btn_frame = tk.Frame(self, bg="#f0f0f0")
        btn_frame.pack(pady=10)
        self.btn_comment = tk.Button(btn_frame, text="Ask AI Agent", command=self.callbacks['comment'], width=20)
        self.btn_comment.pack(side=tk.LEFT, padx=5)
        self.btn_report = tk.Button(btn_frame, text="対局レポートを生成", command=self.callbacks['report'])
        self.btn_report.pack(side=tk.LEFT, padx=5)
        
        # Modes
        mode_frame = tk.Frame(self, bg="#f0f0f0")
        mode_frame.pack(pady=5)
        self.review_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(mode_frame, text="Show AI Candidates", variable=self.review_mode, 
                       command=self.callbacks['update_display'], bg="#f0f0f0").pack(side=tk.LEFT)
        self.edit_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(mode_frame, text="Review Mode (Play Stone)", variable=self.edit_mode, bg="#f0f0f0").pack(side=tk.LEFT)
        tk.Button(mode_frame, text="PASS", command=self.callbacks['pass']).pack(side=tk.LEFT, padx=10)

        # Commentary Area
        self.txt_commentary = tk.Text(self, height=15, width=40, font=("Meiryo", 10))
        self.txt_commentary.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Mistakes Area
        self._setup_mistakes_ui()

    def _setup_mistakes_ui(self):
        self.mistake_buttons = {"b": [], "w": []}
        m_frame = tk.Frame(self, bg="#f0f0f0")
        m_frame.pack(fill=tk.X, padx=10, pady=5)
        for i, color in enumerate(["b", "w"]):
            lbl = "Black Mistakes" if color == "b" else "White Mistakes"
            tk.Label(m_frame, text=lbl, bg="#f0f0f0", font=("Arial", 9, "bold")).grid(row=0, column=i, sticky="w")
            for j in range(3):
                btn = tk.Button(m_frame, text="-", state="disabled", width=18, font=("Arial", 8),
                                command=lambda c=color, idx=j: self.callbacks['goto'](c, idx))
                btn.grid(row=j+1, column=i, padx=2, pady=1)
                self.mistake_buttons[color].append(btn)

    def update_stats(self, wr, score):
        self.lbl_winrate.config(text=f"Winrate (B): {wr}")
        self.lbl_score.config(text=f"Score Lead: {score}")

    def set_commentary(self, text):
        self.txt_commentary.config(state="normal")
        self.txt_commentary.delete("1.0", tk.END)
        self.txt_commentary.insert(tk.END, text)
        self.txt_commentary.config(state="disabled")

    def update_graph(self, wr_history, current_idx):
        self.ax.clear()
        self.ax.plot(wr_history, color='#2c3e50', linewidth=2)
        self.ax.axvline(x=current_idx, color='red', linestyle='--', alpha=0.5)
        self.ax.set_ylim(0, 1)
        self.ax.set_title("Winrate Trend (Black)", fontsize=10)
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.fig.tight_layout()
        self.canvas_graph.draw()

    def update_mistake_button(self, color, idx, text, state):
        btn = self.mistake_buttons[color][idx]
        btn.config(text=text, state=state)

    def _on_level_changed(self, event):
        val = self.combo_level.get()
        level_key = "intermediate" if "1桁級" in val else "beginner"
        # イベント発行
        event_bus.publish(AppEvents.LEVEL_CHANGED, level_key)
        # コールバック（互換用）
        if 'on_level_change' in self.callbacks:
            self.callbacks['on_level_change'](level_key)


class DictionaryTab(tk.Frame):
    """囲碁用語辞典を表示するタブ"""
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0")
        self.callbacks = callbacks
        self._setup_ui()

    def _setup_ui(self):
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#f0f0f0")
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Top: Term List
        list_frame = tk.Frame(paned, bg="#f0f0f0")
        tk.Label(list_frame, text="登録されている用語一覧:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5, pady=2)
        self.list_terms = tk.Listbox(list_frame, height=8)
        self.list_terms.pack(fill=tk.BOTH, expand=True, padx=5)
        self.list_terms.bind("<<ListboxSelect>>", self._on_term_selected)
        paned.add(list_frame, height=150)
        
        # Bottom: Description & Action
        desc_frame = tk.Frame(paned, bg="#f0f0f0")
        self.txt_term_desc = tk.Text(desc_frame, height=10, width=40, font=("Meiryo", 10), state="disabled", bg="#eee")
        self.txt_term_desc.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.btn_visualize = tk.Button(desc_frame, text="具体例（画像）を表示", state="disabled", 
                                       command=self._on_visualize_click)
        self.btn_visualize.pack(pady=5)
        paned.add(desc_frame)

    def set_terms_list(self, term_names):
        self.list_terms.delete(0, tk.END)
        for name in term_names:
            self.list_terms.insert(tk.END, name)

    def _on_term_selected(self, event):
        selection = self.list_terms.curselection()
        if selection:
            idx = selection[0]
            term_name = self.list_terms.get(idx)
            self.callbacks['on_term_select'](term_name)

    def set_term_details(self, description, can_visualize=True):
        self.txt_term_desc.config(state="normal")
        self.txt_term_desc.delete("1.0", tk.END)
        self.txt_term_desc.insert(tk.END, description)
        self.txt_term_desc.config(state="disabled")
        self.btn_visualize.config(state="normal" if can_visualize else "disabled")

    def _on_visualize_click(self):
        selection = self.list_terms.curselection()
        if selection:
            term_name = self.list_terms.get(selection[0])
            self.callbacks['visualize_term'](term_name)


class InfoView(tk.Frame):
    """サイドパネル全体のコンテナ"""
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0")
        self.callbacks = callbacks
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # --- Analysis Tab ---
        self.analysis_tab = AnalysisTab(self.notebook, callbacks)
        self.notebook.add(self.analysis_tab, text=" Analysis ")
        
        # --- Go Dictionary Tab ---
        self.dict_tab = DictionaryTab(self.notebook, callbacks)
        self.notebook.add(self.dict_tab, text=" Go Dictionary ")

        # 互換性のためのエイリアス（既存のAppクラスからの呼び出しに対応）
        self.btn_comment = self.analysis_tab.btn_comment
        self.btn_report = self.analysis_tab.btn_report
        self.review_mode = self.analysis_tab.review_mode
        self.edit_mode = self.analysis_tab.edit_mode

    def update_stats(self, wr, score, commentary):
        self.analysis_tab.update_stats(wr, score)

    def set_commentary(self, text):
        self.analysis_tab.set_commentary(text)

    def update_graph(self, wr_history, current_idx):
        self.analysis_tab.update_graph(wr_history, current_idx)

    def update_mistake_button(self, color, idx, text, state):
        self.analysis_tab.update_mistake_button(color, idx, text, state)

    def set_terms_list(self, term_names):
        self.dict_tab.set_terms_list(term_names)

    def set_term_details(self, description, can_visualize=True):
        self.dict_tab.set_term_details(description, can_visualize)