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
            if r['status'] == 'critical':
                severity = 5
                status_msg = "が極めて危険（生存確率 20%未満）です。即座の救援が必要です。"
            elif r['status'] == 'weak':
                severity = 4
                status_msg = "が弱く、攻撃の対象になっています。"
            elif r['status'] == 'strong':
                severity = 1
                status_msg = "は完全に安定しており、心配ありません。"
            
            if status_msg:
                # 座標リストを簡略化（最初の3つ）
                stones_str = ",".join(r['stones'][:3]) + ("..." if len(r['stones']) > 3 else "")
                desc = f"{r['color']}のグループ [{stones_str}] {status_msg}"
                facts.append(InferenceFact(FactCategory.STABILITY, desc, severity, r))
                
        return facts

    def analyze(self, board, ownership_map):
# ... (rest of the analyze method remains the same)

        """
        board: GameBoardオブジェクト
        ownership_map: 361(or size*size)個の数値リスト (-1.0 to 1.0)
        """
        if not ownership_map:
            return []

        groups = self._find_groups(board)
        analysis_results = []

        for color, stones in groups:
            total_stability = 0
            for p in stones:
                idx = p.row * self.board_size + p.col
                if idx < len(ownership_map):
                    val = ownership_map[idx]
                    # 黒石なら正、白石なら負の値を自分の生存確率として解釈
                    stability = val if color == 'b' else -val
                    total_stability += stability
            
            avg_stability = total_stability / len(stones) if stones else 0
            
            # ステータス判定
            status = "safe"
            if avg_stability < 0.2:    status = "critical" # 死に体
            elif avg_stability < 0.5:  status = "weak"     # 弱い
            elif avg_stability < 0.8:  status = "stable"   # 安定
            else:                      status = "strong"   # 確定
            
            analysis_results.append({
                "color": "黒" if color == 'b' else "白",
                "stones": [p.to_gtp() for p in stones],
                "stability": avg_stability,
                "status": status,
                "count": len(stones)
            })
            
        return analysis_results

    def _find_groups(self, board):
        """盤上の石を連結成分（グループ）に分ける"""
        visited = set()
        groups = [] # List of (color, [Point, ...])

        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(r, c)
                color = board.get(r, c)
                if color and p not in visited:
                    color = color.lower()
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
                    if n_color and n_color.lower() == color:
                        visited.add(neighbor)
                        queue.append(neighbor)
