from core.shapes.base_shape import BaseShape
from core.point import Point

class PonnukiDetector(BaseShape):
    """
    最新の一手で相手の石をちょうど1つ抜き去り、
    ダイヤモンド型（ポン抜き）を完成させた瞬間を検知する。
    """
    key = "ponnuki"

    def detect(self, context):
        if not context.prev_board or not context.last_move:
            return "normal", []

        # 1. 相手の石が消えた場所を特定する
        # (最新の着手によってアゲハマになった地点を探す)
        opp_color = self._get_opponent(context.last_color)
        removed_points = []
        
        # パフォーマンス向上のため、最新着手の周囲に限定して探索
        # ポン抜きの場合、抜かれた石は最新着手の隣接点のはず
        for neighbor in context.last_move.neighbors(self.board_size):
            was_opp = (context.prev_board.get(neighbor.row, neighbor.col) == opp_color)
            is_empty = (context.curr_board.get(neighbor.row, neighbor.col) is None)
            
            if was_opp and is_empty:
                removed_points.append(neighbor)

        # 2. 1石抜きであるかを確認
        if len(removed_points) != 1:
            return "normal", []

        # 3. 抜かれた地点(p)の周囲4方向がすべて攻撃側(last_color)の石であることを確認
        p = removed_points[0]
        if all(self._get_stone(context.curr_board, n) == context.last_color for n in p.neighbors(self.board_size)):
            # 最新の着手(context.last_move)がこの4石のいずれかであることは1.で保証済み
            msg = f"相手に【ポン抜き】を許しました（{p.to_gtp()}の地点）。「ポン抜き30目」と言われるほど強力な厚みを与えてしまった深刻な失着です。"
            return "bad", [msg]

        return "normal", []
