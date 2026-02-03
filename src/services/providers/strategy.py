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
        # 悪手判定（厚みへの近寄り、カス石への手入れ）は「着手前の盤面」に基づくべき
        target_board = context.prev_board
        
        # 1手前のボード情報がない（＝初手など）場合は処理しない
        if not target_board:
            return

        # 前回の解析結果があればそれを使う。なければ現在の解析結果で代用（近似）
        target_ownership = None
        target_influence = None
        target_uncertainty = None
        
        if context.prev_analysis:
            target_ownership = context.prev_analysis.ownership
            target_influence = context.prev_analysis.influence
            target_uncertainty = getattr(context.prev_analysis, 'uncertainty', None)
        else:
            # フォールバック: 現在のOwnershipをそのまま使う
            target_ownership = analysis.ownership
            target_influence = analysis.influence
            target_uncertainty = getattr(analysis, 'uncertainty', None)

        if not target_ownership:
            return

        # 1. 前回の盤面における安定度分析を実行
        stability_results = self.stability_analyzer.analyze(target_board, target_ownership, target_uncertainty)
        
        last_move = context.last_move
        if not last_move:
            return
            
        current_color = context.last_color
        
        for group in stability_results:
            # 2. 最新手と「過去の強い石（厚み）」との距離をチェック
            if group.status == 'strong':
                is_near = False
                for stone_gtp in group.stones:
                    # GTP座標をPointに変換
                    row = int(stone_gtp[1:]) - 1
                    col = ord(stone_gtp[0].upper()) - ord('A')
                    if col >= 9: col -= 1
                    
                    dist = abs(last_move.row - row) + abs(last_move.col - col)
                    if dist <= 2: # マンハッタン距離2以内（接触または1間飛びの位置）
                        is_near = True
                        break
                
                if is_near:
                    msg = ""
                    if group.color_label == current_color.label:
                        msg = f"【警告：重複】{current_color.label}の手は、既に完成している自身の厚み（{group.stones[0]}周辺）に近すぎます。これは『コリ形（Overconcentration）』です。"
                    else:
                        msg = f"【警告：危険】{current_color.label}の手は、相手の強力な厚み（{group.stones[0]}周辺）に近すぎます。これは『自爆』のリスクが高い手です。"
                    
                    collector.add(
                        FactCategory.STRATEGY, 
                        msg, 
                        severity=4, 
                        metadata=group, 
                        scope=TemporalScope.IMMEDIATE
                    )

            # 3. 最新手と「過去の死に石（カス石）」との関係チェック
            # 死んでいる石（status='dead'）の近くに打った場合
            elif group.status == 'dead' and group.color_label != current_color.label:
                # 相手の死に石に接触したか？
                is_touching = False
                for stone_gtp in group.stones:
                    row = int(stone_gtp[1:]) - 1
                    col = ord(stone_gtp[0].upper()) - ord('A')
                    if col >= 9: col -= 1
                    
                    # 距離1（接触）
                    dist = abs(last_move.row - row) + abs(last_move.col - col)
                    if dist <= 1:
                        is_touching = True
                        break
                
                if is_touching:
                    # もしその手が「高評価（Good Move）」なら、何か決定的な手筋かもしれないので警告しない
                    # score_loss が小さい (e.g. < 0.5) ならスルー
                    # analysis.score_loss は AnalysisResult にない場合が多い (candidates[0].score_loss か、score_lead差分で見る)
                    is_good_move = False
                    if analysis.candidates:
                         # 自分が打った手が候補のトップ近くにあるか？
                         # 簡易的に、Top1候補の座標と一致するか
                         top_move = analysis.candidates[0].move
                         if top_move == last_move.to_gtp():
                             is_good_move = True
                    
                    if not is_good_move:
                        msg = f"【警告：緩着】すでに死んでいる{group.color_label}の石（{group.stones[0]}周辺）にさらに手をかけました。これは「カス石」を相手にした効率の悪い手です。"
                        collector.add(
                            FactCategory.STRATEGY,
                            msg,
                            severity=4,
                            metadata=group,
                            scope=TemporalScope.IMMEDIATE
                        )

            # 4. 厚み（Atsumi）としての評価 (EXISTING Fact for Context)
            # 現在の盤面ではなく、全体の状況として「厚みが存在する」ことを伝える
            # ただし、これは StrategyProviderに書くべきか、StabilityProviderか？
            # 「厚み」という概念は戦略的なのでここでOK
            if group.status == 'strong' and target_influence:
                stones_points = [Point.from_gtp(s) for s in group.stones]
                raw_inf = self.stability_analyzer.calculate_group_influence(stones_points, target_influence)
                
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
