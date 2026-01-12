import os
import glob

class KnowledgeManager:
    """知識ベース（用語辞書）の管理、インデックス化、検索を行うクラス"""

    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.index = {} # {category: {term: content}}
        self._build_index()

    def _build_index(self):
        """ディレクトリ構造から知識インデックスを構築する"""
        if not os.path.exists(self.root_dir):
            return

        for category_dir in sorted(os.listdir(self.root_dir)):
            cat_path = os.path.join(self.root_dir, category_dir)
            if not os.path.isdir(cat_path): continue
            
            # カテゴリ名の整形 (01_bad_shapes -> Bad Shapes)
            cat_key = category_dir
            self.index[cat_key] = {}

            for term_dir in sorted(os.listdir(cat_path)):
                term_path = os.path.join(cat_path, term_dir)
                if not os.path.isdir(term_path): continue
                
                # 用語コンテンツの集約
                content = []
                for f_name in glob.glob(os.path.join(term_path, "*.txt")):
                    try:
                        with open(f_name, "r", encoding="utf-8") as f:
                            text = f.read().strip()
                            if text: content.append(text)
                    except: pass
                
                if content:
                    self.index[cat_key][term_dir] = "\n".join(content)

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
