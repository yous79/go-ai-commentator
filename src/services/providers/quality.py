import asyncio
import sys
from core.inference_fact import FactCollector, FactCategory, TemporalScope, MistakeMetadata
from core.board_simulator import SimulationContext
from core.analysis_dto import AnalysisResult
from services.api_client import api_client
from core.point import Point
from .base import BaseFactProvider

class MoveQualityFactProvider(BaseFactProvider):
    """
    着手の評価値下落を検知し、失着の事実を生成するプロバイダ。
    """
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not context.history or len(context.history) < 2:
            return

        # 1. 1手前の局面（相手が打った直後）の解析値を取得し、その「最善手」のスコアを確認する
        prev_history = context.history[:-1]
        prev_analysis = await asyncio.to_thread(api_client.analyze_move, prev_history, self.board_size)
        
        if not prev_analysis or not prev_analysis.candidates:
            return

        # 前の局面での最善の期待スコア（黒視点）
        prev_best_score = prev_analysis.candidates[0].score_lead
        # 現在の着手後のスコア（黒視点）
        curr_score = analysis.score_lead
        # 前の局面の勝率
        prev_winrate = prev_analysis.winrate

        # 下落幅の計算（手番によって符号を調整）
        # len(history) が偶数なら白の手番、奇数なら黒の手番
        was_black = (len(context.history) % 2 != 0)
        
        score_drop = (prev_best_score - curr_score) if was_black else (curr_score - prev_best_score)
        wr_drop = (prev_winrate - analysis.winrate) if was_black else (analysis.winrate - prev_winrate)

        # 閾値判定（目数で 2.0目以上、または勝率 5%以上損した場合を「失着」とする）
        if score_drop > 2.0 or wr_drop > 0.05:
            severity = 3
            if score_drop > 10.0: severity = 5
            elif score_drop > 5.0: severity = 4
            
            player = "黒" if was_black else "白"
            mistake_type = "drop_score"
            
            # --- 追加：自分の死に石を助けようとしたかの判定 ---
            is_saving_junk = False
            is_capturing_junk = False
            
            last_move = context.last_move
            if last_move and prev_analysis.ownership:
                # 着手地点の隣接する石を確認
                for neighbor in last_move.neighbors(self.board_size):
                    prev_stone = context.prev_board.get(neighbor)
                    if not prev_stone: continue
                    
                    # 前の局面でのOwnershipを取得
                    idx = neighbor.row * self.board_size + neighbor.col
                    own = prev_analysis.ownership[idx] # 黒地+, 白地-
                    
                    # 1. 自分の石の救済判定
                    if prev_stone == context.last_color:
                        stability = own if was_black else -own # 自分の地なら正
                        if stability < -0.5: # 強く相手側＝死んでいる
                            is_saving_junk = True
                            
                    # 2. 相手の石の徴収判定
                    elif prev_stone != context.last_color:
                        # 相手の石が、すでに自分（手番側）の地になっているか
                        opponent_stability = own if not was_black else -own # 相手視点の安定度
                        if opponent_stability < -0.5: # 相手にとって死んでいる＝自分にとって確保済み
                            is_capturing_junk = True

            if is_saving_junk:
                mistake_type = "kasu_ishi_salvage"
                msg = f"【警告：救済】{player}の手は、すでに死んでいる石（カス石）を助けようとして評価値を損ねました（下落幅: {score_drop:.1f}目）。これは『沈没船に荷物を積む』ような行為です。"
            elif is_capturing_junk:
                mistake_type = "kasu_ishi_capture"
                msg = f"【警告：空回り】{player}の手は、すでに死んでいる相手の石に追い打ちをかけて評価値を損ねました（下落幅: {score_drop:.1f}目）。これは『レシート拾い』のような非効率な手です。"
            else:
                msg = f"{player}の最新手は評価値を損ねました（下落幅: {score_drop:.1f}目 / 勝率: {wr_drop:.1%})。より価値の高い場所があった可能性があります。"
            
            collector.add(
                FactCategory.MISTAKE, 
                msg, 
                severity=severity, 
                metadata=MistakeMetadata(type=mistake_type, value=score_drop),
                scope=TemporalScope.IMMEDIATE
            )
