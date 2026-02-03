import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from config import TARGET_LEVEL
from utils.event_bus import event_bus, AppEvents
from utils.logger import logger

class AnalysisTab(tk.Frame):
    """解析データ、グラフ、AI解説、悪手一覧を表示するタブ"""
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0")
        self.callbacks = callbacks
        self._subscriptions = []
        self._setup_ui()
        
        # イベント購読の開始（追跡リストに追加）
        self._subscribe_to(AppEvents.STATE_UPDATED, self._on_state_updated)
        self._subscribe_to(AppEvents.MISTAKES_UPDATED, self._on_mistakes_updated)
        self._subscribe_to(AppEvents.COMMENTARY_READY, self._on_commentary_ready)
        self._subscribe_to(AppEvents.FACT_DISCOVERED, self._on_fact_discovered)
        self._subscribe_to(AppEvents.MOVE_CHANGED, lambda _: self._clear_facts())

    def _subscribe_to(self, event_type, callback):
        event_bus.subscribe(event_type, callback)
        self._subscriptions.append((event_type, callback))

    def cleanup(self):
        """タブ固有のリソース、イベント購読を解除する"""
        logger.debug("Cleaning up AnalysisTab subscriptions...", layer="GUI")
        for event_type, callback in self._subscriptions:
            event_bus.unsubscribe(event_type, callback)
        self._subscriptions = []
        # matplotlibの図も解放
        try: plt.close(self.fig)
        except: pass

    def _on_state_updated(self, data):
        """解析データが更新された際の処理"""
        # data: {"winrate_text": str, "score_text": str, "winrate_history": list, "current_move": int}
        if not data: return
        
        self.update_stats(data.get("winrate_text", "--%"), data.get("score_text", "--"))
        
        wr_history = data.get("winrate_history")
        if wr_history:
            self.update_graph(wr_history, data.get("current_move", 0))

    def _on_mistakes_updated(self, data):
        """悪手情報の更新通知を受けた際の処理"""
        # data: {"color": "b"|"w", "mistakes": list}
        color = data.get("color")
        mistakes = data.get("mistakes", [])
        for i in range(3):
            if i < len(mistakes):
                sc_drop, wr_drop, m = mistakes[i]
                text = f"#{m}: -{wr_drop:.1%} / -{sc_drop:.1f}"
                self.update_mistake_button(color, i, text, "normal")
            else:
                self.update_mistake_button(color, i, "-", "disabled")

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
        # --- Top Area: Stats & Controls (2 Rows) ---
        top_frame = tk.Frame(self, bg="#f0f0f0", pady=2)
        top_frame.pack(fill=tk.X)

        # Row 1: Stats & Level
        row1 = tk.Frame(top_frame, bg="#f0f0f0")
        row1.pack(fill=tk.X, pady=1)
        
        self.lbl_winrate = tk.Label(row1, text="WR: --%", font=("Arial", 11, "bold"), bg="#f0f0f0", width=10, anchor="w")
        self.lbl_winrate.pack(side=tk.LEFT, padx=5)
        
        self.lbl_score = tk.Label(row1, text="Lead: --", font=("Arial", 10), bg="#f0f0f0", width=8, anchor="w")
        self.lbl_score.pack(side=tk.LEFT, padx=5)
        
        self.combo_level = ttk.Combobox(row1, values=["1桁級（中級）", "2桁級（初級）"], state="readonly", width=12)
        val = "1桁級（中級）" if TARGET_LEVEL == "intermediate" else "2桁級（初級）"
        self.combo_level.set(val)
        self.combo_level.pack(side=tk.RIGHT, padx=5)

        # Row 2: Action Buttons & Toggles
        row2 = tk.Frame(top_frame, bg="#f0f0f0")
        row2.pack(fill=tk.X, pady=2)
        
        self.btn_comment = tk.Button(row2, text="Ask AI Agent", command=self.callbacks['comment'], 
                                   font=("Arial", 9, "bold"), bg="#3498db", fg="white", width=12)
        self.btn_comment.pack(side=tk.LEFT, padx=5)
        
        self.btn_report = tk.Button(row2, text="Report", command=self.callbacks['report'], font=("Arial", 9), width=6)
        self.btn_report.pack(side=tk.LEFT, padx=2)

        tk.Frame(row2, width=10, bg="#f0f0f0").pack(side=tk.LEFT) # Spacer

        self.review_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(row2, text="Show Candidates", variable=self.review_mode, font=("Arial", 8),
                       command=self.callbacks['update_display'], bg="#f0f0f0").pack(side=tk.LEFT)
        
        self.show_heatmap = tk.BooleanVar(value=True)
        tk.Checkbutton(row2, text="Heatmap", variable=self.show_heatmap, font=("Arial", 8),
                       command=self.callbacks['update_display'], bg="#f0f0f0").pack(side=tk.LEFT, padx=2)
        
        self.edit_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(row2, text="Play Mode", variable=self.edit_mode, font=("Arial", 8), bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        tk.Button(row2, text="Pass", command=self.callbacks['pass'], font=("Arial", 8), width=4).pack(side=tk.LEFT)

        # Graph Area (Compact but Visible)
        self.fig, self.ax = plt.subplots(figsize=(4, 0.6), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax.axis('off')
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_graph.get_tk_widget().pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # Mistakes Area
        self._setup_mistakes_ui()

        # --- Lower Area (Facts 1/3 & Commentary 2/3) using PanedWindow ---
        self.lower_pane = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#bdc3c7", sashrelief=tk.RAISED, sashwidth=4, sashpad=0)
        self.lower_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0) # 余白なしで広げる

        # 1. Live Facts Section (Upper Pane)
        fact_outer_frame = tk.Frame(self.lower_pane, bg="#ecf0f1")
        
        fact_header = tk.Frame(fact_outer_frame, bg="#34495e", pady=2)
        fact_header.pack(fill=tk.X)
        tk.Label(fact_header, text="⚡ LIVE ANALYSIS FACTS", font=("Arial", 8, "bold"), fg="white", bg="#34495e").pack(side=tk.LEFT, padx=5)
        
        self.fact_container = tk.Canvas(fact_outer_frame, bg="#ecf0f1", highlightthickness=0)
        self.fact_scroll = ttk.Scrollbar(fact_outer_frame, orient="vertical", command=self.fact_container.yview)
        self.fact_list_inner = tk.Frame(self.fact_container, bg="#ecf0f1")
        
        self.fact_container.create_window((0, 0), window=self.fact_list_inner, anchor="nw", tags="inner")
        self.fact_container.configure(yscrollcommand=self.fact_scroll.set)
        
        self.fact_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.fact_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.fact_list_inner.bind("<Configure>", lambda e: self.fact_container.configure(scrollregion=self.fact_container.bbox("all")))
        self.fact_container.bind("<Configure>", lambda e: self.fact_container.itemconfig("inner", width=e.width))

        self.lower_pane.add(fact_outer_frame, height=130, minsize=80) 

        # 2. Commentary Section (Lower Pane, Default Larger)
        comm_outer_frame = tk.Frame(self.lower_pane, bg="white")
        comm_header = tk.Frame(comm_outer_frame, bg="#f0f0f0", pady=2)
        comm_header.pack(fill=tk.X)
        tk.Label(comm_header, text="AI Commentary", bg="#f0f0f0", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.txt_commentary = tk.Text(comm_outer_frame, font=("Meiryo", 10), wrap=tk.WORD, bg="white", bd=0, padx=5, pady=5)
        self.txt_commentary.pack(fill=tk.BOTH, expand=True)
        
        self.lower_pane.add(comm_outer_frame, height=300, minsize=100, stretch="always")

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

    def _on_commentary_ready(self, text):
        """解説完了時にボタンをリセットし、テキストを表示"""
        self.set_commentary(text)
        self.btn_comment.config(state="normal", text="Ask AI")

    def _clear_facts(self):
        """新しい手が打たれた際に事実リストをクリアする（解析開始時のみ呼ぶように調整可能）"""
        logger.debug("GUI: Clearing Facts List due to MOVE_CHANGED", layer="GUI")
        self.after(0, self._do_clear_facts)

    def _do_clear_facts(self):
        if not self.fact_list_inner.winfo_exists(): return
        for child in self.fact_list_inner.winfo_children():
            child.destroy()
        self.fact_container.yview_moveto(0)

    def _on_fact_discovered(self, fact):
        """新しい事実が検知された際の処理"""
        # 最初の事実が来たら、古い事実（前の手番のもの）をクリアする
        # （Orchestrator が一括解析を開始した直後の最初の事実のみで行うのが理想）
        logger.debug(f"GUI: Fact Event Received: {fact.description[:30]}", layer="GUI")
        self.after(0, lambda: self._add_fact_card(fact))

    def _add_fact_card(self, fact):
        """実際のUI追加処理（メインスレッドで動作）"""
        logger.debug(f"GUI: Drawing Fact Card: {fact.category.value}", layer="GUI")
        from core.inference_fact import FactCategory, TemporalScope
        
        # 色とアイコンの設定
        bg_color = "#ffffff"
        fg_color = "#333333"
        icon = "•"
        
        if fact.severity >= 5: 
            bg_color = "#fadbd8" 
            icon = "🚨"
        elif fact.severity >= 4:
            bg_color = "#fef9e7" 
            icon = "⚠️"
            
        if fact.scope == TemporalScope.PREDICTED:
            icon = "🔮"
            bg_color = "#ebf5fb" 
        
        # カードの作成
        card = tk.Frame(self.fact_list_inner, bg=bg_color, bd=1, relief="ridge", pady=4, padx=8)
        card.pack(fill=tk.X, pady=2, padx=2)
        
        lbl_icon = tk.Label(card, text=icon, font=("Arial", 12), bg=bg_color, fg=fg_color)
        lbl_icon.pack(side=tk.LEFT)
        
        # カテゴリラベル
        cat_name = fact.category.value.upper()
        lbl_cat = tk.Label(card, text=f"[{cat_name}]", font=("Arial", 8, "bold"), bg=bg_color, fg="#7f8c8d")
        lbl_cat.pack(side=tk.TOP, anchor="w", padx=5)
        
        # 内容
        lbl_desc = tk.Label(card, text=fact.description, font=("Meiryo", 9), bg=bg_color, fg=fg_color, wraplength=350, justify=tk.LEFT)
        lbl_desc.pack(side=tk.TOP, anchor="w", padx=5)
        
        # 自動スクロール
        self.fact_container.update_idletasks()
        self.fact_container.yview_moveto(1.0)

    def update_graph(self, wr_history, current_idx):
        if not self.winfo_exists(): return
        self.ax.clear()
        self.ax.plot(wr_history, color='#2c3e50', linewidth=1.5)
        self.ax.axvline(x=current_idx, color='red', linestyle='--', alpha=0.5)
        self.ax.set_ylim(0, 1)
        self.ax.axis('off')
        self.fig.tight_layout(pad=0)
        self.canvas_graph.draw()

    def update_mistake_button(self, color, idx, text, state):
        if not hasattr(self, 'mistake_buttons'): return
        btn = self.mistake_buttons[color][idx]
        if btn.winfo_exists():
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


class InspectorTab(tk.Frame):
    """開発者用インスペクタ: 生の解析事実を表示"""
    def __init__(self, master, debug_var=None):
        super().__init__(master, bg="#ecf0f1")
        self.debug_var = debug_var
        self._setup_ui()
        self._subscriptions = []
        self._subscribe_to(AppEvents.FACT_DISCOVERED, self._on_fact_discovered)
        self._subscribe_to(AppEvents.MOVE_CHANGED, lambda _: self._clear_list())

    def _subscribe_to(self, event_type, callback):
        event_bus.subscribe(event_type, callback)
        self._subscriptions.append((event_type, callback))

    def _setup_ui(self):
        # Tools / Filter Header
        header = tk.Frame(self, bg="#bdc3c7", pady=2)
        header.pack(fill=tk.X)
        tk.Label(header, text="Raw Facts Stream", bg="#bdc3c7", font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=5)
        
        if self.debug_var:
            tk.Checkbutton(header, text="Show Layers", variable=self.debug_var, bg="#bdc3c7", 
                           activebackground="#bdc3c7", font=("Arial", 8)).pack(side=tk.RIGHT, padx=5)
        
        # Fact List
        self.list_frame = tk.Frame(self, bg="#ecf0f1")
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.list_frame, bg="#ecf0f1", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.canvas.yview)
        self.inner_frame = tk.Frame(self.canvas, bg="#ecf0f1")
        
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw", tags="inner")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig("inner", width=e.width))

    def _on_fact_discovered(self, fact):
        # メインスレッドで描画
        self.after(0, lambda: self._add_fact_row(fact))

    def _add_fact_row(self, fact):
        row = tk.Frame(self.inner_frame, bg="#ffffff", bd=1, relief="solid", pady=2)
        row.pack(fill=tk.X, pady=1, padx=2)
        
        # Severity Indicator
        color = "#e74c3c" if fact.severity >= 5 else "#f1c40f" if fact.severity >= 4 else "#3498db"
        tk.Frame(row, bg=color, width=5).pack(side=tk.LEFT, fill=tk.Y)
        
        # Text
        content = tk.Frame(row, bg="white")
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        header_txt = f"[{fact.category.value.upper()}] Scope: {fact.scope.value}"
        tk.Label(content, text=header_txt, font=("Arial", 7, "bold"), bg="white", fg="#7f8c8d").pack(anchor="w")
        tk.Label(content, text=fact.description, font=("Meiryo", 8), bg="white", wraplength=250, justify=tk.LEFT).pack(anchor="w")

    def _clear_list(self):
        self.after(0, self._do_clear)

    def _do_clear(self):
        for child in self.inner_frame.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)

    def cleanup(self):
        for event_type, callback in self._subscriptions:
            event_bus.unsubscribe(event_type, callback)
        self._subscriptions = []


class ConfigTab(tk.Frame):
    """ロジックパラメータ調整用タブ"""
    def __init__(self, master):
        super().__init__(master, bg="#f0f0f0")
        from core.analysis_config import AnalysisConfig
        self.config = AnalysisConfig
        self._setup_ui()
        self.config.add_observer(self._on_config_updated)

    def _setup_ui(self):
        self.canvas = tk.Canvas(self, bg="#f0f0f0")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="#f0f0f0")
        
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", tags="inner")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig("inner", width=e.width))

        self.controls = {}
        self._refresh_params()

    def _refresh_params(self):
        params = self.config.get_all_params()
        for key, value in params.items():
            if key in self.controls: continue
            
            frame = tk.Frame(self.inner, bg="#ECF0F1", bd=1, relief="groove", pady=4, padx=4)
            frame.pack(fill=tk.X, pady=2, padx=5)
            
            tk.Label(frame, text=key, font=("Arial", 8, "bold"), bg="#ECF0F1").pack(anchor="w")
            
            if isinstance(value, (int, float)):
                var = tk.DoubleVar(value=value)
                self.controls[key] = var
                
                from_v, to_v, res = -1.0, 1.0, 0.01
                if "SEVERITY" in key: from_v, to_v, res = 1, 5, 1
                elif "INFLUENCE" in key: from_v, to_v, res = 0.0, 5.0, 0.1
                elif "LOSS" in key or "MISTAKE" in key: from_v, to_v, res = 0.0, 10.0, 0.1
                
                scale = tk.Scale(frame, variable=var, from_=from_v, to=to_v, resolution=res, orient="horizontal", 
                                 command=lambda v, k=key: self._on_ui_change(k, v), bg="#ECF0F1", length=200)
                scale.pack(fill=tk.X)
            
    def _on_ui_change(self, key, value):
        try:
            val = float(value)
            self.config.set_param(key, val)
        except:
            pass

    def _on_config_updated(self, key, value):
        if key in self.controls:
            current_ui_val = self.controls[key].get()
            if abs(current_ui_val - value) > 0.0001:
                self.controls[key].set(value)

    def cleanup(self):
        self.config.remove_observer(self._on_config_updated)


class InfoView(tk.Frame):
    """サイドパネル全体のコンテナ"""
    def __init__(self, master, callbacks):
        super().__init__(master, bg="#f0f0f0")
        self.callbacks = callbacks
        
        # Debugトグル用
        self.debug_layers_visible = tk.BooleanVar(value=False) # デフォルトOFFにする（ユーザー要望によりON変更可）

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 左右キーがタブ移動に奪われるのを防ぎ、手順移動（callbacks）に回す
        if 'prev_move' in callbacks:
            self.notebook.bind("<Left>", lambda e: self._handle_nav(callbacks['prev_move']))
        if 'next_move' in callbacks:
            self.notebook.bind("<Right>", lambda e: self._handle_nav(callbacks['next_move']))
        
        # --- Analysis Tab ---
        self.analysis_tab = AnalysisTab(self.notebook, callbacks)
        self.notebook.add(self.analysis_tab, text=" Analysis ")
        
        # --- Go Dictionary Tab ---
        self.dict_tab = DictionaryTab(self.notebook, callbacks)
        self.notebook.add(self.dict_tab, text=" Go Dictionary ")

        # --- Inspector Tab (New) ---
        self.inspector_tab = InspectorTab(self.notebook, debug_var=self.debug_layers_visible)
        self.notebook.add(self.inspector_tab, text=" Inspector ")

        # --- Config Tab (New) ---
        self.config_tab = ConfigTab(self.notebook)
        self.notebook.add(self.config_tab, text=" Config ")

        # 互換性のためのエイリアス（既存のAppクラスからの呼び出しに対応）
        self.btn_comment = self.analysis_tab.btn_comment
        self.btn_report = self.analysis_tab.btn_report
        self.review_mode = self.analysis_tab.review_mode
        self.show_heatmap = self.analysis_tab.show_heatmap
        self.edit_mode = self.analysis_tab.edit_mode
        self.analysis_tab.inspector_visible = tk.BooleanVar(value=True) 
        
    def _handle_nav(self, callback):
        """キー入力を手順移動として処理し、タブ移動イベントを遮断する"""
        callback()
        return "break"

    def cleanup(self):
        """内部のタブを含め、リソースを解放する"""
        logger.debug("Cleaning up InfoView tabs...", layer="GUI")
        self.analysis_tab.cleanup()
        self.inspector_tab.cleanup()
        self.config_tab.cleanup()

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

        # 互換性のためのエイリアス（既存のAppクラスからの呼び出しに対応）
        self.btn_comment = self.analysis_tab.btn_comment
        self.btn_report = self.analysis_tab.btn_report
        self.review_mode = self.analysis_tab.review_mode
        self.show_heatmap = self.analysis_tab.show_heatmap
        self.edit_mode = self.analysis_tab.edit_mode

    def cleanup(self):
        """内部のタブを含め、リソースを解放する"""
        logger.debug("Cleaning up InfoView tabs...", layer="GUI")
        self.analysis_tab.cleanup()
        # dict_tab も将来的にイベントを使う場合はここで呼ぶ

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