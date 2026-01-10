class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect_all(self, curr_board, prev_board=None, last_move_color=None):
        """全ての形状を検知し、Gemini用のテキストレポートを生成する"""
        facts = []
        
        # 1. ポン抜き (手順依存)
        if prev_board and last_move_color:
            p_res = self._detect_ponnuki(curr_board, prev_board, last_move_color)
            if p_res:
                facts.append("■ 発生した重要事実（ポン抜き）:")
                facts.append(f"  - 座標 {p_res['coord']} で相手の石を「ポン抜き」しました。非常に効率の良い厚みです。")

        # 2. アキ三角 (静的形状)
        aki_list = self._detect_aki_sankaku(curr_board)
        if aki_list:
            facts.append("■ 確定した悪形（アキ三角）:")
            for res in aki_list:
                facts.append(f"  - 座標 {res['coords']} に「アキ三角」を検知。効率の悪い重い形です。")

        # 3. サカレ形 (静的形状 + 連絡解析)
        sakare_list = self._detect_sakare_gata(curr_board)
        if sakare_list:
            facts.append("■ 形状の分析（分断と連絡）:")
            for res in sakare_list:
                if res['is_sakare']:
                    facts.append(f"  - 相手に突き抜けられ、{res['my_coords']} が「サカレ形」に分断されています。")
                else:
                    facts.append(f"  - 座標 {res['opp_coord']} に「割り込み」がありますが、{res['my_coords']} はコスミ等の形で連絡を保っておりサカレ形ではありません。")

        return "\n".join(facts) if facts else ""

    # --- Helper Methods ---
    def _get_stone(self, board, r, c):
        if 0 <= r < self.board_size and 0 <= c < self.board_size:
            return board.get(r, c)
        return "edge"

    def _to_coord(self, r, c):
        cols = "ABCDEFGHJKLMNOPQRST"
        return f"{cols[c]}{r+1}"

    def _is_connected(self, board, p1, p2, color):
        """2点間の連絡判定 (直接 or コスミ)"""
        r1, c1 = p1; r2, c2 = p2
        dist = abs(r1-r2) + abs(c1-c2)
        if dist == 1: return True # Adjacent
        if abs(r1-r2)==1 and abs(c1-c2)==1: return True # Kosumi direct? No, Kosumi is diagonal relation but usually connected by shape.
        # Check connection via third stone (Kosumi connection)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr==0 and dc==0: continue
                mr, mc = r1+dr, c1+dc
                if self._get_stone(board, mr, mc) == color:
                    # Check if mid stone connects to p2
                    if abs(mr-r2)<=1 and abs(mc-c2)<=1: return True
        return False

    # --- Detection Logic ---
    def _detect_ponnuki(self, curr, prev, color):
        opp = 'w' if color == 'b' else 'b'
        for r in range(self.board_size):
            for c in range(self.board_size):
                # Before: Opponent stone exists. After: Empty.
                if prev.get(r,c) == opp and curr.get(r,c) is None:
                    # Check surroundings
                    surround = 0
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        if self._get_stone(curr, r+dr, c+dc) == color:
                            surround += 1
                    if surround == 4:
                        return {"coord": self._to_coord(r,c), "color": color}
        return None

    def _detect_aki_sankaku(self, board):
        results = []
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                cells = [(r,c), (r+1,c), (r,c+1), (r+1,c+1)]
                for color in ['b', 'w']:
                    stones = [p for p in cells if self._get_stone(board, *p) == color]
                    empties = [p for p in cells if self._get_stone(board, *p) is None]
                    if len(stones) == 3 and len(empties) == 1:
                        empty = empties[0]
                        diag = (r if empty[0]==r+1 else r+1, c if empty[1]==c+1 else c+1)
                        if self._get_stone(board, *diag) == color:
                            coords = [self._to_coord(*p) for p in stones]
                            results.append({"color": color, "coords": sorted(coords)})
        return results

    def _detect_sakare_gata(self, board):
        results = []
        checked = set()
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'
                
                # One-space jump split
                for dr, dc in [(0,2), (2,0)]:
                    nr, nc = r+dr, c+dc
                    if self._get_stone(board, nr, nc) == color:
                        pair = tuple(sorted([(r,c), (nr,nc)]))
                        if pair in checked: continue
                        checked.add(pair)
                        
                        mr, mc = r+dr//2, c+dc//2
                        if self._get_stone(board, mr, mc) == opp:
                            # Check piercing
                            pierced = False
                            if dr == 0: # Horizontal jump, check vertical piercing
                                if self._get_stone(board, mr-1, mc)==opp or self._get_stone(board, mr+1, mc)==opp:
                                    pierced = True
                            else: # Vertical jump, check horizontal piercing
                                if self._get_stone(board, mr, mc-1)==opp or self._get_stone(board, mr, mc+1)==opp:
                                    pierced = True
                            
                            if pierced:
                                linked = self._is_connected(board, (r,c), (nr,nc), color)
                                results.append({
                                    "my_coords": [self._to_coord(r,c), self._to_coord(nr,nc)],
                                    "opp_coord": self._to_coord(mr,mc),
                                    "is_sakare": not linked
                                })

                # Knight's move split
                for dr, dc in [(1,2), (2,1), (-1,2), (-2,1)]:
                    nr, nc = r+dr, c+dc
                    if self._get_stone(board, nr, nc) == color:
                        pair = tuple(sorted([(r,c), (nr,nc)]))
                        if pair in checked: continue
                        checked.add(pair)
                        
                        w1 = (r, c+(1 if dc>0 else -1)) if abs(dc)==2 else (r+(1 if dr>0 else -1), c)
                        w2 = (nr, nc-(1 if dc>0 else -1)) if abs(dc)==2 else (nr-(1 if dr>0 else -1), nc)
                        
                        if self._get_stone(board, *w1)==opp and self._get_stone(board, *w2)==opp:
                            linked = self._is_connected(board, (r,c), (nr,nc), color)
                            results.append({
                                "my_coords": [self._to_coord(r,c), self._to_coord(nr,nc)],
                                "opp_coord": f"{self._to_coord(*w1)}と{self._to_coord(*w2)}",
                                "is_sakare": not linked
                            })
        return results