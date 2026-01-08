import os
from google.genai import types
from prompts.templates import get_report_individual_prompt, get_report_summary_prompt

class ReportGenerator:
    def __init__(self, game_state, renderer, commentator, katago_driver):
        self.game = game_state
        self.renderer = renderer
        self.commentator = commentator # GeminiCommentator instance
        self.katago = katago_driver

    def generate(self, sgf_name, image_dir):
        # 1. データの準備 (黒番のみ)
        mb, _ = self.game.calculate_mistakes()
        if not mb:
            return None, "黒番に顕著な悪手が見つかりませんでした。"

        # 黒番のミス上位3つ
        all_m = sorted(mb, key=lambda x:x[1], reverse=True)[:3]
        all_m = sorted(all_m, key=lambda x:x[2]) # 手数順

        r_dir = os.path.join(image_dir, "report")
        os.makedirs(r_dir, exist_ok=True)
        
        r_md = f"# 対局レポート (黒番視点): {sgf_name}\n\n"
        kn = self.commentator._load_knowledge()

        # 2. 各悪手の解析
        for i, (sc_drop, wr_drop, m_idx) in enumerate(all_m):
            history = self.game.get_history_up_to(m_idx - 1)
            board = self.game.get_board_at(m_idx - 1)
            
            # KataGoで解析
            res = self.katago.analyze_situation(history, board_size=self.game.board_size)
            if 'top_candidates' in res and res['top_candidates']:
                best = res['top_candidates'][0]
                pv_str = best.get('future_sequence', "")
                pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
                
                # 画像生成
                p_img = self.renderer.render_pv(board, pv_list, "B", 
                                              title=f"Move {m_idx} Ref (-{wr_drop:.1%} / -{sc_drop:.1f}pts)")
                f_name = f"mistake_{m_idx:03d}_pv.png"
                p_img.save(os.path.join(r_dir, f_name))
                
                # Gemini解説
                prompt = get_report_individual_prompt(m_idx, "黒", wr_drop, sc_drop, best['move'], pv_str, kn)
                
                resp = self.commentator.client.models.generate_content(
                    model='gemini-3-flash-preview', 
                    contents=prompt,
                    config=types.GenerateContentConfig(system_instruction="プロの囲碁インストラクターとして解説せよ。" )
                )
                
                r_md += f"### 手数 {m_idx} (黒番のミス)\n- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n- **AI推奨**: {best['move']}\n\n![参考図]({f_name})\n\n**解説**: {resp.text}\n\n---\n\n"

        # 3. 総評
        sum_p = get_report_summary_prompt(kn, all_m)
        sum_resp = self.commentator.client.models.generate_content(model='gemini-3-flash-preview', contents=sum_p)
        r_md += f"## 黒番への総評\n\n{sum_resp.text}\n"
        
        report_path = os.path.join(r_dir, "report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(r_md)
            
        return report_path, None
