from typing import List, Optional
from core.mcp_types import Move

class SessionManager:
    """
    MCPサーバ側で対局状態（セッション）を保持・管理するクラス。
    コンテキスト・オフローディングの中核となる。
    """
    
    def __init__(self):
        self._history: List[List] = []  # 内部的には [['B', 'D4'], ...] 形式で保持
        self._board_size: int = 19
        self._is_initialized: bool = False

    def update(self, history: List[List], board_size: int):
        """クライアント（AI等）からの情報を元にセッション状態を同期する"""
        self._history = history
        self._board_size = board_size
        self._is_initialized = True

    @property
    def history(self) -> List[List]:
        """現在の履歴を取得する"""
        return self._history

    @property
    def board_size(self) -> int:
        """現在の盤面サイズを取得する"""
        return self._board_size

    @property
    def is_initialized(self) -> bool:
        """セッションが一度でも同期されたかを確認する"""
        return self._is_initialized

    def get_merged_history(self, additional_moves: List[List]) -> List[List]:
        """現在の履歴に新しい手順を一時的に連結したものを返す（シミュレーション用）"""
        return self._history + additional_moves
