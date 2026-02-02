from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from core.inference_fact import (
    InferenceFact, FactCategory, FactCollector, TemporalScope, 
    BaseFactMetadata, GamePhaseMetadata, KoMetadata, UrgencyMetadata, 
    BaseFactMetadata, GamePhaseMetadata, KoMetadata, UrgencyMetadata, 
    ShapeMetadata, MistakeMetadata, StabilityMetadata, AtsumiMetadata, MoyoMetadata
)
from core.point import Point
from core.board_simulator import SimulationContext, BoardSimulator
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from core.analysis_dto import AnalysisResult
from core.board_region import BoardRegion, RegionType
from services.api_client import api_client
from utils.logger import logger

class BaseFactProvider(ABC):
    """事実生成プロバイダの抽象基底クラス"""
    
    def __init__(self, board_size: int):
        self.board_size = board_size

    @abstractmethod
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        """解析事実を生成してコレクターに追加する"""
        pass

class ShapeFactProvider(BaseFactProvider):
    """現局面の幾何学的形状を検知するプロバイダ"""
    
    def __init__(self, board_size: int, detector: ShapeDetector):
        super().__init__(board_size)
        self.detector = detector

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 形状検知はCPU負荷が高いため、必要に応じて thread で実行
        import asyncio
        shape_facts = await asyncio.to_thread(self.detector.detect_facts, context, analysis_result=analysis)
        for f in shape_facts:
            f.scope = TemporalScope.IMMEDIATE
            collector.add_fact(f)

class StabilityFactProvider(BaseFactProvider):
    """石の安定度（生存確率）を解析するプロバイダ"""
    
    def __init__(self, board_size: int, stability_analyzer: StabilityAnalyzer):
        super().__init__(board_size)
        self.analyzer = stability_analyzer

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if analysis.ownership:
            import asyncio
            # uncertainty map might be None if engine doesn't support it
            uncertainty_map = getattr(analysis, 'uncertainty', None)
            stability_facts = await asyncio.to_thread(self.analyzer.analyze_to_facts, context.board, analysis.ownership, uncertainty_map)
            for f in stability_facts:
                f.scope = TemporalScope.EXISTING
                collector.add_fact(f)

class EndgameFactProvider(BaseFactProvider):
    """局面が終盤（ヨセ）に入ったかを判定するプロバイダ"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.ownership:
            return
            
        SETTLED_THRESHOLD = 0.9
        settled_points = sum(1 for val in analysis.ownership if abs(val) > SETTLED_THRESHOLD)
        settlement_ratio = settled_points / len(analysis.ownership)
        
        if settlement_ratio > 0.85:
            collector.add(
                FactCategory.STRATEGY, 
                "【局面ステータス】終盤（ヨセ）に入りました。細かな得失と正確な計算が重要です。", 
                severity=2, 
                metadata=GamePhaseMetadata(phase="endgame"), 
                scope=TemporalScope.EXISTING
            )

class InfluenceFactProvider(BaseFactProvider):
    """エリアごとの勢力バランスを分析するプロバイダ"""
    
    def __init__(self, board_size: int, board_region: BoardRegion):
        super().__init__(board_size)
        self.board_region = board_region

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.influence:
            return
            
        region_stats = {rt: {"own": 0.0, "inf": 0.0, "count": 0} for rt in RegionType}
        from core.point import Point
        
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

class UrgencyFactProvider(BaseFactProvider):
    """着手の緊急度および将来の悪形予測を行うプロバイダ"""
    
    def __init__(self, board_size: int, simulator: BoardSimulator, detector: ShapeDetector):
        super().__init__(board_size)
        self.simulator = simulator
        self.detector = detector

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        history = context.history
        bs = self.board_size
        
        # Urgency解析は API (ネットワーク) を呼ぶため、特に並列化のメリットが大きい
        import asyncio
        urgency_data = await asyncio.to_thread(api_client.analyze_urgency, history, bs)
        if urgency_data:
            u_severity = 5 if urgency_data['is_critical'] else 2
            u_desc = f"この局面の緊急度は {urgency_data['urgency']:.1f}目 です。{'一手の緩みも許されない急場です。' if urgency_data['is_critical'] else '比較的平穏な局面です。'}"
            
            meta = UrgencyMetadata(
                urgency=urgency_data['urgency'],
                is_critical=urgency_data['is_critical'],
                next_player=urgency_data['next_player']
            )
            collector.add(FactCategory.URGENCY, u_desc, u_severity, meta, scope=TemporalScope.EXISTING)
            
            # 未来の悪形警告（被害予想図における形の崩れを検知）
            thr_pv = urgency_data.get('opponent_pv')
            if thr_pv:
                thr_seq = ["pass"] + thr_pv
                future_ctx = self.simulator.simulate_sequence(context, thr_seq, starting_color=urgency_data['next_player'])
                
                # 1. 現在の盤面での悪形を把握（重複検知を防ぐため）
                p_color_str = urgency_data['next_player']
                from core.game_board import Color
                p_color = Color.from_str(p_color_str)
                
                current_shapes = self.detector.detect_all_facts(context, p_color)
                current_shape_ids = set()
                for fs in current_shapes:
                    s_key = getattr(fs.metadata, 'key', 'unknown')
                    current_shape_ids.add((s_key, fs.description))
                
                # 2. 未来の盤面での悪形をリストアップ
                future_shapes = self.detector.detect_all_facts(future_ctx, p_color)
                for f in future_shapes:
                    s_key = getattr(f.metadata, 'key', 'unknown')
                    if (s_key, f.description) not in current_shape_ids and f.severity >= 4:
                        f.description = f"放置すると {f.description} という悪形が発生する恐れがあります。"
                        f.scope = TemporalScope.PREDICTED
                        collector.add_fact(f)

                # 3. 相手からの攻撃（サカレ形など）を検知
                opp_color = p_color.opposite()
                current_opp_shapes = self.detector.detect_all_facts(context, opp_color)
                current_opp_shape_ids = {(getattr(fs.metadata, 'key', 'unknown'), fs.description) for fs in current_opp_shapes}

                future_opp_shapes = self.detector.detect_all_facts(future_ctx, opp_color)
                for f in future_opp_shapes:
                    s_key = getattr(f.metadata, 'key', 'unknown')
                    # 相対的な形状（相手が自分を割る、など）が新しく発生した場合
                    if s_key in ["sakare_gata", "nimoku_atama", "ryo_atari", "kirichigai"] and \
                       (s_key, f.description) not in current_opp_shape_ids:
                        f.description = f"放置すると {f.description} という急所に打たれる恐れがあります。"
                        f.scope = TemporalScope.PREDICTED
                        collector.add_fact(f)

class KoFactProvider(BaseFactProvider):
    """コウの発生や解消を検知するプロバイダ"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        # 1. コウの発生（今打たれた手によって石が1つ取られた）
        if context.captured_points and len(context.captured_points) == 1:
            cap_pt = context.captured_points[0]
            msg = f"最新の着手によって {cap_pt.to_gtp()} の石が取られました。コウの争いが始まる可能性があります。"
            collector.add(FactCategory.STRATEGY, msg, severity=4, metadata=KoMetadata(type="ko_initiation", point=cap_pt.to_gtp()), scope=TemporalScope.IMMEDIATE)

class MoveQualityFactProvider(BaseFactProvider):
    """
    着手の評価値下落を検知し、失着の事実を生成するプロバイダ。
    """
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not context.history or len(context.history) < 2:
            return

        # 1. 1手前の局面（相手が打った直後）の解析値を取得し、その「最善手」のスコアを確認する
        # ※本来は AnalysisService のキャッシュから渡されるのが理想だが、ここでは並列に取得
        import asyncio
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
        # len(history) が偶数なら白の手番、奇数なら黒の手番（sgfmill等の仕様に依存）
        # ここでは直前の着手（history[-1]）を下したプレイヤーが損をしたかを判定
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
                from core.point import Point
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
                        # 手番が黒なら own > 0.5, 手番が白なら own < -0.5
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

class StrategicFactProvider(BaseFactProvider):
    """
    「厚みに近づくな」「強い石の近くは価値が低い」などの大局的な戦略原則をチェックするプロバイダ。
    """
    def __init__(self, board_size: int, stability_analyzer: StabilityAnalyzer):
        super().__init__(board_size)
        self.analyzer = stability_analyzer

    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        if not analysis.ownership:
            return

        # 1. 安定度分析を実行して強い石（厚み）を特定
        stability_results = self.analyzer.analyze(context.board, analysis.ownership, getattr(analysis, 'uncertainty', None))
        
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
            raw_inf = self.analyzer.calculate_group_influence(stones_points, analysis.influence)
            
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

class BasicStatsFactProvider(BaseFactProvider):
    """勝率や目数差などの基本統計情報を提供"""
    
    async def provide_facts(self, collector: FactCollector, context: SimulationContext, analysis: AnalysisResult):
        sl = analysis.score_lead
        collector.add(
            FactCategory.STRATEGY, 
            f"現在の勝率(黒): {analysis.winrate_label}, 目数差: {sl:.1f}目", 
            severity=3, 
            scope=TemporalScope.EXISTING
        )
