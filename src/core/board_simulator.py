from core.game_board import GameBoard, Color
from core.coordinate_transformer import CoordinateTransformer
from core.point import Point
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class SimulationContext:
    """特定の局面の状態（盤面、履歴、最新手など）をカプセル化したクラス"""
    board: GameBoard
    prev_board: Optional[GameBoard]
    history: List[List[str]]
    last_move: Optional[Point]
    last_color: Optional[Color]
    board_size: int
    captured_points: List[Point] = None # 最新手で取られた石のリスト

class BoardSimulator:
    """着手履歴やPVに基づいて盤面を復元・シミュレーションするクラス"""
    
    def __init__(self, board_size=19):
        self.board_size = board_size

    def reconstruct_to_context(self, history, board_size=None) -> SimulationContext:
        """履歴から SimulationContext を生成する（唯一の復元口）"""
        sz = board_size or self.board_size
        curr = GameBoard(sz)
        prev = GameBoard(sz)
        last_captured = []
        
        for i, move_data in enumerate(history):
            if not isinstance(move_data, (list, tuple)) or len(move_data) < 2:
                continue
            
            c_str, m_str = move_data[0], move_data[1]
            color = Color.from_str(c_str)
            
            if not m_str or (isinstance(m_str, str) and m_str.lower() == "pass"):
                # パスの場合はコウの状態を解除して次へ
                curr.apply_pass()
                if i == len(history) - 1:
                    prev = curr.copy()
                continue
            
            idx = CoordinateTransformer.gtp_to_indices_static(m_str)
            if idx and color:
                pt = Point(idx[0], idx[1])
                # 直前の盤面を記録
                if i == len(history) - 1:
                    prev = curr.copy()
                
                # 合法手チェック（自殺手・コウ等の不備のある履歴をスキップ）
                if curr.is_legal(pt, color):
                    # 石を置き、キャプチャ情報を取得
                    captured = curr.play(pt, color)
                    # 最後の手の場合のみキャプチャ情報を保持
                    if i == len(history) - 1:
                        last_captured = captured
                else:
                    from utils.logger import logger
                    logger.warning(f"Skipping illegal move in history: {c_str}[{m_str}] at move {i}", layer="SIMULATOR")

        last_move_str = history[-1][1] if history else None
        last_move_pt = Point.from_gtp(last_move_str) if (last_move_str and last_move_str != "pass") else None
        last_color = Color.from_str(history[-1][0]) if history else None

        return SimulationContext(
            board=curr,
            prev_board=prev,
            history=history,
            last_move=last_move_pt,
            last_color=last_color,
            board_size=sz,
            captured_points=last_captured
        )

    def simulate_sequence(self, base_ctx: SimulationContext, sequence: List[str], starting_color=None) -> SimulationContext:
        """既存のコンテキストに手順を追加して、新しい未来のコンテキストを生成する"""
        new_history = list(base_ctx.history)
        
        # 開始色の決定
        if starting_color:
            current_color_obj = Color.from_str(starting_color)
        else:
            last_c = base_ctx.last_color or Color.WHITE
            current_color_obj = last_c.opposite()
        
        for move_str in sequence:
            new_history.append([current_color_obj.key.upper()[:1], move_str])
            current_color_obj = current_color_obj.opposite()
            
        return self.reconstruct_to_context(new_history, base_ctx.board_size)