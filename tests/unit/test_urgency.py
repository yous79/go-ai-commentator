import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.api_client import api_client

def test_urgency_analysis():
    print("Testing Urgency (Temperature) Analysis Logic...")
    
    # テスト用局面: B D4, B D6 (一間トビ) に対して W D5 (ワリコミ) が打たれ、
    # 次に黒が打たないと分断される（緊急度が高い）状況をシミュレート
    history = [["B", "D4"], ["B", "D6"], ["W", "D5"]]
    
    if not api_client.health_check():
        print("ERROR: API Server is not running. Start the API server first.")
        return

    print("Analyzing urgency...")
    res = api_client.analyze_urgency(history, board_size=19, visits=100)
    
    if res:
        print("\n--- Urgency Analysis Result ---")
        print(f"Normal Score Lead (B): {res['score_normal']:.2f}")
        print(f"Pass Score Lead (B): {res['score_pass']:.2f}")
        print(f"Calculated Urgency (Temperature): {res['urgency']:.2f} points")
        print(f"Is Critical: {res['is_critical']}")
        
        if res['urgency'] > 0:
            print("\nSUCCESS: Urgency calculated successfully.")
        else:
            print("\nFAILED: Urgency should be positive.")
    else:
        print("FAILED: No response from API.")

if __name__ == "__main__":
    test_urgency_analysis()
