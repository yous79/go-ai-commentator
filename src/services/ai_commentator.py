from google import genai
from google.genai import types
import os
import asyncio
import json
import traceback
import re
import requests
from config import KNOWLEDGE_DIR, GEMINI_MODEL_NAME
from core.knowledge_manager import KnowledgeManager
from prompts.templates import get_unified_system_instruction

class GeminiCommentator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.last_pv = None 
        self.knowledge_manager = KnowledgeManager(KNOWLEDGE_DIR)
        self.api_url = "http://127.0.0.1:8000"

    def generate_commentary(self, move_idx, history, board_size=19):
        """【事実先行型】先に解析を完了させ、確定データをGeminiに渡して解説を生成させる"""
        try:
            print(f"--- FACT-FIRST AI COMMENTARY START (Move {move_idx}) ---")
            
            # 1. 解析データの先行取得 (Sync API Call)
            print("DEBUG: Pre-fetching KataGo analysis...")
            ana_resp = requests.post(f"{self.api_url}/analyze", json={"history": history, "board_size": board_size}, timeout=45)
            ana_data = ana_resp.json()
            
            print("DEBUG: Pre-fetching shape detection...")
            det_resp = requests.post(f"{self.api_url}/detect", json={"history": history, "board_size": board_size}, timeout=15)
            det_data = det_resp.json()

            # 2. データの整理
            best = ana_data.get('top_candidates', [{}])[0]
            self.last_pv = best.get('future_sequence', "").split(" -> ")
            
            fact_summary = (
                f"【最新の確定解析データ（引用必須）】\n"
                f"- 黒の勝率: {ana_data.get('winrate_black', '不明')}\n"
                f"- 目数差: {ana_data.get('score_lead_black', '不明')}目（正の値は黒リード）\n"
                f"- AIの推奨手: {best.get('move', 'なし')}\n"
                f"- 推奨進行: {best.get('future_sequence', 'なし')}\n"
                f"- 盤面の形状事実: {det_data.get('facts', '特筆すべき形状なし')}\n"
                f"- 推奨手の将来予測: {best.get('future_shape_analysis', '特になし')}\n"
            )
            print(f"DEBUG DATA READY: {ana_data.get('winrate_black')} / {best.get('move')}")

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
