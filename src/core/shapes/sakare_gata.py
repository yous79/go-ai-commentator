from core.shapes.base_shape import BaseShape

class SakareGataDetector(BaseShape):
    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        checked_pairs = set()

        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'
                
                # 1. 一間トビのサカレ (距離が2)
                for dr, dc in [(0, 2), (2, 0)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(curr_board, nr, nc) == color:
                        pair = tuple(sorted([(r, c), (nr, nc)]))
                        if pair in checked_pairs: continue
                        checked_pairs.add(pair)

                        mr, mc = r + dr // 2, c + dc // 2
                        if self._get_stone(curr_board, mr, mc) == opp:
                            # 突き抜けチェック (横のライン)
                            s_dr, s_dc = dc // 2, dr // 2
                            if self._get_stone(curr_board, mr + s_dr, mc + s_dc) == opp or \
                               self._get_stone(curr_board, mr - s_dr, mc - s_dc) == opp:
                                if not self._is_connected(curr_board, (r, c), (nr, nc), color):
                                    messages.append(f"  - 相手に一間トビを突き抜けられ、{[self._to_coord(r, c), self._to_coord(nr, nc)]} が「サカレ形」に分断されています。")

                # 2. ケイマのサカレ (1,2 / 2,1)
                for dr, dc in [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(curr_board, nr, nc) == color:
                        pair = tuple(sorted([(r, c), (nr, nc)]))
                        if pair in checked_pairs: continue
                        checked_pairs.add(pair)

                        # ケイマの「間」の2点を決定
                        if abs(dr) == 2:
                            w1, w2 = (r + dr // 2, c), (r + dr // 2, c + dc)
                        else:
                            w1, w2 = (r, c + dc // 2), (r + dr, c + dc // 2)
                        
                        if self._get_stone(curr_board, w1[0], w1[1]) == opp and \
                           self._get_stone(curr_board, w2[0], w2[1]) == opp:
                            if not self._is_connected(curr_board, (r, c), (nr, nc), color):
                                messages.append(f"  - 相手にケイマを突き抜けられ、{[self._to_coord(r, c), self._to_coord(nr, nc)]} が「サカレ形」に分断されています。")

        return "bad" if messages else None, list(set(messages))