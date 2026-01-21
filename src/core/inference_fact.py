from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class FactCategory(Enum):
    SHAPE = "shape"           # 幾何学的な形（アキ三角など）
    STABILITY = "stability"   # 石の生存確率（安定度）
    URGENCY = "urgency"       # 着手の緊急性（温度）
    STRATEGY = "strategy"     # 大局的な戦略（地の境界など）
    MISTAKE = "mistake"       # 明らかな失着（評価値の下落）

class TemporalScope(Enum):
    IMMEDIATE = "immediate"   # まさに最新の手（最終手）によって生じたこと
    EXISTING = "existing"     # 盤上に以前から存在し続けている状態
    PREDICTED = "predicted"   # 将来の予測図（PV）の中で発生すること

@dataclass
class InferenceFact:
    """解析によって得られた個別の『事実』を表すオブジェクト"""
    category: FactCategory
    description: str
    severity: int = 3 # 1 (低) 〜 5 (高)
    metadata: Dict[str, Any] = field(default_factory=dict)
    scope: TemporalScope = TemporalScope.EXISTING # デフォルトは既存の状態
    is_last_move: bool = False # (非推奨：scopeへの移行推奨)
    
    def format_for_ai(self) -> str:
        """AI（Gemini）への提示用テキストに変換"""
        prefix = "⚠️" if self.severity >= 4 else "•"
        # 予測事実にはそれとわかる接頭辞を付ける
        scope_prefix = "[予測] " if self.scope == TemporalScope.PREDICTED else ""
        return f"{prefix} {scope_prefix}{self.description}"

class FactCollector:
    """複数の事実を集約し、優先順位付け（トリアージ）を行うクラス"""
    def __init__(self):
        self.facts: List[InferenceFact] = []

    def add(self, category: FactCategory, description: str, severity: int = 3, metadata: Optional[Dict] = None, scope: TemporalScope = TemporalScope.EXISTING, is_last_move: bool = False):
        # is_last_moveがTrueなら自動的にIMMEDIATEにマッピング（互換性）
        if is_last_move:
            scope = TemporalScope.IMMEDIATE
        self.facts.append(InferenceFact(category, description, severity, metadata or {}, scope, is_last_move))

    def get_by_scope(self, scope: TemporalScope) -> List[InferenceFact]:
        """指定された時間軸の事実のみを抽出する"""
        return [f for f in self.facts if f.scope == scope]

    def get_scope_summary(self, scope: TemporalScope) -> str:
        """特定スコープの事実をテキスト化する"""
        facts = self.get_by_scope(scope)
        if not facts:
            return ""
        # 重要度順にソート
        sorted_facts = sorted(facts, key=lambda x: x.severity, reverse=True)
        return "\n".join([f.format_for_ai() for f in sorted_facts])

    def get_last_move_summary(self) -> str:
        """最新手（IMMEDIATE）に関する事実のみを抽出してテキスト化する"""
        summary = self.get_scope_summary(TemporalScope.IMMEDIATE)
        return summary if summary else "(最新手に関する特筆すべき指摘事項はありません)"

    def get_prioritized_text(self, limit: int = 10) -> str:
        """既存の状態（EXISTING）に関する重要な事実を抽出する"""
        existing_facts = self.get_by_scope(TemporalScope.EXISTING)
        if not existing_facts:
            return "(局面全体に関する特筆すべき事実は検出されませんでした)"

        # 重要度降順、次にカテゴリ順でソート
        sorted_facts = sorted(existing_facts, key=lambda x: (x.severity, x.category.value), reverse=True)
        
        output = []
        for f in sorted_facts[:limit]:
            output.append(f.format_for_ai())
            
        return "\n".join(output)
        
        # 制限数以内でサマリー作成
        output = []
        for f in sorted_facts[:limit]:
            output.append(f.format_for_ai())
            
        return "\n".join(output)

    def clear(self):
        self.facts = []

    def get_game_phase(self) -> str:
        """事実セットの中から局面フェーズ（終盤等）を特定して返す"""
        for f in self.facts:
            if "phase" in f.metadata:
                return f.metadata["phase"]
        return "normal"
