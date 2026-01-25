from core.shapes.base_shape import BaseShape
from core.point import Point
from core.game_board import Color
from core.inference_fact import ShapeMetadata

class PonnukiDetector(BaseShape):
    """
    最新の一手で相手の石をちょうど1つ抜き去り、
    ダイヤモンド型（ポン抜き）を完成させた瞬間を検知する。
    """
    key = "ponnuki"

    def detect(self, context):
        if not context.prev_board or not context.last_move or not context.last_color:
            return "normal", []

        # Ko(コウ)の状態が新しく発生した場合は、ポン抜きとして検知しない
        if context.curr_board.ko_point:
            return "normal", []

        # 1. 相手の石が消えた場所を特定する
        opp_color_char = self._get_opponent(context.last_color)
        removed_points = []
        
        for neighbor in context.last_move.neighbors(self.board_size):
            prev_color = context.prev_board.get(neighbor)
            was_opp = (prev_color and prev_color.value == opp_color_char)
            is_empty = context.curr_board.is_empty(neighbor)
            
            if was_opp and is_empty:
                removed_points.append(neighbor)

        if len(removed_points) != 1:
            return "normal", []

        # 3. 抜かれた地点(p)の周囲4方向がすべて攻撃側(last_color)の石であることを確認
        p = removed_points[0]
        attacker_color_char = context.last_color.value
        
        if all(self._get_stone(context.curr_board, n) == attacker_color_char for n in p.neighbors(self.board_size)):
            msg = f"相手に【ポン抜き】を許しました（{p.to_gtp()}の地点）。「ポン抜き30目」と言われるほど強力な厚みを与えてしまった深刻な失着です。"
            return "bad", [{"message": msg, "metadata": ShapeMetadata(key=self.key)}]

        return "normal", []