class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect_all(self, board):
        facts = []
        
        # 1. アキ三角の検知
        aki_results = self.detect_aki_sankaku(board)
        if aki_results:
            facts.append("■ 確定した悪形（アキ三角）:")
            for res in aki_results:
                facts.append(f"  - 座標 {res['coords']} に「アキ三角」を検知。効率の悪い重い形です。")

        # 2. サカレ形の検知（一間トビ・ケイマの貫通を重視）
        sakare_results = self.detect_sakare_gata(board)
        if sakare_results:
            facts.append("■ 形状の分析（分断と連絡）:")
            for res in sakare_results:
                if res['is_sakare']:
                    facts.append(f"  - 相手に突き抜けられ、{res['my_coords']} が「サカレ形」に分断されています。")
                else:
                    facts.append(f"  - 座標 {res['opp_coord']} に「割り込み」がありますが、{res['my_coords']} はコスミ等の形で連絡を保っておりサカレ形ではありません。")

        return "\n".join(facts) if facts else ""

    def _get_stone(self, board, r, c):
        if 0 <= r < self.board_size and 0 <= c < self.board_size:
            return board.get(r, c)
        return "edge"

    def _to_coord(self, r, c):
        cols = "ABCDEFGHJKLMNOPQRST"
        return f"{cols[c]}{r+1}"

    def detect_aki_sankaku(self, board):
        results = []
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                cells = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                for color in ['b', 'w']:
                    stones = [p for p in cells if self._get_stone(board, p[0], p[1]) == color]
                    empties = [p for p in cells if self._get_stone(board, p[0], p[1]) is None]
                    if len(stones) == 3 and len(empties) == 1:
                        empty_p = empties[0]
                        diag_r = r if empty_p[0] == r + 1 else r + 1
                        diag_c = c if empty_p[1] == c + 1 else c + 1
                        if self._get_stone(board, diag_r, diag_c) == color:
                            coords = [self._to_coord(p[0], p[1]) for p in stones]
                            results.append({"color": color, "coords": sorted(coords)})
        return results

    def _is_connected(self, board, p1, p2, color):
        """2つの石が直接、あるいはコスミ（第3の石）で繋がっているか判定"""
        r1, c1 = p1
        r2, c2 = p2
        # 直接隣接
        if abs(r1-r2) + abs(c1-c2) == 1: return True
        # コスミ
        if abs(r1-r2) == 1 and abs(c1-c2) == 1: return True
        
        # 第3の石によるコスミ連絡の検索
        # p1 と p2 の両方にコスミまたは隣接している自石があるか
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                mid_r, mid_c = r1 + dr, c1 + dc
                if self._get_stone(board, mid_r, mid_c) == color:
                    # この第3の石が p2 とも繋がっているか
                    if (abs(mid_r-r2) <= 1 and abs(mid_c-c2) <= 1):
                        return True
        return False

    def detect_sakare_gata(self, board):
        results = []
        checked_pairs = set()

        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'

                # 1. 一間トビの分断 (縦・横)
                for dr, dc in [(0, 2), (2, 0)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(board, nr, nc) == color:
                        pair = tuple(sorted([(r, c), (nr, nc)]))
                        if pair in checked_pairs: continue
                        checked_pairs.add(pair)

                        mid_r, mid_c = r + dr // 2, c + dc // 2
                        if self._get_stone(board, mid_r, mid_c) == opp:
                            # 突き抜け（貫通）の確認: 相手の石が縦または横に並んでいるか
                            is_pierced = False
                            if dr == 0: # 横トビを縦に抜かれる
                                if self._get_stone(board, mid_r-1, mid_c) == opp or self._get_stone(board, mid_r+1, mid_c) == opp:
                                    is_pierced = True
                            else: # 縦トビを横に抜かれる
                                if self._get_stone(board, mid_r, mid_c-1) == opp or self._get_stone(board, mid_r, mid_c+1) == opp:
                                    is_pierced = True
                            
                            if is_pierced:
                                linked = self._is_connected(board, (r, c), (nr, nc), color)
                                results.append({
                                    "my_coords": [self._to_coord(r, c), self._to_coord(nr, nc)],
                                    "opp_coord": self._to_coord(mid_r, mid_c),
                                    "is_sakare": not linked
                                })

                # 2. ケイマの分断
                for dr, dc in [(1, 2), (2, 1), (-1, 2), (-2, 1)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(board, nr, nc) == color:
                        pair = tuple(sorted([(r, c), (nr, nc)]))
                        if pair in checked_pairs: continue
                        checked_pairs.add(pair)

                        # ケイマの「腰」2点
                        waist1 = (r, c + (1 if dc > 0 else -1)) if abs(dc) == 2 else (r + (1 if dr > 0 else -1), c)
                        waist2 = (nr, nc - (1 if dc > 0 else -1)) if abs(dc) == 2 else (nr - (1 if dr > 0 else -1), nc)
                        
                        # 2点とも相手に占められている場合を貫通とみなす
                        if self._get_stone(board, *waist1) == opp and self._get_stone(board, *waist2) == opp:
                            linked = self._is_connected(board, (r, c), (nr, nc), color)
                            results.append({
                                "my_coords": [self._to_coord(r, c), self._to_coord(nr, nc)],
                                "opp_coord": f"{self._to_coord(*waist1)}と{self._to_coord(*waist2)}",
                                "is_sakare": not linked
                            })
        return results