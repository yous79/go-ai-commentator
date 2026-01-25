from typing import List
from core.point import Point
from core.game_board import GameBoard, Color
from core.inference_fact import InferenceFact, FactCategory, StabilityMetadata

class StabilityAnalyzer:
    """Ownershipデータを元に、盤上の石の『安定度（生存確率）』を分析する"""

    def __init__(self, board_size=19):
        self.board_size = board_size

    def analyze_to_facts(self, board: GameBoard, ownership_map) -> List[InferenceFact]:
        """解析結果を InferenceFact のリストとして返す"""
        results = self.analyze(board, ownership_map)
        facts = []
        
        for r in results:
            severity = 3
            status_msg = ""
            category = FactCategory.STABILITY
            
            # 石の数による重要度の調整
            is_large = r.count >= 3
            # color_label は StabilityMetadata に直接保持されている
            
            if r.status == 'dead':
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
                stones_str = ",".join(r.stones[:3]) + ("..." if len(r.stones) > 3 else "")
                group_type = "戦略的グループ (Move Group)" if r.is_strategic else "グループ"
                desc = f"{r.color_label}の{group_type} [{stones_str}] {status_msg}"
                
                facts.append(InferenceFact(category, desc, severity, r))
                
        return facts

    def analyze(self, board: GameBoard, ownership_map) -> List[StabilityMetadata]:
        if not ownership_map:
            return []

        groups = self._find_strategic_groups(board, ownership_map)
        analysis_results = []

        for color_obj, stones, avg_stability, is_strategic in groups:
            # ステータス判定
            if avg_stability < 0.0:    status = "dead"
            elif avg_stability < 0.2:  status = "critical"
            elif avg_stability < 0.5:  status = "weak"
            elif avg_stability < 0.8:  status = "stable"
            else:                      status = "strong"
            
            analysis_results.append(StabilityMetadata(
                color_label=color_obj.label,
                stones=[p.to_gtp() for p in stones],
                stability=avg_stability,
                status=status,
                count=len(stones),
                is_strategic=is_strategic
            ))
            
        return analysis_results

    def _find_strategic_groups(self, board: GameBoard, ownership_map):
        visited = set()
        physical_groups = self._find_physical_groups(board)
        
        group_data = []
        for color_obj, stones in physical_groups:
            total_own = 0
            for p in stones:
                idx = p.row * self.board_size + p.col
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
