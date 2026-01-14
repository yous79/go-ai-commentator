from google import genai
from google.genai import types
import os
import json
import traceback
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from core.knowledge_manager import KnowledgeManager
from prompts.templates import get_unified_system_instruction
from services.api_client import api_client

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)

    def generate_commentary(self, move_idx, history, board_size=19):
        """【事実先行型】先に解析を完了させ、確定データをGeminiに渡して解説を生成させる"""
        try:
            print(f"--- AI COMMENTARY START (Move {move_idx}) ---")
            
            # 1. 解析データの先行取得 (API Client Singleton)
            ana_data = api_client.analyze_move(history, board_size, visits=100, include_pv=True)
            if not ana_data:
                return "【エラー】KataGoによる解析データの取得に失敗しました。サーバーの状態を確認してください。"
            
            facts = api_client.detect_shapes(history)

            # 2. データの整理
            best = ana_data.get('top_candidates', [{}])[0]
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
                f"- 推奨手の将来予測: {best.get('future_shape_analysis', '特になし')}\n"
            )
            print(f"DEBUG DATA READY: Winrate(B): {ana_data.get('winrate_black')}")

            # 3. プロンプトの構築
            kn = self.knowledge_manager.get_all_knowledge_text()
            player = "黒" if (move_idx % 2 == 0) else "白"
            sys_inst = get_unified_system_instruction(board_size, player, kn)
            
            user_prompt = (
                f"{fact_summary}\n"
                f"あなたは上記の確定データのみを根拠に語るプロの囲碁インストラクターです。\n"
                f"上記データに含まれない架空の数値（勝率など）を生成することは厳禁です。\n"
                f"現在の手数（{move_idx}手目、{player}番）を踏まえ、この局面のポイントを詳しく解説してください。"
            )

            # 4. 生成リクエスト (自律ツールなしのシングルショット、あるいは必要に応じた対話)
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
            # 先行データと照合
            real_wr_val = str(ana_data.get('winrate_black', ''))
            real_move = str(best.get('move', ''))
            
            # 数値が含まれているか (簡易的な照合)
            has_wr = any(x in final_text for x in ["%", "％", "勝率"])
            has_move = real_move.upper() in final_text.upper() if real_move else True

            if not has_wr or not has_move:
                print(f"DEBUG GUARD FAILED: WR:{has_wr} Move:{has_move}")
                # 捏造または欠落があった場合の救済（あるいはエラー）
                return f"【解析結果】\n{fact_summary}\n\n(AIが詳細な解説を生成できませんでしたが、上記データがKataGoによる事実です。)"

            return final_text

        except Exception as e:
            traceback.print_exc()
            return f"SYSTEM ERROR: {str(e)}"

    def reset_chat(self):
        pass
