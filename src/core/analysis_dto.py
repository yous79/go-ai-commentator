from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass(frozen=True)
class MoveCandidate:
    """個別の候補手とその解析データ"""
    move: str
    winrate: float
    score_lead: float
    score_loss: float = 0.0
    pv: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MoveCandidate':
        """KataGoの候補手辞書からオブジェクトを生成"""
        return cls(
            move=d.get('move', 'pass'),
            winrate=d.get('winrate', d.get('winrate_black', 0.5)),
            score_lead=d.get('scoreLead', d.get('score_lead_black', 0.0)),
            score_loss=d.get('scoreLoss', 0.0),
            pv=d.get('pv', [])
        )

@dataclass(frozen=True)
class AnalysisResult:
    """ある局面全体の解析結果"""
    winrate: float
    score_lead: float
    ownership: Optional[List[float]] = None
    influence: Optional[List[float]] = None
    candidates: List[MoveCandidate] = field(default_factory=list)
    
    @property
    def best_move(self) -> Optional[str]:
        return self.candidates[0].move if self.candidates else None

    @property
    def winrate_label(self) -> str:
        return f"{self.winrate:.1%}"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'AnalysisResult':
        """KataGoの解析レスポンス辞書からオブジェクトを生成"""
        if not d:
            return cls(winrate=0.5, score_lead=0.0)
            
        # raw dataの取得 (rootInfo または 直下のキー)
        root = d.get('rootInfo', d)
        
        # 候補手のリスト化
        raw_cands = d.get('top_candidates', []) or d.get('candidates', [])
        candidates = [MoveCandidate.from_dict(c) for c in raw_cands]
        
        return cls(
            winrate=root.get('winrate', root.get('winrate_black', 0.5)),
            score_lead=root.get('scoreLead', root.get('score_lead_black', 0.0)),
            ownership=d.get('ownership'),
            influence=d.get('influence'),
            candidates=candidates
        )
