import logging
import os
import sys
from datetime import datetime

class GoAILogger:
    """システム全体のロギングを統括するクラス"""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoAILogger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self):
        self.logger = logging.getLogger("GoAI")
        self.logger.setLevel(logging.DEBUG)
        
        # ログファイルのパス設定
        log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(log_dir, "system.log")
        
        # フォーマット定義: [時刻] [レイヤー] [レベル] メッセージ
        formatter = logging.Formatter(
            '[%(asctime)s] [%(layer)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # ファイル出力設定
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO) # ファイルにはINFO以上を記録

        # コンソール出力設定
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG) # コンソールには詳細も表示

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, level, message, layer="SYSTEM"):
        """共通ログ出力メソッド"""
        self.logger.log(level, message, extra={'layer': layer.upper()})

    def debug(self, message, layer="SYSTEM"):
        self.log(logging.DEBUG, message, layer)

    def info(self, message, layer="SYSTEM"):
        self.log(logging.INFO, message, layer)

    def warning(self, message, layer="SYSTEM"):
        self.log(logging.WARNING, message, layer)

    def error(self, message, layer="SYSTEM"):
        self.log(logging.ERROR, message, layer)

# Global Singleton Instance
logger = GoAILogger()
