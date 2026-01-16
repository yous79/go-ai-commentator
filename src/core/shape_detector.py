from core.point import Point
from core.inference_fact import InferenceFact, FactCategory
from core.shapes.generic_detector import GenericPatternDetector
from core.shapes.ponnuki import PonnukiDetector
import os
import json
from config import KNOWLEDGE_DIR

class DetectionContext:
    """検知に必要な盤面コンテキストを一元管理するクラス"""
    def __init__(self, curr_board, prev_board, board_size, analysis_result=None):
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
                if self.curr_board.get(r, c) and not self.prev_board.get(r, c):
                    return Point(r, c), self.curr_board.get(r, c)
        return None, None

    def get_ownership(self, r, c):
        """指定座標のOwnershipを取得する (黒地: +1.0, 白地: -1.0)"""
        ownership = self.analysis_result.get("ownership")
        if not ownership:
            return 0.0
        
        # KataGoのOwnershipは通常 1D配列 (row-major)
        idx = r * self.board_size + c
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

    def detect_facts(self, curr_board, prev_board=None, analysis_result=None) -> list[InferenceFact]:
        """形状検知結果を InferenceFact のリストとして返す"""
        actual_size = curr_board.side
        context = DetectionContext(curr_board, prev_board, actual_size, analysis_result)
        facts = []
        
        # 1. 既存の戦略による検知
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
        
        # 2. カス石・過剰干渉の検知 (新規)
        inefficient_moves = self._detect_inefficient_moves(context)
        facts.extend(inefficient_moves)
            
        return facts

    def _detect_inefficient_moves(self, context: DetectionContext) -> list[InferenceFact]:
        """カス石への過剰干渉（死に石への手入れ等）を検知する"""
        facts = []
        move_point = context.last_move
        move_color = context.last_color
        
        if not move_point or not context.analysis_result:
            return []

        # 判定基準: 相手の石に干渉しているが、その石はすでに「死んでいる(Ownershipが自分側)」
        
        # 自分の手番の色 (move_color)
        # 相手の色
        opp_color = "white" if move_color == "black" else "black"
        
        # 自分の地としての確信度閾値 (0.8以上ならほぼ確定地＝中の相手石は死に石)
        OWNERSHIP_THRESHOLD = 0.8
        
        # 周囲の確認
        adjacents = []
        r, c = move_point.row, move_point.col
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < context.board_size and 0 <= nc < context.board_size:
                adjacents.append(Point(nr, nc))

        kasu_ishi_detected = False
        
        for adj in adjacents:
            stone = context.curr_board.get(adj.row, adj.col)
            # 相手の石が隣にあるか？ (または直前に取ったか？ 取った場合は盤面からは消えているため prev_board で確認が必要だが、
            # ここでは『死に石のそばに打った』『死に石を囲った』ケースを主眼に置く。
            # 取ったケース(Capture)は石が消えているため curr_board では判定できないが、
            # Ownershipは『取られた後の盤面』で計算されるため、取った場所は『自分の地』になっているはず。)
            
            target_is_dead = False
            
            # ケースA: 隣に相手の石があるが、それは死んでいる
            if stone == opp_color:
                owner_val = context.get_ownership(adj.row, adj.col)
                # 自分が黒(Black)なら、Ownershipが +1.0 に近ければ黒地＝白石は死んでいる
                if move_color == "black" and owner_val > OWNERSHIP_THRESHOLD:
                    target_is_dead = True
                # 自分が白(White)なら、Ownershipが -1.0 に近ければ白地＝黒石は死んでいる
                elif move_color == "white" and owner_val < -OWNERSHIP_THRESHOLD:
                    target_is_dead = True
            
            if target_is_dead:
                kasu_ishi_detected = True
                break
        
        # ケースB: 石を取った場合 (直前には石があったが今は消えている)
        if not kasu_ishi_detected and context.prev_board:
            # 自分の着手位置、またはその周囲で石が消えたか？
            # 単純化のため、着手した場所自体は石が置かれたので除外。
            # アタリから抜いた場合、隣接する位置の石が消えているはず。
            for adj in adjacents:
                prev_stone = context.prev_board.get(adj.row, adj.col)
                curr_stone = context.curr_board.get(adj.row, adj.col)
                if prev_stone == opp_color and curr_stone is None:
                    # 石が消えた＝取った
                    # 取った後の地点(adj)のOwnershipを確認
                    owner_val = context.get_ownership(adj.row, adj.col)
                    # 取ったのだから当然自分の地になっているはずだが、
                    # 重要なのは『取る前から死んでいたか』...判定は難しいが、
                    # 『取った結果、その場所が完全に自分の地(1.0/-1.0)』であり、かつ
                    # 『評価値上の利益が少ない』場合にカス石と言える。
                    # ここではシンプルに「取った場所が完全に自分の地になっている」なら
                    # それは「取らなくても死んでいたかもしれない」可能性を示唆するが、
                    # 確実に判定するには「取る前のOwnership」が必要。
                    # しかし簡易ロジックとして、「相手の石を取った」事実と、外部から評価損情報があれば結合できる。
                    # 今回は『Ownershipによる死に石判定』に絞るため、ケースBは『取った後の地が確定地』であることだけ確認し、
                    # あとはプロンプトで「評価損なら指摘せよ」とする。
                    pass

        if kasu_ishi_detected:
            facts.append(InferenceFact(
                FactCategory.MISTAKE, # 形状(SHAPE)というよりは判断ミス(MISTAKE)
                "すでに死んでいる石（カス石）に対して手入れが行われました。",
                severity=4,
                metadata={"type": "kasu_ishi_interference"}
            ))

        return facts

    def detect_ids(self, curr_board, prev_board=None):
        """(Legacy互換) 検知された形状IDのリストを返す"""
        facts = self.detect_facts(curr_board, prev_board)
        return list(set([f.metadata.get("key", "unknown") for f in facts]))