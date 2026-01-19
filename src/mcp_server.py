import os
import asyncio
from mcp.server.fastmcp import FastMCP

# 内部モジュールのインポート
from mcp.analysis import AnalysisModule
from mcp.knowledge import KnowledgeModule
from mcp.system import SystemModule

# 共通リポジトリの初期化
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "knowledge"))
PROMPT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "prompts", "templates"))

# リソースの準備
knowledge_repo = KnowledgeRepository(KNOWLEDGE_ROOT)
term_visualizer = TermVisualizer()

# FastMCP インスタンスの作成
mcp = FastMCP("katago-analyzer")

# --- 各モジュールの統合 ---
# 各モジュールは __init__ 内で自律的にツールやリソースを mcp インスタンスに登録する
analysis_mod = AnalysisModule(mcp)
knowledge_mod = KnowledgeModule(mcp, knowledge_repo, term_visualizer)
system_mod = SystemModule(mcp, PROMPT_ROOT)

if __name__ == "__main__":
    mcp.run()