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
from core.inference_fact import TemporalScope

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
                
                # 画像生成: 推奨図 (Suggestion / PV) + 実戦手のマーク (▲)
                # 実戦手を取得して ▲ マーカーを表示
                actual_marks = {"TR": []}
                history_curr_chk = self.game.get_history_up_to(m_idx)
                if history_curr_chk:
                    last_c, last_gtp = history_curr_chk[-1]
                    if last_gtp and last_gtp.lower() != "pass":
                        idx = self.renderer.transformer.gtp_to_indices(last_gtp)
                        if idx:
                            actual_marks["TR"].append(idx)

                # 推奨図の上に実戦手を重ねる
                img_pv = self.renderer.render_pv(board_prev, pv_list, "B", 
                                              title=f"M{m_idx} Suggestion (Actual: Triangle)")
                
                # MarkupLayerを直接使うか、render()を再度呼ぶ。render_pvは内部でrenderを呼んでいる。
                # 最終的な上書きのために、RenderContextを意識して再度描画するか、
                # render_pv 自体を拡張して marks を受け取れるようにするのが理想的。
                # 現状は簡略化のため、render_pv の結果のイメージに後描画するか、
                # render を直接使って PV を手動で渡す。
                
                # 最も確実な方法: render を使用し、candidates(PV) と marks(Actual) を同時に渡す
                mock_candidates = []
                curr_c = "B" # starting_color は暫定
                for i, m_str in enumerate(pv_list[:10]):
                    mock_candidates.append({
                        "move": m_str,
                        "color": curr_c,
                        "winrate": 0.0
                    })
                    curr_c = "W" if curr_c == "B" else "B"

                final_img = self.renderer.render(
                    board_prev, 
                    analysis_text=f"Move {m_idx} Improvement Plan",
                    candidates=mock_candidates,
                    show_numbers=True,
                    marks=actual_marks
                )

                fname_pv = f"mistake_{m_idx:03d}_suggestion.png"
                path_pv = os.path.join(r_dir, fname_pv)
                final_img.save(path_pv)

                # テンプレート選択
                tmpl_name = "report_mistake_detailed" if is_rank_1 else "report_mistake_brief"
                
                # コンテキスト知識フィルタリング
                custom_kn = f"{full_knowledge}\n\n【この局面で検出された事実】:\n{det_facts}"
                
                # 解説生成
                data_curr = self.game.moves[m_idx-1]
                if isinstance(data_curr, dict):
                    wr_after = data_curr.get('winrate', data_curr.get('winrate_black', 0.5))
                    sc_after = data_curr.get('score', data_curr.get('score_lead_black', 0.0))
                else:
                    wr_after = getattr(data_curr, 'winrate', getattr(data_curr, 'winrate_black', 0.5))
                    sc_after = getattr(data_curr, 'score', getattr(data_curr, 'score_lead_black', 0.0))

                move_warnings = collector_curr.get_last_move_summary()
                pv_warnings = collector_curr.get_scope_summary(TemporalScope.PREDICTED)

                prompt_args = {
                    "m_idx": m_idx,
                    "player_color": "黒",
                    "winrate_curr": f"{wr_after:.1%}",
                    "score_curr": f"{sc_after:.1f}",
                    "winrate_drop": f"{wr_drop:.1%}",
                    "score_drop": f"{sc_drop:.1f}",
                    "ai_move": best.move,
                    "pv_str": " -> ".join(pv_list) if pv_list else "",
                    "move_warnings": move_warnings,
                    "pv_warnings": pv_warnings,
                    "knowledge": custom_kn
                }
                
                prompt = self.commentator._load_prompt(tmpl_name, **prompt_args)

                # Commentary Generation
                commentary = await self._call_gemini(prompt)

                # Markdown追加: 単一画像配置
                md_title = f"### 手数 {m_idx} (Rank {rank}: 決定機)" if is_rank_1 else f"### 手数 {m_idx} (Rank {rank})"
                
                r_md += f"{md_title}\n"
                r_md += f"- **勝率下落**: -{wr_drop:.1%}\n- **目数下落**: -{sc_drop:.1f}目\n\n"
                r_md += f"![{m_idx}解説図]({fname_pv})\n\n"
                r_md += f"> ▲印：あなたの着手 / 数字：AIの推奨手順\n\n"
                r_md += f"{commentary}\n\n---\n\n"
                
                # PDFアイテム
                pdf_items.append({
                    "title": f"第 {m_idx} 手: 解析図（▲実戦 / 数字AI）",
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

            # 通常のサイズに戻す
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
        """黒番の好手候補を探す (Tiered Approach)"""
        # Tier 1: AI一致 AND 高緊急度 (Surprise/Urgency)
        # Tier 2: AI一致 (Best Move)
        # Tier 3: 最も損失が少ない手 (Fallback)

        moves = self.game.moves
        if not moves or len(moves) < 2: return None

        # 1. 全黒番の着手についてデータを収集
        candidates_data = []
        for i, data in enumerate(moves):
            if i % 2 != 0: continue # Skip White
            if i == 0: continue # Skip first move
            
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
            
            # Loss計算 (小さいほど良い)
            loss = wb_prev - wb_curr
            
            # 勝負が決している局面(5%以下/95%以上)は好手の価値が薄いが、Tier 3用には残す
            candidates_data.append({
                'm_idx': i + 1,
                'loss': loss,
                'wb_prev': wb_prev
            })

        if not candidates_data: return None

        # 損失が小さい順にソート (Tier 3候補)
        sorted_by_loss = sorted(candidates_data, key=lambda x: x['loss'])
        
        # 解析対象: 損失が特に小さい上位5手 (Tier 1/2 の有望候補)
        # ※ 損失が大きい手はそもそも AI一致である可能性が低い
        analysis_targets = sorted_by_loss[:5]
        
        tier1_candidates = []
        tier2_candidates = []

        best_loss_idx = sorted_by_loss[0]['m_idx'] # Tier 3 Fallback

        for cand in analysis_targets:
            m_idx = cand['m_idx']
            loss = cand['loss']
            
            # あまりに損失が大きい場合は解析スキップ (例: 5%以上損している)
            if loss > 0.05: continue

            history = self.game.get_history_up_to(m_idx)
            try:
                # 前局面解析 (推奨手取得)
                history_prev = self.game.get_history_up_to(m_idx - 1)
                
                # AI解析実行
                res_prev = await asyncio.to_thread(api_client.analyze_move, history_prev, self.game.board_size)
                
                if res_prev and res_prev.candidates:
                    best_move_gtp = res_prev.candidates[0].move
                    
                    # 実戦の手を取得
                    actual_move_gtp = None
                    if history:
                        _, last_gtp = history[-1]
                        actual_move_gtp = last_gtp
                    
                    # 一致判定 (座標文字列の比較)
                    if best_move_gtp and actual_move_gtp and \
                       best_move_gtp.lower() == actual_move_gtp.lower():
                           
                        # 局面の緊急度判定
                        collector = await self._get_cached_analysis(history)
                        max_urgency = 0
                        for f in collector.facts:
                             if f.severity > max_urgency:
                                 max_urgency = f.severity
                        
                        cand_info = {'m_idx': m_idx, 'urgency': max_urgency}
                        
                        # Tier 判定 (Severity 4=CRITICAL is strict Urgent)
                        if max_urgency >= 4:
                             tier1_candidates.append(cand_info)
                        else:
                             tier2_candidates.append(cand_info)

            except Exception as e:
                logger.error(f"Good move analysis failed at {m_idx}: {e}", layer="REPORT")
                continue

        # Selection Logic
        
        # 1. Tier 1: Urgent & Match
        if tier1_candidates:
            tier1_candidates.sort(key=lambda x: (x['urgency'], x['m_idx']), reverse=True)
            logger.info(f"Selected Tier 1 Good Move: {tier1_candidates[0]}", layer="REPORT")
            return tier1_candidates[0]['m_idx']
            
        # 2. Tier 2: Match
        if tier2_candidates:
             tier2_candidates.sort(key=lambda x: x['m_idx'], reverse=True)
             logger.info(f"Selected Tier 2 Good Move: {tier2_candidates[0]}", layer="REPORT")
             return tier2_candidates[0]['m_idx']
             
        # 3. Tier 3: Lowest Loss (Fallback)
        logger.info(f"Selected Tier 3 Good Move (Lowest Loss): {best_loss_idx}", layer="REPORT")
        return best_loss_idx

    async def _process_good_move(self, m_idx, knowledge, r_dir, r_md, pdf_items):
        try:
            history = self.game.get_history_up_to(m_idx)
            collector = await self._get_cached_analysis(history)
            facts = collector.get_prioritized_text(limit=5)
            
            # 画像
            board = self.game.get_board_at(m_idx)
            
            # 着手箇所を特定して▲マークを付ける
            actual_marks = {"TR": []}
            if history:
                last_c, last_gtp = history[-1]
                if last_gtp and last_gtp.lower() != "pass":
                    idx = self.renderer.transformer.gtp_to_indices(last_gtp)
                    if idx:
                        actual_marks["TR"].append(idx)

            p_img = self.renderer.render(board, last_move=None, marks=actual_marks, analysis_text=f"Move {m_idx} (Good Move!)")
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
