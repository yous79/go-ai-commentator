from core.shapes.base_shape import BaseShape

class NimokuAtamaDetector(BaseShape):
    key = "nimoku_no_atama"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        raw_hits = [] # [(victim_coords, attacker_coord), ...]
        
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'

                # 2方向（右、下）を基準にペアを走査
                for dr, dc in [(1, 0), (0, 1)]:
                    r1, c1 = r, c
                    r2, c2 = r + dr, c + dc
                    if self._get_stone(curr_board, r2, c2) != color: continue

                    # 二目の前後を特定
                    directions = [
                        {'tail': (r1-dr, c1-dc), 'head': (r2+dr, c2+dc), 'pair': ((r1, c1), (r2, c2))},
                        {'tail': (r2+dr, c2+dc), 'head': (r1-dr, c1-dc), 'pair': ((r2, c2), (r1, c1))}
                    ]

                    for d in directions:
                        t_r, t_c = d['tail']
                        h_r, h_c = d['head']
                        p1, p2 = d['pair']

                        # 自軍が厳密に「二目」か
                        if self._get_stone(curr_board, t_r, t_c) == color: continue
                        if self._get_stone(curr_board, h_r, h_c) == color: continue

                        # 横のラインをチェック
                        side_dr, side_dc = dc, dr
                        for mult in [1, -1]:
                            s1_r, s1_c = p1[0] + side_dr * mult, p1[1] + side_dc * mult
                            s2_r, s2_c = p2[0] + side_dr * mult, p2[1] + side_dc * mult
                            
                            if self._get_stone(curr_board, s1_r, s1_c) == opp and \
                               self._get_stone(curr_board, s2_r, s2_c) == opp:
                                
                                if self._get_stone(curr_board, h_r, h_c) == opp:
                                    # 1. 【先制の利】反対側の頭が空点か
                                    os_r, os_c = h_r + side_dr * (-mult), h_c + side_dc * (-mult)
                                    if self._get_stone(curr_board, os_r, os_c) != '.': continue
                                    
                                    # 2. 【孤立性】周囲に味方がいないか（二目自身を除く）
                                    has_neighbor = False
                                    nimoku_coords = [p1, p2]
                                    for nr in [-1, 0, 1]:
                                        for nc in [-1, 0, 1]:
                                            if nr == 0 and nc == 0: continue
                                            cr, cc = h_r + nr, h_c + nc
                                            if (cr, cc) not in nimoku_coords:
                                                if self._get_stone(curr_board, cr, cc) == color:
                                                    has_neighbor = True; break
                                        if has_neighbor: break
                                    
                                    if not has_neighbor:
                                        # 候補として一時保存
                                        raw_hits.append({
                                            'victim_pair': set(nimoku_coords),
                                            'attacker': (h_r, h_c),
                                            'msg': f"  - 座標 {[self._to_coord(p1[0], p1[1]), self._to_coord(p2[0], p2[1])]} の二目に対し、相手が {self._to_coord(h_r, h_c)} をハネて「二目の頭」を叩いています。"
                                        })

        # 3. 相互叩き合いの相殺ロジック
        final_messages = []
        excluded_indices = set()

        for i, hit1 in enumerate(raw_hits):
            if i in excluded_indices: continue
            
            is_mutual = False
            for j, hit2 in enumerate(raw_hits):
                if i == j: continue
                # hit1の攻撃者が、hit2の被害者ペアの一部である
                # かつ、hit2の攻撃者が、hit1の被害者ペアの一部である
                if hit1['attacker'] in hit2['victim_pair'] and \
                   hit2['attacker'] in hit1['victim_pair']:
                    is_mutual = True
                    excluded_indices.add(j)
                    break
            
            if not is_mutual:
                final_messages.append(hit1['msg'])

        return "bad" if final_messages else None, final_messages
