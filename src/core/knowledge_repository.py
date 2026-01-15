import os
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json

@dataclass
class KnowledgeItem:
    id: str
    category: str
    title: str
    base_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class KnowledgeRepository:
    """知識ベースのファイルシステムへの直接アクセスを管理する低レイヤーのリポジトリ"""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def get_categories(self) -> List[str]:
        """利用可能なカテゴリ一覧を返す"""
        if not os.path.exists(self.root_dir):
            return []
        return [d for d in sorted(os.listdir(self.root_dir)) 
                if os.path.isdir(os.path.join(self.root_dir, d))]

    def get_items(self, category: str) -> List[KnowledgeItem]:
        """カテゴリ内のアイテム（アキ三角など）一覧を返す"""
        cat_path = os.path.join(self.root_dir, category)
        if not os.path.exists(cat_path):
            return []
        
        items = []
        for d in sorted(os.listdir(cat_path)):
            item_path = os.path.join(cat_path, d)
            if os.path.isdir(item_path):
                # IDはフォルダ名、タイトルはフォルダ名を加工したもの
                title = d.replace("_", " ").title()
                
                # metadata.json があれば読み込む
                metadata = {}
                meta_path = os.path.join(item_path, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                
                items.append(KnowledgeItem(
                    id=d, 
                    category=category, 
                    title=metadata.get("title", title), 
                    base_path=item_path,
                    metadata=metadata
                ))
        return items

    def get_item_content(self, category: str, item_id: str) -> str:
        """特定のアイテムに含まれる全てのテキスト内容を結合して返す"""
        base_path = os.path.join(self.root_dir, category, item_id)
        if not os.path.isdir(base_path):
            return f"Resource not found: {base_path}"

        content = []
        files = sorted(os.listdir(base_path))
        
        # definition.txt があれば最優先にする
        if "definition.txt" in files:
            files.remove("definition.txt")
            files.insert(0, "definition.txt")
            
        for f in files:
            if f.endswith(".txt"):
                path = os.path.join(base_path, f)
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        text = file.read().strip()
                        if text:
                            content.append(f"=== {f} ===\n{text}")
                except Exception:
                    pass
        
        return "\n\n".join(content) if content else "No commentary text found."