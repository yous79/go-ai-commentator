from core.inference_fact import FactCollector, FactCategory, TemporalScope, MoyoMetadata
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from core.board_region import BoardRegion, RegionType
from core.point import Point
from .base import BaseFactProvider

class InfluenceFactProvider(BaseFactProvider):
    """エリアごとの勢力バランスを分析するプロバイダ"""
    
    def __init__(self, board_size: int, board_region: BoardRegion):
        super().__init__(board_size)
        self.board_region = board_region

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.influence:
            return
            
        region_stats = {rt: {"own": 0.0, "inf": 0.0, "count": 0} for rt in RegionType}
        
        for i, inf_val in enumerate(analysis.influence):
            r, c = i // self.board_size, i % self.board_size
            rt = self.board_region.get_region(Point(r, c))
            own = analysis.ownership[i] if analysis.ownership else 0
            
            region_stats[rt]["own"] += own
            region_stats[rt]["inf"] += inf_val
            region_stats[rt]["count"] += 1

        for rt, stats in region_stats.items():
            if stats["count"] == 0: continue
            avg_own, avg_inf = stats["own"] / stats["count"], stats["inf"] / stats["count"]
            
            msg = self._judge_influence(rt, avg_own, avg_inf)
            if msg:
                collector.add(FactCategory.STRATEGY, msg, severity=3, scope=TemporalScope.EXISTING)

        # 模様（Moyo）の検出
        self._detect_moyo(collector, analysis)

    def _detect_moyo(self, collector: FactCollector, analysis: AnalysisResult):
        visited = set()
        moyo_candidates = {} # Point -> color_str

        # 1. 候補点の特定
        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(r, c)
                idx = r * self.board_size + c
                own = analysis.ownership[idx]
                inf = analysis.influence[idx]

                color = None
                # 黒模様候補: 地になりかけ(0.35~0.85) または 影響力大(Inf>2.0)
                if (0.35 < own < 0.85) or (own >= -0.1 and inf > 2.0):
                    color = "黒"
                # 白模様候補
                elif (-0.85 < own < -0.35) or (own <= 0.1 and inf < -2.0):
                    color = "白"
                
                if color:
                    moyo_candidates[p] = color

        # 2. クラスタリング (BFS)
        clusters = []
        for p, color in moyo_candidates.items():
            if p in visited: continue
            
            cluster_points = []
            queue = [p]
            visited.add(p)
            while queue:
                curr = queue.pop(0)
                cluster_points.append(curr)
                for n in curr.neighbors(self.board_size):
                    if n in moyo_candidates and moyo_candidates[n] == color and n not in visited:
                        visited.add(n)
                        queue.append(n)
            
            clusters.append((color, cluster_points))

        # 3. 評価とFact生成
        for color, points in clusters:
            # 閾値: ある程度の広さがないと模様とは呼ばない (例: 12目以上)
            if len(points) >= 12:
                total_own = 0
                for pt in points:
                    idx = pt.row * self.board_size + pt.col
                    val = analysis.ownership[idx]
                    total_own += val if color == "黒" else -val
                
                avg_potential = total_own / len(points)
                points_gtp = [pt.to_gtp() for pt in points]
                center_pt = points[len(points)//2] # 簡易的な中心

                msg = f"{color}の模様が {center_pt.to_gtp()} 周辺に広がっています（大きさ: {len(points)}目）。"
                collector.add(
                    FactCategory.STRATEGY,
                    msg,
                    severity=3,
                    metadata=MoyoMetadata(
                        points=points_gtp,
                        size=len(points),
                        potential=avg_potential,
                        label=f"{color}模様"
                    ),
                    scope=TemporalScope.EXISTING
                )

    def _judge_influence(self, rt: RegionType, avg_own: float, avg_inf: float) -> str:
        TERRITORY_THRES, INFLUENCE_THRES = 0.4, 0.3
        
        status_own = "中立"
        if avg_own > TERRITORY_THRES: status_own = "黒地"
        elif avg_own < -TERRITORY_THRES: status_own = "白地"
        
        status_inf = "互角"
        if avg_inf > INFLUENCE_THRES: status_inf = "黒勢力"
        elif avg_inf < -INFLUENCE_THRES: status_inf = "白勢力"
        
        if status_own == "黒地" and status_inf == "白勢力":
            return f"{rt.value}は黒の実利ですが、白の厚みが勝り、薄い状態です。"
        elif status_own == "白地" and status_inf == "黒勢力":
            return f"{rt.value}は白の実利ですが、黒の厚みが勝り、薄い状態です。"
        elif status_own == "中立":
            if status_inf == "黒勢力": return f"{rt.value}は黒の有望な模様（勢力圏）となっています。"
            elif status_inf == "白勢力": return f"{rt.value}は白の有望な模様（勢力圏）となっています。"
        return ""
