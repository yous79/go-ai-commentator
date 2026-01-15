import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.game_state import GoGameState
from utils.board_renderer import GoBoardRenderer
from config import OUTPUT_BASE_DIR

def generate_sakare_variations():
    renderer = GoBoardRenderer(board_size=9, image_size=500)
    
    variations = [
        {
            "name": "sakare_var1_vertical_split",
            "title": "Sakare: Vertical Ikken-tobi Split",
            "sgf": "(;GM[1]FF[4]SZ[9];B[dd];B[df];W[ce];W[de];W[ee])" # B D6,D4 vs W C5,D5,E5
        },
        {
            "name": "sakare_var2_horizontal_split",
            "title": "Sakare: Horizontal Ikken-tobi Split",
            "sgf": "(;GM[1]FF[4]SZ[9];B[cd];B[ed];W[dc];W[dd];W[de])" # B C6,E6 vs W D7,D6,D5
        },
        {
            "name": "sakare_var3_keima_split",
            "title": "Sakare: Keima Split",
            "sgf": "(;GM[1]FF[4]SZ[9];B[dd];B[ef];W[de];W[ee])" # B D6, E4 (Keima) vs W D5, E5 (Splitter)
        }
    ]

    for var in variations:
        game = GoGameState()
        # 一時ファイルを経由せずに直接ロードする口がないため、一時的に書き出す
        temp_path = "temp_var.sgf"
        with open(temp_path, "w") as f: f.write(var["sgf"])
        game.load_sgf(temp_path)
        
        board = game.get_board_at(game.total_moves)
        img = renderer.render(board, analysis_text=var["title"], history=game.get_history_up_to(game.total_moves), show_numbers=True)
        
        path = os.path.join(OUTPUT_BASE_DIR, f"{var['name']}.png")
        img.save(path)
        print(f"Generated: {path}")
    
    if os.path.exists("temp_var.sgf"): os.remove("temp_var.sgf")

if __name__ == "__main__":
    generate_sakare_variations()
