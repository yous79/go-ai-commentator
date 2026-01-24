from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import DetectionContext
from core.shapes.ponnuki import PonnukiDetector

def test_ponnuki_vs_ko():
    # 1. Setup normal Pon-nuki
    # B: (1, 0), (0, 1), (1, 2), (2, 1)
    # W stone at (1, 1) to be captured
    b1 = GameBoard(19)
    b1.play(Point(1, 0), 'b')
    b1.play(Point(0, 1), 'b')
    b1.play(Point(1, 2), 'b')
    b1.play(Point(1, 1), 'w')
    
    prev_b1 = b1.copy()
    b1.play(Point(2, 1), 'b') # Capture W at (1, 1)
    
    ctx1 = DetectionContext(b1, prev_b1, 19)
    detector = PonnukiDetector(19)
    cat1, res1 = detector.detect(ctx1)
    
    print(f"Normal Pon-nuki Detection: Category={cat1}, Results={res1}")
    
    # 2. Setup Ko situation
    # Black stones forming a "U" around (1, 1)
    b2 = GameBoard(19)
    b2.play(Point(0, 1), 'b')
    b2.play(Point(1, 0), 'b')
    b2.play(Point(1, 2), 'b')
    
    # White stones forming a "U" around (2, 1), with one at (1, 1)
    b2.play(Point(1, 1), 'w')
    b2.play(Point(2, 0), 'w')
    b2.play(Point(2, 2), 'w')
    b2.play(Point(3, 1), 'w')
    
    # B plays at (2, 1) to capture W at (1, 1) -> This establishes Ko
    prev_b2 = b2.copy()
    b2.play(Point(2, 1), 'b')
    
    print(f"Ko Established at: {b2.ko_point.to_gtp() if b2.ko_point else 'None'}")
    
    ctx2 = DetectionContext(b2, prev_b2, 19)
    cat2, res2 = detector.detect(ctx2)
    
    print(f"Ko Capture Detection: Category={cat2}, Results={res2}")

if __name__ == "__main__":
    test_ponnuki_vs_ko()
