import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.term_visualizer import TermVisualizer
from config import OUTPUT_BASE_DIR

def test_term_visualization():
    print("Testing TermVisualizer...")
    visualizer = TermVisualizer()
    
    # 1. テンプレートがある場合 (aki_sankaku, nimoku_no_atama)
    print("Scenario 1: From Template (aki_sankaku)")
    path, err = visualizer.visualize("aki_sankaku")
    if path and os.path.exists(path):
        print(f"SUCCESS: Image generated at {path}")
    else:
        print(f"FAILED: {err}")

    print("\nScenario 1b: From Template (nimoku_no_atama)")
    path_nimoku, err_nimoku = visualizer.visualize("nimoku_no_atama")
    if path_nimoku and os.path.exists(path_nimoku):
        print(f"SUCCESS: Image generated at {path_nimoku}")
    else:
        print(f"FAILED: {err_nimoku}")

    # 2. テンプレートがない場合 (sakare_gata - まだ example.sgf がない)
    print("\nScenario 2: From AI (sakare_gata)")
    path_ai, err_ai = visualizer.visualize("sakare_gata")
    if path_ai and os.path.exists(path_ai):
        print(f"SUCCESS: AI generated image at {path_ai}")
    else:
        print(f"INFO: AI generation skipped or failed: {err_ai}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
    test_term_visualization()
