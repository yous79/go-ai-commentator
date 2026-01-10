from google import genai
from google.genai import types
import os
import glob
import concurrent.futures
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from drivers.katago_driver import KataGoDriver
from core.shape_detector import ShapeDetector
from prompts.templates import (
    get_unified_system_instruction,
    get_integrated_request_prompt
)

class GeminiCommentator:
    def __init__(self, api_key, katago_driver: KataGoDriver):
        self.client = genai.Client(api_key=api_key)
        self.katago = katago_driver
        self.detector = ShapeDetector()
        self.last_pv = None 
        self._knowledge_cache = None
        # チャットセッションを保持するための履歴
        self.chat_history = []

    def _load_knowledge(self):
        if self._knowledge_cache:
            return self._knowledge_cache

        kn_text = "\n=== 【公式例題】座標は無視せよ ===\n"
        if os.path.exists(KNOWLEDGE_DIR):
            subfolders = sorted(os.listdir(KNOWLEDGE_DIR))
            for subdir in subfolders: 
                sub_path = os.path.join(KNOWLEDGE_DIR, subdir)
                if os.path.isdir(sub_path):
                    term = subdir.split("_")[-1]
                    kn_text += f"\n◆ 用語: {term}\n"
                    txt_files = glob.glob(os.path.join(sub_path, "*.txt"))
                    for f_name in txt_files:
                        try:
                            with open(f_name, "r", encoding="utf-8") as f:
                                kn_text += f"  - [例]: {f.read().strip()}\n"
                        except: pass
        
        self._knowledge_cache = kn_text
        return kn_text

    def consult_katago_tool(self, history, board_size=19):
        """Geminiが呼び出すツール本体"""
        print(f"DEBUG: Tool called by Gemini. Analyzing move history of length {len(history)}.")
        res = self.katago.analyze_situation(history, board_size=board_size, priority=True)
        
        if "error" in res:
            return {"error": res["error"]}
        
        if res['top_candidates']:
            self.last_pv = res['top_candidates'][0]['future_sequence'].split(" -> ")

        return {
            "winrate_black": f"{res['winrate']:.1%}",
            "score_lead_black": f"{res['score']:.1f}",
            "top_candidates": [
                {
                    "move": c['move'],
                    "winrate_black": f"{c['winrate']:.1%}",
                    "score_lead_black": f"{c['score']:.1f}",
                    "future_sequence": c['future_sequence']
                } for c in res['top_candidates']
            ]
        }

    def generate_commentary(self, move_idx, history, board_size=19):
        """統合知能モードによる解説生成"""
        self.last_pv = None
        kn = self._load_knowledge()
        player = "黒" if (move_idx % 2 == 0) else "白" 
        
        # 幾何学的検知の実行 (事実データの作成)
        board = getattr(self.katago, 'last_board', None)
        prev_board = getattr(self.katago, 'prev_board', None)
        last_color = getattr(self.katago, 'last_move_color', None)
        
        shape_facts = ""
        if board:
            self.detector.board_size = board_size
            shape_facts = self.detector.detect_all(board, prev_board, last_color)
            if shape_facts:
                shape_facts = f"\n【重要：盤面から検知された事実データ】\n{shape_facts}\n"
                print(f"DEBUG: Shape facts detected:\n{shape_facts}")

        sys_inst = get_unified_system_instruction(board_size, player, kn)
        user_prompt = get_integrated_request_prompt(move_idx, history)
        
        # 事実データをプロンプトの先頭に注入
        full_user_prompt = shape_facts + user_prompt
        
        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
            'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
            'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT'
        ]]

        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(
                name="consult_katago_tool",
                description="KataGoを使用して現在の盤面を詳細に解析します。",
                parameters=types.Schema(type="OBJECT", properties={
                    "moves_list": types.Schema(
                        type="ARRAY", 
                        items=types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        description="対局の着手履歴 [[カラー, 座標], ...]"
                    )
                }, required=["moves_list"])
            )])],
            safety_settings=safety
        )

        try:
            # ツール実行用ラッパー
            def consult_katago_wrapper(moves_list):
                return self.consult_katago_tool(moves_list, board_size)

            # 初回の生成リクエスト
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[types.Content(role="user", parts=[types.Part(text=full_user_prompt)])],
                config=config
            )

            # Function Call のループ処理
            max_iterations = 5
            for _ in range(max_iterations):
                if not response.candidates or not response.candidates[0].content.parts:
                    break
                
                found_fc = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
                if not found_fc:
                    break
                
                print(f"DEBUG: Processing Function Call: {found_fc.name}")
                if found_fc.name == "consult_katago_tool":
                    args = found_fc.args
                    moves = args.get("moves_list", [])
                    result = consult_katago_wrapper(moves)
                    
                    response = self.client.models.generate_content(
                        model=GEMINI_MODEL_NAME,
                        contents=[
                            types.Content(role="user", parts=[types.Part(text=full_user_prompt)]),
                            response.candidates[0].content,
                            types.Content(role="tool", parts=[types.Part(
                                function_response=types.FunctionResponse(name="consult_katago_tool", response=result)
                            )])
                        ],
                        config=config
                    )
                else:
                    break

            final_text = response.text if response.text else "解析データに基づいた回答が得られませんでした。"
            return final_text

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"ERROR: 統合知能モード例外 ({str(e)})"

    def reset_chat(self):
        self.chat_history = []