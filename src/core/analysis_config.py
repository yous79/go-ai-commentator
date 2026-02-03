from typing import Dict, Any, Callable, List
from utils.logger import logger

class AnalysisConfig:
    """
    解析ロジックの閾値や設定パラメータを一元管理するシングルトンクラス。
    Observerパターンを実装し、設定変更を即座に通知する。
    """
    _instance = None
    _observers: List[Callable[[str, Any], None]] = []

    # デフォルト設定値
    _params: Dict[str, Any] = {
        # Stability / Strategy
        "ATSUMI_THRESHOLD": 0.90,       # 厚み認定のOwnership閾値 (0.0 - 1.0)
        "KASUISHI_THRESHOLD": -0.85,    # カス石認定のOwnership閾値 (-1.0 - 0.0)
        "WEAK_THRESHOLD": 0.5,          # 弱い石の境界線
        "CRITICAL_THRESHOLD": 0.2,      # 瀕死の石の境界線
        
        # Shape
        "SHAPE_SEVERITY_THRESHOLD": 4,  # 重大な悪形とみなすSeverity (1-5)
        
        # Influence
        "INFLUENCE_POWER_THRESHOLD": 1.2, # 厚みが影響力を発揮しているとみなす値
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalysisConfig, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get(cls, key: str) -> Any:
        return cls._params.get(key)

    @classmethod
    def set_param(cls, key: str, value: Any):
        if key in cls._params:
            if cls._params[key] != value:
                old_val = cls._params[key]
                cls._params[key] = value
                logger.debug(f"Config Updated: {key} {old_val} -> {value}", layer="CONFIG")
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
        return cls._params.copy()
