from typing import List, Dict, Optional, Any
import hashlib
import dataclasses
from core.analysis_dto import AnalysisResult
from services.api_client import api_client
from utils.event_bus import event_bus, AppEvents
from utils.logger import logger
from core.point import Point

class AnalysisService:
    """
    解析の実行、キャッシュ管理、および結果通知を統括するサービス。
    UIやコントローラーは、このサービスを介してのみ解析をリクエストする。
    """
    def __init__(self, task_manager):
        self.task_manager = task_manager
        # キャッシュ: {history_hash: AnalysisResult}
        self._cache: Dict[str, AnalysisResult] = {}
        # 全体の勝率履歴（グラフ用）
        self._winrate_history: List[float] = []

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
        event_bus.publish(AppEvents.STATE_UPDATED, {
            "result": result,
            "winrate_text": result.winrate_label,
            "score_text": f"{result.score_lead:.1f}",
            "winrate_history": self._winrate_history, # TODO: 履歴の動的生成
            "current_move": move_idx,
            "candidates": [dataclasses.asdict(c) for c in result.candidates]
        })

    def inject_results(self, moves_data: List[Any], board_size: int = 19):
        """バッチ解析結果（リスト）を一括でキャッシュに注入する"""
        logger.info(f"Injecting {len(moves_data)} results into AnalysisService cache.", layer="ANALYSIS_SERVICE")
        self._index_cache = moves_data 

    def get_by_index(self, idx: int) -> Optional[AnalysisResult]:
        """
        指定された手数（インデックス）の解析結果を取得する。
        """
        if not hasattr(self, '_index_cache') or idx >= len(self._index_cache):
            return None
            
        data = self._index_cache[idx]
        if not data: return None
        
        if isinstance(data, AnalysisResult):
            return data
        return AnalysisResult.from_dict(data)

    def generate_full_context_analysis(self, move_idx, history, board_size, gemini, simulator, visualizer):
        """
        解説生成、緊急度解析、および成功/失敗図の生成を一括して非同期で実行する。
        """
        def _task():
            # 1. 解説生成
            commentary_text = gemini.generate_commentary(move_idx, history, board_size)
            
            # 2. 緊急度解析
            urgency_data = api_client.analyze_urgency(history, board_size)
            
            rec_path = None
            thr_path = None
            
            if urgency_data:
                curr_ctx = simulator.reconstruct_to_context(history, board_size)
                
                # 成功図（最善進行）
                best_pv = urgency_data.get("best_pv", [])
                if best_pv:
                    rec_ctx = simulator.simulate_sequence(curr_ctx, best_pv)
                    rec_path, _ = visualizer.visualize_context(rec_ctx, title="AI Recommended Success Plan")
                
                # 失敗図（放置被害）
                if urgency_data.get("is_critical"):
                    opp_pv = urgency_data.get("opponent_pv", [])
                    if opp_pv:
                        thr_seq = ["pass"] + opp_pv
                        thr_ctx = simulator.simulate_sequence(curr_ctx, thr_seq, starting_color=urgency_data['next_player'])
                        title = f"Future Threat Diagram (Potential Loss: {urgency_data['urgency']:.1f})"
                        thr_path, _ = visualizer.visualize_context(thr_ctx, title=title)

            return {
                "text": commentary_text,
                "rec_path": rec_path,
                "thr_path": thr_path
            }

        def _on_success(res):
            # 結果をイベントバスに通知 (UI側でポップアップ等を行う)
            event_bus.publish(AppEvents.COMMENTARY_READY, res["text"])
            # 特殊な結果（画像パス）は追加データとして送るか、別のイベントにする
            if res["rec_path"] or res["thr_path"]:
                event_bus.publish("AI_DIAGRAMS_READY", res)

        self.task_manager.run_task(_task, on_success=_on_success)
