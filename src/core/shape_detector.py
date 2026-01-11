class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size

    def detect_all(self, curr_board, prev_board=None, last_move_color=None):
        """全ての形状を検知し、カテゴリー別にテキストレポートを生成する"""
        bad_shapes = []
        normal_facts = []
        
        # 1. ポン抜きの検知 (好形 or 悪形)
        if prev_board and last_move_color:
            p_res = self._detect_ponnuki(curr_board, prev_board, last_move_color)
            if p_res:
                # 最後に打った色がポン抜きをした = 相手の色がポン抜きをされた
                # Geminiへの報告としては「プレイヤーの視点」で記述する
                if p_res['color'] == last_move_color:
                    normal_facts.append(f"  - 座標 {p_res['coord']} で鮮やかな「ポン抜き」をしました。非常に効率の良い厚みです。")
                else:
                    bad_shapes.append(f"  - 座標 {p_res['coord']} で相手に「ポン抜き」を許しました。極めて深刻な悪形（相手の好形）です。")

        # 2. アキ三角 (悪形)
        aki_list = self._detect_aki_sankaku(curr_board)
        if aki_list:
            for res in aki_list:
                bad_shapes.append(f"  - 座標 {res['coords']} に「アキ三角」を検知。効率の悪い重い形です。")

        # 3. サカレ形 (悪形 or 連絡事実)
        sakare_list = self._detect_sakare_gata(curr_board)
        if sakare_list:
            for res in sakare_list:
                if res['is_sakare']:
                    bad_shapes.append(f"  - 相手に突き抜けられ、{res['my_coords']} が「サカレ形」に分断されています。")
                else:
                    normal_facts.append(f"  - 座標 {res['opp_coord']} に「割り込み」がありますが、{res['my_coords']} は連絡を保っています。")

        # 4. 二目の頭をハネられた形 (悪形)
        atama_list = self._detect_nimoku_no_atama(curr_board)
        if atama_list:
            for res in atama_list:
                bad_shapes.append(f"  - 石 {res['my_coords']} が 座標 {res['opp_coord']} で「二目の頭」をハネられた窮屈な形になっています。")

        # レポートの構築
        report = []
        if bad_shapes:
            report.append("【盤面形状解析：警告（悪形・失着）】")
            report.extend(bad_shapes)
        if normal_facts:
            if bad_shapes: report.append("") # 隙間
            report.append("【盤面形状解析：事実（一般手筋・状態）】")
            report.extend(normal_facts)
            
        return "\n".join(report) if report else ""

    # --- Helper Methods ---
    def _get_stone(self, board, r, c):
        if 0 <= r < self.board_size and 0 <= c < self.board_size:
            return board.get(r, c)
        return "edge"

    def _to_coord(self, r, c):
        cols = "ABCDEFGHJKLMNOPQRST"
        return f"{cols[c]}{r+1}"

    def _is_connected(self, board, p1, p2, color):
        r1, c1 = p1; r2, c2 = p2
        dist = abs(r1-r2) + abs(c1-c2)
        if dist == 1: return True
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr==0 and dc==0: continue
                mr, mc = r1+dr, c1+dc
                if self._get_stone(board, mr, mc) == color:
                    if abs(mr-r2)<=1 and abs(mc-c2)<=1: return True
        return False

    # --- Detection Logic ---
    def _detect_ponnuki(self, curr, prev, color):
        # 注意: ここでの color は最後に着手した石の色
        # 自分の色が抜いたのか、相手の色が抜いたのかの両方をチェック可能にする
        for check_color in ['b', 'w']:
            opp = 'w' if check_color == 'b' else 'b'
            for r in range(self.board_size):
                for c in range(self.board_size):
                    if prev.get(r,c) == opp and curr.get(r,c) is None:
                        surround = 0
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            if self._get_stone(curr, r+dr, c+dc) == check_color:
                                surround += 1
                        if surround == 4:
                            return {"coord": self._to_coord(r,c), "color": check_color}
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
                for dr, dc in [(0,2), (2,0)]:
                    nr, nc = r+dr, c+dc
                    if self._get_stone(board, nr, nc) == color:
                        pair = tuple(sorted([(r,c), (nr,nc)]))
                        if pair in checked: continue
                        checked.add(pair)
                        mr, mc = r+dr//2, c+dc//2
                        if self._get_stone(board, mr, mc) == opp:
                            pierced = False
                            if dr == 0:
                                if self._get_stone(board, mr-1, mc)==opp or self._get_stone(board, mr+1, mc)==opp:
                                    pierced = True
                            else:
                                if self._get_stone(board, mr, mc-1)==opp or self._get_stone(board, mr, mc+1)==opp:
                                    pierced = True
                            if pierced:
                                linked = self._is_connected(board, (r,c), (nr,nc), color)
                                results.append({"my_coords": [self._to_coord(r,c), self._to_coord(nr,nc)], "opp_coord": self._to_coord(mr,mc), "is_sakare": not linked})
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

    def _detect_nimoku_no_atama(self, board):
        results = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(board, r, c)
                if color not in ['b', 'w']: continue
                opp = 'w' if color == 'b' else 'b'
                for dr, dc in [(0, 1), (1, 0)]:
                    nr, nc = r + dr, c + dc
                    if self._get_stone(board, nr, nc) == color:
                        head_r, head_c = nr + dr, nc + dc
                        if self._get_stone(board, head_r, head_c) == opp:
                            if self._get_stone(board, nr, nc+1) == opp or self._get_stone(board, nr, nc-1) == opp or \
                               self._get_stone(board, nr+1, nc) == opp or self._get_stone(board, nr-1, nc) == opp:
                                results.append({
                                    "my_coords": [self._to_coord(r, c), self._to_coord(nr, nc)],
                                    "opp_coord": self._to_coord(head_r, head_c)
                                })
        return results