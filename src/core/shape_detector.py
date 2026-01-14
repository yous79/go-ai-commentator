from core.shapes.aki_sankaku import AkiSankakuDetector
from core.shapes.sakare_gata import SakareGataDetector
from core.shapes.nimoku_atama import NimokuAtamaDetector
from core.shapes.ponnuki import PonnukiDetector
from core.shapes.dango import DangoDetector
from core.shapes.kosumi import KosumiDetector
from core.shapes.takefu import TakefuDetector
from core.shapes.ikken_tobi import IkkenTobiDetector
from core.shapes.keima import KeimaDetector
from core.shapes.tsuke import TsukeDetector
from core.shapes.hane import HaneDetector
from core.shapes.kirichigai import KirichigaiDetector
from core.shapes.nobi import NobiDetector
from core.shapes.butsukari import ButsukariDetector

class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size
        self.strategies = [
            AkiSankakuDetector(board_size),
            SakareGataDetector(board_size),
            NimokuAtamaDetector(board_size),
            PonnukiDetector(board_size),
            DangoDetector(board_size),
            KosumiDetector(board_size),
            TakefuDetector(board_size),
            IkkenTobiDetector(board_size),
            KeimaDetector(board_size),
            TsukeDetector(board_size),
            HaneDetector(board_size),
            KirichigaiDetector(board_size),
            NobiDetector(board_size),
            ButsukariDetector(board_size)
        ]

    def detect_all(self, curr_board, prev_board=None, last_move_color=None):
        bad_shapes = []
        normal_facts = []
        for strategy in self.strategies:
            strategy.board_size = self.board_size
            category, results = strategy.detect(curr_board, prev_board, last_move_color)
            if category == "bad":
                bad_shapes.extend(results)
            elif category == "normal":
                normal_facts.extend(results)
            elif category == "mixed":
                bad_shapes.extend(results[0])
                normal_facts.extend(results[1])
        report = []
        if bad_shapes:
            report.append("【盤面形状解析：警告（悪形・失着）】")
            report.extend(bad_shapes)
        if normal_facts:
            if bad_shapes: report.append("")
            report.append("【盤面形状解析：事実（一般手筋・状態）】")
            report.extend(normal_facts)
        return "\n".join(report) if report else ""

    def detect_ids(self, curr_board, prev_board=None, last_move_color=None):
        detected_ids = set()
        for strategy in self.strategies:
            strategy.board_size = self.board_size
            _, results = strategy.detect(curr_board, prev_board, last_move_color)
            if results:
                has_actual_results = False
                if isinstance(results, tuple):
                    if results[0] or results[1]: has_actual_results = True
                elif results:
                    has_actual_results = True
                if has_actual_results:
                    key = getattr(strategy, "key", "unknown")
                    detected_ids.add(key)
        return list(detected_ids)
