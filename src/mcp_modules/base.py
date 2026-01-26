from typing import List, Optional, Tuple, Any
from mcp_modules.session import SessionManager
from core.mcp_types import Move

class McpModuleBase:
    """
    All MCP modules should inherit from this base class to ensure standardized
    context resolution and session management.
    """
    def __init__(self, session_manager: SessionManager):
        self.session = session_manager

    def resolve_context(self, history: Optional[List[Any]], board_size: Optional[int]) -> Tuple[List[List], int]:
        """
        Resolves the game context (history and board size) from explicit arguments 
        or falls back to the active session.
        
        Args:
            history: Optional list of moves (Move objects or lists).
            board_size: Optional board size integer.
            
        Returns:
            Tuple of (clean_history_list, effective_board_size).
            
        Raises:
            ValueError: If no context is available (neither argument nor session).
        """
        # 1. Prefer explicit arguments if provided
        if history is not None:
            clean_history = [m.to_list() if hasattr(m, "to_list") else m for m in history]
            effective_size = board_size or (self.session.board_size if self.session.is_initialized else 19)
            # If explicit history is given, we prioritize it, but board_size might fallback to session if omitted
            if board_size is None and self.session.is_initialized:
                 effective_size = self.session.board_size
            else:
                 effective_size = board_size or 19
                 
            return clean_history, effective_size

        # 2. Fallback to session
        if not self.session.is_initialized:
            raise ValueError("No active session. Please provide history or sync session first.")
            
        return self.session.history, (board_size or self.session.board_size)
