import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.coordinate_transformer import CoordinateTransformer
from core.game_state import GoGameState
from core.game_board import Color
from core.point import Point

def test_coordinate_fix():
    print("--- Testing Coordinate Fix ---")
    transformer = CoordinateTransformer(image_size=850)
    
    # 1. 850x850 image (canvas 1000x1000)
    cw, ch = 1000, 1000
    # Center click (9, 9)
    px, py = transformer.indices_to_pixel(9, 9)
    # Expected px, py are relative to 850x850 square.
    # pixel_to_indices with 1000x1000 canvas and 850x850 image.
    # ratio = 1000/850 = 1.17...
    res = transformer.pixel_to_indices(500, 500, cw, ch, actual_img_height=850)
    print(f"Canvas 1000x1000, Image 850x850. Click(500, 500) -> {res}")
    
    # 2. 850x950 image (canvas 1000x1200)
    cw, ch = 1000, 1200
    # pixel_to_indices with actual_img_height=950
    res = transformer.pixel_to_indices(500, 500, cw, ch, actual_img_height=950)
    print(f"Canvas 1000x1200, Image 850x950. Click(500, 500) -> {res}")
    
    # 3. Simulate the error case: height 850 image, but transformer assumes 950
    # This is what happened before the fix.
    res_err = transformer.pixel_to_indices(500, 500, 1000, 1000, actual_img_height=950)
    print(f"BEFORE FIX simulation: Image 850x850 but assumed 950 -> {res_err}")

def test_branching_fix():
    print("\n--- Testing Branching Fix ---")
    gs = GoGameState()
    gs.new_game()
    # Add moves: B[Q16], W[D4], B[D16], W[Q4]
    gs.add_move(0, Color.BLACK, 15, 16) # Q16
    gs.add_move(1, Color.WHITE, 3, 3)   # D4
    gs.add_move(2, Color.BLACK, 15, 3)  # D16
    gs.add_move(3, Color.WHITE, 3, 16)  # Q4
    
    print(f"Original sequence length: {gs.total_moves}")
    
    # Go to move 1 (D4) and play a DIFFERENT move 2 instead of D16
    # Move 1 is index 1. We play at index 1 parent to replace move 2?
    # No, to replace move 2 (index 2), we call add_move(2, ...)
    gs.add_move(2, Color.BLACK, 9, 9) # K10
    
    print(f"New sequence length: {gs.total_moves}")
    history = gs.get_history_up_to(gs.total_moves)
    print(f"New History: {history}")
    
    # Check if original move 2 (D16) is still there as Variation
    node = gs.sgf_game.get_root()
    node = node[0] # Move 1 (Q16)
    node = node[0] # Move 2 (D4)
    print(f"Node 2 children count: {len(node)}")
    for i, child in enumerate(node):
        c, mv = child.get_move()
        print(f"  Variation {i}: {c}{mv}")

    # Test Undo
    print("\nUndoing last move...")
    gs.remove_last_move()
    print(f"History after Undo: {gs.get_history_up_to(5)}")
    print(f"Total moves after Undo: {gs.total_moves}")

if __name__ == "__main__":
    test_coordinate_fix()
    test_branching_fix()
