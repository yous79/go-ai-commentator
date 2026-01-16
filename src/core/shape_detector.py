from core.point import Point
from core.inference_fact import InferenceFact, FactCategory
from core.shapes.generic_detector import GenericPatternDetector
from core.shapes.ponnuki import PonnukiDetector
import os
import json
from config import KNOWLEDGE_DIR

class DetectionContext:
    """検知に必要な盤面コンテキストを一元管理するクラス"""
    def __init__(self, curr_board, prev_board, board_size):
        self.curr_board = curr_board
        self.prev_board = prev_board
        self.board_size = board_size
        self.last_move, self.last_color = self._find_last_move()

    def _find_last_move(self):
        """現在の盤面と直前の盤面を比較して最新の着手座標(Point)を特定する"""
        if self.prev_board is None:
            return None, None
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.curr_board.get(r, c) and not self.prev_board.get(r, c):
                    return Point(r, c), self.curr_board.get(r, c)
        return None, None

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
                        self.strategies.append(detector)
                except Exception as e:
                    print(f"Failed to load pattern {path}: {e}")

    def _init_legacy_strategies(self):
        """動的解析が必要なレガシー（ハイブリッド）戦略を読み込む"""
        loaded_keys = {getattr(s, "key", "") for s in self.strategies}
        legacy_list = [
            (PonnukiDetector, "ponnuki")
        ]
        for cls, key in legacy_list:
            if key not in loaded_keys:
                self.strategies.append(cls(self.board_size))

    def detect_facts(self, curr_board, prev_board=None) -> list[InferenceFact]:
        """形状検知結果を InferenceFact のリストとして返す"""
        actual_size = curr_board.side
        context = DetectionContext(curr_board, prev_board, actual_size)
        facts = []
        for strategy in self.strategies:
            orig_size = getattr(strategy, "board_size", 19)
            strategy.board_size = actual_size
            category, results = strategy.detect(context)
            strategy.board_size = orig_size
            
            severity = 4 if category in ["bad", "mixed"] else 2
            
            actual_results = []
            if category == "mixed" and isinstance(results, tuple):
                actual_results = results[0] + results[1]
            else:
                actual_results = results

            for msg in actual_results:
                facts.append(InferenceFact(FactCategory.SHAPE, msg, severity, {"key": getattr(strategy, "key", "unknown")}))
        return facts

    def detect_ids(self, curr_board, prev_board=None):
        """(Legacy互換) 検知された形状IDのリストを返す"""
        facts = self.detect_facts(curr_board, prev_board)
        return list(set([f.metadata.get("key", "unknown") for f in facts]))