from google import genai
from google.genai import types
import os
import json
import traceback
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME, load_api_key
from core.knowledge_manager import KnowledgeManager
from core.stability_analyzer import StabilityAnalyzer
from core.board_simulator import BoardSimulator, SimulationContext
from core.shape_detector import ShapeDetector
from core.inference_fact import InferenceFact, FactCategory, FactCollector
from services.api_client import api_client

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.stability_analyzer = StabilityAnalyzer()
        self.simulator = BoardSimulator()
        self.detector = ShapeDetector() # detectorを初期化
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
        """【事実先行型】先に解析を完了させ、構造化された確定データをGeminiに渡して解説を生成させる"""
        try:
            from utils.logger import logger
            logger.info(f"AI Commentary Generation Start (Move {move_idx})", layer="AI_COMMENTATOR")
            collector = FactCollector()
            
            # 1. 解析データの取得
            ana_data = api_client.analyze_move(history, board_size, include_pv=True)
            if not ana_data:
                logger.error("AI Commentary: KataGo analysis data fetch failed.", layer="AI_COMMENTATOR")
                return "【エラー】KataGoによる解析データの取得に失敗しました。"
            
            curr_ctx = self.simulator.reconstruct_to_context(history, board_size)

            # 2. 形状検知（事実収集）
            # self.detectorを使用するように修正
            shape_facts = self.detector.detect_facts(curr_ctx.board, curr_ctx.prev_board)
            for f in shape_facts: collector.facts.append(f)

            # 3. 緊急度解析（事実収集）
            urgency_data = api_client.analyze_urgency(history, board_size)
            if urgency_data:
                u_severity = 5 if urgency_data['is_critical'] else 2
                u_desc = f"この局面の緊急度は {urgency_data['urgency']:.1f}目 です。{'一手の緩みも許されない急場です。' if urgency_data['is_critical'] else '比較的平穏な局面です。'}"
                collector.add(FactCategory.URGENCY, u_desc, u_severity, urgency_data)
                
                # 未来の悪形警告
                thr_pv = urgency_data['opponent_pv']
                if thr_pv:
                    thr_seq = ["pass"] + thr_pv
                    future_ctx = self.simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=urgency_data['next_player'])
                    # self.detectorを使用するように修正
                    future_shape_facts = self.detector.detect_facts(future_ctx.board, future_ctx.prev_board)
                    for f in future_shape_facts:
                        if f.severity >= 4:
                            f.description = f"放置すると {f.description} という悪形が発生する恐れがあります。"
                            collector.facts.append(f)

            # 4. 安定度分析（事実収集）
            ownership = ana_data.get('ownership')
            if ownership:
                stability_facts = self.stability_analyzer.analyze_to_facts(curr_ctx.board, ownership)
                for f in stability_facts: collector.facts.append(f)

            # 5. 勝率・目数差の事実（追加）
            wr = ana_data.get('winrate_black', 0.5)
            sl = ana_data.get('score_lead_black', 0.0)
            collector.add(FactCategory.STRATEGY, f"現在の勝率(黒): {wr:.1%}, 目数差: {sl:.1f}目", severity=3)

            # 6. プロンプトの構築
            prioritized_facts = collector.get_prioritized_text(limit=12)
            
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

            # 7. プロンプトの構築
            kn = self.knowledge_manager.get_all_knowledge_text()
            
            persona_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Gemini_Persona.md"))
            persona_text = ""
            if os.path.exists(persona_path):
                try:
                    with open(persona_path, "r", encoding="utf-8") as f:
                        persona_text = f.read()
                except: pass

            sys_inst = self._load_prompt("go_instructor_system", board_size=board_size, player=player_color, knowledge=kn)
            if persona_text:
                sys_inst = f"{sys_inst}\n\n=== 執筆・解説ガイドライン ===\n{persona_text}"
            
            user_prompt = self._load_prompt("analysis_request", move_idx=move_idx, history=history)
            user_prompt = f"{fact_summary}\n{user_prompt}"

            # 8. 生成リクエスト
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
