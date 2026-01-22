import os
import sys
import subprocess
import time
import requests
from utils.process_manager import kill_process_on_port, kill_legacy_katago
from utils.logger import logger

class BootstrapService:
    """APIサーバーの起動やプロセス管理を担当するサービス"""
    
    @staticmethod
    def start_api_server(src_dir: str):
        """APIサーバーをクリーンな状態で自動起動し、準備ができるまで待機する"""
        logger.info("System Startup: Initializing Intelligence Infrastructure", layer="STARTUP")
        kill_process_on_port(8000)
        kill_legacy_katago()
        
        api_script = os.path.join(src_dir, "katago_api.py")
        log_file_path = os.path.join(src_dir, "api_server.log")
        
        # サーバーをバックグラウンド起動
        logger.info(f"Launching API Server: {api_script}", layer="STARTUP")
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            proc = subprocess.Popen([sys.executable, api_script], 
                                    stdout=log_file, stderr=log_file, 
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        # サーバーの準備ができるまで待機
        for i in range(20):
            try:
                resp = requests.get("http://127.0.0.1:8000/health", timeout=1)
                if resp.status_code == 200:
                    logger.info("API Server is Ready.", layer="STARTUP")
                    return proc
            except:
                time.sleep(1)
                if i % 5 == 0: logger.info(f"Waiting for API server to initialize... ({i}s)", layer="STARTUP")
                
        logger.warning("API Server startup timed out. Proceeding anyway...", layer="STARTUP")
        return proc
