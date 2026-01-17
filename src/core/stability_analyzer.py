from core.point import Point
from core.inference_fact import InferenceFact, FactCategory

class StabilityAnalyzer:
    """Ownershipデータを元に、盤上の石の『安定度（生存確率）』を分析する"""

    def __init__(self, board_size=19):
        self.board_size = board_size

    def analyze_to_facts(self, board, ownership_map) -> list[InferenceFact]:
        """解析結果を InferenceFact のリストとして返す"""
        results = self.analyze(board, ownership_map)
        facts = []
        
        for r in results:
            severity = 3
            status_msg = ""
            category = FactCategory.STABILITY
            
            # 石の数による重要度の調整
            is_large = r['count'] >= 3
            
            if r['status'] == 'dead':
                severity = 5 if is_large else 4
                status_msg = "は、AIの認識上すでに戦略的役割を終えた『カス石』です。これ以上手をかけず、捨て石として活用するか、放置して大場に先行すべき局面です。"
            elif r['status'] == 'critical':
                severity = 5
                status_msg = "は生存確率が極めて低く、死に体に近い状態です。強引に助け出すよりも、周囲への響きを考慮して軽く扱う判断が求められます。"
            elif r['status'] == 'weak':
                severity = 4
                status_msg = "は根拠が不十分な『弱い石』であり、盤上の急場（きゅうば）です。この石の補強、あるいは逆襲が局面の焦点となります。"
            elif r['status'] == 'strong':
                severity = 1
                status_msg = "は完全に安定しており、当面の手入れは不要です。"
            
            if status_msg:
                # 座標リストを簡略化（最初の3つ）
                stones_str = ",".join(r['stones'][:3]) + ("..." if len(r['stones']) > 3 else "")
                
                # Move Group（戦略的グループ）であることの明示
                group_type = "戦略的グループ (Move Group)" if r['is_strategic'] else "グループ"
                desc = f"{r['color']}の{group_type} [{stones_str}] {status_msg}"
                
                facts.append(InferenceFact(category, desc, severity, r))
                
        return facts

    def analyze(self, board, ownership_map):
        """
        board: GameBoardオブジェクト
        ownership_map: 361(or size*size)個の数値リスト (-1.0 to 1.0)
        """
        if not ownership_map:
            return []

        # AIの認識（Ownership）に基づいてグループ化を行う
        groups = self._find_strategic_groups(board, ownership_map)
        analysis_results = []

        for color_long, stones, avg_stability, is_strategic in groups:
            color_code = 'b' if color_long.startswith('b') else 'w'
            
            # ステータス判定
            if avg_stability < 0.0:    status = "dead"     # 相手の確定地の中にある（完全に死んでいる）
            elif avg_stability < 0.2:  status = "critical" # 死に体
            elif avg_stability < 0.5:  status = "weak"     # 弱い
            elif avg_stability < 0.8:  status = "stable"   # 安定
            else:                      status = "strong"   # 確定
            
            analysis_results.append({
                "color": "黒" if color_code == 'b' else "白",
                "stones": [p.to_gtp() for p in stones],
                "stability": avg_stability,
                "status": status,
                "count": len(stones),
                "is_strategic": is_strategic
            })
            
        return analysis_results

    def _find_strategic_groups(self, board, ownership_map):
        """
        Ownershipの値を『グループID』として直接利用し、
        物理的な距離に関わらず『運命を共にする石』をグループ化する。
        """
        # 1. まず物理的な連結グループを取得
        physical_groups = self._find_physical_groups(board)
        
        # 2. 各物理グループの平均Ownershipを計算
        group_data = []
        for color, stones in physical_groups:
            total_own = 0
            for p in stones:
                idx = p.row * self.board_size + p.col
                total_own += ownership_map[idx]
            avg_own = total_own / len(stones)
            group_data.append({
                "color": color,
                "stones": stones,
                "avg_own": avg_own
            })

        # 3. Ownershipが極めて近い物理グループ同士を結合する (Strategic Merge)
        merged_groups = []
        used_indices = set()

        for i in range(len(group_data)):
            if i in used_indices: continue
            
            current_group = group_data[i]
            current_stones = list(current_group["stones"])
            current_color = current_group["color"]
            current_own = current_group["avg_own"]
            
            is_strategic = False # 他の離れたグループと結合されたか

            for j in range(i + 1, len(group_data)):
                if j in used_indices: continue
                target_group = group_data[j]
                
                # 同じ色、かつOwnershipがほぼ同一（誤差0.001以内）なら同一ユニットとみなす
                if target_group["color"] == current_color:
                    if abs(target_group["avg_own"] - current_own) < 0.001:
                        current_stones.extend(target_group["stones"])
                        used_indices.add(j)
                        is_strategic = True
            
            # 自分の色に合わせた生存確率（安定度）を算出
            stability = current_own if current_color.startswith('b') else -current_own
            merged_groups.append((current_color, current_stones, stability, is_strategic))
            used_indices.add(i)

        return merged_groups

    def _find_physical_groups(self, board):
        """盤上の石を物理的な連結成分（グループ）に分ける"""
        visited = set()
        groups = [] 

        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(r, c)
                color = board.get(r, c)
                if color and p not in visited:
                    color = str(color).lower()
                    group_stones = []
                    self._bfs_group(board, p, color, visited, group_stones)
                    groups.append((color, group_stones))
        return groups

    def _bfs_group(self, board, start_p, color, visited, group_stones):
        queue = [start_p]
        visited.add(start_p)
        while queue:
            curr = queue.pop(0)
            group_stones.append(curr)
            for neighbor in curr.neighbors(self.board_size):
                if neighbor not in visited:
                    n_color = board.get(neighbor.row, neighbor.col)
                    if n_color and str(n_color).lower() == color:
                        visited.add(neighbor)
                        queue.append(neighbor)
