from google import genai
from google.genai import types
import os
import asyncio
import json
import traceback
import re
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from core.knowledge_manager import KnowledgeManager
from prompts.templates import get_unified_system_instruction, get_integrated_request_prompt

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)

    def generate_commentary(self, move_idx, history, board_size=19):
        # 知識ベースの全量取得 (将来的には検知結果に応じたフィルタリングも可能)
        kn = self.knowledge_manager.get_all_knowledge_text()
        
        player = "黒" if (move_idx % 2 == 0) else "白"
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
                    "description": "KataGoで盤面を解析します。",
                    "parameters": {"type": "OBJECT", "properties": {"history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}}, "required": ["history"]}
                },
                {
                    "name": "detect_shapes",
                    "description": "盤面の悪形を検出します。",
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
                    
                    try:
                        res_obj = json.loads(res_data_str)
                    except:
                        res_obj = {"error": res_data_str}

                    if fc.name == "katago_analyze" and isinstance(res_obj, dict):
                        if res_obj.get('top_candidates'):
                            self.last_pv = res_obj['top_candidates'][0]['future_sequence'].split(" -> ")

                    tool_results.append(types.Part(
                        function_response=types.FunctionResponse(name=fc.name, response=res_obj)
                    ))

                contents_history.append(types.Content(role="tool", parts=tool_results))
                
                if i == 0: 
                    contents_history.append(types.Content(role="user", parts=[types.Part(
                        text="ありがとうございます。あなたのこれまでの洞察を、たった今得られたKataGoの正確なデータで裏付け、より洗練されたプロの解説として完成させてください。"
                    )]))

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