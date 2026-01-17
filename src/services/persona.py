from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePersona(ABC):
    """解説人格の基底クラス"""
    
    @property
    @abstractmethod
    def level_id(self) -> str:
        """レベルの識別子 (beginner, intermediate等)"""
        pass

    @property
    @abstractmethod
    def system_template(self) -> str:
        """システムプロンプトのテンプレート名"""
        pass

    @property
    @abstractmethod
    def report_template(self) -> str:
        """個別レポートのテンプレート名"""
        pass

class BeginnerPersona(BasePersona):
    """初心者・二桁級向けの優しい人格"""
    @property
    def level_id(self) -> str: return "beginner"
    
    @property
    def system_template(self) -> str: return "go_instructor_system_beginner"
    
    @property
    def report_template(self) -> str: return "report_individual_beginner"

class IntermediatePersona(BasePersona):
    """中級者・一桁級向けの論理的な人格"""
    @property
    def level_id(self) -> str: return "intermediate"
    
    @property
    def system_template(self) -> str: return "go_instructor_system"
    
    @property
    def report_template(self) -> str: return "report_individual"

class PersonaFactory:
    """設定に応じて適切なPersonaインスタンスを生成するファクトリ"""
    _personas = {
        "beginner": BeginnerPersona(),
        "intermediate": IntermediatePersona()
    }

    @classmethod
    def get_persona(cls, level: str) -> BasePersona:
        return cls._personas.get(level, cls._personas["intermediate"])
