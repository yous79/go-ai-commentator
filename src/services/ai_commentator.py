from google import genai
from google.genai import types
import os
import json
import traceback
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME, load_api_key, TARGET_LEVEL
from core.knowledge_manager import KnowledgeManager
from services.analysis_orchestrator import AnalysisOrchestrator

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.orchestrator = AnalysisOrchestrator() # 解析指揮官を導入
        self.prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "templates"))

    def _load_prompt(self, name, **kwargs):
        """外部のテンプレートファイルを読み込んで引数を適用する"""
        filepath = os.path.join(self.prompt_dir, f"{name}.md")
        if not os.path.exists(filepath):
            return f"Error: Prompt template {name} not found."
        with open(filepath, "r", encoding="utf-8") as f:
            template = f.read()
            return template.format(**kwargs)

    def generate_commentary(self, move_idx, history, board_size=19):
        """【事実先行型】Orchestratorから得た構造化データに基づき、AIによる解説を生成する"""
        try:
            from utils.logger import logger
            logger.info(f"AI Commentary Generation Start (Move {move_idx})", layer="AI_COMMENTATOR")
            
            # 1. Orchestratorによる一括解析
            collector = self.orchestrator.analyze_full(history, board_size)
            ana_data = getattr(collector, 'raw_analysis', {})
            if not ana_data:
                return "【エラー】解析データの取得に失敗しました。"

            # 2. 事実のトリアージとサマリー作成
            prioritized_facts = collector.get_prioritized_text(limit=12)
            
            # 3. データの整理 (推奨手など)
            candidates = ana_data.get('top_candidates', []) or ana_data.get('candidates', [])
            best = candidates[0] if candidates else {}
            
            pv_list = best.get('pv', [])
            self.last_pv = pv_list
            player_color = "黒" if (move_idx % 2 == 0) else "白"
            opp_color = "白" if player_color == "黒" else "黒"
            colored_seq = [f"{i+1}: {player_color if i%2==0 else opp_color}{m}" for i, m in enumerate(pv_list)]
            
            fact_summary = (
                f"【最新の確定解析事実（トリアージ済）】\n"
                f"{prioritized_facts}\n\n"
                f"【AI推奨手と進行】\n"
                f"- 推奨手: {best.get('move', 'なし')}\n"
                f"- 推奨進行: {', '.join(colored_seq) if colored_seq else 'なし'}\n"
                f"- 推奨手の将来予測: {best.get('future_shape_analysis', '特になし')}\n"
            )
            print(f"DEBUG DATA READY: Winrate(B): {ana_data.get('winrate_black')}")

            # 4. プロンプトの構築
            kn = self.knowledge_manager.get_all_knowledge_text()
            
            persona_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Gemini_Persona.md"))
            persona_text = ""
            if os.path.exists(persona_path):
                try:
                    with open(persona_path, "r", encoding="utf-8") as f:
                        persona_text = f.read()
                except: pass

            system_template_name = "go_instructor_system"
            if TARGET_LEVEL == "beginner":
                system_template_name = "go_instructor_system_beginner"

            sys_inst = self._load_prompt(system_template_name, board_size=board_size, player=player_color, knowledge=kn)
            
            # 強力な制約の追加
            constraint = (
                "\n\n=== IMPORTANT CONSTRAINT ===\n"
                "You MUST NOT call any tools or functions. You already have all necessary analysis data.\n"
                "Your task is ONLY to provide a text commentary based on the facts provided above.\n"
                "Focus on reasoning and instruction, using the provided prioritized facts.\n"
            )
            if persona_text:
                sys_inst = f"{sys_inst}\n\n=== 執筆・解説ガイドライン ===\n{persona_text}{constraint}"
            else:
                sys_inst = f"{sys_inst}{constraint}"
            
            user_prompt = self._load_prompt("analysis_request", move_idx=move_idx, history=history)
            user_prompt = f"{fact_summary}\n{user_prompt}"

            # 5. 生成リクエスト
            safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
                'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
                'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT',
                'HARM_CATEGORY_CIVIC_INTEGRITY'
            ]]

            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[types.Content(role="user", parts=[types.Part(text=user_prompt)])],
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    safety_settings=safety
                )
            )

            # 堅牢なテキスト抽出
            final_text = ""
            if response.candidates and response.candidates[0].content.parts:
                final_text = "".join([p.text for p in response.candidates[0].content.parts if p.text])
            
            if not final_text:
                return f"【解析事実】\n{fact_summary}\n\n(AIがテキスト解説を生成できませんでした。)"

            # --- 品質ガード (数値情報の欠落チェック) ---
            has_wr = any(x in final_text for x in ["%", "％", "勝率", "リード"])
            if not has_wr:
                # 重要な数値が含まれていない場合は事実を添える
                return f"【解析事実】\n{fact_summary}\n\n---\n{final_text}"

            return final_text

        except Exception as e:
            traceback.print_exc()
            return f"SYSTEM ERROR: {str(e)}"

    def reset_chat(self):
        pass