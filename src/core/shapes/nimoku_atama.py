from core.shapes.base_shape import BaseShape

class NimokuAtamaDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'

                # dr, dc は自軍二目の伸びる方向
                for dr, dc in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                    # 1. 自軍の構成チェック: 厳密に「二目」か？
                    r1, c1 = r, c
                    r2, c2 = r + dr, c + dc
                    r_prev, c_prev = r - dr, c - dc # 後ろ
                    r_head, c_head = r2 + dr, c2 + dc # 頭の地点
                    
                    # 自軍の石が2つ並んでいて、かつその後ろが自分ではないこと
                    if self._get_stone(curr_board, r2, c2) == color and \
                       self._get_stone(curr_board, r_prev, c_prev) != color:
                        
                        # さらに、頭の地点(r_head, c_head)が自分ではないこと（3つ並びを除外）
                        if self._get_stone(curr_board, r_head, c_head) == color:
                            continue

                        # 2. 相手の構成チェック: 横に2つ以上並走しているか
                        side_dr, side_dc = dc, dr
                        for mult in [1, -1]:
                            opp1_r, opp1_c = r1 + side_dr * mult, c1 + side_dc * mult
                            opp2_r, opp2_c = r2 + side_dr * mult, c2 + side_dc * mult
                            
                            # 自軍二目のそれぞれの横に相手の石が「2つ並んで」並走している
                            if self._get_stone(curr_board, opp1_r, opp1_c) == opp and \
                               self._get_stone(curr_board, opp2_r, opp2_c) == opp:
                                
                                # 3. かつ、その相手の並びから頭(r_head, c_head)をハネているか
                                if self._get_stone(curr_board, r_head, c_head) == opp:
                                    messages.append(
                                        f"  - 座標 {[self._to_coord(r1,c1), self._to_coord(r2,c2)]} の厳密な二目に対し、"
                                        f"横に並走する相手の石が {self._to_coord(r_head, c_head)} で「二目の頭」をハネています。"
                                    )
                                    break
        
        # 重複を排除して返す
        return "bad" if messages else None, list(set(messages))
