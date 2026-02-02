from core.inference_fact import FactCollector, FactCategory, TemporalScope, AtsumiMetadata
from core.board_simulator import SimulationContext
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_dto import AnalysisResult
from core.point import Point
from .base import BaseFactProvider

class StrategicFactProvider(BaseFactProvider):
    """
    「厚みに近づくな」「強い石の近くは価値が低い」などの大局的な戦略原則をチェックするプロバイダ。
    """
    def __init__(self, board_size: int, stability_analyzer: StabilityAnalyzer):
        super().__init__(board_size)
        self.stability_analyzer = stability_analyzer

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.ownership:
            return

        # 1. 安定度分析を実行して強い石（厚み）を特定
        stability_results = self.stability_analyzer.analyze(context.board, analysis.ownership, getattr(analysis, 'uncertainty', None))
        
        last_move = context.last_move
        
        for group in stability_results:
            if group.status != 'strong':
                continue
            
            # 2. 最新手と「強い石」との距離をチェック
            if last_move:
                is_near = False
                for stone_gtp in group.stones:
                    # GTP座標をPointに変換
                    row = int(stone_gtp[1:]) - 1
                    col = ord(stone_gtp[0].upper()) - ord('A')
                    if col >= 9: col -= 1 # 'I'を飛ばす処理
                    
                    dist = abs(last_move.row - row) + abs(last_move.col - col)
                    if dist <= 2:
                        is_near = True
                        break
                
                if is_near:
                    msg = ""
                    if group.color_label == context.last_color.label:
                        msg = f"【警告：重複】{context.last_color.label}の手は、{group.color_label}自身の厚み（{group.stones[0]}周辺）に近すぎます。これは『コリ形（Overconcentration）』です。"
                    else:
                        msg = f"【警告：危険】{context.last_color.label}の手は、{group.color_label}の厚み（{group.stones[0]}周辺）に近すぎます。これは『自爆』のリスクが高い手です。"
                    
                    collector.add(
                        FactCategory.STRATEGY, 
                        msg, 
                        severity=4, 
                        metadata=group, 
                        scope=TemporalScope.IMMEDIATE
                    )

            # 3. 厚み（Atsumi）としての評価
            stones_points = [Point.from_gtp(s) for s in group.stones]
            raw_inf = self.stability_analyzer.calculate_group_influence(stones_points, analysis.influence)
            
            is_black_group = (group.color_label == "黒")
            inf_power = raw_inf if is_black_group else -raw_inf
            
            if inf_power > 1.2:
                msg = f"{group.color_label}の石（{group.stones[0]}周辺）は『厚み』として機能しており、周囲に強い影響力を及ぼしています。"
                collector.add(
                    FactCategory.STRATEGY,
                    msg,
                    severity=3,
                    metadata=AtsumiMetadata(
                        stones=group.stones,
                        strength=group.stability,
                        influence_power=inf_power,
                        direction="omnidirectional" 
                    ),
                    scope=TemporalScope.EXISTING
                )
