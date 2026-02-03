from typing import Dict, Any, Callable, List
import json
import os
from utils.logger import logger

class AnalysisConfig:
    """
    解析ロジックの閾値や設定パラメータを一元管理するシングルトンクラス。
    Observerパターンを実装し、設定変更を即座に通知する。
    """
    _instance = None
    _observers: List[Callable[[str, Any], None]] = []
    
    # プロジェクトルート/config/analysis_settings.json を絶対パスで指定
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _config_file = os.path.join(_base_dir, "config", "analysis_settings.json")
    
    _initialized = False

    # デフォルト設定値
    _params: Dict[str, Any] = {
        # Stability / Strategy
        "ATSUMI_THRESHOLD": 0.90,       # 厚み認定のOwnership閾値 (0.0 - 1.0)
        "CRITICAL_THRESHOLD": 0.2,      # 死に体（及びカス石）の境界線
        "WEAK_THRESHOLD": 0.5,          # 弱い石の境界線
        "MISTAKE_LOSS_THRESHOLD": 2.0,  # カス石と呼ぶための最小目数損失
        
        # Shape
        "SHAPE_SEVERITY_THRESHOLD": 4,  # 重大な悪形とみなすSeverity (1-5)
        
        # Influence
        "INFLUENCE_POWER_THRESHOLD": 1.2, # 厚みが影響力を発揮しているとみなす値
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalysisConfig, cls).__new__(cls)
            cls._ensure_loaded()
        return cls._instance

    @classmethod
    def _ensure_loaded(cls):
        if not cls._initialized:
            cls.load()
            cls._initialized = True

    @classmethod
    def load(cls):
        """設定ファイルからパラメータを読み込む"""
        if os.path.exists(cls._config_file):
            try:
                with open(cls._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in cls._params:
                            cls._params[k] = v
                logger.info(f"AnalysisConfig loaded from {cls._config_file}", layer="CONFIG")
            except Exception as e:
                logger.error(f"Failed to load AnalysisConfig: {e}", layer="CONFIG")

    @classmethod
    def save(cls):
        """現在のパラメータを設定ファイルに保存する"""
        try:
            os.makedirs(os.path.dirname(cls._config_file), exist_ok=True)
            with open(cls._config_file, "w", encoding="utf-8") as f:
                json.dump(cls._params, f, indent=4, ensure_ascii=False)
            logger.debug(f"AnalysisConfig saved to {cls._config_file}", layer="CONFIG")
        except Exception as e:
            logger.error(f"Failed to save AnalysisConfig: {e}", layer="CONFIG")

    @classmethod
    def get(cls, key: str) -> Any:
        cls._ensure_loaded()
        return cls._params.get(key)

    @classmethod
    def set_param(cls, key: str, value: Any):
        cls._ensure_loaded()
        if key in cls._params:
            if cls._params[key] != value:
                old_val = cls._params[key]
                cls._params[key] = value
                logger.debug(f"Config Updated: {key} {old_val} -> {value}", layer="CONFIG")
                cls.save()
                cls._notify(key, value)
        else:
            logger.warning(f"Unknown config key: {key}", layer="CONFIG")

    @classmethod
    def add_observer(cls, callback: Callable[[str, Any], None]):
        cls._observers.append(callback)

    @classmethod
    def remove_observer(cls, callback: Callable[[str, Any], None]):
        if callback in cls._observers:
            cls._observers.remove(callback)

    @classmethod
    def _notify(cls, key: str, value: Any):
        for callback in cls._observers:
            try:
                callback(key, value)
            except Exception as e:
                logger.error(f"Error in config observer: {e}", layer="CONFIG")

    @classmethod
    def get_all_params(cls) -> Dict[str, Any]:
        cls._ensure_loaded()
        return cls._params.copy()
