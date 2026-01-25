from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext

class AnalysisLayer(RenderLayer):
    """AIの候補手を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.candidates: return
        t = ctx.theme
        
        for i, c in enumerate(ctx.candidates[:3]): # Top 3
            move_str = c.get('move')
            idx_pair = ctx.transformer.gtp_to_indices(move_str)
            if not idx_pair: continue
            
            px, py = ctx.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
            gs = ctx.transformer.grid_size
            rad = gs // 2 - 2
            
            # V2: 重要度（順位）に応じた色分け (TODO: テーマ化)
            color = "#00ff00" if i == 0 else "#00aaff"
            draw.ellipse([px-rad, py-rad, px+rad, py+rad], outline=color, width=3)
            
            wr = c.get('winrate_black', c.get('winrate', 0))
            if isinstance(wr, (float, int)):
                txt = f"{wr:.0%}"
                num_c = t.markup_color_light if i == 0 else "blue" # TODO: Improve contrast
                self._draw_centered_text(draw, px, py, txt, ctx.font_number, num_c)
