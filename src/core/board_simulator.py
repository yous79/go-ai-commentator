from sgfmill import boards

class BoardSimulator:
    """着手履歴やPVに基づいて盤面を復元・シミュレーションするクラス"""
    
    def __init__(self, board_size=19):
        self.board_size = board_size
        self.cols = "ABCDEFGHJKLMNOPQRST"

    def reconstruct(self, history):
        """履歴から最新の盤面と直前の盤面を復元する"""
        curr = boards.Board(self.board_size)
        prev = boards.Board(self.board_size)
        
        for i, move_data in enumerate(history):
            # 履歴データの形式チェック (リスト/タプルで長さ2以上)
            if not isinstance(move_data, (list, tuple)) or len(move_data) < 2:
                continue
            
            c_str, m_str = move_data[0], move_data[1]
            
            if not m_str or (isinstance(m_str, str) and m_str.lower() == "pass"):
                if i < len(history) - 1:
                    # パスの場合でも手番が進むので、prevの状態管理が必要ならここに記述
                    # 今回は盤面配置のみ重要なのでスキップ
                    pass
                continue
            
            try:
                col = self.cols.index(m_str[0].upper())
                row = int(m_str[1:]) - 1
                
                # 直前の盤面（prev）は、最後の一手が打たれる前の状態
                if i < len(history) - 1:
                    prev.play(row, col, c_str.lower())
                
                curr.play(row, col, c_str.lower())
            except ValueError:
                pass # 無効な座標などは無視
                
        last_color = history[-1][0].lower() if history else None
        return curr, prev, last_color

    def simulate_pv(self, base_board, pv_list, start_color):
        """
        基準となる盤面からPV（変化図）を進行させ、
        各ステップごとの盤面状態をジェネレーターとして返す
        """
        if not base_board:
            return

        # 副作用を防ぐためにコピー
        sim_board = base_board.copy()
        current_color = start_color.lower()

        for move_str in pv_list:
            if not move_str or move_str.lower() == "pass":
                current_color = 'w' if current_color == 'b' else 'b'
                yield move_str, sim_board.copy(), None # パスの場合は盤面変化なし
                continue

            prev_state = sim_board.copy()
            try:
                col = self.cols.index(move_str[0].upper())
                row = int(move_str[1:]) - 1
                sim_board.play(row, col, current_color)
                
                # move_str, 適用後の盤面, 適用前の盤面, 打った色
                yield move_str, sim_board, prev_state, current_color
                
                current_color = 'w' if current_color == 'b' else 'b'
            except ValueError:
                break
