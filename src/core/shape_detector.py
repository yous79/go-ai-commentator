from core.shapes.aki_sankaku import AkiSankakuDetector
from core.shapes.sakare_gata import SakareGataDetector
from core.shapes.nimoku_atama import NimokuAtamaDetector
from core.shapes.ponnuki import PonnukiDetector

class ShapeDetector:
    def __init__(self, board_size=19):
        self.board_size = board_size
        # 登録されたストラテジーのリスト
        self.strategies = [
            AkiSankakuDetector(board_size),
            SakareGataDetector(board_size),
            NimokuAtamaDetector(board_size),
            PonnukiDetector(board_size)
        ]

    def detect_all(self, curr_board, prev_board=None, last_move_color=None):
        """全てのストラテジーを実行し、レポートを生成する"""
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
                # (bad_list, normal_list) のタプルを受け取る
                bad_shapes.extend(results[0])
                normal_facts.extend(results[1])

        # レポート構築
        report = []
        if bad_shapes:
            report.append("【盤面形状解析：警告（悪形・失着）】")
            report.extend(bad_shapes)
        if normal_facts:
            if bad_shapes: report.append("")
            report.append("【盤面形状解析：事実（一般手筋・状態）】")
            report.extend(normal_facts)
            
        return "\n".join(report) if report else ""