import os
import json
from PIL import Image
from services.api_client import GoAPIClient
from utils.logger import logger

class AppController:
    """アプリケーションの状態管理とロジックを担当するController"""
    
    def __init__(self, game_state):
        self.game = game_state
        self.api_client = GoAPIClient()
        self.current_move = 0
        self.image_cache = {}
        self.image_dir = None
        self.current_sgf_name = "unknown"

    def set_image_dir(self, path):
        self.image_dir = path
        self.image_cache = {}
        logger.info(f"Image directory set to: {path}", layer="CONTROLLER")

    def get_current_image(self):
        """現在の画像を取得し、必要ならロード・キャッシュする"""
        if not self.image_dir: return None
        
        n = self.current_move
        if n in self.image_cache:
            return self.image_cache[n]
            
        p = os.path.join(self.image_dir, f"move_{n:03d}.png")
        if os.path.exists(p):
            try:
                img = Image.open(p)
                img.load()
                self.image_cache[n] = img
                logger.debug(f"Loaded and cached image for move {n}", layer="CONTROLLER")
                return img
            except Exception as e:
                logger.error(f"Failed to load image {p}: {e}", layer="CONTROLLER")
                return None
        return None

    def sync_state_to_api(self):
        """現在の状態をAPIサーバーへ同期"""
        logger.debug(f"Syncing state to API at move {self.current_move}", layer="CONTROLLER")
        history = self.game.get_history_up_to(self.current_move)
        # 直近10手に制限して負荷軽減（Rev 18.0の方針を継承）
        history_mini = history[-10:] if len(history) > 10 else history
        
        metadata = self.game.get_metadata()
        state = {
            "history": history_mini,
            "current_move_index": self.current_move,
            "total_moves": self.game.total_moves,
            "metadata": metadata
        }
        self.api_client.sync_game_state(state)

    def next_move(self):
        if self.current_move < self.game.total_moves:
            self.current_move += 1
            self.sync_state_to_api()
            return True
        return False

    def prev_move(self):
        if self.current_move > 0:
            self.current_move -= 1
            self.sync_state_to_api()
            return True
        return False

    def jump_to_move(self, n):
        if 0 <= n <= self.game.total_moves:
            self.current_move = n
            self.sync_state_to_api()
            return True
        return False
