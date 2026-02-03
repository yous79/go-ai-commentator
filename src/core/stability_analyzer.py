from typing import List, Optional
from core.point import Point
from core.game_board import GameBoard, Color
from core.inference_fact import InferenceFact, FactCategory, StabilityMetadata

class StabilityAnalyzer:
    """Ownershipデータを元に、盤上の石の『安定度（生存確率）』を分析する"""

    def __init__(self, board_size=19):
        self.board_size = board_size

    def analyze_to_facts(self, board: GameBoard, ownership_map, uncertainty_map=None) -> List[InferenceFact]:
        """解析結果を InferenceFact のリストとして返す"""
        results = self.analyze(board, ownership_map, uncertainty_map)
        facts = []
        
        for r in results:
            severity = 3
            status_msg = ""
            category = FactCategory.STABILITY
            
            # 石の数による重要度の調整
            is_large = r.count >= 3
            
            # --- AJI (味) Logic ---
            if r.uncertainty > 0.2: # Threshold for "Bad Aji"
                category = FactCategory.STABILITY # AJI category could be added later
                severity = 4
                status_msg = f"は生存が確定しておらず、味が悪い（不安定な）状態です。コウや手が生じる余地があります (不確実性: {r.uncertainty:.2f})。"
            # --- End AJI Logic ---
            
            elif r.status == 'dead':
                severity = 5 if is_large else 4
                status_msg = "は、AIの認識上すでに戦略的役割を終えた『カス石』です。これ以上手をかけず、捨て石として活用するか、放置して大場に先行すべき局面です。"
            elif r.status == 'critical':
                severity = 5
                status_msg = "は生存確率が極めて低く、死に体に近い状態です。強引に助け出すよりも、周囲への響きを考慮して軽く扱う判断が求められます。"
            elif r.status == 'weak':
                severity = 4
                status_msg = "は根拠が不十分な『弱い石』であり、盤上の急場（きゅうば）です。この石の補強、あるいは逆襲が局面の焦点となります。"
            elif r.status == 'strong':
                severity = 1
                status_msg = "は完全に安定しており、当面の手入れは不要です。"
            
            if status_msg:
                # 代表的な座標（中心付近や最小インデックス）を表示
                # stones は文字列リストだが、ソート済みか不明。
                # 基本的に左上が先頭に来る順序で追加されているはず。
                first_stone = r.stones[0] if r.stones else "?"
                num_stones = len(r.stones)
                
                group_label = f"{first_stone}付近の{num_stones}子" if num_stones > 1 else f"{first_stone}"
                
                # group_type = "戦略的グループ (Move Group)" if r.is_strategic else "グループ"
                # "Move Group" は少し内部的すぎるので、表現を柔らかくする
                
                desc = f"{r.color_label}の{group_label}は、{status_msg}"
                # desc = f"{r.color_label}の{group_type} [{stones_str}] {status_msg}"
                
                facts.append(InferenceFact(category, desc, severity, r))
                
        return facts

    def analyze(self, board: GameBoard, ownership_map, uncertainty_map=None) -> List[StabilityMetadata]:
        """グループごとの安定度と不確実性を分析する"""
        if not ownership_map:
            return []

        from core.analysis_config import AnalysisConfig

        groups = self._find_strategic_groups(board, ownership_map)
        analysis_results = []

        dead_thresh = AnalysisConfig.get("KASUISHI_THRESHOLD") # e.g. -0.85
        crit_thresh = AnalysisConfig.get("CRITICAL_THRESHOLD") # e.g. 0.2
        weak_thresh = AnalysisConfig.get("WEAK_THRESHOLD")     # e.g. 0.5
        atsumi_thresh = AnalysisConfig.get("ATSUMI_THRESHOLD") # e.g. 0.9

        for color_obj, stones, avg_stability, is_strategic in groups:
            # ステータス判定 (AnalysisConfigの閾値を使用)
            if avg_stability <= dead_thresh:     status = "dead"
            elif avg_stability < crit_thresh:    status = "critical"
            elif avg_stability < weak_thresh:    status = "weak"
            elif avg_stability < atsumi_thresh:  status = "stable"
            else:                                status = "strong"
            
            # 不確実性の計算（uncertainty_mapがあれば使用、なければ0）
            avg_uncertainty = 0.0
            if uncertainty_map:
                total_unc = 0.0
                for p in stones:
                    kata_row = (self.board_size - 1) - p.row
                    idx = kata_row * self.board_size + p.col
                    if idx < len(uncertainty_map):
                        total_unc += uncertainty_map[idx]
                avg_uncertainty = total_unc / len(stones) if stones else 0.0
            
            analysis_results.append(StabilityMetadata(
                color_label=color_obj.label,
                stones=[p.to_gtp() for p in stones],
                stability=avg_stability,
                status=status,
                count=len(stones),
                is_strategic=is_strategic,
                uncertainty=avg_uncertainty
            ))
            
        return analysis_results

    def _find_strategic_groups(self, board: GameBoard, ownership_map):
        visited = set()
        physical_groups = self._find_physical_groups(board)
        
        group_data = []
        for color_obj, stones in physical_groups:
            total_own = 0
            for p in stones:
                kata_row = (self.board_size - 1) - p.row
                idx = kata_row * self.board_size + p.col
                total_own += ownership_map[idx]
            avg_own = total_own / len(stones)
            group_data.append({
                "color_obj": color_obj,
                "stones": stones,
                "avg_own": avg_own
            })

        merged_groups = []
        used_indices = set()

        for i in range(len(group_data)):
            if i in used_indices: continue
            
            current_group = group_data[i]
            current_stones = list(current_group["stones"])
            current_color = current_group["color_obj"]
            current_own = current_group["avg_own"]
            is_strategic = False

            for j in range(i + 1, len(group_data)):
                if j in used_indices: continue
                target_group = group_data[j]
                
                if target_group["color_obj"] == current_color:
                    if abs(target_group["avg_own"] - current_own) < 0.001:
                        current_stones.extend(target_group["stones"])
                        used_indices.add(j)
                        is_strategic = True
            
            # 自分の色に合わせた生存確率を算出
            stability = current_own if current_color == Color.BLACK else -current_own
            merged_groups.append((current_color, current_stones, stability, is_strategic))
            used_indices.add(i)

        return merged_groups

    def _find_physical_groups(self, board: GameBoard):
        visited = set()
        groups = [] 

        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(r, c)
                color = board.get(p)
                if color and p not in visited:
                    group_stones = []
                    self._bfs_group(board, p, color, visited, group_stones)
                    groups.append((color, group_stones))
        return groups

    def _bfs_group(self, board: GameBoard, start_p: Point, color: Color, visited: set, group_stones: list):
        queue = [start_p]
        visited.add(start_p)
        while queue:
            curr = queue.pop(0)
            group_stones.append(curr)
            for neighbor in curr.neighbors(self.board_size):
                if neighbor not in visited:
                    n_color = board.get(neighbor)
                    if n_color == color:
                        visited.add(neighbor)
                        queue.append(neighbor)

    def calculate_group_influence(self, stones: List[Point], influence_map: List[float]) -> float:
        """
        グループ周辺の影響力平均値を算出する。
        影響力マップは黒プラス、白マイナスの前提。
        """
        if not influence_map:
            return 0.0

        targets = set()
        visited_stones = set(stones)
        
        # 距離1の近傍
        for s in stones:
            for n in s.neighbors(self.board_size):
                if n not in visited_stones:
                    targets.add(n)
        
        # 距離2の近傍
        second_targets = set()
        for t in targets:
            for n in t.neighbors(self.board_size):
                if n not in visited_stones and n not in targets:
                    second_targets.add(n)
                    
        all_targets = targets.union(second_targets)
        if not all_targets:
            return 0.0
            
        total = 0.0
        for p in all_targets:
            kata_row = (self.board_size - 1) - p.row
            idx = kata_row * self.board_size + p.col
            if 0 <= idx < len(influence_map):
                total += influence_map[idx]
                
        return total / len(all_targets)
