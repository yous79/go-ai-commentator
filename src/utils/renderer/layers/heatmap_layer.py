from PIL import ImageDraw, Image
from utils.renderer.base import RenderLayer, RenderContext

class HeatmapLayer(RenderLayer):
    """盤面の領土優劣（Ownership）を色で表示するレイヤー"""
    def draw(self, draw: ImageDraw.ImageDraw, ctx: RenderContext):
        # 1. データの取得
        ownership = ctx.ownership
        if not ownership and hasattr(ctx, 'analysis_result') and ctx.analysis_result:
            ownership = ctx.analysis_result.ownership
            
        if not ownership:
            print("DEBUG: No ownership data available for HeatmapLayer") # DEBUG
            return
            
        print(f"DEBUG: HeatmapLayer drawing... ownership len={len(ownership)}") # DEBUG
        
        gs = ctx.transformer.grid_size
        radius = gs // 2
        
        # テーマから色を取得
        c_black, c_white = ctx.theme.heatmap_colors
        
        # 描画用のオーバーレイ画像を作成（後で合成）
        overlay = Image.new('RGBA', ctx.image.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)

        for i, val in enumerate(ownership):
            if i >= ctx.board_size * ctx.board_size: break
            
            row = i // ctx.board_size
            col = i % ctx.board_size
            
            # 確信度が低い場合はスキップ
            conf = abs(val)
            if conf < 0.1: continue

            px, py = ctx.transformer.indices_to_pixel(row, col)
            
            # 透明度計算 (最大128程度の半透明)
            alpha = int(128 * conf)
            
            # 色の決定 (+: 黒地, -: 白地)
            base_color = c_black if val > 0 else c_white
            fill_color = (*base_color, alpha)
            
            # 矩形で塗りつぶし（隣とくっつくように）
            # px, py は交点の中心。グリッドサイズ分の矩形を描く
            x0, y0 = px - radius, py - radius
            x1, y1 = px + radius, py + radius
            
            # 微調整: 完全に埋めるために少しオーバーラップさせるか、ぴったりにするか
            # ここではぴったりにする
            ov_draw.rectangle([x0, y0, x1, y1], fill=fill_color)

        # 元画像に合成
        ctx.image.alpha_composite(overlay)
