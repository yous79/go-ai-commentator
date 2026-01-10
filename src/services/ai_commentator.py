from google import genai
from google.genai import types
import os
import concurrent.futures
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from drivers.katago_driver import KataGoDriver
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
from prompts.templates import (
    get_unified_system_instruction,
    get_integrated_request_prompt
)

class GeminiCommentator:
    def __init__(self, api_key, katago_driver: KataGoDriver):
        self.client = genai.Client(api_key=api_key)
        self.katago = katago_driver
        self.detector = ShapeDetector()
        self.simulator = BoardSimulator()
        self.last_pv = None 
        self._knowledge_cache = None
        self.chat_history = []

    def _load_knowledge(self):
        if self._knowledge_cache: return self._knowledge_cache
        kn_text = "\n=== 【公式例題】座標は無視せよ ===\n"
        if os.path.exists(KNOWLEDGE_DIR):
            import glob
            for subdir in sorted(os.listdir(KNOWLEDGE_DIR)):
                sub_path = os.path.join(KNOWLEDGE_DIR, subdir)
                if os.path.isdir(sub_path):
                    term = subdir.split("_")[-1]
                    kn_text += f"\n◆ 用語: {term}\n"
                    for f_name in glob.glob(os.path.join(sub_path, "*.txt")):
                        try:
                            with open(f_name, "r", encoding="utf-8") as f:
                                kn_text += f"  - [例]: {f.read().strip()}\n"
                        except: pass
        self._knowledge_cache = kn_text
        return kn_text

    def _analyze_pv_shapes(self, base_board, pv_list, start_color):
        """Simulatorを使用してPVの変化を検知"""
        all_facts = []
        # ジェネレーターから盤面状態を順次受け取る
        for move_str, sim_board, prev_board, current_color in self.simulator.simulate_pv(base_board, pv_list, start_color):
            if not prev_board: continue # パス等
            
            # ここで検知 (ShapeDetectorはステートレス)
            facts = self.detector.detect_all(sim_board, prev_board, current_color)
            if facts:
                all_facts.append(f"  [進行中 {move_str}]:\n{facts}")
        
        return "\n".join(all_facts) if all_facts else "特になし"

    def consult_katago_tool(self, history, board_size=19):
        """Geminiが呼び出すツール本体"""
        print(f"DEBUG: Tool called by Gemini. Analyzing history of length {len(history)}.")
        res = self.katago.analyze_situation(history, board_size=board_size, priority=True)
        if "error" in res: return {"error": res["error"]}
        
        if res['top_candidates']:
            self.last_pv = res['top_candidates'][0]['future_sequence'].split(" -> ")

        # 現在の盤面を復元 (Simulator使用)
        self.simulator.board_size = board_size
        self.detector.board_size = board_size
        curr_b, _, _ = self.simulator.reconstruct(history)
        player_color = "B" if len(history) % 2 == 0 else "W"
        
        candidates_data = []
        for c in res['top_candidates']:
            pv_str = c.get('future_sequence', "")
            pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
            # 将来予測
            future_facts = self._analyze_pv_shapes(curr_b, pv_list, player_color)
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
        
        # 現在の盤面検知 (Simulator使用)
        self.simulator.board_size = board_size
        self.detector.board_size = board_size
        curr_b, prev_b, last_c = self.simulator.reconstruct(history)
        
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