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
                    # 1. 自軍の二目 (r1,c1) -> (r2,c2)
                    r1, c1 = r, c
                    r2, c2 = r + dr, c + dc
                    if self._get_stone(curr_board, r2, c2) == color:
                        
                        # 自軍の頭（進行方向の3点目）
                        head_r, head_c = r2 + dr, c2 + dc
                        
                        # 2. 真横のラインをチェック (side_dr, side_dc)
                        # 垂直移動なら左右、水平移動なら上下
                        side_dr, side_dc = dc, dr
                        for mult in [1, -1]:
                            # 自軍二目のそれぞれの横
                            opp1_r, opp1_c = r1 + side_dr * mult, c1 + side_dc * mult
                            opp2_r, opp2_c = r2 + side_dr * mult, c2 + side_dc * mult
                            
                            # 相手の石が「2つ並んで」並走しているか
                            if self._get_stone(curr_board, opp1_r, opp1_c) == opp and \
                               self._get_stone(curr_board, opp2_r, opp2_c) == opp:
                                
                                # 3. かつ、その相手の並びの先端(opp2)から頭(head)をハネているか
                                if self._get_stone(curr_board, head_r, head_c) == opp:
                                    messages.append(
                                        f"  - 座標 {[self._to_coord(r1,c1), self._to_coord(r2,c2)]} の二目に対し、"
                                        f"横に並んだ相手の石 {[self._to_coord(opp1_r,opp1_c), self._to_coord(opp2_r,opp2_c)]} が "
                                        f"{self._to_coord(head_r, head_c)} で「二目の頭」をハネています。"
                                    )
                                    break
        
        return "bad" if messages else None, list(set(messages))
