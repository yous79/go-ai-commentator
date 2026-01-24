import json
import os
import sys
from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import DetectionContext, ShapeDetector
from core.shapes.generic_detector import GenericPatternDetector

# Mock pattern for Aki-sankaku if file not found, but we will use the actual one
AKI_PATTERN_PATH = r"c:\Users\youst\go-ai-commentator\knowledge\01_bad_shapes\aki_sankaku\pattern.json"

def test_aki_sankaku_vs_ko_fill():
    with open(AKI_PATTERN_PATH, "r", encoding="utf-8") as f:
        pattern_def = json.load(f)
    
    detector = GenericPatternDetector(pattern_def, 19)
    
    # 1. Normal Aki-sankaku
    # B: (0, 0), (1, 0)
    # Next B: (0, 1) -> Creates Aki-sankaku with (1, 1) empty
    b1 = GameBoard(19)
    b1.play(Point(0, 0), 'b')
    b1.play(Point(1, 0), 'b')
    
    prev_b1 = b1.copy()
    b1.play(Point(0, 1), 'b')
    
    ctx1 = DetectionContext(b1, prev_b1, 19)
    cat1, res1 = detector.detect(ctx1)
    print(f"Normal Aki-sankaku Detection: Category={cat1}, Results={res1}")

    # 2. Ko Fill forming Aki-sankaku
    # We need a Ko at Point(1, 1) and two B stones at (1, 0) and (0, 1)
    # Move B(1, 1) creates Aki-sankaku with (0, 0).
    # Wait, the pattern is:
    # (0,0): last, (1,0): last, (0,1): last, (1,1): empty -> Aki-sankaku
    
    b2 = GameBoard(19)
    # Setup stones for Aki-sankaku around (0, 0), (1, 0), (0, 1)
    b2.play(Point(1, 0), 'b')
    b2.play(Point(0, 1), 'b')
    
    # Setup Ko at (0, 0)
    # To have Ko at (0, 0), B must have just captured W at (0, 0).
    # W was at (0, 0). B stones at (1, 0), (0, 1), (-1, 0)? No.
    # Actually, simpler: Use the Ko setup from previous test and make it form Aki-sankaku.
    
    # Let's say we have B at (1, 0) and (0, 1).
    # There's a Ko point at (0, 0).
    # B plays at (0, 0). This fills Ko.
    # It also forms Aki-sankaku with (1, 0) and (0, 1) (if (1, 1) is empty).
    
    # Manually set Ko point for b2
    b2.ko_point = Point(0, 0)
    
    prev_b2 = b2.copy()
    # Ensure (0, 0) is empty in prev_b2
    # prev_b2.get(Point(0, 0)) is already None
    
    b2.play(Point(0, 0), 'b') # Filling Ko
    
    ctx2 = DetectionContext(b2, prev_b2, 19)
    cat2, res2 = detector.detect(ctx2)
    print(f"Ko Fill Aki-sankaku Detection: Category={cat2}, Results={res2}")

if __name__ == "__main__":
    test_aki_sankaku_vs_ko_fill()
