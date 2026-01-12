import os
import json
import requests
from google.genai import types
from prompts.templates import get_report_individual_prompt, get_report_summary_prompt
from config import GEMINI_MODEL_NAME

class ReportGenerator:
    def __init__(self, game_state, renderer, commentator):
        self.game = game_state
        self.renderer = renderer
        self.commentator = commentator # GeminiCommentator instance
        self.api_url = "http://127.0.0.1:8000/analyze"

    def generate(self, sgf_name, image_dir):
        mb, _ = self.game.calculate_mistakes()
        if not mb: return None, "黒番に顕著な悪手が見つかりませんでした。"

        all_m = sorted(mb, key=lambda x:x[1], reverse=True)[:3]
        all_m = sorted(all_m, key=lambda x:x[2]) 

        r_dir = os.path.join(image_dir, "report")
        os.makedirs(r_dir, exist_ok=True)
        r_md = f"# 対局レポート (黒番視点): {sgf_name}\n\n"
        kn = self.commentator._load_knowledge()

        for i, (sc_drop, wr_drop, m_idx) in enumerate(all_m):
            history = self.game.get_history_up_to(m_idx - 1)
            board = self.game.get_board_at(m_idx - 1)
            
            try:
                resp = requests.post(self.api_url, json={"history": history, "board_size": self.game.board_size}, timeout=40)
                if resp.status_code != 200:
                    print(f"Report API Error at Move {m_idx}: {resp.status_code}")
                    continue
                res = resp.json()
            except Exception as e:
                print(f"Report Request Failed at Move {m_idx}: {e}")
                continue

            if 'top_candidates' in res and res['top_candidates']:
                best = res['top_candidates'][0]
                pv_str = best.get('future_sequence', "")
                pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
                
                p_img = self.renderer.render_pv(board, pv_list, "B", 
                                              title=f"Move {m_idx} Ref (-{wr_drop:.1%} / -{sc_drop:.1f}pts)")
                f_name = f"mistake_{m_idx:03d}_pv.png"
                p_img.save(os.path.join(r_dir, f_name))
                
                prompt = get_report_individual_prompt(m_idx, "黒", wr_drop, sc_drop, best['move'], pv_str, kn)
                resp_gemini = self.commentator.client.models.generate_content(
                    model=GEMINI_MODEL_NAME, 
                    contents=prompt,
                    config=types.GenerateContentConfig(system_instruction="プロの囲碁インストラクターとして解説せよ。" )
                )
                r_md += f"### 手数 {m_idx} (黒番のミス)\n- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n- **AI推奨**: {best['move']}\n\n![参考図]({f_name})\n\n**解説**: {resp_gemini.text}\n\n---\n\n"

        sum_p = get_report_summary_prompt(kn, all_m)
        sum_resp = self.commentator.client.models.generate_content(model=GEMINI_MODEL_NAME, contents=sum_p)
        r_md += f"## 黒番への総評\n\n{sum_resp.text}\n"
        
        report_path = os.path.join(r_dir, "report.md")
        with open(report_path, "w", encoding="utf-8") as f: f.write(r_md)
        return report_path, None