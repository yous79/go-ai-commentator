from core.shapes.base_shape import BaseShape

class IkkenTobiDetector(BaseShape):
    key = "ikken_tobi"

    def detect(self, curr_board, prev_board=None, last_move_color=None):
        messages = []
        checked_pairs = set()

        for r in range(self.board_size):
            for c in range(self.board_size):
                color = self._get_stone(curr_board, r, c)
                if color not in ['b', 'w']: continue

                # 全ての直線方向（距離2）をチェック
                for dr, dc in [(0, 2), (0, -2), (2, 0), (-2, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                        if self._get_stone(curr_board, nr, nc) == color:
                            # 中間が空点であることを確認
                            mid_r, mid_c = r + dr // 2, c + dc // 2
                            if self._get_stone(curr_board, mid_r, mid_c) == '.':
                                pair = tuple(sorted([(r, c), (nr, nc)]))
                                if pair not in checked_pairs:
                                    checked_pairs.add(pair)
                                    coords = sorted([self._to_coord(r, c), self._to_coord(nr, nc)])
                                    messages.append(f"  - 座標 {coords} に「一間トビ」を検知。効率的な進出です。")

        return "normal", list(set(messages))