import os
import json
from typing import Optional, List
from core.point import Point
from core.game_board import GameBoard, Color
from core.inference_fact import InferenceFact, FactCategory, TemporalScope, ShapeMetadata, MistakeMetadata
from core.shapes.generic_detector import GenericPatternDetector
from core.shapes.ponnuki import PonnukiDetector
from core.shapes.atari import AtariDetector, RyoAtariDetector
from config import KNOWLEDGE_DIR

class DetectionContext:
    """検知に必要な盤面コンテキストを一元管理するクラス"""
    def __init__(self, curr_board: GameBoard, prev_board: Optional[GameBoard], board_size: int, analysis_result=None):
        self.curr_board = curr_board
        self.prev_board = prev_board
        self.board_size = board_size
        self.analysis_result = analysis_result or {}
        self.last_move, self.last_color = self._find_last_move()

    def _find_last_move(self):
        """現在の盤面と直前の盤面を比較して最新の着手座標(Point)を特定する"""
        if self.prev_board is None:
            return None, None
        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(r, c)
                color = self.curr_board.get(p)
                if color and self.prev_board.is_empty(p):
                    return p, color
        return None, None

    def get_ownership(self, pt: Point):
        """指定座標のOwnershipを取得する (黒地: +1.0, 白地: -1.0)"""
        if not hasattr(self.analysis_result, 'ownership') or not self.analysis_result.ownership:
            return 0.0
        
        idx = pt.row * self.board_size + pt.col
        if 0 <= idx < len(self.analysis_result.ownership):
            return self.analysis_result.ownership[idx]
        return 0.0

class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size
        self.strategies = []
        self._load_generic_patterns()
        self._init_legacy_strategies()

    def _load_generic_patterns(self):
        """KNOWLEDGE_DIR から pattern.json を検索して GenericPatternDetector を初期化する"""
        if not os.path.exists(KNOWLEDGE_DIR): return
        for root, dirs, files in os.walk(KNOWLEDGE_DIR):
            if "pattern.json" in files:
                path = os.path.join(root, "pattern.json")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        pattern_def = json.load(f)
                        detector = GenericPatternDetector(pattern_def, self.board_size)
                        
                        # 優先度の設定 (rules.md に準拠)
                        if pattern_def.get("category") == "bad":
                            detector.priority = 100
                        elif detector.key == "kirichigai":
                            detector.priority = 90
                        elif detector.key in ["katatsugi", "kaketsugi"]:
                            detector.priority = 75
                        elif detector.key == "butsukari":
                            detector.priority = 60
                        elif detector.key in ["nobi", "narabi"]:
                            detector.priority = 30
                        elif detector.key == "tsuke":
                            detector.priority = 10
                        else:
                            detector.priority = 20
                            
                        self.strategies.append(detector)
                except Exception as e:
                    print(f"Failed to load pattern {path}: {e}")

    def _init_legacy_strategies(self):
        """動的解析が必要なレガシー（ハイブリッド）戦略を読み込む"""
        loaded_keys = {getattr(s, "key", "") for s in self.strategies}
        legacy_list = [
            (PonnukiDetector, "ponnuki", 100),
            (RyoAtariDetector, "ryo_atari", 98),
            (AtariDetector, "atari", 95)
        ]
        for cls, key, priority in legacy_list:
            if key not in loaded_keys:
                instance = cls(self.board_size)
                instance.priority = priority
                self.strategies.append(instance)

    def detect_facts(self, curr_board: GameBoard, prev_board: Optional[GameBoard] = None, analysis_result=None) -> List[InferenceFact]:
        """形状検知結果を InferenceFact のリストとして返す"""
        actual_size = curr_board.side
        context = DetectionContext(curr_board, prev_board, actual_size, analysis_result)
        facts = []
        labeled_coords = set()

        # 1. 戦略を優先度順にソート
        sorted_strategies = sorted(self.strategies, key=lambda s: getattr(s, "priority", 50), reverse=True)
        
        for strategy in sorted_strategies:
            orig_size = getattr(strategy, "board_size", 19)
            strategy.board_size = actual_size
            category, results = strategy.detect(context)
            strategy.board_size = orig_size
            
            severity = 4 if category in ["bad", "mixed"] else 2

            for res in results:
                # res は {"message": str, "metadata": ShapeMetadata} の形式を想定
                msg = res["message"]
                meta = res["metadata"]
                
                coord = context.last_move.to_gtp() if context.last_move else "unknown"
                if coord != "unknown" and coord in labeled_coords:
                    continue
                
                labeled_coords.add(coord)
                facts.append(InferenceFact(FactCategory.SHAPE, msg, severity, meta, scope=TemporalScope.IMMEDIATE))
        
        # 2. 過剰干渉の検知
        facts.extend(self._detect_inefficient_moves(context))
            
        return facts

    def _detect_inefficient_moves(self, context: DetectionContext) -> List[InferenceFact]:
        facts = []
        move_point = context.last_move
        move_color = context.last_color
        
        if not move_point or not move_color or not context.analysis_result:
            return []

        opp_color = move_color.opposite()
        OWNERSHIP_THRESHOLD = 0.8
        
        for adj in move_point.neighbors(context.board_size):
            stone = context.curr_board.get(adj)
            if stone == opp_color:
                owner_val = context.get_ownership(adj)
                is_dead = (move_color == Color.BLACK and owner_val > OWNERSHIP_THRESHOLD) or \
                          (move_color == Color.WHITE and owner_val < -OWNERSHIP_THRESHOLD)
                
                if is_dead:
                    facts.append(InferenceFact(
                        FactCategory.MISTAKE, 
                        "すでに死んでいる石（カス石）に対して手入れが行われました。",
                        severity=4,
                        metadata=MistakeMetadata(type="kasu_ishi_interference"),
                        scope=TemporalScope.IMMEDIATE
                    ))
                    break
        return facts

    def detect_ids(self, curr_board: GameBoard, prev_board: Optional[GameBoard] = None):
        """(Legacy互換) 検知された形状IDのリストを返す"""
        facts = self.detect_facts(curr_board, prev_board)
        # metadata は BaseFactMetadata オブジェクトか辞書
        keys = []
        for f in facts:
            if isinstance(f.metadata, ShapeMetadata):
                keys.append(f.metadata.key)
            elif isinstance(f.metadata, dict):
                keys.append(f.metadata.get("key", "unknown"))
        return list(set(keys))