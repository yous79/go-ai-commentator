import os
from core.knowledge_repository import KnowledgeRepository

class KnowledgeManager:
    """知識ベース（用語辞書）の管理、インデックス化、検索を行うクラス"""

    def __init__(self, root_dir):
        self.repository = KnowledgeRepository(root_dir)
        self.index = {} # {category: {term_id: KnowledgeItem}}
        self._build_index()

    def _build_index(self):
        """Repositoryを使用して知識インデックスを構築する"""
        categories = self.repository.get_categories()
        for cat in categories:
            self.index[cat] = {}
            items = self.repository.get_items(cat)
            for item in items:
                # contentをitemオブジェクト自体に紐付けて保持（キャッシュ）
                # 大規模化する場合はオンデマンド読み込みを検討
                item.full_content = self.repository.get_item_content(cat, item.id)
                self.index[cat][item.id] = item

    def get_all_knowledge_text(self):
        """プロンプト用に全知識をテキスト化して返す"""
        if not self.index:
            return "\n=== 囲碁知識ベース (用語辞書) ===\n(知識ベースが見つかりません)\n"

        text = "\n=== 囲碁知識ベース (用語辞書) ===\n"
        for cat_key, terms in self.index.items():
            cat_label = "【重要：悪形・失着】" if "bad_shapes" in cat_key else "【一般手筋・概念】"
            text += f"\n{cat_label}\n"
            for term_id, item in terms.items():
                meta = item.metadata
                importance = f" (重要度: {meta['importance']})" if "importance" in meta else ""
                text += f"◆ {item.title}{importance}:\n"
                
                content = getattr(item, 'full_content', "")
                # インデントして追記
                for line in content.split('\n'):
                    text += f"  - {line}\n"
        return text

    def get_related_knowledge(self, detected_terms: list):
        """
        検知された用語に関連する知識のみを抽出する
        metadataのrelated_termsやtagsも考慮して拡張。
        """
        if not detected_terms: return ""
        
        results = []
        seen_ids = set()

        # 1. 直接一致または関連用語(related_terms)に含まれるものを抽出
        for cat_key, terms in self.index.items():
            for term_id, item in terms.items():
                meta = item.metadata
                is_match = False
                
                # 直接一致
                if any(dt in term_id for dt in detected_terms):
                    is_match = True
                
                # 関連項目IDに一致
                related = meta.get("related_terms", [])
                if any(dt in related for dt in detected_terms):
                    is_match = True
                
                # タグに一致
                tags = meta.get("tags", [])
                if any(dt in tags for dt in detected_terms):
                    is_match = True

                if is_match and term_id not in seen_ids:
                    seen_ids.add(term_id)
                    results.append(item)

        if not results: return ""

        # 重要度順にソート（デフォルト3）
        results.sort(key=lambda x: x.metadata.get("importance", 3), reverse=True)

        text = "\n=== 関連する知識 (ピックアップ) ===\n"
        for item in results:
            content = getattr(item, 'full_content', "No content")
            text += f"◆ {item.title}:\n{content}\n"
        return text
