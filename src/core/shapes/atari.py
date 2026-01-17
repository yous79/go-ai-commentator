from core.point import Point
from core.board_simulator import BoardSimulator
from core.inference_fact import InferenceFact, FactCategory

class AtariDetector:
    """アタリ（呼吸点1）の状態を検知するディテクター"""
    key = "atari"

    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect(self, context):
        """現在の盤面からアタリのグループを抽出する"""
        board = context.curr_board
        size = board.side
        visited = set()
        atari_facts = []

        for r in range(size):
            for c in range(size):
                p = Point(r, c)
                color = board.get(r, c)
                if color and p not in visited:
                    # グループとその呼吸点を取得
                    group, liberties = BoardSimulator.get_group_and_liberties(board, p)
                    visited.update(group)
                    
                    # print(f"DEBUG: Group at {p.to_gtp()} color={color} liberties={len(liberties)}")
                    
                    if len(liberties) == 1:
                        # アタリ状態を検知
                        lib_point = list(liberties)[0]
                        color_name = "黒" if color == 'b' else "白"
                        stones_str = ",".join([s.to_gtp() for s in list(group)[:3]])
                        if len(group) > 3: stones_str += "..."
                        
                        desc = f"{color_name}の石 [{stones_str}] がアタリ（残り呼吸点: {lib_point.to_gtp()}）です。"
                        atari_facts.append(desc)

        return "info", atari_facts
