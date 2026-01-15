import os
import sys
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.knowledge_manager import KnowledgeManager
from config import KNOWLEDGE_DIR

def test_metadata_loading():
    print("Testing KnowledgeManager with Metadata...")
    km = KnowledgeManager(KNOWLEDGE_DIR)
    
    # Check all knowledge text
    all_text = km.get_all_knowledge_text()
    if "アキ三角 (Aki-sankaku) (重要度: 5)" in all_text:
        print("SUCCESS: Metadata found in all knowledge text.")
    else:
        print("FAILED: Metadata not found in all knowledge text.")
        # print(all_text)

    # Check related knowledge with tag match
    related = km.get_related_knowledge(["empty_triangle"]) # aki_sankaku has this in related_terms
    if "アキ三角" in related:
        print("SUCCESS: Related knowledge found via metadata link.")
    else:
        print("FAILED: Related knowledge not found via metadata link.")
        print(f"Detected: ['empty_triangle'], Output: {related}")

if __name__ == "__main__":
    test_metadata_loading()
