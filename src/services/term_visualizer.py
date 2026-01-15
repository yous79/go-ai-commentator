import os
import json
from core.game_state import GoGameState
from utils.board_renderer import GoBoardRenderer
from core.shape_detector import ShapeDetector
from config import KNOWLEDGE_DIR, OUTPUT_BASE_DIR, load_api_key, GEMINI_MODEL_NAME
from google import genai
from google.genai import types

class TermVisualizer:
    """用語から具体的な局面画像を生成するサービス"""

    def __init__(self):
        self.renderer = GoBoardRenderer(board_size=9, image_size=600)
        self.detector = ShapeDetector(board_size=9)
        self.api_key = load_api_key()
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def visualize(self, term_id, category="01_bad_shapes"):
        """用語IDから画像を生成し、保存先パスを返す"""
        term_dir = os.path.join(KNOWLEDGE_DIR, category, term_id)
        example_sgf = os.path.join(term_dir, "example.sgf")
        
        sgf_content = None
        # 1. テンプレートSGFがあるか確認
        if os.path.exists(example_sgf):
            with open(example_sgf, "r", encoding="utf-8") as f:
                sgf_content = f.read()
        
        # 2. なければAIに生成を依頼
        if not sgf_content and self.client:
            sgf_content = self._generate_sgf_via_ai(term_id)

        if not sgf_content:
            return None, "No example data or AI available."

        # 3. SGFから画像を生成
        return self._render_from_sgf(term_id, sgf_content)

    def _generate_sgf_via_ai(self, term_id):
        """Geminiに用語を説明する最小限のSGFを生成させる"""
        prompt = (
            f"囲碁の用語『{term_id}』の具体例を示す、最小限の手数のSGFデータを作成してください。\n"
            f"条件:\n"
            f"- 盤面サイズは 9x9 とすること。\n"
            f"- 余計な着手は含まず、その形状が完成した直後の状態で終わること。\n"
            f"- SGF形式のテキストのみを出力すること。"
        )
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME, # Gemini 3 Flash Preview を使用
                contents=[prompt]
            )
            text = response.text.strip()
            # SGFの括弧を抽出
            if "(" in text and ")" in text:
                return text[text.find("("):text.rfind(")")+1]
        except Exception as e:
            print(f"AI SGF Generation failed: {e}")
        return None

    def _render_from_sgf(self, term_id, sgf_content):
        """SGFをレンダリングし、論理チェックを行う"""
        temp_game = GoGameState()
        try:
            # 一時ファイルとして保存してロード
            temp_path = os.path.join(OUTPUT_BASE_DIR, f"temp_{term_id}.sgf")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.read() if False else f.write(sgf_content)
            
            temp_game.load_sgf(temp_path)
            last_move_idx = temp_game.total_moves
            board = temp_game.get_board_at(last_move_idx)
            prev_board = temp_game.get_board_at(last_move_idx - 1) if last_move_idx > 0 else None
            
            # 論理検証
            ids = self.detector.detect_ids(board, prev_board)
            if term_id not in ids and term_id != "unknown":
                print(f"Warning: Generated image for {term_id} might not contain the shape. Detected: {ids}")

            # レンダリング
            img = self.renderer.render(board, history=temp_game.get_history_up_to(last_move_idx), show_numbers=True)
            
            output_path = os.path.join(OUTPUT_BASE_DIR, f"term_{term_id}.png")
            img.save(output_path)
            return output_path, None
        except Exception as e:
            return None, str(e)
