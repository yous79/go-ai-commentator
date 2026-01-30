import copy
from core.shapes.base_shape import BaseShape
from core.point import Point
from core.game_board import Color
from core.inference_fact import ShapeMetadata

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
        root_purity = self.pattern_def.get("purity", False)
        root_self_purity = self.pattern_def.get("self_purity", False)

        for bp in base_patterns:
            bp["remedy_offset"] = base_remedy
            if "purity" not in bp: bp["purity"] = root_purity
            if "self_purity" not in bp: bp["self_purity"] = root_self_purity
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

    def detect(self, context, center_point=None):
        """context.curr_board に対してパターン照合を行う。center_point が指定された場合はその座標を起点とする。"""
        target_pt = center_point or context.last_move
        if not target_pt:
            return self.category, []

        # アキ三角の検知除外条件: コウを解消（埋める）した手である場合
        if self.key == "aki_sankaku":
            if context.prev_board and context.prev_board.ko_point == target_pt:
                return self.category, []

        results = []
        matched_points = set()

        for variant in self.patterns:
            # パターン内の基準となるエレメントを探す
            # 1. 'last' (最新手) 
            # 2. 'self' (自分の石) -> scan_all モード用
            target_states = ["last", "self"]
            
            for state in target_states:
                for i, target_el in enumerate(variant["elements"]):
                    if target_el.get("state") != state: 
                        continue
                    
                    # 基準点が target_pt と一致するように原点を逆算
                    origin = target_pt - tuple(target_el["offset"])
                    
                    if self._match_at(context, variant, origin, target_pt):
                        coord = target_pt.to_gtp()
                        if coord not in matched_points:
                            msg = self.message_template.format(coord)
                            
                            meta = ShapeMetadata(key=self.key)
                            remedy_off = variant.get("remedy_offset")
                            if remedy_off:
                                abs_remedy = origin + tuple(remedy_off)
                                if abs_remedy.is_valid(context.board_size):
                                    meta.remedy_gtp = abs_remedy.to_gtp()
                            
                            results.append({"message": msg, "metadata": meta})
                            matched_points.add(coord)
                        break # この variant で1つ見つかれば OK
                if matched_points: break # 'last' で見つかれば 'self' は不要

        return self.category, results

    def _match_at(self, context, pattern, origin, target_pt=None):
        """特定の原点位置でパターンが一致するか判定する"""
        # 起点の石の色を基準にする
        ref_pt = target_pt or context.last_move
        ref_color = context.curr_board.get(ref_pt) if ref_pt else context.last_color
        
        last_color_char = ref_color.value if ref_color else '.'
        opp_color_char = 'w' if last_color_char == 'b' else 'b'
        opp_color_obj = ref_color.opposite() if ref_color else None
        
        matched_pts = {} # pattern_local_index -> abs_point
        
        # 1. 基本的な要素の一致確認
        for el_idx, el in enumerate(pattern["elements"]):
            abs_pos = origin + tuple(el["offset"])
            state_needed = el["state"]
            
            # 盤外チェック
            if not abs_pos.is_valid(context.board_size):
                if state_needed == "edge": 
                    continue
                else: 
                    return False
            
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
                    # 取りの結果としての空点はアキとはみなさない(badのみ)
                    if self.category == "bad" and context.prev_board:
                        prev_stone = context.prev_board.get(abs_pos)
                        if prev_stone and prev_stone.value == opp_color_char:
                            match = False
                else:
                    match = False
            elif state_needed == "captured":
                # prev_boardで相手の石があり、curr_boardで空点であること
                if context.prev_board and actual_char == '.':
                    prev_stone = context.prev_board.get(abs_pos)
                    match = (prev_stone and prev_stone.value == opp_color_char)
                else:
                    match = False
            elif state_needed == "any":
                match = True
            
            if not match:
                return False
            
            # --- 動的プロパティ（呼吸点・石数）のチェック ---
            if actual and (actual_char in [last_color_char, opp_color_char]):
                # liberties, min_liberties, max_liberties, min_stones, max_stones
                group, liberties = context.curr_board.get_group_and_liberties(abs_pos)
                
                if "liberties" in el and len(liberties) != el["liberties"]: return False
                if "min_liberties" in el and len(liberties) < el["min_liberties"]: return False
                if "max_liberties" in el and len(liberties) > el["max_liberties"]: return False
                
                if "min_stones" in el and len(group) < el["min_stones"]: return False
                if "max_stones" in el and len(group) > el["max_stones"]: return False

            # 孤立チェック（互換性のために残すが、min_stones: 1, max_stones: 1 でも代用可能）
            if el.get("check_isolation") and state_needed == "opponent":
                if actual:
                    group, _ = context.curr_board.get_group_and_liberties(abs_pos)
                    if len(group) != 1:
                        return False

            matched_pts[el_idx] = abs_pos

        # 2. 周囲8マスの清浄性チェック (purity)
        if pattern.get("purity"):
            all_pattern_pts = set(matched_pts.values())
            for neighbor in context.last_move.all_neighbors(context.board_size):
                if neighbor in all_pattern_pts:
                    continue
                if not context.curr_board.is_empty(neighbor):
                    return False

        # 2.5 自分の石の清浄性チェック (self_purity)
        if pattern.get("self_purity"):
            all_pattern_pts = set(matched_pts.values())
            for neighbor in context.last_move.all_neighbors(context.board_size):
                if neighbor in all_pattern_pts:
                    continue
                if context.curr_board.get(neighbor) == context.last_color:
                    return False

        # 3. 隣接条件制約 (constraints)
        for const in pattern.get("constraints", []):
            # target となる要素を特定
            targets = []
            target_label = const.get("target")
            for idx, el in enumerate(pattern["elements"]):
                if el.get("label") == target_label or (not target_label and el["state"] == "last"):
                    if idx in matched_pts:
                        targets.append(matched_pts[idx])
            
            for t_pt in targets:
                # 相手の石の隣接数をカウント
                opp_count = 0
                for n in t_pt.neighbors(context.board_size):
                    if context.curr_board.get(n) == opp_color_obj:
                        opp_count += 1
                
                if "max" in const and opp_count > const["max"]: return False
                if "min" in const and opp_count < const["min"]: return False

            # 3.2 異なるグループであることの制約 (different_group)
            if const.get("type") == "different_group":
                target_labels = const.get("targets", [])
                groups_seen = []
                for label in target_labels:
                    found_group = False
                    for idx, el in enumerate(pattern["elements"]):
                        if el.get("label") == label and idx in matched_pts:
                            pt = matched_pts[idx]
                            group, _ = context.curr_board.get_group_and_liberties(pt)
                            if group in groups_seen:
                                return False
                            groups_seen.append(group)
                            found_group = True
                            break
                    if not found_group: return False

        return True