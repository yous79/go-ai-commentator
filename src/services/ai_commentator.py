from google import genai
from google.genai import types
import os
import asyncio
import threading
import json
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from prompts.templates import get_unified_system_instruction, get_integrated_request_prompt

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self._knowledge_cache = None
        self.mcp_config = {
            "katago": {
                "command": "python",
                "args": [os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_server.py")]
            }
        }

    def _load_knowledge(self):
        if self._knowledge_cache: return self._knowledge_cache
        kn_text = "\n=== 囲碁知識ベース (用語辞書) ===\n"
        if os.path.exists(KNOWLEDGE_DIR):
            for category in sorted(os.listdir(KNOWLEDGE_DIR)):
                cat_path = os.path.join(KNOWLEDGE_DIR, category)
                if not os.path.isdir(cat_path): continue
                cat_label = "【重要：悪形・失着】" if "bad_shapes" in category else "【一般手筋・概念】"
                kn_text += f"\n{cat_label}\n"
                for term_dir in sorted(os.listdir(cat_path)):
                    term_path = os.path.join(cat_path, term_dir)
                    if not os.path.isdir(term_path): continue
                    kn_text += f"◆ {term_dir.replace('_', ' ').title()}:\n"
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
        player = "黒" if (move_idx % 2 == 0) else "白"
        sys_inst = get_unified_system_instruction(board_size, player, kn)
        user_prompt = get_integrated_request_prompt(move_idx, history)
        
        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
            'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
            'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT'
        ]]

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    tools=[
                        {
                            "function_declarations": [
                                {
                                    "name": "katago_analyze",
                                    "description": "KataGoで盤面を解析します。",
                                    "parameters": {"type": "OBJECT", "properties": {"history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}}, "required": ["history"]}
                                },
                                {
                                    "name": "detect_shapes",
                                    "description": "悪形や手筋を検出します。",
                                    "parameters": {"type": "OBJECT", "properties": {"history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}}, "required": ["history"]}
                                }
                            ]
                        }
                    ],
                    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='AUTO')),
                    safety_settings=safety
                )
            )

            final_response = self._process_mcp_requests(response, history, board_size, sys_inst, safety)
            
            return final_response.text if final_response.text else "解析に失敗しました。"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"ERROR: MCP連携モード例外 ({str(e)})\n"

    def _process_mcp_requests(self, response, history, board_size, sys_inst, safety):
        from mcp_server import handle_call_tool 
        
        max_iters = 5
        current_resp = response
        
        for _ in range(max_iters):
            if not current_resp.candidates or not current_resp.candidates[0].content.parts:
                break
            
            fc = next((p.function_call for p in current_resp.candidates[0].content.parts if p.function_call), None)
            if not fc: break
            
            print(f"DEBUG: Relaying to MCP tool: {fc.name}")
            args = fc.args
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            mcp_res_list = loop.run_until_complete(handle_call_tool(fc.name, args))
            loop.close()
            
            result_data = mcp_res_list[0].text if mcp_res_list else "Error"
            
            if fc.name == "katago_analyze":
                try:
                    data = json.loads(result_data)
                    if data.get('top_candidates'):
                        self.last_pv = data['top_candidates'][0]['future_sequence'].split(" -> ")
                except: pass

            next_prompt = get_integrated_request_prompt(len(history), history)
            
            current_resp = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=next_prompt)]),
                    current_resp.candidates[0].content,
                    types.Content(role="tool", parts=[types.Part(
                        function_response=types.FunctionResponse(name=fc.name, response={"result": result_data})
                    )])
                ],
                config=types.GenerateContentConfig(system_instruction=sys_inst, safety_settings=safety)
            )
            
        return current_resp