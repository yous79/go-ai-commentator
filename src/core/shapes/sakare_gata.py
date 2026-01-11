from core.shapes.base_shape import BaseShape

class SakareGataDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        bad_messages = []
        normal_messages = []
        checked = set()
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'
                
                # 1. 一間トビ
                for dr, dc in [(0,2), (2,0)]:
                    nr, nc = r+dr, c+dc
                    if self._get_stone(curr_board, nr, nc) == color:
                        pair = tuple(sorted([(r,c), (nr,nc)]))
                        if pair in checked: continue
                        checked.add(pair)
                        mr, mc = r+dr//2, c+dc//2
                        if self._get_stone(curr_board, mr, mc) == opp:
                            pierced = False
                            if dr == 0:
                                if self._get_stone(curr_board, mr-1, mc)==opp or self._get_stone(curr_board, mr+1, mc)==opp:
                                    pierced = True
                            else:
                                if self._get_stone(curr_board, mr, mc-1)==opp or self._get_stone(curr_board, mr, mc+1)==opp:
                                    pierced = True
                            if pierced:
                                if not self._is_connected(curr_board, (r,c), (nr,nc), color):
                                    bad_messages.append(f"  - 相手に突き抜けられ、{[self._to_coord(r,c), self._to_coord(nr,nc)]} が「サカレ形」に分断されています。")
                                else:
                                    normal_messages.append(f"  - 座標 {self._to_coord(mr,mc)} に「割り込み」がありますが、{[self._to_coord(r,c), self._to_coord(nr,nc)]} は連絡を保っています。")

                # 2. ケイマ
                for dr, dc in [(1,2), (2,1), (-1,2), (-2,1)]:
                    nr, nc = r+dr, c+dc
                    if self._get_stone(curr_board, nr, nc) == color:
                        pair = tuple(sorted([(r,c), (nr,nc)]))
                        if pair in checked: continue
                        checked.add(pair)
                        w1 = (r, c+(1 if dc>0 else -1)) if abs(dc)==2 else (r+(1 if dr>0 else -1), c)
                        w2 = (nr, nc-(1 if dc>0 else -1)) if abs(dc)==2 else (nr-(1 if dr>0 else -1), nc)
                        if self._get_stone(curr_board, *w1)==opp and self._get_stone(curr_board, *w2)==opp:
                            if not self._is_connected(curr_board, (r,c), (nr,nc), color):
                                bad_messages.append(f"  - 相手に突き抜けられ、{[self._to_coord(r,c), self._to_coord(nr,nc)]} が「サカレ形」に分断されています。")
                            else:
                                normal_messages.append(f"  - 座標 {self._to_coord(*w1)}と{self._to_coord(*w2)} に「割り込み」がありますが、連絡を保っています。")
        return "mixed", (bad_messages, normal_messages)
