from sgfmill import boards
from core.coordinate_transformer import CoordinateTransformer
from core.point import Point
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class SimulationContext:
    """特定の局面の状態（盤面、履歴、最新手など）をカプセル化したクラス"""
    board: any
    prev_board: Optional[any]
    history: List[List[str]]
    last_move: Optional[Point]
    last_color: Optional[str] # 'b' or 'w'
    board_size: int

class BoardSimulator:
    """着手履歴やPVに基づいて盤面を復元・シミュレーションするクラス"""
    
    def __init__(self, board_size=19):
        self.board_size = board_size

    def reconstruct_to_context(self, history, board_size=None) -> SimulationContext:
        """履歴から SimulationContext を生成する（唯一の復元口）"""
        sz = board_size or self.board_size
        curr = boards.Board(sz)
        prev = boards.Board(sz)
        
        for i, move_data in enumerate(history):
            if not isinstance(move_data, (list, tuple)) or len(move_data) < 2:
                continue
            
            c_str, m_str = move_data[0], move_data[1]
            if not m_str or (isinstance(m_str, str) and m_str.lower() == "pass"):
                continue
            
            idx = CoordinateTransformer.gtp_to_indices_static(m_str)
            if idx:
                row, col = idx
                if i < len(history) - 1:
                    prev.play(row, col, c_str.lower())
                try:
                    curr.play(row, col, c_str.lower())
                except: pass # 非合法手は無視

        last_move_str = history[-1][1] if history else None
        last_move_pt = Point.from_gtp(last_move_str) if (last_move_str and last_move_str != "pass") else None
        last_color = history[-1][0].lower() if history else None

        return SimulationContext(
            board=curr,
            prev_board=prev,
            history=history,
            last_move=last_move_pt,
            last_color=last_color,
            board_size=sz
        )

    def simulate_sequence(self, base_ctx: SimulationContext, sequence: List[str], starting_color=None) -> SimulationContext:
        """既存のコンテキストに手順を追加して、新しい未来のコンテキストを生成する"""
        new_history = list(base_ctx.history)
        
        # 開始色の決定
        if starting_color:
            current_color = starting_color.lower()
        else:
            last_c = base_ctx.last_color or 'w'
            current_color = 'b' if last_c == 'w' else 'w'
        
        for move_str in sequence:
            new_history.append([current_color.upper(), move_str])
            current_color = 'w' if current_color == 'b' else 'b'
            
        return self.reconstruct_to_context(new_history, base_ctx.board_size)