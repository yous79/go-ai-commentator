from core.point import Point
from core.game_board import GameBoard, Color
from core.inference_fact import InferenceFact, FactCategory

class AtariDetector:
    """アタリ（呼吸点1）の状態を検知するディテクター"""
    key = "atari"

    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect(self, context):
        """最新の着手によって相手がアタリになったか判定する"""
        if not context.last_move:
            return "normal", []
            
        board = context.curr_board
        opp_color = context.last_color.opposite()
        atari_msgs = []
        
        # 最新手の隣接点にある相手石をチェック
        for neighbor in context.last_move.neighbors(board.side):
            if board.get(neighbor) == opp_color:
                group, liberties = board.get_group_and_liberties(neighbor)
                if len(liberties) == 1:
                    lib_point = list(liberties)[0]
                    msg = f"相手の石を【アタリ】にしました（{neighbor.to_gtp()}付近、逃げ道は{lib_point.to_gtp()}）。"
                    if msg not in atari_msgs:
                        atari_msgs.append(msg)

        return "info", atari_msgs
