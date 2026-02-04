from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext
from core.game_board import Color

class AnalysisLayer(RenderLayer):
    """AIの候補手や手順(PV)を描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if not ctx.candidates: return
        
        # オーバーレイは一度だけで作成 (高速化)
        from PIL import Image
        overlay = Image.new('RGBA', ctx.image.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        
        # モード判定: 手順表示(show_numbers) か 候補手表示(Top 3) か
        items_to_draw = ctx.candidates if ctx.show_numbers else ctx.candidates[:3]
        
        for i, c in enumerate(items_to_draw):
            move_str = c.get('move')
            if not move_str: continue
            
            idx_pair = ctx.transformer.gtp_to_indices(move_str)
            if not idx_pair: continue
            
            px, py = ctx.transformer.indices_to_pixel(idx_pair[0], idx_pair[1])
            gs = ctx.transformer.grid_size
            
            # 石より少し小さくする
            rad = int((gs // 2) * 0.85) # 少し大きめに調整
            
            if ctx.show_numbers:
                # --- 手順表示モード (PV) ---
                # 指定された色で石を描画
                color_obj = c.get('color')
                
                # Robust color check
                is_black = False
                if isinstance(color_obj, Color):
                    is_black = (color_obj == Color.BLACK)
                else:
                    # Fallback string check
                    c_str = str(color_obj).lower() if color_obj else ""
                    is_black = (c_str in ['b', 'black', '黒'])
                
                fill_color = "black" if is_black else "white"
                outline_color = "white" if is_black else "black"
                text_color = "white" if is_black else "black"
                
                # 石を描画
                ov_draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_color, outline=outline_color)
                
                # 手数を描画 (1-based index)
                num = str(i + 1)
                self._draw_centered_text(ov_draw, px, py, num, ctx.font_number, text_color)
                
            else:
                # --- 候補手表示モード (Winrate) ---
                # 従来通りのリング表示
                rad = int((gs // 2) * 0.8)
                
                # 重要度（順位）に応じた色分け
                outline_color = "#00ff00" if i == 0 else "#00aaff"
                fill_color = (0, 255, 0, 60) if i == 0 else (0, 170, 255, 60)
                
                ov_draw.ellipse([px-rad, py-rad, px+rad, py+rad], fill=fill_color, outline=outline_color, width=3)
                
                wr = c.get('winrate_black', c.get('winrate', 0))
                if isinstance(wr, (float, int)):
                    txt = f"{wr:.0%}"
                    num_c = "black" if i == 0 else "blue" 
                    self._draw_centered_text(ov_draw, px, py, txt, ctx.font_number, num_c)
        
        # 最後に合成
        ctx.image.alpha_composite(overlay)
