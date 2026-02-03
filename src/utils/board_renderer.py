from utils.renderer.renderer import LayeredBoardRenderer
from utils.renderer.layers.debug_layers import StatusLayer, ShapeLayer

class GoBoardRenderer(LayeredBoardRenderer):
    """
    既存コードとの互換性のためのラッパークラス。
    実体は src/utils/renderer/renderer.py の LayeredBoardRenderer。
    デバッグ用レイヤー（Inspector機能）を追加で搭載する。
    """
    def __init__(self, board_size=19, image_size=850):
        super().__init__(board_size, image_size)
        self.layers.append(StatusLayer())
        self.layers.append(ShapeLayer())

    def render(self, board, **kwargs):
        show_debug = kwargs.pop('show_debug_layers', False)
        for layer in self.layers:
            if isinstance(layer, (StatusLayer, ShapeLayer)):
                layer.visible = show_debug
        return super().render(board, **kwargs)
