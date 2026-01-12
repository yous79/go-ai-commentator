from google import genai
from google.genai import types
import os
import asyncio
import json
import traceback
import re
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from prompts.templates import get_unified_system_instruction, get_integrated_request_prompt

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self._knowledge_cache = None

    def _load_knowledge(self):
        if self._knowledge_cache: return self._knowledge_cache
        kn_text = "\n=== Go Knowledge Base ===\n"
        if os.path.exists(KNOWLEDGE_DIR):
            for category in sorted(os.listdir(KNOWLEDGE_DIR)):
                cat_path = os.path.join(KNOWLEDGE_DIR, category)
                if not os.path.isdir(cat_path): continue
                for term_dir in sorted(os.listdir(cat_path)):
                    term_path = os.path.join(cat_path, term_dir)
                    if not os.path.isdir(term_path): continue
                    kn_text += f"Term: {term_dir.replace('_', ' ').title()}:\n"
                    import glob
                    for f_name in glob.glob(os.path.join(term_path, "*.txt")):
                        try:
                            with open(f_name, "r", encoding="utf-8") as f:
                                kn_text += f"  - {f.read().strip()}\n"
                        except: pass
        self._knowledge_cache = kn_text
        return kn_text

    def generate_commentary(self, move_idx, history, board_size=19):
        kn = self._load_knowledge()
        player = "Black" if (move_idx % 2 == 0) else "White"
        sys_inst = get_unified_system_instruction(board_size, player, kn)
        user_prompt = get_integrated_request_prompt(move_idx, history)
        
        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
            'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
            'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT',
            'HARM_CATEGORY_CIVIC_INTEGRITY'
        ]]

        tools_config = [{
            "function_declarations": [
                {
                    "name": "katago_analyze",
                    "description": "Analyze board using KataGo.",
                    "parameters": {"type": "OBJECT", "properties": {"history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}}, "required": ["history"]}
                },
                {
                    "name": "detect_shapes",
                    "description": "Detect bad shapes geometrically.",
                    "parameters": {"type": "OBJECT", "properties": {"history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}}, "required": ["history"]}
                }
            ]
        }]

        try:
            print(f"--- AI COMMENTARY START (Move {move_idx}) ---")
            contents_history = [types.Content(role="user", parts=[types.Part(text=user_prompt)])]
            max_iters = 5
            final_text = ""

            for i in range(max_iters):
                print(f"DEBUG: Attempt {i+1}...")
                resp = self.client.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=contents_history,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_inst, tools=tools_config,
                        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='AUTO')),
                        safety_settings=safety
                    )
                )
                if not resp.candidates or not resp.candidates[0].content or not resp.candidates[0].content.parts:
                    break
                
                contents_history.append(resp.candidates[0].content)
                parts = resp.candidates[0].content.parts
                for p in parts:
                    if p.text: final_text += p.text
                
                fcs = [p.function_call for p in parts if p.function_call]
                if not fcs:
                    if final_text: break
                    continue

                tool_results = []
                for fc in fcs:
                    print(f"DEBUG: Executing tool '{fc.name}'...")
                    res_data_str = self._call_mcp_tool_sync(fc.name, fc.args)
                    
                    # 1. データをパースして「生オブジェクト」として渡す
                    try:
                        res_obj = json.loads(res_data_str)
                    except:
                        res_obj = {"error": res_data_str}

                    # 2. GUI用の最善手PVを保存
                    if fc.name == "katago_analyze" and isinstance(res_obj, dict):
                        if res_obj.get('top_candidates'):
                            self.last_pv = res_obj['top_candidates'][0]['future_sequence'].split(" -> ")

                    # 3. ツールレスポンスを生成 (オブジェクトを直接渡す)
                    tool_results.append(types.Part(
                        function_response=types.FunctionResponse(name=fc.name, response=res_obj)
                    ))

                # 履歴に結果を積み上げる
                contents_history.append(types.Content(role="tool", parts=tool_results))
                
                # 4. 追加のフィードバック（推論と事実の融合を促す）
                if i == 0: # 最初のツール呼び出し後
                    contents_history.append(types.Content(role="user", parts=[types.Part(
                        text="ありがとうございます。得られた数値データはすべて『黒番視点』（正の値は黒リード、勝率は黒の勝機）です。これを踏まえて、あなたのこれまでの洞察を事実で裏付け、洗練されたプロの解説として完成させてください。"
                    )]))

            # --- 品質ガード (全角・半角対応) ---
            has_winrate = any(x in final_text for x in ["%", "％", "勝率"])
            has_move = re.search(r"[A-T][0-9]{1,2}", final_text.upper()) is not None
            
            if not final_text or not has_winrate or not has_move:
                print(f"DEBUG GUARD FAILED: WR:{has_winrate} Move:{has_move}")
                return "【Error】AI failed to generate a valid commentary based on analysis data."
            
            return final_text
        except Exception as e:
            traceback.print_exc()
            return f"SYSTEM ERROR: {str(e)}"

    def _call_mcp_tool_sync(self, name, args):
        from mcp_server import handle_call_tool 
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mcp_res_list = loop.run_until_complete(handle_call_tool(name, args))
            loop.close()
            if mcp_res_list and hasattr(mcp_res_list[0], 'text'): return mcp_res_list[0].text
            return "Error: Invalid response"
        except Exception as e: return f"Error: {str(e)}"

    def reset_chat(self):
        pass
