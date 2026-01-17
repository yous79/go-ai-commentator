import requests
import threading
import concurrent.futures
import time
from enum import Enum
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import logger
from core.analysis_dto import AnalysisResult

class CircuitState(Enum):
    CLOSED = "CLOSED"      # 正常：リクエストを許可
    OPEN = "OPEN"          # 遮断：リクエストを即座に拒否
    HALF_OPEN = "HALF_OPEN" # 試験的：1回だけリクエストを試行

class CircuitBreaker:
    """API通信の安定性を守る遮断機"""
    def __init__(self, failure_threshold=3, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self._lock = threading.Lock()

    def can_execute(self):
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            # OPEN状態の場合、一定時間経過していればHALF_OPENとして試行を許可
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    logger.info("Circuit Breaker: Entering HALF_OPEN state (test recovery)", layer="API_CLIENT")
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            
            # HALF_OPEN状態は1つのリクエストのみ許可（簡易的な制御）
            return self.state == CircuitState.HALF_OPEN

    def record_success(self):
        with self._lock:
            if self.state != CircuitState.CLOSED:
                logger.info(f"Circuit Breaker: Recovered to CLOSED from {self.state.value}", layer="API_CLIENT")
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.error(f"Circuit Breaker: OPENED due to {self.failure_count} consecutive failures", layer="API_CLIENT")
                self.state = CircuitState.OPEN
            else:
                logger.warning(f"Circuit Breaker: Failure recorded ({self.failure_count}/{self.failure_threshold})", layer="API_CLIENT")

class GoAPIClient:
    """APIサーバー（katago_api）との通信を専門に扱うクラス（シングルトン推奨）"""
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GoAPIClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, base_url="http://127.0.0.1:8000"):
        if hasattr(self, '_initialized'): return
        self.base_url = base_url
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self._is_syncing = False
        self.breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        # 堅牢なリトライ設定
        # サーキットブレーカーで管理するため、HTTPレイヤーのリトライは無効化または最小限にする
        retry_strategy = Retry(
            total=0, 
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self._initialized = True

    def _safe_request(self, method, endpoint, **kwargs):
        """サーキットブレーカーを考慮した安全なリクエスト実行"""
        if not self.breaker.can_execute():
            return None, "CIRCUIT_OPEN"

        try:
            url = f"{self.base_url}/{endpoint}"
            timeout = kwargs.pop('timeout', 10)
            
            resp = self.session.request(method, url, timeout=timeout, **kwargs)
            
            if resp.status_code == 200:
                self.breaker.record_success()
                return resp, None
            else:
                logger.error(f"API HTTP Error: {resp.status_code} at {endpoint}", layer="API_CLIENT")
                self.breaker.record_failure()
                return None, f"HTTP_{resp.status_code}"
        except Exception as e:
            logger.error(f"API Connection Failed at {endpoint}: {e}", layer="API_CLIENT")
            self.breaker.record_failure()
            return None, "CONNECTION_FAILED"

    def health_check(self):
        """サーバーの生存確認"""
        resp, err = self._safe_request("GET", "health", timeout=2)
        return resp is not None

    def sync_game_state(self, state_data):
        """現在の対局状態を非同期でAPIサーバーへ送信する"""
        if self._is_syncing: return
        if not self.breaker.can_execute(): return
        
        def _send():
            self._is_syncing = True
            try:
                self._safe_request("POST", "game/state", json=state_data, timeout=3)
            except: pass
            finally: self._is_syncing = False

        self.executor.submit(_send)

    def analyze_move(self, history, board_size=19, visits=150, include_pv=True) -> Optional[AnalysisResult]:
        """特定の手の解析リクエストを行い、AnalysisResultオブジェクトを返す"""
        payload = {
            "history": history,
            "board_size": board_size,
            "visits": visits,
            "include_pv_shapes": include_pv,
            "include_ownership": True
        }
        logger.debug(f"Requesting analysis: history_len={len(history)}, visits={visits}", layer="API_CLIENT")
        resp, err = self._safe_request("POST", "analyze", json=payload, timeout=60)
        
        if resp:
            data = resp.json()
            result = AnalysisResult.from_dict(data)
            logger.debug(f"Analysis response received: candidates={len(result.candidates)}, has_ownership={result.ownership is not None}", layer="API_CLIENT")
            return result
        elif err == "CIRCUIT_OPEN":
            logger.warning("Analysis skipped: Circuit Breaker is OPEN.", layer="API_CLIENT")
        return None

    def analyze_urgency(self, history, board_size=19, visits=150):
        """着手の緊急度（温度）を算出し、推奨手順と放置時の被害手順の両方を取得する"""
        logger.debug(f"Urgency Check Start: history_len={len(history)}", layer="API_CLIENT")
        
        # 1. 現在の局面の解析（最善手PVを取得）
        current_res = self.analyze_move(history, board_size, visits, include_pv=True)
        if not current_res: 
            return None

        # 自分の最善手のPVを取得
        best_pv = current_res.candidates[0].pv[:3] if current_res.candidates else []

        # 2. パスをした局面の解析（相手の連打PVを取得）
        color = "W" if history and history[-1][0] == "B" else "B"
        pass_history = history + [[color, "pass"]]
        pass_res = self.analyze_move(pass_history, board_size, visits, include_pv=True)
        if not pass_res: 
            return None

        score_normal = current_res.score_lead
        score_pass = pass_res.score_lead
        urgency = abs(score_normal - score_pass)
        
        # 相手の連打手順を取得
        opponent_pv = pass_res.candidates[0].pv[:3] if pass_res.candidates else []

        logger.debug(f"Urgency Results: best_pv={best_pv}, opponent_pv={opponent_pv}", layer="API_CLIENT")

        return {
            "urgency": urgency,
            "score_normal": score_normal,
            "score_pass": score_pass,
            "is_critical": urgency > 10.0,
            "best_pv": best_pv,      # 成功図用の手順
            "opponent_pv": opponent_pv, # 失敗図用の手順
            "next_player": color
        }

    def detect_shapes(self, history):
        """形状検知リクエスト"""
        logger.debug("Requesting shape detection", layer="API_CLIENT")
        resp, err = self._safe_request("POST", "detect", json={"history": history}, timeout=10)
        
        if resp:
            return resp.json().get("facts", "特筆すべき形状は検出されませんでした。")
        elif err == "CIRCUIT_OPEN":
            return "APIサーバーが一時停止中のため、形状検知をスキップしました。"
        return "検知エラーが発生しました。"

    def detect_shape_ids(self, history):
        """形状ID検知リクエスト"""
        logger.debug("Requesting shape ID detection", layer="API_CLIENT")
        resp, err = self._safe_request("POST", "detect/ids", json={"history": history}, timeout=10)
        
        if resp:
            return resp.json().get("ids", [])
        return []

    def get_game_state(self):
        """現在の対局状態（同期されているもの）を取得"""
        resp, err = self._safe_request("GET", "game/state", timeout=3)
        if resp:
            return resp.json()
        return None

# Global Singleton Instance
api_client = GoAPIClient()

# Global Singleton Instance
api_client = GoAPIClient()
