import os
import json
from google.genai import types
from config import GEMINI_MODEL_NAME, TARGET_LEVEL
from utils.pdf_generator import PDFGenerator
from services.api_client import api_client
from services.persona import PersonaFactory

class ReportGenerator:
    def __init__(self, game_state, renderer, commentator):
        self.game = game_state
        self.renderer = renderer
        self.commentator = commentator # GeminiCommentator instance

    def generate(self, sgf_name, image_dir):
        """最新の知識ベースと形状検知事実を用いた対局レポート(Markdown & PDF)生成"""
        mb, _ = self.game.calculate_mistakes()
        if not mb: return None, "黒番に顕著な悪手が見つかりませんでした。"

        # 損失の大きいトップ3を抽出
        all_m = sorted(mb, key=lambda x:x[1], reverse=True)[:3]
        all_m = sorted(all_m, key=lambda x:x[2]) 

        r_dir = os.path.join(image_dir, "report")
        os.makedirs(r_dir, exist_ok=True)
        
        r_md = f"# 対局レポート (黒番視点): {sgf_name}\n\n"
        kn = self.commentator.knowledge_manager.get_all_knowledge_text()
        
        pdf_items = [] # PDF用のデータ蓄積

        for i, (sc_drop, wr_drop, m_idx) in enumerate(all_m):
            history_prev = self.game.get_history_up_to(m_idx - 1)
            history_curr = self.game.get_history_up_to(m_idx)
            board = self.game.get_board_at(m_idx - 1)
            
            try:
                # 1. 前局面の解析 (AI推奨手を得るため)
                res_prev = api_client.analyze_move(history_prev, self.game.board_size)
                
                # 2. 現局面のフル解析 (形状・安定度・緊急度などの『事実』を得るため)
                collector_curr = self.commentator.orchestrator.analyze_full(history_curr, self.game.board_size)
                det_facts = collector_curr.get_prioritized_text(limit=10)
                
            except Exception as e:
                print(f"Report Error at Move {m_idx}: {e}")
                continue

            if res_prev and res_prev.candidates:
                best = res_prev.candidates[0]
                pv_list = best.pv
                pv_str = " -> ".join(pv_list) if pv_list else ""
                
                # 参考図画像の生成と保存
                p_img = self.renderer.render_pv(board, pv_list, "B", 
                                              title=f"Move {m_idx} Ref (-{wr_drop:.1%} / -{sc_drop:.1f}pts)")
                f_name = f"mistake_{m_idx:03d}_pv.png"
                img_path = os.path.join(r_dir, f_name)
                p_img.save(img_path)
                
                # Geminiによる個別解説 (トリアージされた事実を渡す)
                custom_kn = f"{kn}\n\n【この局面で検出された事実（重要度順）】:\n{det_facts}"
                
                # 人格（Persona）の動的選択
                persona = PersonaFactory.get_persona(TARGET_LEVEL)
                prompt = self.commentator._load_prompt(persona.report_template, m_idx=m_idx, player_color="黒", 
                                                       wr_drop=f"-{wr_drop:.1%}", sc_drop=f"-{sc_drop:.1f}目", 
                                                       ai_move=best.move, pv_str=pv_str, knowledge=custom_kn)
                
                
                
                resp_gemini = self.commentator.client.models.generate_content(
                    model=GEMINI_MODEL_NAME, 
                    contents=prompt,
                    config=types.GenerateContentConfig(system_instruction="プロの囲碁インストラクターとして解説せよ。" )
                )
                commentary = resp_gemini.text if resp_gemini.text else "(解説生成失敗)"
                
                # Markdown追加
                r_md += f"### 手数 {m_idx} (黒番のミス)\n- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n- **AI推奨**: {best.get('move', 'なし')}\n\n![参考図]({f_name})\n\n**解説**: {commentary}\n\n---\n\n"
                
                # PDFアイテム追加
                pdf_items.append({
                    "move": m_idx,
                    "image": img_path,
                    "text": commentary
                })
            else:
                r_md += f"### 手数 {m_idx} (黒番のミス)\n(解析データ欠落)\n\n---\n\n"

        # 3. 総評
        sum_p = self.commentator._load_prompt("report_summary", knowledge=kn, mistakes_data=str(all_m))
        sum_resp = self.commentator.client.models.generate_content(model=GEMINI_MODEL_NAME, contents=sum_p)
        total_summary = sum_resp.text if sum_resp.text else "対局お疲れ様でした。"
        r_md += f"## 黒番への総評\n\n{total_summary}\n"
        
        # Markdown出力
        md_path = os.path.join(r_dir, "report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(r_md)
            
        # 4. PDF出力
        pdf_path = os.path.join(r_dir, "report.pdf")
        try:
            pdf_gen = PDFGenerator()
            pdf_gen.generate_report(f"囲碁AI対局レポート: {sgf_name}", pdf_items, total_summary, pdf_path)
        except Exception as e:
            print(f"PDF Generation Failed: {e}")
            return md_path, f"Markdownは保存されましたが、PDF生成に失敗しました: {e}"
            
        return pdf_path, None
