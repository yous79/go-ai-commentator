import os
import asyncio
from mcp.server.fastmcp import FastMCP

# 内部モジュールのインポート
from mcp_modules.analysis import AnalysisModule
from mcp_modules.knowledge import KnowledgeModule
from mcp_modules.system import SystemModule
from mcp_modules.session import SessionManager
from mcp_modules.local_solver import LocalSolverModule # 新しい解法モジュール

# 共通リポジトリの初期化
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer

# 共通サービスの初期化 (Dependency Injection Root)
from services.api_client import api_client
from services.analysis_orchestrator import AnalysisOrchestrator

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "knowledge"))
PROMPT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "prompts", "templates"))

# リソースの準備
knowledge_repo = KnowledgeRepository(KNOWLEDGE_ROOT)
term_visualizer = TermVisualizer()
session_manager = SessionManager()
orchestrator = AnalysisOrchestrator() # 共通のオーケストレーター

# FastMCP インスタンスの作成
mcp = FastMCP("katago-analyzer")

# --- 各モジュールの統合 ---
# 依存性を明示的に注入する
analysis_mod = AnalysisModule(mcp, session_manager)
knowledge_mod = KnowledgeModule(mcp, knowledge_repo, term_visualizer, session_manager)
system_mod = SystemModule(mcp, PROMPT_ROOT, session_manager)
local_solver_mod = LocalSolverModule(mcp, session_manager) # 登録

if __name__ == "__main__":
    mcp.run()
