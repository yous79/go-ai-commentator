from typing import Callable, Dict, List, Any
from utils.logger import logger

class EventBus:
    """
    システム内でのイベント発行・購読を管理するシンプルなメッセージバス。
    コンポーネント間の疎結合を実現する。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers: Dict[str, List[Callable]] = {}
        return cls._instance

    def subscribe(self, event_type: str, callback: Callable[[Any], None]):
        """特定のイベントタイプに対して購読を登録する"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to event: {event_type}", layer="EVENT")

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]):
        """特定の購読を解除する"""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_type}", layer="EVENT")

    def clear_all_subscribers(self):
        """すべての購読をリセットする（アプリ全体の再初期化時用）"""
        self._subscribers = {}
        logger.warning("All event subscribers cleared.", layer="EVENT")

    def publish(self, event_type: str, data: Any = None):
        """イベントを発行し、登録されているすべての購読者に通知する"""
        if event_type in self._subscribers:
            logger.debug(f"Publishing event: {event_type}", layer="EVENT")
            # 実行中に購読解除される可能性を考慮してコピーを使用
            for callback in list(self._subscribers[event_type]):
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}", layer="EVENT")

# Global Singleton Instance
event_bus = EventBus()

# Event Type Definitions
class AppEvents:
    MOVE_CHANGED = "MOVE_CHANGED"       # 手番が移動した (data: move_idx)
    STATE_UPDATED = "STATE_UPDATED"     # 盤面・解析データが更新された (data: dict)
    LEVEL_CHANGED = "LEVEL_CHANGED"     # 解説レベルが変更された (data: level_id)
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED" # 解析が完了した
    
    # --- 新規追加 ---
    BOARD_REDRAW_REQUESTED = "BOARD_REDRAW_REQUESTED" # 盤面の再描画 (data: dict)
    MISTAKES_UPDATED = "MISTAKES_UPDATED"             # 悪手情報の更新 (data: dict)
    COMMENTARY_READY = "COMMENTARY_READY"             # 解説テキストの準備完了 (data: str)
    STATUS_MSG_UPDATED = "STATUS_MSG_UPDATED"         # ステータスバーのメッセージ (data: str)
    PROGRESS_UPDATED = "PROGRESS_UPDATED"             # 進捗バーの更新 (data: int)
    FACT_DISCOVERED = "FACT_DISCOVERED"               # 解析エンジンが新しい事実を発見した (data: InferenceFact)
