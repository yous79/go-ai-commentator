from typing import List, Dict, Optional, Any
import hashlib
import dataclasses
from core.analysis_dto import AnalysisResult
from services.api_client import api_client
from utils.event_bus import event_bus, AppEvents
from utils.logger import logger

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
        
        # 履歴を1手ずつ再現しながらハッシュを生成して格納
        history = []
        for i, data in enumerate(moves_data):
            if not data: continue
            
            # 履歴の更新
            color = "B" if i % 2 != 0 else "W" # 1手目は黒
            if i == 0: color = "W" # 0手目（初期盤面）は便宜上白の後の黒番とみなす？ 
            # 実際には SGF からの情報を元にするのが正確だが、ここでは簡易化
            
            # AnalysisResultへの変換
            if not isinstance(data, AnalysisResult):
                res_obj = AnalysisResult.from_dict(data)
            else:
                res_obj = data
            
            # ハッシュ登録 (ここでは本来のhistoryが必要だが、
            # 簡易的にインデックスでも管理できるようにするか検討)
            # とりあえず、現在の手順から逆算して登録を試みる
            pass

        # 暫定：インデックスベースの高速アクセス用
        self._index_cache = moves_data 

    def get_by_index(self, idx: int) -> Optional[AnalysisResult]:
        """インデックスによる取得（バッチ解析データ用）"""
        if hasattr(self, '_index_cache') and idx < len(self._index_cache):
            data = self._index_cache[idx]
            if not data: return None
            return data if isinstance(data, AnalysisResult) else AnalysisResult.from_dict(data)
        return None
