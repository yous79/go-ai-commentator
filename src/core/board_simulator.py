from sgfmill import boards
from core.coordinate_transformer import CoordinateTransformer

class BoardSimulator:
    """着手履歴やPVに基づいて盤面を復元・シミュレーションするクラス"""
    
    def __init__(self, board_size=19):
        self.board_size = board_size

    def reconstruct(self, history):
        """履歴から最新の盤面と直前の盤面を復元する"""
        curr = boards.Board(self.board_size)
        prev = boards.Board(self.board_size)
        
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
                curr.play(row, col, c_str.lower())
                
        last_color = history[-1][0].lower() if history else None
        return curr, prev, last_color

    def simulate_pv(self, base_board, pv_list, start_color):
        """
        基準となる盤面からPV（変化図）を進行させ、
        各ステップごとの盤面状態をジェネレーターとして返す
        """
        if not base_board:
            return

        sim_board = base_board.copy()
        current_color = start_color.lower()

        for move_str in pv_list:
            if not move_str or move_str.lower() == "pass":
                current_color = 'w' if current_color == 'b' else 'b'
                yield move_str, sim_board.copy(), None
                continue

            prev_state = sim_board.copy()
            idx = CoordinateTransformer.gtp_to_indices_static(move_str)
            if idx:
                row, col = idx
                try:
                    sim_board.play(row, col, current_color)
                    yield move_str, sim_board, prev_state, current_color
                    current_color = 'w' if current_color == 'b' else 'b'
                except:
                    break
            else:
                break