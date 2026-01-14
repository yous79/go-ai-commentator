from core.shapes.base_shape import BaseShape
from core.point import Point

class NimokuAtamaDetector(BaseShape):
    key = "nimoku_no_atama"

    def detect(self, context):
        raw_hits = [] 
        sz = context.board_size
        for r in range(sz):
            for c in range(sz):
                p = Point(r, c)
                color = self._get_stone(context.curr_board, p)
                if color not in ['b', 'w']: continue
                opp = self._get_opponent(color)
                
                for dr, dc in [(0, 1), (1, 0)]:
                    np = p + (dr, dc)
                    if self._get_stone(context.curr_board, np) == color:
                        # 二目を発見 (p, np)
                        for ap in [p - (dr, dc), np + (dr, dc)]:
                            if self._get_stone(context.curr_board, ap) == opp:
                                # 頭を叩かれた。反対側の端(opp_p)が空点か
                                opp_p = np + (dr, dc) if ap == p - (dr, dc) else p - (dr, dc)
                                if self._get_stone(context.curr_board, opp_p) in ['.', 'edge']:
                                    raw_hits.append(([p, np], ap))
        
        messages = []
        for victims, attacker in raw_hits:
            v_coords = sorted([v.to_gtp() for v in victims])
            messages.append(f"  - 座標 {v_coords} の二石に対し、{attacker.to_gtp()} で「二目の頭」を叩かれました。非常に痛い形です。")
        return "bad", list(set(messages))
