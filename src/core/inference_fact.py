from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class FactCategory(Enum):
    SHAPE = "shape"           # 幾何学的な形（アキ三角など）
    STABILITY = "stability"   # 石の生存確率（安定度）
    URGENCY = "urgency"       # 着手の緊急性（温度）
    STRATEGY = "strategy"     # 大局的な戦略（地の境界など）
    MISTAKE = "mistake"       # 明らかな失着（評価値の下落）

@dataclass
class InferenceFact:
    """解析によって得られた個別の『事実』を表すオブジェクト"""
    category: FactCategory
    description: str
    severity: int = 3 # 1 (低) 〜 5 (高)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def format_for_ai(self) -> str:
        """AI（Gemini）への提示用テキストに変換"""
        prefix = "⚠️" if self.severity >= 4 else "•"
        return f"{prefix} {self.description}"

class FactCollector:
    """複数の事実を集約し、優先順位付け（トリアージ）を行うクラス"""
    def __init__(self):
        self.facts: List[InferenceFact] = []

    def add(self, category: FactCategory, description: str, severity: int = 3, metadata: Optional[Dict] = None):
        self.facts.append(InferenceFact(category, description, severity, metadata or {}))

    def get_prioritized_text(self, limit: int = 10) -> str:
        """重要度（severity）順にソートし、AI用のサマリーテキストを生成する"""
        if not self.facts:
            return "(特筆すべき事実は検出されませんでした)"

        # 重要度降順、次にカテゴリ順でソート
        sorted_facts = sorted(self.facts, key=lambda x: (x.severity, x.category.value), reverse=True)
        
        # 制限数以内でサマリー作成
        output = []
        for f in sorted_facts[:limit]:
            output.append(f.format_for_ai())
            
        return "\n".join(output)

    def clear(self):
        self.facts = []
