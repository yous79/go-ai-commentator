from google import genai
from google.genai import types
import os
import glob
import concurrent.futures
from config import KNOWLEDGE_DIR
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

    def _load_knowledge(self):
        kn_text = ""
        if os.path.exists(KNOWLEDGE_DIR):
            subfolders = sorted(os.listdir(KNOWLEDGE_DIR))
            for subdir in subfolders:
                sub_path = os.path.join(KNOWLEDGE_DIR, subdir)
                if os.path.isdir(sub_path):
                    term = subdir.split("_")[-1]
                    kn_text += f"\n### 用語: {term}\n"
                    txt_files = glob.glob(os.path.join(sub_path, "*.txt"))
                    for f_name in txt_files:
                        try:
                            with open(f_name, "r", encoding="utf-8") as f:
                                kn_text += f"- {f.read().strip()}\n"
                        except:
                            pass
        return kn_text

    def consult_katago_tool(self, moves_list: list[list[str]], board_size=19):
        """wrapper for KataGo driver to be used as a tool result"""
        print(f"DEBUG TOOL: Consulting KataGo for {board_size}x{board_size} board...")
        try:
            result = self.katago.analyze_situation(moves_list, board_size=board_size)
            if 'top_candidates' in result and result['top_candidates']:
                pv_str = result['top_candidates'][0].get('future_sequence', "")
                if pv_str:
                    self.last_pv = [m.strip() for m in pv_str.split("->")]
            return result
        except Exception as e:
            return {"error": str(e)}

    def generate_commentary(self, move_idx, history, board_size=19):
        self.last_pv = None
        kn = self._load_knowledge()
        player = "黒" if (move_idx % 2 == 0) else "白" 
        
        display_history = history[-50:] if len(history) > 50 else history
        
        sys_inst_force = get_system_instruction_force_tool(board_size, player, kn)
        prompt = get_analysis_request_prompt(move_idx, display_history)

        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in ['HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT']]

        # Step 1: Force Tool Call (Manual Schema)
        tool_decl = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="consult_katago_tool",
                    description="Analyze the Go board situation using KataGo.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "moves_list": types.Schema(type="ARRAY", items=types.Schema(type="ARRAY", items=types.Schema(type="STRING")))
                        },
                        required=["moves_list"]
                    )
                )
            ]
        )

        config_force = types.GenerateContentConfig(
            tools=[tool_decl],
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY', allowed_function_names=['consult_katago_tool'])),
            system_instruction=sys_inst_force,
            safety_settings=safety
        )

        req_contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

        try:
            resp1 = self.client.models.generate_content(
                model='gemini-3-flash-preview', contents=req_contents, config=config_force
            )
            
            part1 = resp1.candidates[0].content.parts[0]
            if not part1.function_call:
                return "エラー: ツール呼び出しに失敗しました。"

            # Step 2: Execute Tool
            args = part1.function_call.args
            tool_result = self.consult_katago_tool(args.get('moves_list'), board_size=board_size)

            if tool_result.get("error"):
                return f"解析エラー: {tool_result['error']}"

            req_contents.append(types.Content(role="model", parts=[part1]))
            req_contents.append(types.Content(role="user", parts=[
                types.Part(function_response=types.FunctionResponse(name='consult_katago_tool', response={'result': tool_result}))
            ]))

            # Step 3: Explanation
            sys_inst_talk = get_system_instruction_explanation(board_size, player, kn)
            config_talk = types.GenerateContentConfig(
                system_instruction=sys_inst_talk,
                safety_settings=safety,
                tools=[], 
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='NONE'))
            )

            def call_gemini_step3():
                return self.client.models.generate_content(
                    model='gemini-3-flash-preview', contents=req_contents, config=config_talk
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(call_gemini_step3)
                resp2 = future.result(timeout=30)
            
            return resp2.text if resp2.text else "解説生成エラー"

        except concurrent.futures.TimeoutError:
            return "エラー: 解説生成がタイムアウトしました。"
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"