from PIL import ImageDraw
from utils.renderer.base import RenderLayer, RenderContext

class InfoLayer(RenderLayer):
    """下部の情報テキストを描画するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        if ctx.analysis_text:
            t = ctx.theme
            # V2: 描画色をテーマに準拠させることも可能だが、視認性のため暗色固定
            # Draw bottom area
            draw.rectangle([(0, ctx.image_size), (ctx.image_size, ctx.image_size + 100)], fill=(30, 30, 30))
            self._draw_centered_text(draw, ctx.image_size // 2, ctx.image_size + 50, ctx.analysis_text, ctx.font, "white")
