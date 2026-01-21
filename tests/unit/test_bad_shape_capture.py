import unittest
import sys
import os

# srcディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import ShapeDetector, DetectionContext
from core.shapes.generic_detector import GenericPatternDetector
import json

class TestBadShapeCapture(unittest.TestCase):
    def setUp(self):
        self.detector = ShapeDetector(19)
        # アキ三角のパターンを直接定義
        self.aki_pattern = {
            "key": "aki_sankaku",
            "category": "bad",
            "patterns": [{
                "elements": [
                    {"offset": [0, 0], "state": "last"},
                    {"offset": [1, 0], "state": "self"},
                    {"offset": [0, 1], "state": "self"},
                    {"offset": [1, 1], "state": "empty"}
                ]
            }]
        }
        self.gen_detector = GenericPatternDetector(self.aki_pattern, 19)

    def test_standard_empty_triangle(self):
        """通常のアキ三角が正しく検知されること"""
        b = GameBoard(19)
        # 基本形に合わせて配置
        b.play(Point(11, 10), Color.BLACK) # self
        b.play(Point(10, 11), Color.BLACK) # self
        
        # 最新手: (10, 10) に黒
        curr = b.copy()
        curr.play(Point(10, 10), Color.BLACK) # last
        # (11, 11) は空点のまま
        
        ctx = DetectionContext(curr, b, 19)
        ctx.last_move = Point(10, 10)
        ctx.last_color = Color.BLACK
        
        cat, results = self.gen_detector.detect(ctx)
        self.assertTrue(len(results) > 0, "通常のアキ三角は検知されるべき")

    def test_capture_not_empty_triangle(self):
        """石を取った結果のL字型はアキ三角と検知されないこと"""
        prev = GameBoard(19)
        prev.play(Point(10, 10), Color.BLACK)
        prev.play(Point(11, 10), Color.BLACK)
        prev.play(Point(11, 11), Color.WHITE) # ここに相手の石がある
        
        # 最新手: (10, 11) に黒を打ち、(11, 11) の白を取る
        curr = prev.copy()
        curr.play(Point(10, 11), Color.BLACK)
        
        ctx = DetectionContext(curr, prev, 19)
        ctx.last_move = Point(10, 11)
        ctx.last_color = Color.BLACK
        
        cat, results = self.gen_detector.detect(ctx)
        self.assertEqual(len(results), 0, "石を取った結果の空点はアキ三角とみなすべきではない")

if __name__ == "__main__":
    unittest.main()
