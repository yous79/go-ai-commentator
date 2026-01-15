from core.shapes.base_shape import BaseShape
from core.point import Point

class SakareGataDetector(BaseShape):

    key = "sakare_gata"



    def detect(self, context):

        messages = []

        checked_pairs = set()

        sz = context.board_size

        

        # 調査対象のオフセット（一間トビとケイマの全方向）

        offsets = [

            (0, 2), (0, -2), (2, 0), (-2, 0), # 一間トビ

            (1, 2), (1, -2), (-1, 2), (-1, -2), # ケイマ

            (2, 1), (2, -1), (-2, 1), (-2, -1)

        ]



        for r in range(sz):

            for c in range(sz):

                p = Point(r, c)

                color = self._get_stone(context.curr_board, p)

                if color not in ['b', 'w']: continue

                opp = self._get_opponent(color)

                

                for dr, dc in offsets:

                    np = p + (dr, dc)

                    if not np.is_valid(sz): continue

                    if self._get_stone(context.curr_board, np) == color:

                        

                        # 中間点（急所）のリストアップ

                        vitals = []

                        if abs(dr) == 0 or abs(dc) == 0: # 一間トビ

                            vitals.append(p + (dr // 2, dc // 2))

                        else: # ケイマ

                            if abs(dr) == 1: # 横長ケイマ

                                vitals.append(p + (0, dc // 2))

                                vitals.append(p + (dr, dc // 2))

                            else: # 縦長ケイマ

                                vitals.append(p + (dr // 2, 0))

                                vitals.append(p + (dr // 2, dc))

                        

                        # すでに連結されている場合はサカレ形ではない

                        if self._is_connected(context.curr_board, p, np, color):

                            continue

                        

                        # 急所のいずれかに相手の石があるかチェック

                        is_split = any(self._get_stone(context.curr_board, v) == opp for v in vitals)

                        

                        if is_split:

                            pair = tuple(sorted([p, np]))

                            if pair not in checked_pairs:

                                checked_pairs.add(pair)

                                messages.append(f"  - 座標 {sorted([p.to_gtp(), np.to_gtp()])} が「サカレ形」に分断されました。")

        

        return "bad", list(set(messages))
