import threading
import concurrent.futures
from typing import Callable, Any, Optional
from utils.logger import logger

class AsyncTaskManager:
    """
    GUIをフリーズさせずに重い処理（AI解析等）を実行し、
    結果を安全にメインスレッドへ戻すためのマネージャー。
    """
    def __init__(self, root, max_workers: int = 3):
        self.root = root
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="GoAIWorker"
        )
        logger.info(f"AsyncTaskManager initialized with {max_workers} workers.", layer="ASYNC")

    def run_task(self, 
                 task_func: Callable[[], Any], 
                 on_success: Optional[Callable[[Any], None]] = None,
                 on_error: Optional[Callable[[Exception], None]] = None,
                 pre_task: Optional[Callable[[], None]] = None):
        """
        タスクを非同期で実行する。
        
        Args:
            task_func: バックグラウンドで実行する重い処理。
            on_success: 成功時にメインスレッドで呼ばれるコールバック（引数はtask_funcの戻り値）。
            on_error: 例外発生時にメインスレッドで呼ばれるコールバック。
            pre_task: 実行直前にメインスレッドで呼ばれる前処理（ボタンの無効化など）。
        """
        # 1. 前処理（メインスレッド）
        if pre_task:
            pre_task()

        def _wrapper():
            try:
                # 2. 本処理（バックグラウンドスレッド）
                result = task_func()
                
                # 3. 成功時コールバック（メインスレッドに戻す）
                if on_success:
                    self.root.after(0, lambda: on_success(result))
                    
            except Exception as e:
                logger.error(f"Async task failed: {e}", layer="ASYNC")
                # 4. エラー時コールバック（メインスレッドに戻す）
                if on_error:
                    self.root.after(0, lambda: on_error(e))
                else:
                    # デフォルトのエラー表示（もし必要なら）
                    import traceback
                    traceback.print_exc()

        # スレッドプールへ投入
        self.executor.submit(_wrapper)

    def shutdown(self):
        """スレッドプールを安全に停止させる"""
        logger.info("Shutting down AsyncTaskManager...", layer="ASYNC")
        self.executor.shutdown(wait=False)
