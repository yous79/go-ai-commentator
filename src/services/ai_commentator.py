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

    async def generate_commentary(self, move_idx, history, board_size=19):
        """【事実先行型】Orchestratorから得た構造化データに基づき、AIによる解説を生成する (非同期版)"""
        try:
            from utils.logger import logger
            import asyncio
            logger.info(f"AI Commentary Generation Start (Move {move_idx})", layer="AI_COMMENTATOR")
            
            # 1. Orchestratorによる一括並列解析
            collector = await self.orchestrator.analyze_full(history, board_size)
            ana_result = getattr(collector, 'raw_analysis', None)
            if not ana_result:
                return "【エラー】解析データの取得に失敗しました。"

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
            )
            
            user_prompt = self._load_prompt("analysis_request", move_idx=move_idx, history=history)
            user_prompt = f"【最新の解析事実】\n{fact_summary}\n\n{user_prompt}"

            # 5. 生成リクエスト (Gemini API)
            safety = [types.SafetySetting(category=c, threshold='BLOCK_NONE') for c in [
                'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_HARASSMENT', 
                'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT',
                'HARM_CATEGORY_CIVIC_INTEGRITY'
            ]]

            async def _call_gemini_async(sys, usr):
                return await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=GEMINI_MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=sys, safety_settings=safety),
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
                return f"【解析事実】\n{fact_summary}\n\n(AIがテキスト解説を生成できませんでした。)"

            # --- 高速化・品質保証ロジック (案1 & 案2) ---
            
            # 1. 検証が必要な重要局面か判定 (案1)
            from core.inference_fact import FactCategory
            needs_strict_check = False
            for f in collector.facts:
                # 失着、急場、または重要度4以上の事実がある場合は厳格チェック対象
                if (f.category == FactCategory.MISTAKE and f.severity >= 4) or \
                   (f.category == FactCategory.URGENCY and f.severity >= 5) or \
                   (f.severity >= 5):
                    needs_strict_check = True
                    break
            
            # 2. 自己診断タグの解析とリトライ (案2)
            if "[自己診断: 再考が必要" in final_text:
                logger.warning("AI detected its own mistake via Self-Diagnosis. Retrying...", layer="AI")
                diag_reason = final_text.split("[自己診断: 再考が必要")[-1].split("]")[0].strip("（）")
                retry_prompt = f"{user_prompt}\n\n=== AI自己診断による再生成の指示 ===\n自身の内部チェックで以下の懸念が発見されました：\n{diag_reason}\n\nこれを修正して解説を再生成してください。"
                
                logger.info("Calling Gemini for RE-GENERATION (Self-Correction Retry)...", layer="AI")
                retry_res = await _call_gemini_async(sys_inst, retry_prompt)
                if retry_res.candidates and retry_res.candidates[0].content.parts:
                    final_text = "".join([p.text for p in retry_res.candidates[0].content.parts if p.text])
                    logger.info("AI Commentary Corrected (Self-Check).", layer="AI")
                # リトライした場合は、念のため外部検証も行う（論理が複雑な可能性が高いため）
                needs_strict_check = True

            # 3. 外部検証（Double Check）の実行判定
            if needs_strict_check:
                # --- Self-Correction (Double Check) ---
                try:
                    logger.debug("Starting External Self-Correction (Double Check)...", layer="AI")
                    verify_prompt = self._load_prompt("commentary_verification", facts=fact_summary, generated_text=final_text)
                    
                    logger.debug("Calling Gemini for verification...", layer="AI")
                    check_res = await _call_gemini_async("You are a strict logic checker.", verify_prompt)
                    
                    if not check_res.candidates or not check_res.candidates[0].content.parts:
                        logger.debug("Verification response was empty, skipping self-correction.", layer="AI")
                    else:
                        check_text = check_res.candidates[0].content.parts[0].text.strip()
                        if check_text.startswith("NG"):
                            logger.warning(f"AI Logic Error Detected: {check_text}", layer="AI")
                            # 指摘事項を含めてリトライ
                            retry_prompt = f"{user_prompt}\n\n=== 前回の生成に対する修正指示 ===\nあなたの前回の回答には以下の論理矛盾がありました：\n{check_text}\n\nこの指摘を修正し、正しい解説を再生成してください。"
                            
                            logger.info("Calling Gemini for RE-GENERATION (Retry)...", layer="AI")
                            retry_res = await _call_gemini_async(sys_inst, retry_prompt)
                            if retry_res.candidates and retry_res.candidates[0].content.parts:
                                final_text = "".join([p.text for p in retry_res.candidates[0].content.parts if p.text])
                                logger.info("AI Commentary Corrected and Regenerated.", layer="AI")
                        else:
                            logger.debug(f"Verification Result: {check_text[:100]}...", layer="AI")
                except Exception as e:
                    logger.debug(f"Verification Process Error (Ignored): {e}", layer="AI")
                    pass
            else:
                logger.info("Skipping external verification for routine scenario.", layer="AI")

            # --- 最終クリーンアップ処理 ---

            # ユーザーに見せる前に診断タグ（および区切り線）を削除
            if "---" in final_text and "[自己診断:" in final_text:
                final_text = final_text.split("---")[0].strip()
            
            # --- 品質ガード (数値情報の欠落チェック) ---
            # 解説に勝率などの具体的数値が全く含まれていない場合、念のためFactsを添える
            has_wr = any(x in final_text for x in ["%", "％", "勝率", "リード", "目"])
            if not has_wr:
                return f"【解析事実】\n{fact_summary}\n\n---\n{final_text}"

            return final_text

        except Exception as e:
            traceback.print_exc()
            return f"SYSTEM ERROR: {str(e)}"

    def reset_chat(self):
        pass