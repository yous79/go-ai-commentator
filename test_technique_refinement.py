from core.game_board import GameBoard, Color
from core.point import Point
from core.shape_detector import DetectionContext, ShapeDetector
import sys

def setup_context(board, prev_board):
    return DetectionContext(board, prev_board, board.side)

def print_facts(label, facts):
    print(f"--- {label} ---")
    if not facts:
        print("No facts detected.")
    for f in facts:
        print(f"[{f.metadata.get('key')}] {f.description} (Sev: {f.severity})")

def test_technique_refinements():
    detector = ShapeDetector(19)

    # 1. Tsuke: Isolated opponent vs Connected opponent
    # Case A: Tsuke on isolated stone (K10)
    b1 = GameBoard(19)
    b1.play(Point(9, 9), 'w') # K10
    prev_b1 = b1.copy()
    b1.play(Point(10, 9), 'b') # L10: Tsuke
    print_facts("Tsuke on Isolated Stone (L10)", detector.detect_facts(b1, prev_b1))

    # Case B: Contact with connected stones (NOT Tsuke)
    b2 = GameBoard(19)
    b2.play(Point(9, 9), 'w')
    b2.play(Point(9, 10), 'w') # K10-K11 connected
    prev_b2 = b2.copy()
    b2.play(Point(10, 9), 'b') # L10: Contact but NOT Tsuke
    print_facts("Contact with Connected Stones (L10)", detector.detect_facts(b2, prev_b2))

    # 2. Hane: Proper Purity vs Crowded
    # Case A: Proper Hane (L11 relative to B:K11, W:K10)
    # B: K11(10,10), W: K10(9,9), Last B: L10(10,9)? No, Hane definition:
    # last diagonal to self, adjacent to opponent.
    b3 = GameBoard(19)
    b3.play(Point(10, 10), 'b') # K11
    b3.play(Point(9, 9), 'w')  # J10? Wait, indices. row 9=row 10(K)? 
    # Let's use indices directly for clarity.
    # self=(10,10), last=(9,9), opp=(10,9) or (9,10).
    b3 = GameBoard(19)
    b3.play(Point(10, 10), 'b') # self
    b3.play(Point(10, 9), 'w')  # opp
    prev_b3 = b3.copy()
    b3.play(Point(9, 9), 'b')   # last: Diagonal to self, Adjacent to opp.
    print_facts("Proper Hane", detector.detect_facts(b3, prev_b3))

    # Case B: Hane with extra stone (should be ignored due to purity)
    b4 = b3.copy()
    b4.play(Point(8, 9), 'w') # Extra stone nearby
    prev_b4 = b4.copy() # Need a new move to detect
    # Re-play last move logic
    b4_final = b3.copy()
    b4_final.play(Point(8, 9), 'w') 
    prev_b4 = b4_final.copy()
    b4_final.play(Point(9, 9), 'b')
    print_facts("Hane with Purity Violation", detector.detect_facts(b4_final, prev_b4))

    # 3. Nobi vs Narabi
    # Case A: Nobi (self adjacent to opponent)
    b5 = GameBoard(19)
    b5.play(Point(10, 10), 'b') # self
    b5.play(Point(10, 9), 'w')  # opp
    prev_b5 = b5.copy()
    b5.play(Point(11, 10), 'b') # last: Nobi
    print_facts("Nobi (Enemy nearby)", detector.detect_facts(b5, prev_b5))

    # Case B: Narabi (no enemy near self/last)
    b6 = GameBoard(19)
    b6.play(Point(10, 10), 'b') # self
    prev_b6 = b6.copy()
    b6.play(Point(11, 10), 'b') # last: Narabi
    print_facts("Narabi (Peaceful)", detector.detect_facts(b6, prev_b6))

    # 4. Priority: Atari vs Nobi
    # Move forms both Nobi and gives Atari
    b7 = GameBoard(19)
    # Surround (11,9) almost completely
    b7.play(Point(10, 9), 'b')
    b7.play(Point(12, 9), 'b')
    b7.play(Point(11, 8), 'b')
    b7.play(Point(11, 9), 'w')  # opp - now has 1 liberty at (11,10)
    
    # Also need self for Nobi
    b7.play(Point(11, 11), 'b') # self at (11,11)
    
    prev_b7 = b7.copy()
    b7.play(Point(11, 10), 'b') # last at (11,10). Adjacent to self(11,11) AND gives atari to (11,9)
    print_facts("Atari vs Nobi Priority", detector.detect_facts(b7, prev_b7))

if __name__ == "__main__":
    test_technique_refinements()
