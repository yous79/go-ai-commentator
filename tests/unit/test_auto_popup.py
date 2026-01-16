import os
import sys
import time
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.api_client import api_client
from services.term_visualizer import TermVisualizer
from config import OUTPUT_BASE_DIR

def test_auto_popup_logic():
    print("Testing Automatic Reference Diagram Generation Logic...")
    visualizer = TermVisualizer()
    
    # テスト用局面: 緊急度が高いはずの一間トビ割り込み状態
    history = [["B", "D4"], ["B", "D6"], ["W", "D5"]]
    
    if not api_client.health_check():
        print("ERROR: API Server not running.")
        return

    # 1. 緊急度解析の実行
    print("Step 1: Calculating urgency...")
    urgency_data = api_client.analyze_urgency(history, board_size=19)
    
    if urgency_data and urgency_data.get("is_critical"):
        print(f"  CRITICAL detected! Urgency: {urgency_data['urgency']:.1f} pts")
        
        # 2. 自動生成ロジックのシミュレート
        print("Step 2: Simulating automatic reference diagram generation...")
        pv = urgency_data.get("opponent_pv", [])
        if pv:
            title = f"Ref Diagram (Loss: {urgency_data['urgency']:.1f} pts)"
            path, err = visualizer.visualize_sequence(history, pv, title=title)
            
            if path and os.path.exists(path):
                print(f"SUCCESS: Reference diagram generated at {path}")
                print(f"  Future moves by opponent: {pv}")
            else:
                print(f"FAILED: Image generation failed: {err}")
        else:
            print("FAILED: No opponent PV found for reference diagram.")
    else:
        print("INFO: Urgency was not critical enough to trigger popup in this scenario.")

if __name__ == "__main__":
    test_auto_popup_logic()
