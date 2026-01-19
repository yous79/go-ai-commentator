from core.shapes.base_shape import BaseShape
from core.point import Point
from core.game_board import Color
import copy

class GenericPatternDetector(BaseShape):
    """
    宣言的なパターン定義（JSON形式）に基づき形状を検知する汎用エンジン。
    回転(90, 180, 270度)および反転を自動的に網羅する。
    """
    def __init__(self, pattern_def, board_size=19):
        super().__init__(board_size)
        self.pattern_def = pattern_def
        self.key = pattern_def.get("key", "unknown")
        self.name = pattern_def.get("name", "Unknown Shape")
        self.category = pattern_def.get("category", "normal")
        self.message_template = pattern_def.get("message", "{}を検知しました。")
        self.patterns = self._prepare_patterns(pattern_def.get("patterns", []))

    def _prepare_patterns(self, base_patterns):
        """回転・反転を適用した全バリエーションのパターンを生成する"""
        all_variants = []
        auto_rotate = self.pattern_def.get("auto_rotate", True)
        auto_reflect = self.pattern_def.get("auto_reflect", True)
        base_remedy = self.pattern_def.get("remedy_offset")

        for bp in base_patterns:
            bp["remedy_offset"] = base_remedy
            variants = [bp]
            
            if auto_reflect:
                # 左右反転を追加
                reflected = copy.deepcopy(bp)
                for el in reflected["elements"]:
                    el["offset"] = [el["offset"][0], -el["offset"][1]]
                if base_remedy:
                    reflected["remedy_offset"] = [base_remedy[0], -base_remedy[1]]
                variants.append(reflected)

            if auto_rotate:
                rotated_variants = []
                for v in variants:
                    # 90, 180, 270度回転
                    v_remedy = v.get("remedy_offset")
                    for angle in [90, 180, 270]:
                        rv = copy.deepcopy(v)
                        for el in rv["elements"]:
                            r, c = el["offset"]
                            if angle == 90:    el["offset"] = [c, -r]
                            elif angle == 180: el["offset"] = [-r, -c]
                            elif angle == 270: el["offset"] = [-c, r]
                        
                        if v_remedy:
                            r, c = v_remedy
                            if angle == 90:    rv["remedy_offset"] = [c, -r]
                            elif angle == 180: rv["remedy_offset"] = [-r, -c]
                            elif angle == 270: rv["remedy_offset"] = [-c, r]
                        
                        rotated_variants.append(rv)
                variants.extend(rotated_variants)
            
            # 重複を除去（座標セットが同じものを排除）
            unique_variants = []
            seen_sigs = set()
            for v in variants:
                # 正規化してシグネチャ作成
                sig = tuple(sorted([(tuple(el["offset"]), el["state"]) for el in v["elements"]]))
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    unique_variants.append(v)
            all_variants.extend(unique_variants)
            
        return all_variants

    def detect(self, context):
        """context.curr_board に対してパターン照合を行う"""
        if not context.last_move:
            return self.category, []

        results = []
        matched_points = set()

        for variant in self.patterns:
            for i, target_el in enumerate(variant["elements"]):
                if target_el.get("state") != "last": 
                    continue
                
                origin = context.last_move - tuple(target_el["offset"])
                
                if self._match_at(context, variant, origin):
                    coord = context.last_move.to_gtp()
                    if coord not in matched_points:
                        msg = self.message_template.format(coord)
                        
                        # 構造化データとして結果を構築
                        res_data = {"message": msg}
                        remedy_off = variant.get("remedy_offset")
                        if remedy_off:
                            abs_remedy = origin + tuple(remedy_off)
                            if abs_remedy.is_valid(context.board_size):
                                res_data["remedy_gtp"] = abs_remedy.to_gtp()
                        
                        results.append(res_data)
                        matched_points.add(coord)
                    break 

        return self.category, results

    def _match_at(self, context, pattern, origin):
        """特定の原点位置でパターンが一致するか判定する"""
        last_color_char = context.last_color.value if context.last_color else '.'
        opp_color_char = 'w' if last_color_char == 'b' else 'b'
        
        for el in pattern["elements"]:
            abs_pos = origin + tuple(el["offset"])
            state_needed = el["state"]
            
            # 盤外チェック
            if not abs_pos.is_valid(context.board_size):
                if state_needed == "edge": continue
                else: return False
            
            # 石の取得
            actual = context.curr_board.get(abs_pos)
            actual_char = actual.value if actual else '.'
            
            match = False
            if state_needed == "self" or state_needed == "last":
                match = (actual_char == last_color_char)
            elif state_needed == "opponent":
                match = (actual_char == opp_color_char)
            elif state_needed == "empty":
                if actual_char == '.':
                    match = True
                    # 【重要】取り（Capture）の判定
                    if context.prev_board:
                        prev_stone = context.prev_board.get(abs_pos)
                        if prev_stone and prev_stone.value == opp_color_char:
                            if self.category == "bad":
                                match = False # 取りの結果としての空点はアキとはみなさない
                else:
                    match = False
            elif state_needed == "any":
                match = (actual_char != 'edge')
            
            if not match:
                return False
            
        return True