import os
import json
import asyncio
import io
import matplotlib.pyplot as plt
from google.genai import types
from config import GEMINI_MODEL_NAME, TARGET_LEVEL
from utils.pdf_generator import PDFGenerator
from services.api_client import api_client
from services.persona import PersonaFactory
from utils.logger import logger

class ReportGenerator:
    def __init__(self, game_state, renderer, commentator):
        self.game = game_state
        self.renderer = renderer
        self.commentator = commentator # GeminiCommentator instance
        self.analysis_cache = {}  # Cache for full analysis results
        
        # Use Agg backend for matplotlib to avoid GUI requirement
        import matplotlib
        matplotlib.use('Agg')

    async def generate(self, sgf_name, image_dir):
        """最新の知識ベースと形状検知事実を用いた対局レポート(Markdown & PDF)生成"""
        logger.info("Starting Report Generation...", layer="REPORT")
        
        # 1. 悪手の抽出とソート (方針 C)
        mb, _ = self.game.calculate_mistakes()
        if not mb:
            # 悪手ゼロなら好手だけでも探すか、素晴らしいと返す
            return None, "黒番に顕著な悪手が見つかりませんでした。素晴らしい対局です。"

        # 評価値損失が大きい順にソート (Rank 1が最大損失)
        # item: (score_loss, winrate_loss, move_idx)
        # 勝率が大きく減ったものを優先 (x[1] desc), 次に目数 (x[0] desc)
        all_m = sorted(mb, key=lambda x: (x[1], x[0]), reverse=True)[:3]
        
        r_dir = os.path.join(image_dir, "report")
        os.makedirs(r_dir, exist_ok=True)
        
        r_md = f"# 対局レポート (黒番視点): {sgf_name}\n\n"
        pdf_items = [] # PDF用のデータ蓄積

        # 2. 評価値グラフの生成 (方針 B)
        graph_path = os.path.join(r_dir, "winrate_graph.png")
        if self._generate_winrate_graph(graph_path):
            r_md += f"![勝率グラフ](winrate_graph.png)\n\n"
            # PDFの先頭にグラフを追加
            pdf_items.append({
                "title": "対局全体の推移",
                "move": 0,
                "image": graph_path,
                "text": "対局全体の勝率推移です。グラフが大きく下がったポイントが、詳細解説の対象となる改善点です。"
            })

        # 3. 好手の探索 (方針 Modified C: 緊急度高の好手を1つピックアップ)
        good_move_idx = await self._find_best_move_candidate()
        if good_move_idx:
            logger.info(f"Good move candidate found at {good_move_idx}", layer="REPORT")

        # 知識ベース (全量取得し、後でフィルタリング検討)
        full_knowledge = self.commentator.knowledge_manager.get_all_knowledge_text()

        # 4. 悪手の解説とPDFアイテム生成
        for rank, (sc_drop, wr_drop, m_idx) in enumerate(all_m, 1):
            # Rank 1 は詳細、2,3は簡易
            is_rank_1 = (rank == 1)
            
            # 解析実行 (キャッシュ活用)
            history_prev = self.game.get_history_up_to(m_idx - 1)
            history_curr = self.game.get_history_up_to(m_idx)
            board_prev = self.game.get_board_at(m_idx - 1)
            
            try:
                # 前局面解析 (推奨手取得)
                res_prev = await asyncio.to_thread(api_client.analyze_move, history_prev, self.game.board_size)
                # 現局面フル解析 (事実取得) - Rank 1 または 詳細が必要なら
                collector_curr = await self._get_cached_analysis(history_curr)
                
                det_facts = collector_curr.get_prioritized_text(limit=10 if is_rank_1 else 5)
            except Exception as e:
                logger.error(f"Report Error at Move {m_idx}: {e}", layer="REPORT")
                continue

            if res_prev and res_prev.candidates:
                best = res_prev.candidates[0]
                pv_list = best.pv
                
                # 画像生成 A: 実戦図 (Actual)
                # 実戦手を取得してマーカーを表示
                last_move_data = None
                history_curr_chk = self.game.get_history_up_to(m_idx)
                if history_curr_chk:
                    last_c, last_gtp = history_curr_chk[-1]
                    if last_gtp and last_gtp.lower() != "pass":
                        idx = self.renderer.transformer.gtp_to_indices(last_gtp)
                        if idx:
                            last_move_data = (last_c, idx)

                img_actual = self.renderer.render(self.game.get_board_at(m_idx), last_move=last_move_data)
                fname_actual = f"mistake_{m_idx:03d}_actual.png"
                path_actual = os.path.join(r_dir, fname_actual)
                img_actual.save(path_actual)

                # 画像生成 B: 推奨図 (Suggestion / PV)
                # board_prev は打つ前の盤面
                img_pv = self.renderer.render_pv(board_prev, pv_list, "B", 
                                              title=f"M{m_idx} Suggestion")
                fname_pv = f"mistake_{m_idx:03d}_pv.png"
                path_pv = os.path.join(r_dir, fname_pv)
                img_pv.save(path_pv)

                # テンプレート選択
                tmpl_name = "report_mistake_detailed" if is_rank_1 else "report_mistake_brief"
                
                # コンテキスト知識フィルタリング
                custom_kn = f"{full_knowledge}\n\n【この局面で検出された事実】:\n{det_facts}"
                
                # Persona
                persona = PersonaFactory.get_persona(TARGET_LEVEL)
                
                prompt_args = {
                    "m_idx": m_idx,
                    "player_color": "黒",
                    "wr_drop": f"-{wr_drop:.1%}",
                    "sc_drop": f"-{sc_drop:.1f}目",
                    "ai_move": best.move,
                    "pv_str": " -> ".join(pv_list) if pv_list else "",
                    "related_knowledge": det_facts,
                    "knowledge": custom_kn
                }
                
                prompt = self.commentator._load_prompt(tmpl_name, **prompt_args)

                # Commentary Generation
                commentary = await self._call_gemini(prompt)

                # Markdown追加: 左右配置のテーブル
                md_title = f"### 手数 {m_idx} (Rank {rank}: 決定機)" if is_rank_1 else f"### 手数 {m_idx} (Rank {rank})"
                
                r_md += f"{md_title}\n"
                r_md += f"- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n\n"
                r_md += f"| 実戦 (Actual) | AI推奨 (Suggestion) |\n| :---: | :---: |\n"
                r_md += f"| ![{m_idx}実戦]({fname_actual}) | ![{m_idx}推奨]({fname_pv}) |\n\n"
                r_md += f"{commentary}\n\n---\n\n"
                
                # PDFアイテム
                # PDFではサイドバイサイドが難しい場合があるので、順に並べるか、PDFGenerator側で工夫が必要
                # ここでは順に追加する形をとる（タイトルで区別）
                pdf_items.append({
                    "title": f"第 {m_idx} 手: 実戦（あなたの手）",
                    "move": m_idx,
                    "image": path_actual,
                    "text": "実戦の局面です。"
                })
                pdf_items.append({
                    "title": f"第 {m_idx} 手: AI推奨の進行",
                    "move": m_idx,
                    "image": path_pv,
                    "text": commentary
                })
            else:
                r_md += f"### 手数 {m_idx}\n(解析データ取得失敗)\n\n"

        # 5. 好手の解説 (もしあれば)
        if good_move_idx:
            gm_md = await self._process_good_move(good_move_idx, full_knowledge, r_dir, r_md, pdf_items)
            r_md += gm_md

        # 6. 総評
        sum_p = self.commentator._load_prompt("report_summary", knowledge=full_knowledge, mistakes_data=str([(m[2], m[1]) for m in all_m]))
        total_summary = await self._call_gemini(sum_p)
        r_md += f"## 黒番への総評\n\n{total_summary}\n"
        
        # 出力
        md_path = os.path.join(r_dir, "report.md")
        with open(md_path, "w", encoding="utf-8") as f: f.write(r_md)
            
        pdf_path = os.path.join(r_dir, "report.pdf")
        try:
            pdf_gen = PDFGenerator()
            pdf_gen.generate_report(f"囲碁AI対局レポート: {sgf_name}", pdf_items, total_summary, pdf_path)
        except Exception as e:
            logger.error(f"PDF Generation Failed: {e}", layer="REPORT")
            return md_path, f"Markdown作成完了、PDF生成失敗: {e}"
            
        return pdf_path, None

    async def _get_cached_analysis(self, history):
        h_key = str(history) # history is list of lists, stringify for key
        if h_key in self.analysis_cache:
            return self.analysis_cache[h_key]
        
        # 既存解析がない場合のみ実行
        res = await self.commentator.orchestrator.analyze_full(history, self.game.board_size)
        self.analysis_cache[h_key] = res
        return res

    async def _call_gemini(self, prompt):
        def _call():
            return self.commentator.client.models.generate_content(
                model=GEMINI_MODEL_NAME, 
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction="プロの囲碁インストラクターとして解説せよ。" )
            )
        resp = await asyncio.to_thread(_call)
        return resp.text if resp.text else "(解説生成失敗)"

    def _generate_winrate_graph(self, output_path):
        try:
            moves = self.game.moves
            if not moves: return False
            
            # Extract winrates for Black
            indices = []
            wrs = []
            
            # moves[i] is state AFTER move i+1 (0-indexed logic in game_state) or i (1-indexed)?
            # calculate_mistakes uses 1..len.
            # moves list usually: [Result of Move 1, Result of Move 2, ...]
            # Move 1 (Black): result dict has 'winrate_black'.
            
            for i, data in enumerate(moves):
                if not data: continue
                # 黒の勝率を取得
                if isinstance(data, dict):
                    wb = data.get('winrate', data.get('winrate_black'))
                else:
                    wb = getattr(data, 'winrate', getattr(data, 'winrate_black', None))

                if wb is not None:
                    indices.append(i + 1)
                    wrs.append(wb * 100) # %
            
            if not indices: return False

            plt.figure(figsize=(10, 4))
            plt.plot(indices, wrs, marker='o', markersize=2, linestyle='-', color='black', label='Black Winrate')
            plt.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
            plt.title('Winrate History (Black)')
            plt.xlabel('Move Number')
            plt.ylabel('Winrate (%)')
            plt.ylim(0, 100)
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            plt.savefig(output_path, bbox_inches='tight')
            plt.close()
            return True
        except Exception as e:
            logger.error(f"Graph Generation Failed: {e}", layer="REPORT")
            return False

    async def _find_best_move_candidate(self):
        """黒番の好手候補（損失が少なく、かつ緊急度が高い可能性がある場面）を探す"""
        candidates = []
        moves = self.game.moves
        if not moves or len(moves) < 2: return None

        # 黒番の手(奇数手目)をチェック
        # game.moves[i] は (i+1) 手目の結果。
        # 例: i=0 -> 1手目(黒)。 
        for i, data in enumerate(moves):
            # Check only Black moves (0, 2, 4...) -> Moves 1, 3, 5...
            if i % 2 != 0: continue # Skip White
            if i == 0: continue # Skip first move (joseki usually)
            
            prev = moves[i-1]
            curr = data
            if not prev or not curr: continue

            if isinstance(prev, dict):
                wb_prev = prev.get('winrate', prev.get('winrate_black', 0.5))
            else:
                wb_prev = getattr(prev, 'winrate', getattr(prev, 'winrate_black', 0.5))

            if isinstance(curr, dict):
                wb_curr = curr.get('winrate', curr.get('winrate_black', 0.5))
            else:
                wb_curr = getattr(curr, 'winrate', getattr(curr, 'winrate_black', 0.5))
            
            # Loss = Prev - Curr. Good move means Loss near 0 or Gain (negative loss).
            loss = wb_prev - wb_curr
            
            # 条件: 損失が非常に小さい (1%未満) か 利得がある
            # かつ、勝負が決まっていない (5% < WR < 95%)
            if loss < 0.01 and 0.05 < wb_prev < 0.95:
                # 候補として登録。優先度は「直前のWinrate変動が大きかった（激戦）」など簡易指標で
                candidates.append(i + 1)
        
        if not candidates: return None
        
        # 候補の中からランダムか、あるいは特定の条件で1つ選んでフル解析
        # ここでは「候補のなかで最も評価値が高い（＝最善に近い）もの」から順に3つ調べ、Urgency高いものを採用
        # 簡易的に、候補リストの後ろの方（中盤・終盤）を優先してみる
        candidates.reverse()
        
        for m_idx in candidates[:3]: # 最大3候補だけチェック
            history = self.game.get_history_up_to(m_idx)
            # 緊急度チェックのためフル解析
            collector = await self._get_cached_analysis(history)
            
            # Urgencyファクトがあるか、Severityが高いファクトがあるか
            # UrgencyProvider creates facts with category STRATEGY or URGENCY?
            # Usually Urgency is a metric. FactCollector doesn't expose raw metrics easily unless in text.
            # But let's check facts severity.
            high_urgency = any(f.severity >= 4 for f in collector.facts)
            
            if high_urgency:
                return m_idx
                
        return None

    async def _process_good_move(self, m_idx, knowledge, r_dir, r_md, pdf_items):
        try:
            history = self.game.get_history_up_to(m_idx)
            collector = await self._get_cached_analysis(history)
            facts = collector.get_prioritized_text(limit=5)
            
            # 画像
            board = self.game.get_board_at(m_idx)
            p_img = self.renderer.render(board, last_move=None, analysis_text=f"Move {m_idx} (Good Move!)")
            img_path = os.path.join(r_dir, f"good_move_{m_idx:03d}.png")
            p_img.save(img_path)
            
            # 解説生成
            prompt_args = {
                "m_idx": m_idx, "player_color": "黒",
                "ai_move": "実戦の手 (AI一致)",
                "urgency": "高 (High)", # Detected by logic
                "related_knowledge": facts
            }
            prompt = self.commentator._load_prompt("report_good_move", **prompt_args)
            commentary = await self._call_gemini(prompt)
            
            # Markdown update (Reference passed by mutation of r_md string? No, strings are immutable)
            # Python strings are immutable. I cannot update `r_md` passed as arg.
            # Wait, I used `r_md +=` inside methods? No, this is a separate method. 
            # I should return the text and append it in caller.
        except Exception as e:
            logger.error(f"Good move processing failed: {e}", layer="REPORT")
            return ""

        # Using a trick to update items list is fine, but string must be returned.
        pdf_items.append({
            "title": f"第 {m_idx} 手: 本局の好手！",
            "move": m_idx,
            "image": img_path,
            "text": commentary
        })
        return f"### 第 {m_idx} 手 (ナイスプレー！)\n\n![好手]({os.path.basename(img_path)})\n\n{commentary}\n\n---\n\n"
