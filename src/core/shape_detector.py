from core.point import Point
from core.game_board import GameBoard, Color
from core.inference_fact import InferenceFact, FactCategory
from core.shapes.generic_detector import GenericPatternDetector
from core.shapes.ponnuki import PonnukiDetector
from core.shapes.atari import AtariDetector
import os
import json
from typing import Optional
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
        ownership = self.analysis_result.ownership
        if not ownership:
            return 0.0
        
        idx = pt.row * self.board_size + pt.col
        if 0 <= idx < len(ownership):
            return ownership[idx]
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
                        
                        # 優先度の設定
                        if pattern_def.get("category") == "bad":
                            detector.priority = 80
                        elif detector.key == "tsuke":
                            detector.priority = 10
                        elif detector.key in ["nobi", "narabi"]:
                            detector.priority = 30
                        else:
                            detector.priority = 50
                            
                        self.strategies.append(detector)
                except Exception as e:
                    print(f"Failed to load pattern {path}: {e}")

    def _init_legacy_strategies(self):
        """動的解析が必要なレガシー（ハイブリッド）戦略を読み込む"""
        loaded_keys = {getattr(s, "key", "") for s in self.strategies}
        legacy_list = [
            (PonnukiDetector, "ponnuki", 100), # 最優先
            (AtariDetector, "atari", 95)
        ]
        for cls, key, priority in legacy_list:
            if key not in loaded_keys:
                instance = cls(self.board_size)
                instance.priority = priority
                self.strategies.append(instance)

    def detect_facts(self, curr_board: GameBoard, prev_board: Optional[GameBoard] = None, analysis_result=None) -> list[InferenceFact]:
        """形状検知結果を InferenceFact のリストとして返す"""
        actual_size = curr_board.side
        context = DetectionContext(curr_board, prev_board, actual_size, analysis_result)
        facts = []
        
        # 同一座標に対して複数のラベルがつくのを防ぐための記録
        labeled_coords = set()

        # 1. 戦略を優先度順にソート (高い順)
        sorted_strategies = sorted(self.strategies, key=lambda s: getattr(s, "priority", 50), reverse=True)
        
        for strategy in sorted_strategies:
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

            for res in actual_results:
                msg = res["message"] if isinstance(res, dict) else res
                
                # 座標の特定 (メッセージから抽出するか、あるいは個別に渡す)
                # GenericPatternDetector はメッセージに座標を入れているため、
                # context.last_move を代表座標として使用する（最新手のみが対象のため）
                coord = context.last_move.to_gtp() if context.last_move else "unknown"
                
                if coord != "unknown" and coord in labeled_coords:
                    continue # 既に高優先度のラベルがついている
                
                labeled_coords.add(coord)
                
                metadata = {"key": getattr(strategy, "key", "unknown")}
                if isinstance(res, dict):
                    for k, v in res.items():
                        if k != "message":
                            metadata[k] = v

                from core.inference_fact import TemporalScope
                facts.append(InferenceFact(FactCategory.SHAPE, msg, severity, metadata, scope=TemporalScope.IMMEDIATE))
        
        # 2. カス石・過剰干渉の検知 (新規)
        inefficient_moves = self._detect_inefficient_moves(context)
        facts.extend(inefficient_moves)
            
        return facts

    def _detect_inefficient_moves(self, context: DetectionContext) -> list[InferenceFact]:
        """カス石への過剰干渉（死に石への手入れ等）を検知する"""
        facts = []
        move_point = context.last_move
        move_color = context.last_color
        
        if not move_point or not move_color or not context.analysis_result:
            return []

        # 相手の色
        opp_color = move_color.opposite()
        
        # 自分の地としての確信度閾値 (0.8以上ならほぼ確定地＝中の相手石は死に石)
        OWNERSHIP_THRESHOLD = 0.8
        
        kasu_ishi_detected = False
        
        for adj in move_point.neighbors(context.board_size):
            stone = context.curr_board.get(adj)
            
            target_is_dead = False
            
            # ケースA: 隣に相手の石があるが、それは死んでいる
            if stone == opp_color:
                owner_val = context.get_ownership(adj)
                # 自分が黒なら、Ownershipが +1.0 に近ければ黒地＝白石は死んでいる
                if move_color == Color.BLACK and owner_val > OWNERSHIP_THRESHOLD:
                    target_is_dead = True
                # 自分が白なら、Ownershipが -1.0 に近ければ白地＝黒石は死んでいる
                elif move_color == Color.WHITE and owner_val < -OWNERSHIP_THRESHOLD:
                    target_is_dead = True
            
            if target_is_dead:
                kasu_ishi_detected = True
                break

        if kasu_ishi_detected:
            from core.inference_fact import TemporalScope
            facts.append(InferenceFact(
                FactCategory.MISTAKE, 
                "すでに死んでいる石（カス石）に対して手入れが行われました。",
                severity=4,
                metadata={"type": "kasu_ishi_interference"},
                scope=TemporalScope.IMMEDIATE
            ))

        return facts

    def detect_ids(self, curr_board: GameBoard, prev_board: Optional[GameBoard] = None):
        """(Legacy互換) 検知された形状IDのリストを返す"""
        facts = self.detect_facts(curr_board, prev_board)
        return list(set([f.metadata.get("key", "unknown") for f in facts]))
        """(Legacy互換) 検知された形状IDのリストを返す"""
        facts = self.detect_facts(curr_board, prev_board)
        return list(set([f.metadata.get("key", "unknown") for f in facts]))