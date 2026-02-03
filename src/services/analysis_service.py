import os
import hashlib
import dataclasses
import json
import time
import concurrent.futures
from typing import List, Dict, Optional, Any, Tuple
from sgfmill import sgf

from core.analysis_dto import AnalysisResult
from core.game_board import GameBoard, Color
from core.point import Point
from services.api_client import api_client
from utils.event_bus import event_bus, AppEvents
from utils.logger import logger
from config import OUTPUT_BASE_DIR

class AnalysisService:
    """
    解析の実行、キャッシュ管理、および結果通知を統括するサービス。
    UIやコントローラーは、このサービスを介してのみ解析をリクエストする。
    """
    def __init__(self, task_manager):
        self.task_manager = task_manager
        # キャッシュ: {history_hash: AnalysisResult}
        self._cache: Dict[str, AnalysisResult] = {}
        # インデックスベースのキャッシュ（SGF一括解析用）
        self._index_cache: List[Optional[AnalysisResult]] = []
        # 全体の勝率履歴（グラフ用）
        self._winrate_history: List[float] = []
        
        self.analyzing_sgf = False
        self._stop_requested = False

    def _get_history_hash(self, history: List[List[str]]) -> str:
        """着手履歴からユニークなハッシュ値を生成する"""
        return hashlib.md5(str(history).encode()).hexdigest()

    def request_analysis(self, history: List[List[str]], board_size: int = 19):
        """
        指定された履歴の解析をリクエストする。
        キャッシュがあれば即座にイベントを発行し、なければ非同期で取得する。
        """
        h_hash = self._get_history_hash(history)
        move_idx = len(history)
        
        # 1. キャッシュチェック
        if h_hash in self._cache:
            logger.debug(f"Analysis Cache Hit for move {move_idx}", layer="ANALYSIS_SERVICE")
            self._notify_result(self._cache[h_hash], move_idx)
            return

        # 2. 非同期で解析実行
        def _task():
            return api_client.analyze_move(history, board_size)

        def _on_success(result: Optional[AnalysisResult]):
            if result:
                self._cache[h_hash] = result
                self._notify_result(result, move_idx)
            else:
                logger.warning(f"Analysis failed for move {move_idx}", layer="ANALYSIS_SERVICE")

        self.task_manager.run_task(_task, on_success=_on_success)

    def _notify_result(self, result: AnalysisResult, move_idx: int):
        """解析結果をイベントバスに流す"""
        # UIが期待するデータ構造を作成
    def _notify_result(self, result: AnalysisResult, move_idx: int):
        """解析結果をイベントバスに流す"""
        # UIが期待するデータ構造を作成
        # STATE_UPDATED は GUI更新用として頻繁に使われるため、
        # 解析完了専用のイベントを発行して App側で確実にキャッチさせる
        event_bus.publish("ANALYSIS_RESULT_READY", {
            "result": result,
            "winrate_text": result.winrate_label,
            "score_text": f"{result.score_lead:.1f}",
            "winrate_history": self._winrate_history,
            "current_move": move_idx,
            "candidates": [dataclasses.asdict(c) for c in result.candidates]
        })

    def get_by_index(self, idx: int) -> Optional[AnalysisResult]:
        """指定された手数（インデックス）の解析結果を取得する"""
        if idx < len(self._index_cache):
            return self._index_cache[idx]
        return None

    def start_sgf_analysis(self, sgf_path: str, renderer: Any):
        """SGFファイルの一括解析を開始する"""
        if self.analyzing_sgf:
            self.stop_sgf_analysis()
        
        self.analyzing_sgf = True
        self._stop_requested = False
        
        def _task():
            self._run_bulk_analysis(sgf_path, renderer)
            return True

        self.task_manager.run_task(_task)

    def stop_sgf_analysis(self):
        """一括解析を停止する"""
        self._stop_requested = True
        self.analyzing_sgf = False

    def _run_bulk_analysis(self, path: str, renderer: Any):
        """バックグラウンドスレッドで実行される一括解析の実体"""
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            out_dir = os.path.join(OUTPUT_BASE_DIR, name)
            os.makedirs(out_dir, exist_ok=True)

            with open(path, "rb") as f:
                game = sgf.Sgf_game.from_bytes(f.read())
            board_size = game.get_size()
            
            nodes = []
            curr_node = game.get_root()
            while True:
                nodes.append(curr_node)
                try: curr_node = curr_node[0]
                except: break
            
            total_moves = len(nodes)
            event_bus.publish(AppEvents.STATUS_MSG_UPDATED, f"Loading SGF: {total_moves} moves")
            event_bus.publish("set_max", total_moves) # TODO: Move to AppEvents
            
            history = []
            temp_board = GameBoard(board_size)
            self._index_cache = [None] * total_moves
            self._winrate_history = [0.5] * total_moves
            
            # 1. 局面の事前構築
            all_moves_info = []
            for m_num, node in enumerate(nodes):
                color, move = node.get_move()
                if color and move:
                    c_obj = Color.from_str(color)
                    temp_board.play(Point(move[0], move[1]), c_obj)
                    cols = "ABCDEFGHJKLMNOPQRST"
                    history.append([c_obj.key.upper()[:1], cols[move[1]] + str(move[0]+1)])
                elif color: # pass
                    history.append(["B" if color == 'b' else "W", "pass"])
                
                all_moves_info.append({
                    "m_num": m_num,
                    "history": list(history),
                    "board_copy": temp_board.copy()
                })

            completed_count = 0
            
            # 2. 並列解析
            # 注: api_client.analyze_move は内部でリトライ等を行う
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(api_client.analyze_move, m["history"], board_size, include_pv=True): m 
                    for m in all_moves_info
                }
                
                for future in concurrent.futures.as_completed(futures):
                    if self._stop_requested: break
                    
                    move_info = futures[future]
                    m_num = move_info["m_num"]
                    
                    try:
                        result = future.result()
                        if result:
                            # キャッシュへの保存
                            self._index_cache[m_num] = result
                            h_hash = self._get_history_hash(move_info["history"])
                            self._cache[h_hash] = result
                            self._winrate_history[m_num] = result.winrate
                            
                            # 画像の保存（レンダラーを使用）
                            img_text = f"Move {m_num} | WR(B): {result.winrate_label} | Score(B): {result.score_lead:.1f}"
                            
                            # ヒートマップ用データの準備
                            render_kwargs = {"analysis_text": img_text, "history": move_info["history"]}
                            if result.ownership:
                                render_kwargs["ownership"] = result.ownership
                                
                            img = renderer.render(move_info["board_copy"], **render_kwargs)
                            img.save(os.path.join(out_dir, f"move_{m_num:03d}.png"))
                            
                            completed_count += 1
                            event_bus.publish(AppEvents.PROGRESS_UPDATED, completed_count)
                            event_bus.publish(AppEvents.STATUS_MSG_UPDATED, f"Analyzing: {completed_count}/{total_moves}")
                            
                            # リアルタイム更新のためにイベント発行
                            # NOTE: _notify_result は winrate_history 全体を使うが、マルチスレッド中は不完全かもしれない。
                            # しかし個別の結果通知としては十分。
                            event_bus.publish("ANALYSIS_RESULT_READY", {
                                "result": result,
                                "winrate_text": result.winrate_label,
                                "score_text": f"{result.score_lead:.1f}",
                                "winrate_history": list(self._winrate_history), # コピーを渡す
                                "current_move": m_num,
                                "candidates": [dataclasses.asdict(c) for c in result.candidates]
                            })
                    except Exception as e:
                        logger.error(f"Bulk Analysis Error at move {m_num}: {e}")

            # 解析データの永続化
            self._save_analysis_json(out_dir, board_size)
            
            self.analyzing_sgf = False
            event_bus.publish(AppEvents.STATUS_MSG_UPDATED, "Analysis Ready")
            event_bus.publish(AppEvents.ANALYSIS_COMPLETED)

        except Exception as e:
            logger.error(f"Critical error in bulk analysis: {e}")
            self.analyzing_sgf = False

    def _save_analysis_json(self, out_dir: str, board_size: int):
        """解析結果をJSONファイルとして保存する"""
        try:
            log_data = {
                "board_size": board_size,
                "moves": [dataclasses.asdict(r) if r else None for r in self._index_cache]
            }
            json_path = os.path.join(out_dir, "analysis.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save analysis.json: {e}")

    def generate_full_context_analysis(self, move_idx, history, board_size, gemini, simulator, visualizer):
        """
        解説生成、緊急度解析、および成功/失敗図の生成を一括して非同期で実行する。
        """
        import asyncio
        def _task():
            # asyncメソッドを同期コンテキストから呼び出すためのエントリーポイント
            async def _run_async():
                # 0. 1手前の解析結果をキャッシュから取得
                prev_result = None
                if len(history) > 1:
                    prev_history = history[:-1]
                    prev_hash = self._get_history_hash(prev_history)
                    if prev_hash in self._cache:
                         prev_result = self._cache[prev_hash]
                
                # 1. 解説生成 (内部で orchestrator.analyze_full を実行し、並列解析が行われる)
                # generate_commentary returns {"text": str, "collector": FactCollector}
                res = await gemini.generate_commentary(move_idx, history, board_size, prev_analysis=prev_result)
                commentary_text = res["text"]
                collector = res["collector"]
                
                # IMPORTANT: collector might be None if analysis failed
                if not collector:
                     # Fallback or error handling if needed, though generate_commentary handles errors gracefully usually
                     pass

                # Pre-calculate paths
                rec_path = None
                thr_path = None
                
                if collector:
                    # UrgencyMetadata を探す
                    from core.inference_fact import FactCategory, UrgencyMetadata
                    u_fact = next((f for f in collector.facts if f.category == FactCategory.URGENCY), None)
                    
                    if u_fact and isinstance(u_fact.metadata, UrgencyMetadata):
                        meta = u_fact.metadata
                        curr_ctx = collector.context
                    
                    # 成功図（最善進行）
                    best_pv = collector.raw_analysis.candidates[0].pv if collector.raw_analysis.candidates else []
                    if best_pv:
                        rec_ctx = simulator.simulate_sequence(curr_ctx, best_pv)
                        rec_path, _ = visualizer.visualize_context(rec_ctx, title="AI Recommended Success Plan")
                    
                    # 失敗図（放置被害）
                    if meta.is_critical:
                        # UrgencyFactProvider が内部で既に分析している opponent_pv を取得したいが、
                        # 現状 metadata には含まれていないため、必要なら provider を拡張して保持させる。
                        # ここでは簡単のため、再度取得（非同期なので速い）
                        urgency_data = await asyncio.to_thread(api_client.analyze_urgency, history, board_size)
                        opp_pv = urgency_data.get("opponent_pv", [])
                        if opp_pv:
                            thr_seq = ["pass"] + opp_pv
                            thr_ctx = simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=meta.next_player)
                            title = f"Future Threat Diagram (Potential Loss: {meta.urgency:.1f})"
                            thr_path, _ = visualizer.visualize_context(thr_ctx, title=title)

                return {
                    "text": commentary_text,
                    "rec_path": rec_path,
                    "thr_path": thr_path
                }

            return asyncio.run(_run_async())

        def _on_success(res):
            # 結果をイベントバスに通知
            event_bus.publish(AppEvents.COMMENTARY_READY, res["text"])
            if res["rec_path"] or res["thr_path"]:
                event_bus.publish("AI_DIAGRAMS_READY", res)

        self.task_manager.run_task(_task, on_success=_on_success)
