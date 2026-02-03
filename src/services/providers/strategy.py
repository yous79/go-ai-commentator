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
            # --- 厳格化: 平均Ownershipによる本当にその状態かの確認 ---
            stones_indices = []
            for s_gtp in group.stones:
                col = ord(s_gtp[0].upper()) - ord('A')
                if col >= 9: col -= 1
                row = int(s_gtp[1:]) - 1
                stones_indices.append(row * self.board_size + col)
            
            if not stones_indices or not target_ownership:
                continue
                
            avg_own = sum(target_ownership[i] for i in stones_indices) / len(stones_indices)
            
            # 色とOwnershipの符号の整合性確認
            # 黒石ならOwnershipプラスが生き、マイナスが死
            is_black = (group.color_label == "黒")
            
            # --- Statusごとの厳格なフィルタリング ---
            from core.analysis_config import AnalysisConfig
            atsumi_thresh = AnalysisConfig.get("ATSUMI_THRESHOLD")   # e.g. 0.90
            kasuishi_thresh = AnalysisConfig.get("KASUISHI_THRESHOLD") # e.g. -0.85

            if group.status == 'strong':
                # 黒でStrongならOwn > 0.9, 白でStrongならOwn < -0.9 (abs > 0.9)
                current_val = avg_own if is_black else -avg_own
                if current_val < atsumi_thresh:
                    continue # 厚みというほど確定していない
                    
                # 2. 最新手と「過去の強い石（厚み）」との距離をチェック
                is_near = False
                for s_gtp in group.stones:
                    # 簡易マンハッタン距離
                    row = int(s_gtp[1:]) - 1
                    col = ord(s_gtp[0].upper()) - ord('A')
                    if col >= 9: col -= 1
                    dist = abs(last_move.row - row) + abs(last_move.col - col)
                    if dist <= 2:
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

            elif group.status == 'dead':
                # 黒でDeadならOwn < -0.85, 白でDeadならOwn > 0.85 (逆の色が支配)
                # つまり「支配度」は -current_val (相手の支配)
                current_val = avg_own if is_black else -avg_own
                # current_val は マイナスであるはず（死んでいるから）
                # 相手の支配度が閾値を超えているか？ -> current_val < -0.85
                if current_val > kasuishi_thresh:
                    continue # まだ味が残っている（完全なカス石ではない）

                # 3. 最新手と「過去の死に石（カス石）」との関係チェック
                # カス石取り（相手の死に石への手入れ）
                if group.color_label != current_color.label:
                    # 厳格化: 「接触 (Distance<=1)」のみ警告対象とする
                    is_touching = False
                    for s_gtp in group.stones:
                        row = int(s_gtp[1:]) - 1
                        col = ord(s_gtp[0].upper()) - ord('A')
                        if col >= 9: col -= 1
                        dist = abs(last_move.row - row) + abs(last_move.col - col)
                        if dist <= 1:
                            is_touching = True
                            break
                    
                    if is_touching:
                        is_good_move = False
                        if analysis.candidates:
                             top_move = analysis.candidates[0].move
                             if top_move == last_move.to_gtp():
                                 is_good_move = True
                        
                        if not is_good_move:
                            msg = f"【警告：緩着】すでに死んでいる{group.color_label}の石（{group.stones[0]}周辺）にわざわざ接触しました。これは「カス石」を相手にした効率の悪い手です。"
                            collector.add(
                                FactCategory.STRATEGY,
                                msg,
                                severity=4,
                                metadata=group,
                                scope=TemporalScope.IMMEDIATE
                            )
                
                # カス石救済（自己の死に石への手入れ）のロジック追加
                # ユーザー要望の「カス石救済」警告
                elif group.color_label == current_color.label:
                     # 自分の死に石に接触（助けようとしている？）
                    is_trying_to_save = False
                    for s_gtp in group.stones:
                        row = int(s_gtp[1:]) - 1
                        col = ord(s_gtp[0].upper()) - ord('A')
                        if col >= 9: col -= 1
                        dist = abs(last_move.row - row) + abs(last_move.col - col)
                        if dist <= 1:
                            is_trying_to_save = True
                            break
                    
                    if is_trying_to_save:
                        # 助ける手が有力でない限り警告
                        is_good_move = False
                        if analysis.candidates:
                             top_move = analysis.candidates[0].move
                             if top_move == last_move.to_gtp():
                                 is_good_move = True

                        if not is_good_move:
                            msg = f"【警告：救済】助かる見込みの薄い{group.color_label}の石（{group.stones[0]}周辺）を動きました。これは被害を拡大する『重い手』になるリスクがあります。"
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
