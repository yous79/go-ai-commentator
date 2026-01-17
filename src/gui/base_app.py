import tkinter as tk
from abc import ABC, abstractmethod
from core.game_state import GoGameState
from gui.controller import AppController
from services.async_task_manager import AsyncTaskManager
from utils.event_bus import event_bus, AppEvents
from services.ai_commentator import GeminiCommentator
from config import load_api_key
from utils.logger import logger

class GoAppBase(ABC):
    """すべての囲碁アプリ（メイン、デバッグ、練習用など）の共通基底クラス"""
    
    def __init__(self, root: tk.Tk, api_proc=None):
        self.root = root
        self.api_proc = api_proc
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 1. コア・サービスと状態の初期化
        self.game = GoGameState()
        self.controller = AppController(self.game)
        self.task_manager = AsyncTaskManager(root, max_workers=3)
        self.gemini = None
        
        # 2. 共通のイベント購読
        event_bus.subscribe(AppEvents.LEVEL_CHANGED, self.on_level_change)
        
        # 3. AIエンジンの初期化
        self._init_ai_base()

    def _init_ai_base(self):
        """AIエンジンの共通初期化ロジック"""
        api_key = load_api_key()
        if api_key:
            # サーバーの生存確認
            if self.controller.api_client.health_check():
                self.gemini = GeminiCommentator(api_key)
                logger.info("AI Services Initialized.", layer="STARTUP")
            else:
                logger.warning("API Server not responding. AI features will be disabled.", layer="STARTUP")

    @abstractmethod
    def setup_layout(self, callbacks: dict):
        """UIの配置を各アプリで実装する"""
        pass

    def on_level_change(self, new_level):
        """解説レベル変更時の共通処理（必要に応じて各アプリでオーバーライド）"""
        import config
        config.TARGET_LEVEL = new_level
        logger.info(f"Commentary Mode changed to: {new_level}", layer="GUI")

    def on_close(self):
        """終了時のクリーンアップ処理（プロセスを強制終了して高速化）"""
        logger.info("Closing application (Force Exit)...", layer="GUI")
        
        # 1. APIプロセスの強制終了
        if self.api_proc:
            try:
                self.api_proc.kill()
            except: pass
            
        # 2. 自分自身のプロセスを即座に終了 (スレッドのjoin待ちをスキップ)
        import os
        os._exit(0)
