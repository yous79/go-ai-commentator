from google import genai
from google.genai import types
import os
import json
import traceback
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME, load_api_key, TARGET_LEVEL
from core.knowledge_manager import KnowledgeManager
from services.analysis_orchestrator import AnalysisOrchestrator
from services.persona import PersonaFactory

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.orchestrator = AnalysisOrchestrator() # 解析指揮官を導入
        self.prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "templates"))

    def _load_prompt(self, name, **kwargs):
        """外部のテンプレートファイルを読み込んで引数を適用する（{}が含まれる文字列でも安全なように手動置換）"""
        filepath = os.path.join(self.prompt_dir, f"{name}.md")
        if not os.path.exists(filepath):
            return f"Error: Prompt template {name} not found."
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # str.format() は {} を解釈してしまうため、手動で置換
            for k, v in kwargs.items():
                content = content.replace("{" + k + "}", str(v))
            return content

    async def generate_commentary(self, move_idx, history, board_size=19, prev_analysis=None):
        """【事実先行型】Orchestratorから得た構造化データに基づき、AIによる解説を生成する (非同期版)"""
        try:
            from utils.logger import logger
            import asyncio
            logger.info(f"AI Commentary Generation Start (Move {move_idx})", layer="AI_COMMENTATOR")
            
            # 1. Orchestratorによる一括並列解析
            collector = await self.orchestrator.analyze_full(history, board_size, prev_analysis=prev_analysis)
            ana_result = getattr(collector, 'raw_analysis', None)
            if not ana_result:
                return {
                    "text": "【エラー】解析データの取得に失敗しました。",
                    "collector": None
                }

            # 2. 事実のトリアージと時間軸別サマリー作成
            from core.inference_fact import TemporalScope
            immediate_facts = collector.get_scope_summary(TemporalScope.IMMEDIATE)
            existing_facts = collector.get_prioritized_text(limit=8) # EXISTING事実
            predicted_facts = collector.get_scope_summary(TemporalScope.PREDICTED)
            
            # 3. データの整理 (推奨手など)
            best = ana_result.candidates[0] if ana_result.candidates else None
            
            pv_list = best.pv if best else []
            self.last_pv = pv_list
            player_color = "黒" if (move_idx % 2 == 0) else "白"
            opp_color = "白" if player_color == "黒" else "黒"
            colored_seq = [f"{i+1}: {player_color if i%2==0 else opp_color}{m}" for i, m in enumerate(pv_list)]
            
            fact_summary = (
                f"【最新手 Evaluation (Immediate)】\n"
                f"{immediate_facts or '(特筆すべき変化なし)'}\n\n"
                f"【局面の現状 Review (Existing)】\n"
                f"{existing_facts}\n\n"
                f"【将来の予測 Prediction (Predicted)】\n"
                f"{predicted_facts or '(特筆すべき予測なし)'}\n\n"
                f"【AI推奨手と進行】\n"
                f"- 推奨手: {best.move if best else 'なし'}\n"
                f"- 推奨進行: {', '.join(colored_seq) if colored_seq else 'なし'}\n"
            )
            logger.debug(f"Analysis Data Ready: Winrate: {ana_result.winrate_label}", layer="AI")

            # 4. プロンプトの構築 (Prompt Offloading対応)
            # 詳細な定義は MCP リソース mcp://prompts/system/instructor-guidelines に移譲
            sys_inst = (
                "あなたはプロの囲碁インストラクターです。\n"
                "以下のリソースからあなたの『基本哲学』『指導方針』『人格定義』を読み取り、それに完全に従ってください。\n"
                "- mcp://prompts/system/instructor-guidelines\n\n"
                "また、局面に現れている具体的な悪形や手筋の定義については、以下のリソースも参照してください。\n"
                "- mcp://game/current/relevant-knowledge\n\n"
                "=== IMPORTANT CONSTRAINT ===\n"
                "You MUST NOT call any tools or functions. You already have all necessary analysis data.\n"
                "Your task is ONLY to provide a text commentary based on the facts provided above.\n"
                "Focus on reasoning and instruction, using the provided prioritized facts.\n"
                "IMPORTANT: The analysis provided is from the perspective of {next_player}. Talk to {next_player} about {last_player}'s move.\n"
            )
            
            # 手番（プレイヤー色）の明確化
            # history[-1] は直前に打たれた手。move_idx は次の手番の手数（例：1手目黒、その直後のmove_idx=1の局面で、次は白番）
            # よって、直前の手番(last_player)は move_idxが奇数なら黒、偶数なら白。
            # 例: move_idx=1 (1手目黒が打たれた直後) -> last=黒, next=白
            last_c_jp = "黒" if (move_idx % 2 != 0) else "白"
            next_c_jp = "白" if last_c_jp == "黒" else "黒"
            
            user_prompt = self._load_prompt("analysis_request", move_idx=move_idx, history=history, last_player=last_c_jp, next_player=next_c_jp)
            user_prompt = f"【最新の解析事実】\n{fact_summary}\n\n{user_prompt}"

            # 5. 生成リクエスト (Gemini API)
            safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
                'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
                'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT',
                'HARM_CATEGORY_CIVIC_INTEGRITY'
            ]]

            async def _call_gemini_async(sys, usr):
                # システムプロンプト内の変数も置換
                final_sys = sys.replace("{last_player}", last_c_jp).replace("{next_player}", next_c_jp)
                return await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=GEMINI_MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=final_sys, safety_settings=safety),
                    contents=[types.Content(role="user", parts=[types.Part(text=usr)])]
                )

            # 初回生成
            logger.debug("Calling Gemini for initial commentary...", layer="AI")
            response = await _call_gemini_async(sys_inst, user_prompt)
            final_text = ""
            if response.candidates and response.candidates[0].content.parts:
                final_text = "".join([p.text for p in response.candidates[0].content.parts if p.text])
            
            if not final_text:
                logger.error("Empty response from Gemini", layer="AI")
                return {
                    "text": f"【解析事実】\n{fact_summary}\n\n(AIがテキスト解説を生成できませんでした。)",
                    "collector": collector
                }

            # --- 高速化・品質保証ロジック ---
            
            # 1. 自己診断タグの解析とリトライ
            if "[自己診断: 再考が必要" in final_text:
                logger.warning("AI detected its own mistake via Self-Diagnosis. Retrying...", layer="AI")
                diag_reason = final_text.split("[自己診断: 再考が必要")[-1].split("]")[0].strip("（）")
                retry_prompt = f"{user_prompt}\n\n=== AI自己診断による再生成の指示 ===\n自身の内部チェックで以下の懸念が発見されました：\n{diag_reason}\n\nこれを修正して解説を再生成してください。"
                
                logger.info("Calling Gemini for RE-GENERATION (Self-Correction Retry)...", layer="AI")
                retry_res = await _call_gemini_async(sys_inst, retry_prompt)
                if retry_res.candidates and retry_res.candidates[0].content.parts:
                    final_text = "".join([p.text for p in retry_res.candidates[0].content.parts if p.text])
                    logger.info("AI Commentary Corrected (Self-Check).", layer="AI")

            # --- 最終クリーンアップ処理 ---

            # ユーザーに見せる前に診断タグ（および区切り線）を削除
            if "---" in final_text and "[自己診断:" in final_text:
                final_text = final_text.split("---")[0].strip()
            
            # --- 品質ガード (数値情報の欠落チェック) ---
            # 解説に勝率などの具体的数値が全く含まれていない場合、念のためFactsを添える
            has_wr = any(x in final_text for x in ["%", "％", "勝率", "リード", "目"])
            if not has_wr:
                return {
                    "text": f"【解析事実】\n{fact_summary}\n\n---\n{final_text}",
                    "collector": collector
                }

            return {
                "text": final_text,
                "collector": collector
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "text": f"SYSTEM ERROR: {str(e)}",
                "collector": None
            }

    def reset_chat(self):
        pass