from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import DetectionContext, ShapeDetector

def print_facts(label, facts):
    print(f"--- {label} ---")
    if not facts:
        print("No facts detected.")
    for f in facts:
        print(f"[{f.metadata.get('key')}] {f.description} (Priority Metadata: {f.severity})")

def test_priority_adjustments():
    detector = ShapeDetector(19)

    # 1. Bad Shape vs Others (Aki-sankaku should dominate)
    # Aki-sankaku: last(10,10), self(10,11), self(11,10), empty(11,11)
    # This also matches Nobi/Narabi? No, let's see. 
    # Just check if it's detected and has the right severity.
    b1 = GameBoard(19)
    b1.play(Point(10, 11), 'b')
    b1.play(Point(11, 10), 'b')
    prev_b1 = b1.copy()
    b1.play(Point(10, 10), 'b') # Aki-sankaku
    print_facts("Aki-sankaku (Priority 100)", detector.detect_facts(b1, prev_b1))

    # 2. General (Keima) vs Nobi
    # If a move matches both Keima and Nobi? Unlikely in standard geometry.
    # But let's check Keima's absolute priority (it should be 20).
    # Keima: last(10,10), self(8,9), empty(9,10), empty(9,9)
    b2 = GameBoard(19)
    b2.play(Point(8, 9), 'b')
    prev_b2 = b2.copy()
    b2.play(Point(10, 10), 'b')
    print_facts("Keima Check (Should be Priority 20 group)", detector.detect_facts(b2, prev_b2))

    # 3. Nobi Check
    b3 = GameBoard(19)
    b3.play(Point(10, 10), 'b')
    b3.play(Point(10, 9), 'w') # Enemy for Nobi
    prev_b3 = b3.copy()
    b3.play(Point(11, 10), 'b')
    print_facts("Nobi Check (Should be Priority 30)", detector.detect_facts(b3, prev_b3))

if __name__ == "__main__":
    test_priority_adjustments()
