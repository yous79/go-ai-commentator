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

    def publish(self, event_type: str, data: Any = None):
        """イベントを発行し、登録されているすべての購読者に通知する"""
        if event_type in self._subscribers:
            logger.debug(f"Publishing event: {event_type}", layer="EVENT")
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}", layer="EVENT")

# Global Singleton Instance
event_bus = EventBus()

# Event Type Definitions
class AppEvents:
    MOVE_CHANGED = "MOVE_CHANGED"       # 手番が移動した (data: move_idx)
    STATE_UPDATED = "STATE_UPDATED"     # 盤面・解析データが更新された (data: AnalysisResult)
    LEVEL_CHANGED = "LEVEL_CHANGED"     # 解説レベルが変更された (data: level_id)
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED" # 解析が完了した
