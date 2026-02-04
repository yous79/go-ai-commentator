import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import queue
import json
import threading
import traceback
import sys
import config

from config import OUTPUT_BASE_DIR, load_api_key
from core.game_state import GoGameState
from core.game_board import GameBoard, Color
from core.point import Point
from core.coordinate_transformer import CoordinateTransformer
from utils.board_renderer import GoBoardRenderer
from services.ai_commentator import GeminiCommentator
from services.report_generator import ReportGenerator
from services.term_visualizer import TermVisualizer
from services.async_task_manager import AsyncTaskManager
from services.analysis_service import AnalysisService
from core.commands import CommandInvoker, PlayMoveCommand
from core.knowledge_manager import KnowledgeManager
from core.board_simulator import BoardSimulator
from config import KNOWLEDGE_DIR
from utils.logger import logger
from utils.event_bus import event_bus, AppEvents

from gui.board_view import BoardView
from gui.info_view import InfoView
from gui.controller import AppController
from gui.base_app import GoAppBase

class GoReplayApp(GoAppBase):
    def __init__(self, root, api_proc=None, is_child=False):
        super().__init__(root, api_proc=api_proc, is_child=is_child)
        self.root.title("Go AI Commentator (Rev 40.0 God-class decomposed)")
        self.root.geometry("1200x950")

        # イベント購読
        event_bus.subscribe(AppEvents.STATUS_MSG_UPDATED, lambda msg: self.lbl_status.config(text=msg))
        event_bus.subscribe(AppEvents.PROGRESS_UPDATED, lambda val: self.progress_bar.config(value=val))
        event_bus.subscribe("AI_DIAGRAMS_READY", self._on_ai_diagrams_ready)
        event_bus.subscribe("ANALYSIS_RESULT_READY", self._on_state_updated)

        # 再生モード固有の初期化
        self.transformer = CoordinateTransformer()
        self.renderer = GoBoardRenderer()
        self.visualizer = TermVisualizer()
        self.simulator = BoardSimulator() 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.command_invoker = CommandInvoker()
        
        self.report_generator = None
        if self.gemini:
            self.report_generator = ReportGenerator(self.game, self.renderer, self.gemini)

        # UI State
        self.moves_m_b = [None] * 3
        self.moves_m_w = [None] * 3

        # Callbacks
        callbacks = {
            'comment': self.generate_commentary, 
            'report': self.generate_full_report,
            'show_pv': self.show_pv, 
            'goto': self.goto_mistake,
            'pass': self.pass_move, 
            'update_display': self.update_display,
            'goto_move': self.show_image,
            'on_term_select': self.on_term_select,
            'visualize_term': self.visualize_term,
            'prev_move': self.prev_move,
            'next_move': self.next_move
        }

        self.setup_layout(callbacks)
        self._load_dictionary_terms()
        # self._start_queue_monitor() <-- REMOVED (Handled by events)
        
        self.root.bind("<Left>", lambda e: self.prev_move())
        self.root.bind("<Right>", lambda e: self.next_move())
        self.root.bind("<Configure>", self.on_resize)
        
        # Hover handling
        self.board_view.bind_motion(self._on_board_hover)

    def _on_board_hover(self, event):
        """マウスホバー時にOwnership情報を表示する"""
        # ヒートマップ表示時のみ有効
        if not hasattr(self, 'info_view') or not self.info_view.show_heatmap.get():
            return

        # 1. 座標変換
        cw = self.board_view.canvas.winfo_width()
        ch = self.board_view.canvas.winfo_height()
        # 画像がロードされていない場合はスキップ
        img_h = self.board_view.original_image.height if hasattr(self.board_view, 'original_image') and self.board_view.original_image else None
        
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch, actual_img_height=img_h)
        
        if not res:
            return
            
        r, c = res
        
        # 2. Ownershipデータの取得
        val_str = "--"
        curr = self.controller.current_move
        
        if hasattr(self.game, 'moves') and curr < len(self.game.moves):
            d = self.game.moves[curr]
            ownership = None
            if d:
                if hasattr(d, 'ownership'): # AnalysisResult
                    ownership = d.ownership
                elif isinstance(d, dict) and 'ownership' in d: # Dict
                    ownership = d['ownership']
            
            if ownership:
                # 座標変換: bottom-up (r) -> top-down (kata_row)
                bs = self.game.board_size
                kata_row = (bs - 1) - r
                idx = kata_row * bs + c
                
                if 0 <= idx < len(ownership):
                    val = ownership[idx]
                    # 黒地: +, 白地: -
                    val_str = f"{val:+.2f}"

        # 3. 表示更新
        gtp = self.transformer.indices_to_gtp(r, c)
        if gtp:
            self.lbl_status.config(text=f"Point: {gtp} | Ownership: {val_str}")

    def setup_layout(self, callbacks):
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        
        # Menu Configuration
        if self.is_child:
            # MasterAppのメニューバーを取得して拡張
            try:
                # 既存のメニューバーを取得
                menubar_Name = self.root.cget("menu")
                if menubar_Name:
                    menubar = self.root.nametowidget(menubar_Name)
                    
                    # Fileメニューがあるか確認、なければ作成
                    file_menu = None
                    try:
                        # 既存のFileメニューを探す（ラベル名で特定は困難なので、新規作成して追加する方針で）
                        # ただしSystemメニューの前に追加したいが、index指定は複雑。
                        # ここではシンプルに末尾（Systemの次）に追加するか、Systemがあればその前に追加を試みる。
                        
                        filemenu = tk.Menu(menubar, tearoff=0)
                        filemenu.add_command(label="Open SGF...", command=self.open_sgf)
                        # ChildモードではExitは表示しない（MasterAppが管理）
                        
                        # Systemメニューの位置を探してその前に挿入したいが、簡単のため末尾に追加
                        menubar.add_cascade(label="File", menu=filemenu)
                    except: pass
            except: pass
        else:
            # 独立起動モード
            menubar = tk.Menu(self.root)
            filemenu = tk.Menu(menubar, tearoff=0)
            filemenu.add_command(label="Open SGF...", command=self.open_sgf)
            filemenu.add_command(label="Exit", command=self.on_close)
            menubar.add_cascade(label="File", menu=filemenu)
            self.root.config(menu=menubar)

        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.grid(row=0, column=0, sticky="ew")
        self.progress_bar = ttk.Progressbar(top_frame, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_status = tk.Label(top_frame, text="Idle", width=30, bg="#ddd")
        self.lbl_status.pack(side=tk.RIGHT, padx=10)

        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned.grid(row=1, column=0, sticky="nsew")
        self.board_view = BoardView(self.paned, self.transformer)
        self.paned.add(self.board_view, width=600)
        self.board_view.bind_click(self.click_on_board)
        
        self.info_view = InfoView(self.paned, callbacks)
        self.paned.add(self.info_view)
        
        # Debug toggle trace
        if hasattr(self.info_view, 'debug_layers_visible'):
            self.info_view.debug_layers_visible.trace_add('write', lambda *args: self.update_display())
            
        self._setup_bottom_bar()

    def _load_dictionary_terms(self):
        """知識ベースから用語一覧をロードしてUIにセットする"""
        terms = []
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                terms.append(item.title)
        self.info_view.set_terms_list(sorted(terms))

    def on_term_select(self, term_title):
        """用語が選択された際の詳細表示ロジック"""
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    desc = getattr(item, 'full_content', "詳細な解説はありません。")
                    meta = item.metadata
                    header = f"【{item.title}】\n"
                    if "importance" in meta: header += f"重要度: {'★' * meta['importance']}\n"
                    if "description" in meta: header += f"概要: {meta['description']}\n"
                    
                    full_text = f"{header}\n--- 解説 ---\n{desc}"
                    self.info_view.set_term_details(full_text)
                    return

    def visualize_term(self, term_title):
        """選択された用語の具体例画像を生成・表示する"""
        term_id = None
        for cat in self.knowledge_manager.index.values():
            for item in cat.values():
                if item.title == term_title:
                    term_id = item.id
                    break
        
        if term_id:
            path, err = self.visualizer.visualize(term_id)
            if path:
                self._show_image_popup(term_title, path)
            else:
                messagebox.showerror("Error", f"画像の生成に失敗しました: {err}")

    def _show_image_popup(self, title, image_path):
        """画像を別ウィンドウで表示する"""
        from PIL import Image, ImageTk
        top = tk.Toplevel(self.root)
        top.title(f"Diagram: {title}")
        
        try:
            img = Image.open(image_path)
            img.thumbnail((600, 600))
            photo = ImageTk.PhotoImage(img)
            
            lbl = tk.Label(top, image=photo)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)
            
            tk.Button(top, text="Close", command=top.destroy).pack(pady=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open diagram: {e}")


    def _setup_bottom_bar(self):
        bot = tk.Frame(self.root, bg="#e0e0e0", height=60)
        bot.grid(row=2, column=0, sticky="ew")
        bot.grid_propagate(False)
        bot.columnconfigure(0, weight=1); bot.columnconfigure(4, weight=1)
        tk.Button(bot, text="< Prev", command=self.prev_move, width=15).grid(row=0, column=1, padx=10, pady=10)
        tk.Button(bot, text="UNDO", command=self.undo_move, width=10, bg="#ffcccc").grid(row=0, column=2, padx=5)
        self.lbl_counter = tk.Label(bot, text="0 / 0", font=("Arial", 12, "bold"), bg="#e0e0e0")
        self.lbl_counter.grid(row=0, column=3, padx=20)
        tk.Button(bot, text="Next >", command=self.next_move, width=15).grid(row=0, column=4, padx=10, pady=10)

    def open_sgf(self):
        p = filedialog.askopenfilename(filetypes=[("SGF Files", "*.sgf")])
        if p: self.start_analysis(p)

    def start_analysis(self, path):
        try:
            self.game.load_sgf(path)
            # Update dependencies
            self.transformer = CoordinateTransformer(board_size=self.game.board_size)
            self.board_view.transformer = self.transformer
            self.renderer = GoBoardRenderer(board_size=self.game.board_size)
            
            # Controller setup
            name = os.path.splitext(os.path.basename(path))[0]
            self.controller.current_sgf_name = name
            self.controller.set_image_dir(os.path.join(OUTPUT_BASE_DIR, name))
            self.controller.jump_to_move(0)
            
            if self.report_generator:
                self.report_generator.renderer = self.renderer
                
            self.lbl_status.config(text="Starting Analysis...")
            # AnalysisServiceに委譲
            self.analysis_service.start_sgf_analysis(path, self.renderer)
            self._monitor_images_on_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start analysis: {e}")

    def _monitor_images_on_disk(self):
        if not self.controller.image_dir: return
        import glob
        files = glob.glob(os.path.join(self.controller.image_dir, "move_*.png"))
        if len(files) > 0 and not self.controller.image_cache: self.show_image(0)
        if self.analysis_service.analyzing_sgf:
            self._sync_analysis_data()
            self.root.after(2000, self._monitor_images_on_disk)

    def _sync_analysis_data(self):
        if not self.controller.image_dir: return
        p = os.path.join(self.controller.image_dir, "analysis.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
                self.game.moves = d.get("moves", [])
                mb, mw = self.game.calculate_mistakes()
                # 内部情報の更新とUI通知のリクエスト
                for i in range(3):
                    self._upd_mistake_ui("b", i, mb)
                    self._upd_mistake_ui("w", i, mw)
                self.update_display()
            except Exception as e:
                logger.error(f"Error in _sync_analysis_data: {e}")

    def _upd_mistake_ui(self, color, idx, mistakes):
        store = self.moves_m_b if color == "b" else self.moves_m_w
        if idx < len(mistakes):
            sc_drop, wr_drop, m = mistakes[idx]
            if wr_drop > 0 or sc_drop > 0:
                store[idx] = m
                text = f"#{m}: -{wr_drop:.1%} / -{sc_drop:.1f}"
                self.info_view.update_mistake_button(color, idx, text, "normal")
                return
        store[idx] = None
        self.info_view.update_mistake_button(color, idx, "-", "disabled")

    def _monitor_images_on_disk(self):
        if not self.controller.image_dir: return
        import glob
        files = glob.glob(os.path.join(self.controller.image_dir, "move_*.png"))
        if len(files) > 0 and not self.controller.image_cache: self.show_image(0)
        if self.analysis_service.analyzing_sgf:
            self._sync_analysis_data()
            self.root.after(2000, self._monitor_images_on_disk)

    def show_image(self, n):
        if self.controller.jump_to_move(n):
            self.update_display()

    def update_display(self):
        # SGFがロードされていない場合は中断
        if not self.game.sgf_game:
            return
            
        curr = self.controller.current_move
        
        # 1. 必要なデータの準備
        img = None
        board = self.game.get_board_at(curr)
        moves = self.game.moves
        wr_text, sc_text, cands = "--%", "--", []
        
        analysis_res = None
        ownership_data = None
        
        if moves and curr < len(moves):
            d = moves[curr]
            if d:
                # AnalysisResultオブジェクトか辞書かを判別して属性取得
                if hasattr(d, 'winrate_label'): # AnalysisResult Object
                    analysis_res = d
                    wr_text = d.winrate_label
                    sc_text = f"{d.score_lead:.1f}"
                    from dataclasses import is_dataclass, asdict
                    cands = [asdict(c) if is_dataclass(c) else c for c in d.candidates]
                elif isinstance(d, dict): # Dictionary
                    wr_text = d.get('winrate_label', f"{d.get('winrate_black', 0.5):.1%}")
                    sc_text = f"{d.get('score_lead', d.get('score_lead_black', 0.0)):.1f}"
                    cands = d.get('candidates', [])
                    if 'ownership' in d:
                        ownership_data = d['ownership']

        # 2. 画像の生成（ここでヒートマップを適用）
        # analysis_result または ownership_data がある場合は、キャッシュを使わず再レンダリングする
        if analysis_res or ownership_data:
            kwargs = {}
            if analysis_res: kwargs['analysis_result'] = analysis_res
            if ownership_data: kwargs['ownership'] = ownership_data
            
            # ヒートマップ表示設定を適用
            kwargs['show_heatmap'] = self.info_view.show_heatmap.get()

            # レンダリング実行
            img = self.renderer.render(board, candidates=cands, **kwargs)
        else:
            # データがない場合はキャッシュまたはController任せ
            img = self.controller.get_current_image()
            
        if not img: return
        
        self.lbl_counter.config(text=f"{curr} / {self.game.total_moves}")
        
        # --- イベント発行によるUI更新 ---
        wrs = []
        for m in moves:
            if m is None:
                wrs.append(0.5)
            elif hasattr(m, 'winrate'):
                wrs.append(m.winrate)
            elif isinstance(m, dict):
                wrs.append(m.get('winrate', m.get('winrate_black', 0.5)))
            else:
                wrs.append(0.5)

        event_bus.publish(AppEvents.STATE_UPDATED, {
            "winrate_text": wr_text,
            "score_text": sc_text,
            "winrate_history": wrs,
            "current_move": curr
        })
        
        # 前回の通知手数と異なる場合のみ発行
        if getattr(self, '_last_notified_move', -1) != curr:
            event_bus.publish(AppEvents.MOVE_CHANGED, curr)
            self._last_notified_move = curr

        # board_viewはまだイベント対応していないため直接呼ぶ（移行期）
        # analysis_res または ownership_data を渡す
        kwargs = {}
        if 'analysis_res' in locals() and analysis_res:
            kwargs['analysis_result'] = analysis_res
        if 'ownership_data' in locals() and ownership_data:
            kwargs['ownership'] = ownership_data
            
        # BoardViewでの二重描画を防ぐため、candidatesは渡さない（レンダラー側で描画済み）
        self.board_view.update_board(img, self.info_view.review_mode.get(), [], **kwargs)

    def generate_commentary(self):
        """AI解説をサービス経由で非同期実行する"""
        if not self.gemini: return

        curr = self.controller.current_move
        h = self.game.get_history_up_to(curr)
        bs = self.game.board_size

        self.info_view.btn_comment.config(state="disabled", text="Thinking...")
        
        # サービスに処理を譲渡
        self.analysis_service.generate_full_context_analysis(
            curr, h, bs, 
            self.gemini, self.simulator, self.visualizer
        )

    def _update_commentary_ui(self, text):
        """AI解説の表示を更新する (イベント経由)"""
        event_bus.publish(AppEvents.COMMENTARY_READY, text)
        self.info_view.btn_comment.config(state="normal", text="Ask AI Agent")

    def _on_state_updated(self, data):
        """解析更新イベントのハンドラ。AnalysisServiceからの通知であればgame.movesを更新する"""
        if not data or not isinstance(data, dict): return
        
        # AnalysisServiceからの通知には 'result' キーが含まれる
        if 'result' in data:
            # メインスレッドで安全に実行するために after を使用
            self.root.after(0, lambda: self._process_state_update(data))

    def _process_state_update(self, data):
        """メインスレッドで実行される更新処理"""
        try:
            result = data['result']
            curr_move = data.get('current_move')
            
            
            if curr_move is not None:
                # game.moves の該当箇所を更新
                while len(self.game.moves) <= curr_move:
                    self.game.moves.append(None)
                self.game.moves[curr_move] = result
                
                # 現在表示中の手番と同じなら再描画
                if curr_move == self.controller.current_move:
                    self.update_display()
        except Exception as e:
            print(f"ERROR in _process_state_update: {e}")
            traceback.print_exc()

    def _on_ai_diagrams_ready(self, res):
        """AIが生成した図を表示する"""
        if res.get("rec_path"):
            self._show_image_popup("AI Recommended Plan", res["rec_path"])
        if res.get("thr_path"):
            # 連続して出すと重なるため少し遅延
            self.root.after(200, lambda: self._show_image_popup("WARNING: Future Threat", res["thr_path"]))

    def generate_full_report(self):
        """対局レポートを非同期で生成する"""
        if not self.report_generator: return

        def _task():
            import asyncio
            return asyncio.run(self.report_generator.generate(self.controller.current_sgf_name, self.controller.image_dir))

        def _on_success(res):
            path, err = res
            msg = err if err else f"PDFレポートを生成しました:\n{path}"
            messagebox.showinfo("Done", msg)
            self.info_view.btn_report.config(state="normal", text="対局レポートを生成")

        def _on_error(e):
            messagebox.showerror("Error", f"レポート生成に失敗しました: {str(e)}")
            self.info_view.btn_report.config(state="normal", text="対局レポートを生成")

        def _pre_task():
            self.info_view.btn_report.config(state="disabled", text="Generating...")

        self.task_manager.run_task(_task, on_success=_on_success, on_error=_on_error, pre_task=_pre_task)

    def show_pv(self):
        curr = self.controller.current_move
        if curr < len(self.game.moves):
            d = self.game.moves[curr]
            if d:
                # AnalysisResultオブジェクトか辞書かを判別
                if hasattr(d, 'candidates'):
                    cands = d.candidates
                else:
                    cands = d.get('candidates', []) or d.get('top_candidates', [])
                
                if cands:
                    # 候補手がMoveCandidate オブジェクトか辞書かを判別
                    first_cand = cands[0]
                    if hasattr(first_cand, 'pv'):
                        pv_list = first_cand.pv
                    elif isinstance(first_cand, dict) and 'pv' in first_cand:
                        pv_list = first_cand['pv']
                    else:
                        return
                    
                    if pv_list:
                        self._show_pv_window("Variation", pv_list)

    def _show_pv_window(self, title, pv_list):
        top = tk.Toplevel(self.root); top.title(title)
        curr = self.controller.current_move
        board = self.game.get_board_at(curr)
        start_color = "W" if (curr % 2 != 0) else "B"
        img = self.renderer.render_pv(board, pv_list, starting_color=start_color, title=title)
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img)
        cv = tk.Canvas(top, bg="#333", width=img.width, height=img.height)
        cv.pack(fill=tk.BOTH, expand=True)
        cv.create_image(0, 0, image=photo, anchor=tk.NW); cv.image = photo

    def click_on_board(self, event):
        if not self.info_view.edit_mode.get(): return
        cw, ch = self.board_view.canvas.winfo_width(), self.board_view.canvas.winfo_height()
        img_h = self.board_view.original_image.height if hasattr(self.board_view, 'original_image') and self.board_view.original_image else None
        res = self.transformer.pixel_to_indices(event.x, event.y, cw, ch, actual_img_height=img_h)
        if res:
            color = "B" if (self.controller.current_move % 2 == 0) else "W"
            self.play_interactive_move(color, res[0], res[1])

    def pass_move(self):
        if not self.info_view.edit_mode.get(): return
        color = "B" if (self.controller.current_move % 2 == 0) else "W"
        self.play_interactive_move(color, None, None)

    def play_interactive_move(self, color_str, row, col):
        """ユーザーが盤面をクリックして石を置いた際の非同期処理 (コマンド化 + サービス化)"""
        curr = self.controller.current_move
        color_obj = Color.from_str(color_str)
        pt = Point(row, col) if row is not None else None
        
        # コマンドの作成と実行
        cmd = PlayMoveCommand(self.game, curr, color_obj, pt)
        if not self.command_invoker.execute(cmd):
            return
        
        new_idx = curr + 1
        history = self.game.get_history_up_to(new_idx)
        bs = self.game.board_size

        # 分析サービスへ依頼 (表示更新はイベントバス経由で自動で行われる)
        self.info_view.analysis_tab.btn_comment.config(state="disabled", text="Analyzing...")
        self.analysis_service.request_analysis(history, bs)
        
        # ボタン復帰のための遅延処理（またはイベント購読を検討）
        self.root.after(500, lambda: self.info_view.analysis_tab.btn_comment.config(state="normal", text="Ask AI Agent"))
        self.show_image(new_idx)

    def undo_move(self):
        """直前の操作を取り消す"""
        self.command_invoker.undo()
        # 表示を一つ前に戻す
        if self.controller.current_move > 0:
            self.show_image(self.controller.current_move - 1)
        else:
            self.update_display()
        logger.info("Undo performed", layer="GUI")

    def prev_move(self):
        if self.controller.prev_move(): self.update_display()

    def next_move(self):
        if self.controller.next_move(): self.update_display()

    def on_resize(self, event):
        if self.controller.image_cache: self.update_display()

    def goto_mistake(self, color, idx):
        m = self.moves_m_b[idx] if color == "b" else self.moves_m_w[idx]
        if m is not None: self.show_image(m)

    def cleanup(self):
        """リソースの解放（イベント購読の解除、タブのクリーンアップ）"""
        logger.info("GoReplayApp cleaning up...", layer="GUI")
        if hasattr(self, 'info_view') and self.info_view:
            self.info_view.cleanup()
        super().cleanup()

    def on_close(self):
        self.analysis_service.stop_sgf_analysis()
        super().on_close()

    def run_auto_verify(self, sgf_path: str):
        """アプリの主要機能を自動検証する (タイムアウト付き)"""
        logger.info(f"Starting auto-verification with: {sgf_path}", layer="GUI")
        self.verification_completed = False
        
        # 90秒のタイムアウトを設定
        self.root.after(90000, self._handle_verification_timeout)

        if not os.path.exists(sgf_path):
            logger.error(f"Verification failed: {sgf_path} not found.", layer="GUI")
            return

        # 1. SGFロード
        self.start_analysis(sgf_path)

        def _wait_for_analysis():
            if self.verification_completed: return
            if self.analysis_service.analyzing_sgf:
                logger.debug("Waiting for analysis to complete...", layer="GUI")
                self.root.after(2000, _wait_for_analysis)
            else:
                logger.info("Analysis completed. Proceeding to commentary check.", layer="GUI")
                # 2. 4手目にジャンプ
                self.show_image(4)
                # 3. 解説生成を実行
                self.root.after(1000, self.generate_commentary)
                # 4. 結果確認の準備 (Textエリアを監視)
                self.root.after(5000, _check_commentary_result)

        def _check_commentary_result():
            if self.verification_completed: return
            # InfoViewリファクタリングによりパスが変更された
            text = self.info_view.analysis_tab.txt_commentary.get("1.0", tk.END).strip()
            if len(text) > 50: # 適当な長さがあれば成功とみなす
                logger.info("Auto-verification SUCCESS: Commentary generated.", layer="GUI")
                self.verification_completed = True
                # 目標達成。即座に終了する
                self.root.after(1000, self.on_close)
            else:
                # まだ生成中かもしれないので、もう少し待つ
                logger.debug("Commentary not ready yet, waiting...", layer="GUI")
                self.root.after(2000, _check_commentary_result)

        self.root.after(2000, _wait_for_analysis)

    def _handle_verification_timeout(self):
        """タイムアウト発生時の処理"""
        if not self.verification_completed:
            logger.error("Auto-verification TIMED OUT after 90s.", layer="GUI")
            # 継続を断念してアプリを閉じる（または警告を出す）
            self.on_close()
    
        
