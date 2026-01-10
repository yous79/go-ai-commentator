from google import genai
from google.genai import types
import os
import glob
import concurrent.futures
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from drivers.katago_driver import KataGoDriver
from prompts.templates import (
    get_system_instruction_force_tool,
    get_analysis_request_prompt,
    get_system_instruction_explanation
)

class GeminiCommentator:
    def __init__(self, api_key, katago_driver: KataGoDriver):
        self.client = genai.Client(api_key=api_key)
        self.katago = katago_driver
        self.last_pv = None 
        self._knowledge_cache = None

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

    def generate_commentary(self, move_idx, history, board_size=19):
        self.last_pv = None
        kn = self._load_knowledge()
        player = "黒" if (move_idx % 2 == 0) else "白" 
        display_history = history[-50:] if len(history) > 50 else history
        
        sys_inst_force = get_system_instruction_force_tool(board_size, player, kn)
        prompt = get_analysis_request_prompt(move_idx, display_history)
        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in ['HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT']]

        tool_decl = types.Tool(function_declarations=[types.FunctionDeclaration(
            name="consult_katago_tool",
            description="Analyze the Go board using KataGo.",
            parameters=types.Schema(type="OBJECT", properties={
                "moves_list": types.Schema(type="ARRAY", items=types.Schema(type="ARRAY", items=types.Schema(type="STRING")))
            }, required=["moves_list"])
        )])

        try:
            # --- Step 1: Force Tool ---
            resp1 = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    tools=[tool_decl],
                    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY')),
                    system_instruction=sys_inst_force,
                    safety_settings=safety
                )
            )
            
            parts = resp1.candidates[0].content.parts
            found_fc = next((p.function_call for p in parts if p.function_call), None)
            if not found_fc or any(p.text and p.text.strip() for p in parts):
                return "ERROR: AIが解析をサボり独断で回答しようとしたためブロックしました。"

            # --- Step 2: KataGo Execution (FORCED HISTORY) ---
            print(f"DEBUG: Gemini requested tool. Forcing verified history (length={{len(history)}}).")
            tool_result = self.katago.analyze_situation(history, board_size=board_size, priority=True)

            if "error" in tool_result:
                return f"ERROR: KataGo解析失敗 ({tool_result['error']})"

            # --- Step 3: Commentary ---
            best = tool_result['top_candidates'][0]
            pv_str = best['future_sequence']
            self.last_pv = pv_str.split(" -> ")

            final_prompt = (
                f"【最新事実データ】\n- 黒勝率: {tool_result['winrate']:.1%}\n- 目数差: {tool_result['score']:.1f}目\n"
                f"- AI推奨手: {best['move']}\n- 推奨進行: {pv_str}\n\n"
                f"あなたは上記データのみを根拠に語る読み上げ機です。独自の推測は1文字も許されません。"
            )

            sys_inst_talk = get_system_instruction_explanation(board_size, player, kn)
            config_talk = types.GenerateContentConfig(system_instruction=sys_inst_talk, safety_settings=safety)

            def call_gen():
                return self.client.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=[types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                    config=config_talk
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                resp2 = executor.submit(call_gen).result(timeout=30)
            
            final_text = resp2.text if resp2.text else ""
            
            # FINAL HARD GUARD
            if best['move'].upper() not in final_text.upper():
                return f"ERROR: AIがデータを無視したため表示をブロックしました。(推奨手: {best['move']})"

            return final_text

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"ERROR: システム例外 ({str(e)})"