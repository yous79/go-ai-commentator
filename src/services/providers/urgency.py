import asyncio
from core.inference_fact import FactCollector, FactCategory, TemporalScope, UrgencyMetadata
from core.board_simulator import SimulationContext, BoardSimulator
from core.shape_detector import ShapeDetector
from core.analysis_dto import AnalysisResult
from services.api_client import api_client
from core.game_board import Color
from .base import BaseFactProvider

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
