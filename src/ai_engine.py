from google import genai
from google.genai import types
import os
import glob
from config import KNOWLEDGE_DIR
from katago_driver import KataGoDriver

class GeminiCommentator:
    def __init__(self, api_key, katago_driver: KataGoDriver):
        self.client = genai.Client(api_key=api_key)
        self.katago = katago_driver
        self.last_pv = None # Store the last PV for UI visualization

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
            
            # Capture PV for UI
            if 'top_candidates' in result and result['top_candidates']:
                pv_str = result['top_candidates'][0].get('future_sequence', "")
                if pv_str:
                    self.last_pv = [m.strip() for m in pv_str.split("->")]
                    print(f"DEBUG TOOL: Captured PV list: {self.last_pv}")
            
            return result
        except Exception as e:
            return {"error": str(e)}

    def generate_commentary(self, move_idx, history, board_size=19):
        self.last_pv = None
        kn = self._load_knowledge()
        player = "黒" if (move_idx % 2 == 0) else "白"
        
        sys_inst = (
            f"あなたはプロの囲碁インストラクターですが、現在「盤面が全く見えていない」状態です。"
            f"したがって、あなたの知識だけで局面を解説することは物理的に不可能です。"
            f"必ず 'consult_katago_tool' を呼び出して、勝率・目数差・変化図(PV)のデータを取得し、"
            f"そのデータのみを根拠にして解説を行ってください。ツールを呼ばずに回答することは禁止されています。"
            f"現在は{board_size}路盤。手番{player}。知識ベース: {kn}"
        )
        
        prompt = (
            f"分析依頼: 手数 {move_idx}手目。履歴 {history}。"
            f"現在、私には盤面が見えません。まずツールを呼び出して状況を確認してください。"
            f"その後、ツールの結果に基づいて解説してください。"
        )

        safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in ['HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT']]

        # --- Manual 3-Step Execution ---

        # Step 1: Force Tool Call
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
            system_instruction=sys_inst,
            safety_settings=safety
        )

        req_contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

        try:
            resp1 = self.client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=req_contents,
                config=config_force
            )
            
            part1 = resp1.candidates[0].content.parts[0]
            if not part1.function_call:
                return "エラー: ツール呼び出しに失敗しました。"

            # Step 2: Execute Tool
            fc = part1.function_call
            print(f"DEBUG: Executing tool {fc.name}")
            args = fc.args
            moves_arg = args.get('moves_list')
            tool_result = self.consult_katago_tool(moves_arg, board_size=board_size)

            # Check for analysis failure
            if tool_result.get("error"):
                return f"解析エラー: {tool_result['error']} (KataGoの起動または通信に失敗しました)"

            tool_response_part = types.Part(
                function_response=types.FunctionResponse(
                    name='consult_katago_tool',
                    response={'result': tool_result}
                )
            )

            req_contents.append(types.Content(role="model", parts=[part1]))
            req_contents.append(types.Content(role="user", parts=[tool_response_part]))

            # Step 3: Generate Explanation
            # Update system instruction to tell the model it now has the data
            sys_inst_talk = (
                f"あなたはプロの囲碁インストラクターです。現在は{board_size}路盤。手番{player}。知識ベース: {kn}\n"
                f"【状況】ツール解析により、正確な盤面データ（勝率・目数・PV）を取得済みです。\n"
                f"【指示】\n"
                f"1. 取得した解析データと知識ベースを根拠に、論理的に解説してください。\n"
                f"2. 知識ベースの用語（サカレ形など）については、現在の局面や変化図(PV)に「実際にその形が現れている場合」のみ言及してください。\n"
                f"3. 局面に関係のない用語を無理に持ち出すことは「厳禁」です。形が現れていない場合は、通常の筋や効率の観点から解説してください。\n"
                f"4. ユーザーの「盤面が見えない」という以前の発言は無視し、プロとして自信を持って回答してください。"
            )

            config_talk = types.GenerateContentConfig(
                system_instruction=sys_inst_talk,
                safety_settings=safety,
                tools=[], # Explicitly disable tools
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='NONE'))
            )

            import concurrent.futures
            
            def call_gemini_step3():
                return self.client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=req_contents,
                    config=config_talk
                )

            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(call_gemini_step3)
                    resp2 = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                return "エラー: 解説生成がタイムアウトしました（30秒）。"
            
            # DEBUG OUTPUT
            if resp2.candidates:
                cand = resp2.candidates[0]
                print(f"DEBUG Step 3 Finish Reason: {cand.finish_reason}")
                if cand.content and cand.content.parts:
                    print(f"DEBUG Step 3 Content: {cand.content.parts[0]}")
            else:
                print("DEBUG Step 3: No candidates returned.")

            return resp2.text if resp2.text else "解説生成エラー"

        except Exception as e:
            print(f"Gemini Error: {e}")
            return f"エラーが発生しました: {str(e)}"
            print(f"Gemini Error: {e}")
            return f"エラーが発生しました: {str(e)}"