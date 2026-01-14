import os
from core.knowledge_repository import KnowledgeRepository

class KnowledgeManager:
    """知識ベース（用語辞書）の管理、インデックス化、検索を行うクラス"""

    def __init__(self, root_dir):
        self.repository = KnowledgeRepository(root_dir)
        self.index = {} # {category: {term: content}}
        self._build_index()

    def _build_index(self):
        """Repositoryを使用して知識インデックスを構築する"""
        categories = self.repository.get_categories()
        for cat in categories:
            self.index[cat] = {}
            items = self.repository.get_items(cat)
            for item in items:
                content = self.repository.get_item_content(cat, item.id)
                if content and "No commentary text found" not in content:
                    self.index[cat][item.id] = content

    def get_all_knowledge_text(self):
        """プロンプト用に全知識をテキスト化して返す（従来互換）"""
        if not self.index:
            return "\n=== 囲碁知識ベース (用語辞書) ===\n(知識ベースが見つかりません)\n"

        text = "\n=== 囲碁知識ベース (用語辞書) ===\n"
        for cat_key, terms in self.index.items():
            cat_label = "【重要：悪形・失着】" if "bad_shapes" in cat_key else "【一般手筋・概念】"
            text += f"\n{cat_label}\n"
            for term_key, content in terms.items():
                term_name = term_key.replace("_", " ").title()
                text += f"◆ {term_name}:\n"
                # インデントして追記
                for line in content.split('\n'):
                    text += f"  - {line}\n"
        return text

    def get_related_knowledge(self, detected_terms: list):
        """
        検知された用語に関連する知識のみを抽出する（コンテキスト節約用）
        detected_terms: ['aki_sankaku', 'ponnuki', ...] 
        """
        if not detected_terms: return ""
        
        text = "\n=== 関連する知識 (ピックアップ) ===\n"
        found = False
        for cat_key, terms in self.index.items():
            for term_key, content in terms.items():
                # 部分一致などでヒットさせる
                if any(dt in term_key for dt in detected_terms):
                    term_name = term_key.replace("_", " ").title()
                    text += f"◆ {term_name}:\n{content}\n"
                    found = True
        return text if found else ""
