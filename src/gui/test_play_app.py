import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageTk

from core.game_state import GoGameState
from core.game_board import Color
from core.point import Point
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from gui.board_view import BoardView
from gui.info_view import InfoView
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
from core.knowledge_manager import KnowledgeManager
from services.term_visualizer import TermVisualizer
from services.async_task_manager import AsyncTaskManager
from services.analysis_service import AnalysisService
from utils.event_bus import event_bus, AppEvents
from config import KNOWLEDGE_DIR, load_api_key
from services.ai_commentator import GeminiCommentator
from gui.controller import AppController
from utils.logger import logger
from gui.base_app import GoAppBase

class TestPlayApp(GoAppBase):
    def __init__(self, root, api_proc=None, is_child=False):
        super().__init__(root, api_proc=api_proc, is_child=is_child)
        self.root.title("Go Test Play & Shape Detection Debugger (Rev 40.0)")
        self.root.geometry("1200x950")

        # イベント購読
        event_bus.subscribe(AppEvents.STATUS_MSG_UPDATED, lambda msg: logger.info(f"Status: {msg}", layer="GUI"))
        event_bus.subscribe(AppEvents.COMMENTARY_READY, lambda text: self.info_view.analysis_tab.set_commentary(text))
        event_bus.subscribe("AI_DIAGRAMS_READY", self._on_ai_diagrams_ready)

        # デバッグモード固有の初期化
        self.game.new_game(19) 
        self.transformer = CoordinateTransformer(19)
        self.renderer = GoBoardRenderer(19)
        self.detector = ShapeDetector(19)
        self.simulator = BoardSimulator() 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.visualizer = TermVisualizer()

        # UI State
        self.current_move = 0
        self.show_numbers = tk.BooleanVar(value=True)
        self.current_tool = tk.StringVar(value="stone")
        self.review_stones = []
        self.redo_review_stones = [] # Redo用のスタックを追加

        callbacks = {
            'comment': self.generate_commentary,
            'report': lambda: messagebox.showinfo("Info", "Report not supported in debug mode"),
            'show_pv': lambda: None,
            'goto': lambda c, i: None,
            'pass': self.pass_move,
            'update_display': self.update_display,
            'on_term_select': self.on_term_select,
            'visualize_term': self.visualize_term
        }

        self.setup_layout(callbacks)
        self._load_dictionary_terms()
        self.update_display()

        # キーバインドの追加
        self.root.bind_all("<Left>", self.prev_move)
        self.root.bind_all("<Right>", self.next_move)
        self.root.focus_set()

    def cleanup(self):
        """リソースの解放（イベント購読の解除、タブのクリーンアップ）"""
        logger.info("TestPlayApp cleaning up...", layer="GUI")
        if hasattr(self, 'info_view') and self.info_view:
            self.info_view.cleanup()
        super().cleanup()

    def setup_layout(self, callbacks):
        # 1. Top Frame
        top_frame = tk.Frame(self.root, bg="#ddd", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(top_frame, text="Board Size:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        for size in [9, 13, 19]:
            btn = tk.Button(top_frame, text=f"{size}x{size}", command=lambda s=size: self.reset_game(s), width=8)
            btn.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="Tools:", bg="#ddd", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        tools = [("Stone", "stone"), ("□", "square"), ("△", "triangle"), ("×", "cross")]
        for label, mode in tools:
            rb = tk.Radiobutton(top_frame, text=label, variable=self.current_tool, value=mode, 
                                indicatoron=0, width=6, bg="#ccc", selectcolor="#aaa")
            rb.pack(side=tk.LEFT, padx=2)

        tk.Checkbutton(top_frame, text="Show Numbers", variable=self.show_numbers, 
                       command=self.update_display, bg="#ddd").pack(side=tk.RIGHT, padx=10)

        # 2. Main Content
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=750)
        self.board_view.bind_click(self.click_on_board)

        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)

        # 3. Bottom Controls
        bot_frame = tk.Frame(self.root, bg="#eee", height=60)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        tk.Button(bot_frame, text="Clear Review", command=self.clear_review, width=12, bg="#f44336", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="Pass", command=self.pass_move, width=10, bg="#607D8B", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(bot_frame, text="< Undo", command=self.undo_move, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(bot_frame, text="Save Image", command=self.save_image, width=12, bg="#4CAF50", fg="white").pack(side=tk.RIGHT, padx=20)

    def _load_dictionary_terms(self):
        terms = []
        for cat in self.knowledge_manager.index.values():
            for item in cat.values(): terms.append(item.title)
        self.info_view.set_terms_list(sorted(terms))

    def on_term_select(self, term_title):
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    desc = getattr(item, 'full_content', "")
                    self.info_view.set_term_details(f"【{item.title}】\n\n{desc}")
                    return

    def visualize_term(self, term_title):
        term_id = None
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title: term_id = item.id; break
        if term_id:
            path, err = self.visualizer.visualize(term_id)
            if path: self._show_image_popup(term_title, path)

    def _show_image_popup(self, title, image_path):
        from PIL import Image, ImageTk
        top = tk.Toplevel(self.root); top.title(f"Example: {title}")
        img = Image.open(image_path); img.thumbnail((600, 600))
        photo = ImageTk.PhotoImage(img); lbl = tk.Label(top, image=photo); lbl.image = photo; lbl.pack(padx=10, pady=10)

    def _on_ai_diagrams_ready(self, res):
        """AIが生成した図を表示する"""
        if res.get("rec_path"):
            self._show_image_popup("AI Recommended Plan", res["rec_path"])
        if res.get("thr_path"):
            self.root.after(200, lambda: self._show_image_popup("WARNING: Future Threat", res["thr_path"]))
        self.info_view.analysis_tab.btn_comment.config(state="normal", text="Ask AI Agent")

    def generate_commentary(self):
        """AI解説をサービス経由で非同期実行する"""
        if not self.gemini: return
        
        h = list(self.game.get_history_up_to(self.current_move))
        for (r, c), color, n in self.review_stones:
            h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        bs = self.game.board_size

        self.info_view.analysis_tab.btn_comment.config(state="disabled", text="Thinking...")
        
        # サービスに処理を譲渡
        self.analysis_service.generate_full_context_analysis(
            len(h), h, bs, 
            self.gemini, self.simulator, self.visualizer
        )

    def reset_game(self, size):
        self.game.new_game(size)
        self.transformer = CoordinateTransformer(size)
        self.board_view.transformer = self.transformer
        self.renderer = GoBoardRenderer(size)
        self.detector = ShapeDetector(size)
        self.current_move = 0
        self.review_stones = []
        self.redo_review_stones = [] # クリア
        self.update_display()

    def clear_review(self):
        self.review_stones = []
        self.redo_review_stones = [] # クリア
        self.update_display()

    def undo_move(self):
        """1手戻る（ボタン用）"""
        self.prev_move()

    def prev_move(self, event=None):
        logger.debug(f"Event: Left Key pressed. Current move: {self.current_move}, Review: {len(self.review_stones)}", layer="GUI")
        # 1. 検討モードの石があれば、Redoバッファに移して消す
        if self.info_view.analysis_tab.edit_mode.get() and self.review_stones:
            stone = self.review_stones.pop()
            self.redo_review_stones.append(stone)
            self.update_display()
            return

        # 2. 検討用の石がなければ、正規手順を戻す
        if self.current_move > 0:
            self.current_move -= 1
            self.update_display()
        else:
            logger.debug("Already at the start of the game.", layer="GUI")

    def next_move(self, event=None):
        logger.debug(f"Event: Right Key pressed. Current move: {self.current_move}, Redo: {len(self.redo_review_stones)}", layer="GUI")
        # 1. Redoバッファに石があれば、それを復元する
        if self.info_view.analysis_tab.edit_mode.get() and self.redo_review_stones:
            stone = self.redo_review_stones.pop()
            self.review_stones.append(stone)
            self.update_display()
            return

        # 2. Redoバッファがなければ、正規手順を進める
        if self.current_move < self.game.total_moves:
            self.current_move += 1
            self.update_display()
        else:
            logger.debug("Already at the latest move.", layer="GUI")

    def click_on_board(self, event):
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        img_h = self.board_view.original_image.height if hasattr(self.board_view, 'original_image') and self.board_view.original_image else None
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch, actual_img_height=img_h)
        if res:
            row, col = res
            tool = self.current_tool.get()
            if self.info_view.analysis_tab.edit_mode.get() and tool == "stone":
                color = "B" if ((self.current_move + len(self.review_stones)) % 2 == 0) else "W"
                logger.info(f"EDIT MODE Attempt -> Move: {self.current_move + len(self.review_stones) + 1}, Color: {color}, Point: {CoordinateTransformer.indices_to_gtp_static(row, col)}", layer="GUI")
                
                # 現在の局面（正規手順 + 既存の検討用の石）を正確に復元
                combined_h = list(self.game.get_history_up_to(self.current_move))
                for (r, c), c_col, _ in self.review_stones:
                    combined_h.append([c_col, CoordinateTransformer.indices_to_gtp_static(r, c)])
                
                # 一時的なシミュレーションを実行
                temp_ctx = self.simulator.reconstruct_to_context(combined_h, self.game.board_size)
                target_pt = Point(row, col)
                
                if temp_ctx.board.is_legal(target_pt, color):
                    # 同一座標のチェックを削除（囲碁では一度抜かれた場所に再度打つことが可能なため）
                    self.review_stones.append(((row, col), color, len(self.review_stones) + 1))
                    sys.stdout.write(f"[GUI] Placed review stone: {color}[{target_pt.to_gtp()}] (Total review stones: {len(self.review_stones)})\n")
                    sys.stdout.flush()
                    
                    self.redo_review_stones = [] # 新しく打ったらRedo不可
                    self.update_display()
                else:
                    msg = f"Reject: {target_pt.to_gtp()} is illegal (Suicide or Ko)"
                    sys.stderr.write(f"[GUI] {msg}\n")
                    sys.stderr.flush()
                    messagebox.showerror("ルール違反", f"{target_pt.to_gtp()} は打てません。")
                return
            if tool == "stone":
                color = "B" if (self.current_move % 2 == 0) else "W"
                logger.info(f"NORMAL MODE Attempt -> Move: {self.current_move + 1}, Color: {color}, Point: {CoordinateTransformer.indices_to_gtp_static(row, col)}", layer="GUI")
                # 合法手チェック
                curr_board = self.game.get_board_at(self.current_move)
                target_pt = Point(row, col)
                if not curr_board.is_legal(target_pt, color):
                    msg = f"着手禁止点です: {target_pt.to_gtp()} (自殺手、またはコウ)"
                    print(f"[GUI] {msg}")
                    messagebox.showerror("ルール違反", msg)
                    return

                if self.game.add_move(self.current_move, color, row, col):
                    # 実際の手順におけるキャプチャを確認
                    curr_board = self.game.get_board_at(self.current_move + 1)
                    # 一手前のボードとの差分からキャプチャを特定（簡易的）
                    prev_board = self.game.get_board_at(self.current_move)
                    
                    self.current_move += 1
                    self.redo_review_stones = [] # 新しく打ったらRedo不可
                    
                    logger.info(f"Move {self.current_move} played at {CoordinateTransformer.indices_to_gtp_static(row, col)}", layer="GUI")
                    
                    # 検討モードでなければ解析をリクエスト
                    h = self.game.get_history_up_to(self.current_move)
                    self.analysis_service.request_analysis(h, self.game.board_size)
                    self.update_display()
            else:
                self.game.toggle_mark(self.current_move, row, col, tool)
                self.update_display()

    def pass_move(self):
        color = "B" if (self.current_move % 2 == 0) else "W"
        if self.game.add_move(self.current_move, color, None, None):
            self.current_move += 1
            self.update_display()

    def save_image(self):
        from tkinter import filedialog
        history = self.game.get_history_up_to(self.current_move)
        
        # 履歴の統合（正規手順 + 検討用の石）を update_display と同様に行う
        combined_h = list(history)
        if self.info_view.analysis_tab.edit_mode.get():
            for (r, c), color, n in self.review_stones:
                combined_h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        try:
            # シミュレータで正確な盤面を復元
            curr_ctx = self.simulator.reconstruct_to_context(combined_h, self.game.board_size)
            turn_color = "Black" if (len(combined_h) % 2 == 0) else "White"
            info_text = f"Move {len(combined_h)} | Turn: {turn_color} (Saved Image)"

            img = self.renderer.render(curr_ctx.board, last_move=None, analysis_text=info_text, 
                                       history=combined_h, show_numbers=self.show_numbers.get(),
                                       marks=self.game.get_marks_at(self.current_move))
            
            file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
            if file_path: 
                img.save(file_path)
                logger.info(f"Image saved to: {file_path}", layer="GUI")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save image: {e}")

    def update_display(self):
        """盤面と解析情報の表示を更新する"""
        history = self.game.get_history_up_to(self.current_move)
        turn_color = "Black" if (self.current_move % 2 == 0) else "White"
        info_text = f"Move {self.current_move} | Turn: {turn_color}"
        
        # 1. 履歴の統合（正規手順 + 検討用の石）
        combined_h = list(history)
        if self.info_view.analysis_tab.edit_mode.get():
            for (r, c), color, n in self.review_stones:
                combined_h.append([color, CoordinateTransformer.indices_to_gtp_static(r, c)])
        
        try:
            # 2. 統合された履歴からシミュレータで盤面を復元
            curr_ctx = self.simulator.reconstruct_to_context(combined_h, self.game.board_size)
            
            # 3. 復元された最新盤面をレンダリング
            img = self.renderer.render(curr_ctx.board, last_move=None, analysis_text=info_text, 
                                       history=combined_h, show_numbers=self.show_numbers.get(),
                                       marks=self.game.get_marks_at(self.current_move))
            self.board_view.update_board(img)

            # 4. 解析サービスのキャッシュからデータを取得
            ana_data = self.analysis_service.get_by_index(self.current_move)
            
            # 5. 形状検知
            facts = self.detector.detect_facts(curr_ctx, analysis_result=ana_data)
            text = "\n".join([f.description for f in facts])
            
            # 6. イベント発行によるUI更新
            winrate = ana_data.winrate_label if ana_data else "--%"
            score = f"{ana_data.score_lead:.1f}" if ana_data else "--"
            
            event_bus.publish(AppEvents.STATE_UPDATED, {
                "winrate_text": winrate,
                "score_text": score,
                "winrate_history": [],
                "current_move": self.current_move
            })
            self.info_view.analysis_tab.set_commentary(text)
        except Exception as e:
            self.info_view.analysis_tab.set_commentary(f"Display Error: {e}")