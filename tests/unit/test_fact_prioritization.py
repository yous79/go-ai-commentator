import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.inference_fact import FactCollector, FactCategory
from core.shape_detector import ShapeDetector
from core.stability_analyzer import StabilityAnalyzer
from core.board_simulator import BoardSimulator

def test_fact_prioritization():
    print("Testing Fact Collection and Prioritization...")
    collector = FactCollector()
    simulator = BoardSimulator(board_size=9)
    detector = ShapeDetector(board_size=9)
    stability_analyzer = StabilityAnalyzer(board_size=9)
    
    # 局面シミュレーション: B D4, B D6, B E5 (アキ三角) かつ 低安定度を想定
    history = [["B", "D4"], ["W", "A1"], ["B", "D6"], ["W", "A2"], ["B", "E5"]]
    curr_b, prev_b, _ = simulator.reconstruct(history)
    
    # 1. 形状事実の収集 (Aki-sankaku should be severity 4)
    shape_facts = detector.detect_facts(curr_b, prev_b)
    for f in shape_facts: collector.facts.append(f)
    
    # 2. 安定度事実の収集 (Low stability scenario)
    # 手動で低いOwnershipマップを作成 (-1.0 to 1.0)
    fake_ownership = [0.0] * 81
    idx = 3 * 9 + 3 # D4
    fake_ownership[idx] = 0.1 # Very low stability for Black
    
    stability_facts = stability_analyzer.analyze_to_facts(curr_b, fake_ownership)
    for f in stability_facts: collector.facts.append(f)
    
    # 3. 緊急度事実の追加 (Manual high urgency)
    collector.add(FactCategory.URGENCY, "緊急度が 20.5目 と非常に高いです。", severity=5)

    # 4. トリアージ結果の確認
    prioritized_text = collector.get_prioritized_text(limit=5)
    print("\n--- Prioritized Facts for Gemini ---")
    print(prioritized_text)
    
    # 検証
    if "緊急度" in prioritized_text and "アキ三角" in prioritized_text:
        print("\nSUCCESS: Both critical urgency and bad shape are prioritized.")
    else:
        print("\nFAILED: Missing critical facts in summary.")

if __name__ == "__main__":
    test_fact_prioritization()
