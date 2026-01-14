from core.shapes.base_shape import BaseShape

class PonnukiDetector(BaseShape):
    key = "ponnuki"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        bad_messages = []
        if not prev_board:
            return "normal", []

        # 盤面全体を走査して「石が抜かれた地点」を探す
        for r in range(self.board_size):
            for c in range(self.board_size):
                p_stone = self._get_stone(prev_board, r, c)
                c_stone = self._get_stone(curr_board, r, c)
                
                # 1手前に自分（または敵）の石があり、現在は空点になっているか
                if p_stone in ['b', 'w'] and c_stone == '.':
                    # 抜いた側の色（＝相手の色）
                    capturer_color = 'w' if p_stone == 'b' else 'b'
                    
                    # ポン抜きのダイヤモンド形チェック
                    surround = 0
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        if self._get_stone(curr_board, r + dr, c + dc) == capturer_color:
                            surround += 1
                    
                    if surround == 4:
                        # 3. 【純粋性のチェック】斜め4隅に味方の石がいないか確認
                        has_diagonal_stone = False
                        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                            if self._get_stone(curr_board, r + dr, c + dc) == capturer_color:
                                has_diagonal_stone = True
                                break
                        
                        if has_diagonal_stone:
                            continue # 斜めに石がある場合は「効率の悪い重い形」なのでポン抜きとは呼ばない

                        coord = self._to_coord(r, c)
                        # 被害者の視点で警告を出す
                        victim_color = "黒" if p_stone == 'b' else "白"
                        bad_messages.append(
                            f"  - 座標 {coord} で相手に「ポン抜き」を許しました。{victim_color}にとって極めて深刻な悪形であり、相手に絶対的な厚みを与えてしまいました。"
                        )
                            
        # 全て "bad" として報告
        return "bad" if bad_messages else None, bad_messages
