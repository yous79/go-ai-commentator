import os
import json
import time
from core.game_state import GoGameState
from utils.board_renderer import GoBoardRenderer
from core.shape_detector import ShapeDetector
from core.coordinate_transformer import CoordinateTransformer
from core.board_simulator import SimulationContext
from config import KNOWLEDGE_DIR, OUTPUT_BASE_DIR, load_api_key, GEMINI_MODEL_NAME
from google import genai
from google.genai import types

class TermVisualizer:
    """局面状態から画像をレンダリングする責任のみを持つクラス"""

    def __init__(self):
        # レンダラーは内部で動的にサイズ調整される
        self.renderer = GoBoardRenderer(board_size=19, image_size=600)
        self.api_key = load_api_key()
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def visualize_context(self, ctx: SimulationContext, title="Reference Diagram"):
        """SimulationContextを受け取り、画像を生成する（推奨の描画口）"""
        from utils.logger import logger
        
        # レンダラーのサイズ同期
        self.renderer.board_size = ctx.board_size
        self.renderer.transformer = CoordinateTransformer(ctx.board_size, self.renderer.image_size)
        
        try:
            img = self.renderer.render(
                ctx.board, 
                analysis_text=title, 
                history=ctx.history, 
                show_numbers=True
            )
            
            filename = f"ref_{{int(time.time())}}_{os.urandom(4).hex()}.png"
            output_path = os.path.join(OUTPUT_BASE_DIR, filename)
            img.save(output_path)
            return output_path, None
        except Exception as e:
            logger.error(f"Error in visualize_context rendering: {e}", layer="VISUALIZER")
            return None, str(e)

    def visualize(self, term_id, category="01_bad_shapes"):
        """(Legacy互換) 用語IDから画像を生成し、保存先パスを返す"""
        term_dir = os.path.join(KNOWLEDGE_DIR, category, term_id)
        example_sgf = os.path.join(term_dir, "example.sgf")
        
        sgf_content = None
        if os.path.exists(example_sgf):
            with open(example_sgf, "r", encoding="utf-8") as f:
                sgf_content = f.read()
        
        if not sgf_content and self.client:
            sgf_content = self._generate_sgf_via_ai(term_id)

        if not sgf_content:
            return None, "No example data or AI available."

        return self._render_from_sgf(term_id, sgf_content)

    def _generate_sgf_via_ai(self, term_id):
        """Geminiに用語を説明する最小限のSGFを生成させる"""
        prompt = (
            f"囲碁の用語『{term_id}』の具体例を示す、最小限の手数のSGFデータを作成してください。\n"
            f"条件:\n"
            f"- 盤面サイズは 9x9 とすること。\n"
            f"- SGF形式のテキストのみを出力すること。"
        )
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[prompt]
            )
            text = response.text.strip()
            if "(" in text and ")" in text:
                return text[text.find("("):text.rfind(")")+1]
        except Exception as e:
            print(f"AI SGF Generation failed: {e}")
        return None

    def _render_from_sgf(self, term_id, sgf_content):
        """SGFから画像への変換（内部用）"""
        temp_game = GoGameState()
        try:
            temp_path = os.path.join(OUTPUT_BASE_DIR, f"temp_{term_id}.sgf")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(sgf_content)
            
            temp_game.load_sgf(temp_path)
            # BoardSimulatorを使用して一度コンテキストにする（論理の統一）
            from core.board_simulator import BoardSimulator
            simulator = BoardSimulator(temp_game.board_size)
            ctx = simulator.reconstruct_to_context(temp_game.get_history_up_to(temp_game.total_moves))
            
            return self.visualize_context(ctx, title=f"Example: {term_id}")
        except Exception as e:
            return None, str(e)