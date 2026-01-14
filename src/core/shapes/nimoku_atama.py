from core.shapes.base_shape import BaseShape

class NimokuAtamaDetector(BaseShape):
    key = "nimoku_no_atama"

    def detect(self, context):
        raw_hits = [] 
        for r in range(context.board_size):
            for c in range(context.board_size):
                color = self._get_stone(context.curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = self._get_opponent(color)
                
                for dr, dc in [(0, 1), (1, 0)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(context.curr_board, nr, nc) == color:
                        # 二目(r,c)-(nr,nc)を発見
                        for ar, ac in [(r-dr, c-dc), (nr+dr, nc+dc)]:
                            if self._get_stone(context.curr_board, ar, ac) == opp:
                                # 反対側の急所が空点(.)または盤外(edge)であることを確認
                                opp_r, opp_c = (ar-dr, ac-dc) if ar==r-dr else (ar+dr, ac+dc)
                                if self._get_stone(context.curr_board, opp_r, opp_c) in ['.', 'edge']:
                                    raw_hits.append(([(r,c), (nr,nc)], (ar,ac)))
        
        messages = []
        for victims, attacker in raw_hits:
            v_coords = sorted([self._to_coord(p[0], p[1]) for p in victims])
            a_coord = self._to_coord(attacker[0], attacker[1])
            messages.append(f"  - 座標 {v_coords} の二石に対し、{a_coord} で「二目の頭」を叩かれました。非常に痛い形です。")
        
        return "bad", list(set(messages))