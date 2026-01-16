from google import genai
from google.genai import types
import os
import json
import traceback
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME, load_api_key
from core.knowledge_manager import KnowledgeManager
from core.stability_analyzer import StabilityAnalyzer
from core.board_simulator import BoardSimulator, SimulationContext
from services.api_client import api_client

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.stability_analyzer = StabilityAnalyzer()
        self.simulator = BoardSimulator()
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
        """【事実先行型】先に解析を完了させ、確定データをGeminiに渡して解説を生成させる"""
        try:
            from utils.logger import logger
            logger.info(f"AI Commentary Generation Start (Move {move_idx})", layer="AI_COMMENTATOR")
            
            # 1. 解析データの取得
            ana_data = api_client.analyze_move(history, board_size, include_pv=True)
            if not ana_data:
                logger.error("AI Commentary: KataGo analysis data fetch failed.", layer="AI_COMMENTATOR")
                return "【エラー】KataGoによる解析データの取得に失敗しました。"
            
            # 2. 現在のコンテキストの構築
            curr_ctx = self.simulator.reconstruct_to_context(history, board_size)
            facts = api_client.detect_shapes(history)

            # 3. 緊急度（温度）と未来予測の解析
            urgency_data = api_client.analyze_urgency(history, board_size)
            urgency_fact = ""
            if urgency_data:
                urgency_fact = (
                    f"【未来予測：成功と失敗の対比】\n"
                    f"- 緊急度: {urgency_data['urgency']:.1f}目\n"
                    f"- 推奨進行（成功図）: {urgency_data['best_pv']}\n"
                )
                
                # 被害シミュレーション
                thr_pv = urgency_data['opponent_pv']
                if thr_pv:
                    urgency_fact += f"- 放置した場合の被害（失敗図）: 相手に {thr_pv} と連打されます。\n"
                    
                    # SimulationContextを使用して未来の悪形を検知
                    thr_seq = ["pass"] + thr_pv
                    future_ctx = self.simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=urgency_data['next_player'])
                    
                    try:
                        logger.debug(f"Future shape detection for Threat scenario...", layer="AI_COMMENTATOR")
                        future_facts = api_client.detect_shapes(future_ctx.history)
                        if future_facts and "特筆すべき形状" not in future_facts:
                            urgency_fact += f"- 警告: 放置すると以下の悪形が発生します。\n  {future_facts}\n"
                    except Exception as e:
                        logger.warning(f"Future shape detection failed: {e}", layer="AI_COMMENTATOR")

            # 4. 安定度分析の実行
            stability_facts = ""
            ownership = ana_data.get('ownership')
            if ownership:
                stability_results = self.stability_analyzer.analyze(curr_ctx.board, ownership)
                logger.debug(f"Stability results: group_count={len(stability_results)}", layer="AI_COMMENTATOR")
                
                weak_stones = [r for r in stability_results if r['status'] in ['weak', 'critical']]
                strong_stones = [r for r in stability_results if r['status'] == 'strong']
                
                stability_facts = "【石の強弱（安定度）分析】\n"
                if weak_stones:
                    stability_facts += "- ⚠️ 弱い石 (攻められている可能性):\n"
                    for ws in weak_stones:
                        stability_facts += f"  - {ws['stones']} ({ws['color']}): 安定度 {ws['stability']:.2f} ({ws['status']})\n"
                if strong_stones:
                    stability_facts += "- ✅ 強い石 (安定している):\n"
                    for ss in strong_stones:
                        stones_str = str(ss['stones'][:3]) + ("..." if len(ss['stones']) > 3 else "")
                        stability_facts += f"  - {stones_str} ({ss['color']}): 確定地に近い\n"
            
            # 5. データの整理
            logger.debug("Finalizing data for Gemini prompt...", layer="AI_COMMENTATOR")
            candidates = ana_data.get('top_candidates', []) or ana_data.get('candidates', [])
            best = candidates[0] if candidates else {}
            
            pv_list = best.get('pv', [])
            self.last_pv = pv_list
            
            # 手番の色を考慮した番号付きリスト作成
            player_color = "黒" if (move_idx % 2 == 0) else "白"
            opp_color = "白" if player_color == "黒" else "黒"
            colored_seq = []
            for i, m in enumerate(pv_list):
                c = player_color if i % 2 == 0 else opp_color
                colored_seq.append(f"{i+1}: {c}{m}")
            numbered_seq = ", ".join(colored_seq) if colored_seq else "なし"
            
            fact_summary = (
                f"【最新の確定解析データ（引用必須）】\n"
                f"- 黒の勝率: {ana_data.get('winrate_black', '不明')}\n"
                f"- 目数差: {ana_data.get('score_lead_black', '不明')}目（正の値は黒リード）\n"
                f"- AIの推奨手: {best.get('move', 'なし')}\n"
                f"- 推奨進行（色・番号付き）: {numbered_seq}\n"
                f"- 盤面の形状事実: {facts}\n"
                f"{urgency_fact}"
                f"{stability_facts}\n"
                f"- 推奨手の将来予測: {best.get('future_shape_analysis', '特になし')}\n"
            )
            print(f"DEBUG DATA READY: Winrate(B): {ana_data.get('winrate_black')}")

            # 6. プロンプトの構築
            kn = self.knowledge_manager.get_all_knowledge_text()
            player = "黒" if (move_idx % 2 == 0) else "白"
            
            # ペルソナ（Gemini_Persona.md）の読み込み
            persona_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Gemini_Persona.md"))
            persona_text = ""
            if os.path.exists(persona_path):
                with open(persona_path, "r", encoding="utf-8") as f:
                    persona_text = f.read()

            sys_inst = self._load_prompt("go_instructor_system", board_size=board_size, player=player, knowledge=kn)
            if persona_text:
                sys_inst = f"{sys_inst}\n\n=== 執筆・解説ガイドライン ===\n{persona_text}"
            
            user_prompt = self._load_prompt("analysis_request", move_idx=move_idx, history=history)
            user_prompt = f"{fact_summary}\n{user_prompt}"

            # 7. 生成リクエスト
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

            final_text = response.text if response.text else "【エラー】解説の生成に失敗しました。"

            # --- 品質ガード (捏造チェック) ---
            real_move = str(best.get('move', ''))
            has_wr = any(x in final_text for x in ["%", "％", "勝率"])
            has_move = real_move.upper() in final_text.upper() if real_move else True

            if not has_wr or not has_move:
                print(f"DEBUG GUARD FAILED: WR:{has_wr} Move:{has_move}")
                return f"【解析結果】\n{fact_summary}\n\n(AIが詳細な解説を生成できませんでしたが、上記データがKataGoによる事実です。)"

            return final_text

        except Exception as e:
            traceback.print_exc()
            return f"SYSTEM ERROR: {str(e)}"

    def reset_chat(self):
        pass
