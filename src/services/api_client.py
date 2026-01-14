import requests
import threading
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import logger

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
        
        # 堅牢なリトライ設定
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self._initialized = True

    def health_check(self):
        """サーバーの生存確認"""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def sync_game_state(self, state_data):
        """現在の対局状態を非同期でAPIサーバーへ送信する"""
        if self._is_syncing: return
        
        def _send():
            self._is_syncing = True
            try:
                self.session.post(f"{self.base_url}/game/state", json=state_data, timeout=3)
            except: pass
            finally: self._is_syncing = False

        self.executor.submit(_send)

    def analyze_move(self, history, board_size=19, visits=100, include_pv=True):
        """特定の手の解析リクエスト"""
        payload = {
            "history": history,
            "board_size": board_size,
            "visits": visits,
            "include_pv_shapes": include_pv
        }
        try:
            logger.debug(f"Requesting analysis (Visits: {visits}, PV: {include_pv})", layer="API_CLIENT")
            resp = self.session.post(f"{self.base_url}/analyze", json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"API Error: {resp.status_code}", layer="API_CLIENT")
        except Exception as e:
            logger.error(f"HTTP Connection Failed: {e}", layer="API_CLIENT")
        return None

    def detect_shapes(self, history):
        """形状検知リクエスト"""
        try:
            logger.debug("Requesting shape detection", layer="API_CLIENT")
            resp = self.session.post(f"{self.base_url}/detect", json={"history": history}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("facts", "特筆すべき形状は検出されませんでした。")
        except Exception as e:
            logger.error(f"Shape Detection Request Failed: {e}", layer="API_CLIENT")
        return "検知エラーが発生しました。"

    def detect_shape_ids(self, history):
        """形状ID検知リクエスト"""
        try:
            logger.debug("Requesting shape ID detection", layer="API_CLIENT")
            resp = self.session.post(f"{self.base_url}/detect/ids", json={"history": history}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("ids", [])
        except Exception as e:
            logger.error(f"Shape ID Detection Request Failed: {e}", layer="API_CLIENT")
        return []

    def get_game_state(self):
        """現在の対局状態（同期されているもの）を取得"""
        try:
            resp = self.session.get(f"{self.base_url}/game/state", timeout=3)
            if resp.status_code == 200:
                return resp.json()
        except: pass
        return None

# Global Singleton Instance
api_client = GoAPIClient()
