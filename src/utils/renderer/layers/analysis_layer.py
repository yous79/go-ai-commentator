from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext

class AnalysisLayer(RenderLayer):
    """AIの候補手を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.candidates: return
        t = ctx.theme
        
        # オーバーレイは一度だけで作成 (高速化)
        from PIL import Image
        overlay = Image.new('RGBA', ctx.image.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        
        for i, c in enumerate(ctx.candidates[:3]): # Top 3
            move_str = c.get('move')
            idx_pair = ctx.transformer.gtp_to_indices(move_str)
            if not idx_pair: continue
            
            px, py = ctx.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
            gs = ctx.transformer.grid_size
            
            # 石より少し小さくする (圧迫感の軽減)
            rad = int((gs // 2) * 0.8)
            
            # V2: 重要度（順位）に応じた色分け
            # 外枠の色
            outline_color = "#00ff00" if i == 0 else "#00aaff"
            # 塗りつぶしの色
            fill_color = (0, 255, 0, 60) if i == 0 else (0, 170, 255, 60)
            
            ov_draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_color, outline=outline_color, width=3)
            
            wr = c.get('winrate_black', c.get('winrate', 0))
            if isinstance(wr, (float, int)):
                txt = f"{wr:.0%}"
                num_c = "black" if i == 0 else "blue" 
                self._draw_centered_text(ov_draw, px, py, txt, ctx.font_number, num_c)
        
        # 最後に合成
        ctx.image.alpha_composite(overlay)
