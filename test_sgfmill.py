from sgfmill import boards

def test_suicide():
    b = boards.Board(19)
    # Surround (1, 1) with white stones
    b.play(0, 1, 'w')
    b.play(2, 1, 'w')
    b.play(1, 0, 'w')
    b.play(1, 2, 'w')
    
    print("Board initialized with white stones surrounding (1, 1)")
    
    try:
        captured = b.play(1, 1, 'b')
        print(f"Play (1, 1) as black. Captured stones: {captured}")
        print(f"Stone at (1, 1) after play: {b.get(1, 1)}")
    except ValueError as e:
        print(f"Caught ValueError: {e}")

def test_ko():
    b = boards.Board(19)
    # Set up a Ko situation
    # White: (0, 1), (1, 2), (2, 1)
    # Black: (1, 0), (2, 1), (1, 2) -- Wait
    # Standard Ko:
    # W: (1, 0), (0, 1), (1, 2)
    # B: (2, 1), (1, 2), (1, 0) -- No
    
    # Correct Ko setup:
    # B stones at (1, 0), (0, 1), (1, 2)
    # W stones at (2, 1), (3, 2), (2, 3)
    
    # Let's use simpler setup
    b.play(1, 0, 'b')
    b.play(0, 1, 'b')
    b.play(1, 2, 'b')
    
    b.play(2, 0, 'w')
    b.play(3, 1, 'w')
    b.play(2, 2, 'w')
    
    # B plays at (1, 1)
    b.play(1, 1, 'b')
    # W captures B at (1, 1) by playing at (2, 1)
    # Wait, B is at (1,0), (0,1), (1,2), (1,1). (1,1) neighbor is (2,1)
    captured = b.play(2, 1, 'w')
    print(f"White plays (2, 1) capturing Black at (1, 1). Captured: {captured}")
    
    # Check for Ko point related attributes
    ko_attrs = [a for a in dir(b) if 'ko' in a.lower()]
    print(f"Found Ko-related attributes: {ko_attrs}")
    
    if 'ko_point' in ko_attrs:
        print(f"Current ko_point: {b.ko_point}")
    
    try:
        # B tries to capture back immediately (Ko)
        captured2 = b.play(1, 1, 'b')
        print(f"Black tries to recapture (1, 1). Captured: {captured2}")
    except ValueError as e:
        print(f"Caught ValueError on Ko: {e}")

if __name__ == "__main__":
    print("--- Testing Suicide ---")
    test_suicide()
    print("\n--- Testing Ko ---")
    test_ko()
