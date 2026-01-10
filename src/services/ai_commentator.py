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
from sgfmill import boards

class GeminiCommentator:
    def __init__(self, api_key, katago_driver: KataGoDriver):
        self.client = genai.Client(api_key=api_key)
        self.katago = katago_driver
        self.detector = ShapeDetector()
        self.last_pv = None 
        self._knowledge_cache = None
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

    def _reconstruct_board(self, history, board_size):
        """着手履歴から盤面オブジェクト（最新と1手前）を復元する"""
        b_curr = boards.Board(board_size)
        b_prev = boards.Board(board_size)
        cols = "ABCDEFGHJKLMNOPQRST"
        
        for i, (c_str, m_str) in enumerate(history):
            if not m_str or m_str.lower() == "pass":
                if i < len(history) - 1:
                    pass # skip prev update
                continue
            try:
                col = cols.index(m_str[0].upper())
                row = int(m_str[1:]) - 1
                if i < len(history) - 1:
                    b_prev.play(row, col, c_str.lower())
                b_curr.play(row, col, c_str.lower())
            except: pass
        
        last_color = history[-1][0].lower() if history else None
        return b_curr, b_prev, last_color

    def _analyze_pv_shapes(self, base_board, pv_list, start_color, board_size):
        """変化図（PV）をシミュレーションし、発生する形状を検知する"""
        if not base_board or not pv_list:
            return ""
        
        sim_board = base_board.copy()
        prev_board = base_board.copy()
        current_color = start_color.lower()
        
        all_facts = []
        cols = "ABCDEFGHJKLMNOPQRST"

        for move_str in pv_list:
            if not move_str or move_str.lower() == "pass":
                current_color = 'w' if current_color == 'b' else 'b'
                continue
            try:
                c_idx = cols.index(move_str[0].upper())
                r_idx = int(move_str[1:]) - 1
                sim_board.play(r_idx, c_idx, current_color)
                facts = self.detector.detect_all(sim_board, prev_board, current_color)
                if facts:
                    all_facts.append(f"  [進行中 {move_str}]:\n{facts}")
                prev_board = sim_board.copy()
                current_color = 'w' if current_color == 'b' else 'b'
            except: break
        
        return "\n".join(all_facts) if all_facts else "特になし"

    def consult_katago_tool(self, history, board_size=19):
        """Geminiが呼び出すツール本体"""
        print(f"DEBUG: Tool called by Gemini. Analyzing history of length {len(history)}.")
        res = self.katago.analyze_situation(history, board_size=board_size, priority=True)
        if "error" in res: return {"error": res["error"]}
        
        if res['top_candidates']:
            self.last_pv = res['top_candidates'][0]['future_sequence'].split(" -> ")

        curr_b, _, _ = self._reconstruct_board(history, board_size)
        player_color = "B" if len(history) % 2 == 0 else "W"
        
        candidates_data = []
        for c in res['top_candidates']:
            pv_str = c.get('future_sequence', "")
            pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
            future_facts = self._analyze_pv_shapes(curr_b, pv_list, player_color, board_size)
            candidates_data.append({
                "move": c['move'],
                "winrate_black": f"{c['winrate']:.1%}",
                "score_lead_black": f"{c['score']:.1f}",
                "future_sequence": pv_str,
                "future_shape_analysis": future_facts
            })
        return {
            "winrate_black": f"{res['winrate']:.1%}",
            "score_lead_black": f"{res['score']:.1f}",
            "top_candidates": candidates_data
        }

    def generate_commentary(self, move_idx, history, board_size=19):
        """統合知能モードによる解説生成"""
        self.last_pv = None
        kn = self._load_knowledge()
        player = "黒" if (move_idx % 2 == 0) else "白" 
        
        curr_b, prev_b, last_c = self._reconstruct_board(history, board_size)
        self.detector.board_size = board_size
        shape_facts = self.detector.detect_all(curr_b, prev_b, last_c)
        
        if shape_facts:
            shape_facts = f"\n【重要：現時点の盤面から検知された事実】\n{shape_facts}\n"

        sys_inst = get_unified_system_instruction(board_size, player, kn)
        user_prompt = get_integrated_request_prompt(move_idx, history)
        full_user_prompt = shape_facts + user_prompt
        
        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
            'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
            'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT'
        ]]

        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(
                name="consult_katago_tool",
                description="KataGoを使用して現在の盤面を解析し、将来の変化図における形状変化も予測します。",
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
            def consult_katago_wrapper(moves_list):
                return self.consult_katago_tool(moves_list, board_size)

            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[types.Content(role="user", parts=[types.Part(text=full_user_prompt)])],
                config=config
            )

            max_iterations = 5
            for _ in range(max_iterations):
                if not response.candidates or not response.candidates[0].content.parts: break
                found_fc = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
                if not found_fc: break
                
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
                else: break

            return response.text if response.text else "解析データに基づいた回答が得られませんでした。"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"ERROR: 統合知能モード例外 ({str(e)})"

    def reset_chat(self):
        self.chat_history = []
