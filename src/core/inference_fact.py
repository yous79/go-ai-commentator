from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
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
class BaseFactMetadata:
    """事実の補足情報の基底クラス"""
    def to_dict(self) -> Dict[str, Any]:
        import dataclasses
        return dataclasses.asdict(self)

@dataclass
class ShapeMetadata(BaseFactMetadata):
    """形状（Shape）に関するメタデータ"""
    key: str                    # 手筋のキー（aki_sankaku等）
    remedy_gtp: Optional[str] = None # 解消地点（ある場合）
    all_remedies: List[str] = field(default_factory=list) # 複数の解消地点

@dataclass
class StabilityMetadata(BaseFactMetadata):
    """生存確率（Stability）に関するメタデータ"""
    status: str                 # dead, critical, weak, stable, strong
    stability: float            # 生存確率数値 (0.0 〜 1.0)
    stones: List[str]          # 対象となる石の座標リスト
    count: int                  # 石の数
    color_label: str            # 黒 または 白
    is_strategic: bool = False # 戦略的グループ（一塊）か
    uncertainty: float = 0.0   # 不確実性（味の悪さ）。高いほど未解決

@dataclass
class UrgencyMetadata(BaseFactMetadata):
    """緊急度（Urgency）に関するメタデータ"""
    urgency: float              # 緊急度の値（目数）
    is_critical: bool           # 急場判定フラグ
    next_player: str           # 手順予測の開始プレイヤー

@dataclass
class GamePhaseMetadata(BaseFactMetadata):
    """局面フェーズに関するメタデータ"""
    phase: str                  # endgame, early, mid

@dataclass
class KoMetadata(BaseFactMetadata):
    """コウに関するメタデータ"""
    type: str                   # ko_initiation, ko_resolution
    point: Optional[str] = None # コウの座標

@dataclass
class MistakeMetadata(BaseFactMetadata):
    """失着に関するメタデータ"""
    type: str                   # drop_winrate, drop_score, kasu_ishi_salvage, kasu_ishi_capture
    value: Optional[float] = None # スコアの下落幅
    winrate_drop: Optional[float] = None # 勝率の下落幅 (0.0 〜 1.0)

@dataclass
class AtsumiMetadata(BaseFactMetadata):
    """厚みに関するメタデータ"""
    stones: List[str]       # 石の座標
    strength: float         # 強度（安定度）
    influence_power: float  # 周囲への影響力
    direction: Optional[str] = None # 影響力が向いている主な方向

@dataclass
class MoyoMetadata(BaseFactMetadata):
    """模様に関するメタデータ"""
    points: List[str]       # 領域を構成する座標
    size: int               # 大きさ（目数）
    potential: float        # 地になる期待値（平均Ownership）
    label: str              # 黒模様 or 白模様

@dataclass
class InferenceFact:
    """解析によって得られた個別の『事実』を表すオブジェクト"""
    category: FactCategory
    description: str
    severity: int = 3 # 1 (低) 〜 5 (高)
    metadata: Union[Dict[str, Any], BaseFactMetadata] = field(default_factory=dict)
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

    def add(self, category: FactCategory, description: str, severity: int = 3, metadata: Optional[Union[Dict, BaseFactMetadata]] = None, scope: TemporalScope = TemporalScope.EXISTING, is_last_move: bool = False):
        # is_last_moveがTrueなら自動的にIMMEDIATEにマッピング（互換性）
        if is_last_move:
            scope = TemporalScope.IMMEDIATE
        fact = InferenceFact(category, description, severity, metadata or {}, scope, is_last_move)
        self.add_fact(fact)

    def add_fact(self, fact: InferenceFact):
        """既存の事実オブジェクトを追加し、更新イベントを発行する"""
        self.facts.append(fact)
        
        # リアルタイム表示用にイベントを発行
        from utils.event_bus import event_bus, AppEvents
        from utils.logger import logger
        logger.debug(f"Fact Discovered: [{fact.category.value}] {fact.description[:30]}...", layer="CORE")
        event_bus.publish(AppEvents.FACT_DISCOVERED, fact)


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

    def clear(self):
        self.facts = []

    def get_game_phase(self) -> str:
        """事実セットの中から局面フェーズ（終盤等）を特定して返す"""
        for f in self.facts:
            if isinstance(f.metadata, GamePhaseMetadata):
                return f.metadata.phase
            if isinstance(f.metadata, dict) and "phase" in f.metadata:
                return f.metadata["phase"]
        return "normal"
