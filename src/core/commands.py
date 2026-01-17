from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass
from core.point import Point
from core.game_board import Color
from utils.logger import logger

class Command(ABC):
    """すべての対局操作コマンドの基底クラス"""
    @abstractmethod
    def execute(self) -> bool:
        """コマンドを実行する"""
        pass

    @abstractmethod
    def undo(self):
        """コマンドを取り消す（逆の操作を行う）"""
        pass

@dataclass
class PlayMoveCommand(Command):
    """石を置く（またはパスする）コマンド"""
    def __init__(self, game_state, move_idx: int, color: Color, pt: Optional[Point]):
        self.game = game_state
        self.move_idx = move_idx
        self.color = color
        self.pt = pt
        self.prev_total_moves = 0
        self.added_node = None # Undo用の記録

    def execute(self) -> bool:
        self.prev_total_moves = self.game.total_moves
        # 実際に追加するロジック（後ほどGameState側にコマンド対応メソッドを作るか、ここで行う）
        success = self.game.add_move(self.move_idx, self.color.key.upper()[:1], 
                                     self.pt.row if self.pt else None, 
                                     self.pt.col if self.pt else None)
        if success:
            logger.info(f"Executed: PlayMove({self.color.label} {self.pt.to_gtp() if self.pt else 'PASS'})", layer="COMMAND")
        return success

    def undo(self):
        # GameStateに「最新の1手を削除する」機能を実装する必要あり
        if self.game.remove_last_move():
            logger.info("Undone: PlayMove", layer="COMMAND")


class CommandInvoker:
    """コマンドの実行と履歴（Undo/Redo）を管理するクラス"""
    def __init__(self):
        self.history: List[Command] = []
        self.redo_stack: List[Command] = []

    def execute(self, command: Command) -> bool:
        if command.execute():
            self.history.append(command)
            self.redo_stack.clear() # 新しい操作をしたらRedoは消える
            return True
        return False

    def undo(self):
        if not self.history:
            return
        cmd = self.history.pop()
        cmd.undo()
        self.redo_stack.append(cmd)

    def redo(self):
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        if cmd.execute():
            self.history.append(cmd)
