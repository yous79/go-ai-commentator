from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import DetectionContext, ShapeDetector

def print_facts(label, facts):
    print(f"--- {label} ---")
    if not facts:
        print("No facts detected.")
    for f in facts:
        print(f"[{f.metadata.get('key')}] {f.description} (Sev: {f.severity})")

def test_tsugi_purity():
    detector = ShapeDetector(19)

    # 1. Clean Kake-tsugi
    b2 = GameBoard(19)
    b2.play(Point(5, 5), 'b') # pivot
    b2.play(Point(4, 5), 'w') # opp
    b2.play(Point(4, 6), 'b') # wing
    prev_b2 = b2.copy()
    b2.play(Point(6, 6), 'b') # last
    print_facts("Clean Kake-tsugi Scenario", detector.detect_facts(b2, prev_b2))

    # 2. Kake-tsugi with Purity Violation (Extra self stone near last move)
    b3 = GameBoard(19)
    b3.play(Point(5, 5), 'b') # pivot
    b3.play(Point(4, 5), 'w') # opp
    b3.play(Point(4, 6), 'b') # wing
    b3.play(Point(6, 5), 'b') # EXTRA SELF STONE (Neighbor of F6/6,6)
    prev_b3 = b3.copy()
    b3.play(Point(6, 6), 'b') # last
    print_facts("Kake-tsugi with Purity Violation (Should be empty)", detector.detect_facts(b3, prev_b3))

if __name__ == "__main__":
    test_tsugi_purity()
