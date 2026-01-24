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

class RyoAtariDetector:
    """両アタリ（2つ以上のグループを同時にアタリにする）を検知するディテクター"""
    key = "ryo_atari"

    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect(self, context):
        """最新の着手によって複数の相手グループがアタリになったか判定する"""
        if not context.last_move:
            return "normal", []
            
        board = context.curr_board
        opp_color = context.last_color.opposite()
        atari_groups = []
        liberty_coords = []
        
        # 最新手の隣接点にある相手石をチェック
        for neighbor in context.last_move.neighbors(board.side):
            if board.get(neighbor) == opp_color:
                group, liberties = board.get_group_and_liberties(neighbor)
                # print(f"[DEBUG RyoAtari] Neighbor {neighbor.to_gtp()} group={len(group)} liberties={len(liberties)}")
                if len(liberties) == 1:
                    # グループの代表座標（最小座標など）で重複を避ける
                    representative = min(group)
                    if representative not in [g[0] for g in atari_groups]:
                        lib_point = list(liberties)[0]
                        atari_groups.append((representative, lib_point))
                        liberty_coords.append(lib_point.to_gtp())

        # print(f"[DEBUG RyoAtari] Final count: {len(atari_groups)}")
        if len(atari_groups) >= 2:
            # 重複を除去した逃げ道のリストを作成
            unique_libs = sorted(list(set(liberty_coords)))
            msg = f"相手の2つの群を同時に【両アタリ】にしました（逃げ道は {' と '.join(unique_libs)}）。"
            res = {"message": msg, "remedy_gtp": unique_libs[0], "all_remedies": unique_libs}
            return "info", [res]

        return "normal", []
