from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext
from core.inference_fact import FactCategory, TemporalScope

class StatusLayer(RenderLayer):
    """
    石のステータス（Stability）を色分け表示するデバッグレイヤー
    Strong: Green, Stable: Blue, Weak: Yellow, Dead: Red
    """
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        # コンテキストに facts が含まれていることを想定
        # FactCollector.facts から STABILITY 系のFactを抽出して表示
        # ※本来は StabilityAnalyzer の生データがあればよいが、Fact経由で簡易表示する
        
        collector = getattr(ctx, 'fact_collector', None)
        if not collector: return

        for fact in collector.facts:
            if fact.category != FactCategory.STABILITY: continue
            
            # メタデータから対象の石を取得
            metadata = getattr(fact, 'metadata', None)
            if not metadata or not hasattr(metadata, 'stones'): continue
            
            stones = metadata.stones # List[str] (GTP coords) or List[Point] depending on implementation
            
            # 色の決定
            fill_color = None
            outline_color = None
            
            if "Strong" in fact.description or "安定" in fact.description:
                fill_color = (0, 255, 0, 40)
                outline_color = "#00FF00"
            elif "Dead" in fact.description or "カス石" in fact.description:
                fill_color = (255, 0, 0, 40)
                outline_color = "#FF0000"
            elif "Weak" in fact.description or "弱い" in fact.description:
                fill_color = (255, 255, 0, 40)
                outline_color = "#FFFF00"
            else:
                fill_color = (0, 0, 255, 40)
                outline_color = "#0000FF"

            for stone_gtp in stones:
                # GTP -> Index -> Pixel
                idx_pair = ctx.transformer.gtp_to_indices(stone_gtp)
                if not idx_pair: continue
                col, row = idx_pair
                
                px, py = ctx.transformer.indices_to_pixel(col, row)
                gs = ctx.transformer.grid_size
                rad = int(gs * 0.4) # 石より少し小さい四角形
                
                # 四角形で囲む (丸い石と区別するため)
                draw.rectangle([px-rad, py-rad, px+rad, py+rad], fill=fill_color, outline=outline_color, width=2)
                
                # Severityを表示（オプション）
                if ctx.theme.show_coordinates: # デバッグモードフラグの代用
                    self._draw_centered_text(draw, px, py, str(fact.severity), ctx.font_small, outline_color)


class ShapeLayer(RenderLayer):
    """
    検知された悪形（Shape）を強調表示するデバッグレイヤー
    """
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        collector = getattr(ctx, 'fact_collector', None)
        if not collector: return

        for fact in collector.facts:
            if fact.category != FactCategory.SHAPE: continue
            
            # メタデータから対象の石を取得
            stones = []
            if hasattr(fact, 'metadata'):
                if isinstance(fact.metadata, list): # List of Points/GTP
                     stones = fact.metadata
                elif hasattr(fact.metadata, 'stones'):
                     stones = fact.metadata.stones
            
            if not stones: continue
            
            is_predicted = (fact.scope == TemporalScope.PREDICTED)
            line_color = "#FF00FF" if not is_predicted else "#AAAAFF" # Magenta for Immediate, Pale Blue for Predicted
            line_width = 3 if fact.severity >= 4 else 1
            
            # 対象の石を線で囲む (Convex Hull的な描画は難しいので、個別に枠表示 + リンク線)
            prev_px, prev_py = None, None
            
            for s in stones:
                s_gtp = s if isinstance(s, str) else s.to_gtp()
                idx_pair = ctx.transformer.gtp_to_indices(s_gtp)
                if not idx_pair: continue
                col, row = idx_pair
                px, py = ctx.transformer.indices_to_pixel(col, row)
                
                # 枠表示
                gs = ctx.transformer.grid_size
                rad = int(gs * 0.5)
                draw.ellipse([px-rad, py-rad, px+rad, py+rad], outline=line_color, width=line_width)
                
                # 連結線を描画（形状のつながりを可視化）
                if prev_px is not None:
                    draw.line([prev_px, prev_py, px, py], fill=line_color, width=1)
                
                prev_px, prev_py = px, py
