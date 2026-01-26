import os
from typing import List
from mcp.server.fastmcp import FastMCP
from mcp_modules.session import SessionManager
from mcp_modules.base import McpModuleBase
from core.mcp_types import Move

class SystemModule(McpModuleBase):
    """人格定義、プロンプトテンプレート、システムメタデータ、セッション管理を担当するモジュール"""
    
    def __init__(self, mcp: FastMCP, prompt_root: str, session_manager: SessionManager):
        super().__init__(session_manager)
        self.prompt_root = prompt_root
        
        # 1. Resources
        mcp.resource("mcp://prompts/system/instructor-guidelines")(self.get_instructor_guidelines)
        
        # 2. Prompts
        mcp.prompt("go-instructor-system")(self.prompt_instructor_system)
        mcp.prompt("analysis-request")(self.prompt_analysis_request)

        # 3. Tools
        mcp.tool()(self.sync_session)

    def get_instructor_guidelines(self) -> str:
        """囲碁インストラクターとしての基本哲学、指導方針、および人格定義を取得します。"""
        filepath = os.path.join(self.prompt_root, "go_instructor_system.md")
        if not os.path.exists(filepath): return "Error: Guideline file not found."
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def prompt_instructor_system(self, board_size: str, player: str, knowledge: str) -> str:
        """インストラクターとしての基本人格を定義するプロンプトです。"""
        filepath = os.path.join(self.prompt_root, "go_instructor_system.md")
        with open(filepath, "r", encoding="utf-8") as f:
            template = f.read()
        return template.format(board_size=board_size, player=player, knowledge=knowledge)

    def prompt_analysis_request(self, move_idx: str, history: str) -> str:
        """特定の局面に対する解説リクエストのテンプレートです。"""
        filepath = os.path.join(self.prompt_root, "analysis_request.md")
        with open(filepath, "r", encoding="utf-8") as f:
            template = f.read()
        return template.format(move_idx=move_idx, history=history)

    def sync_session(self, history: List[Move], board_size: int = 19) -> str:
        """
        現在の対局状態（履歴と盤面サイズ）をサーバーに同期し、オフロードします。
        局面フェーズの判定結果も返します。
        """
        clean_history = [m.to_list() for m in history]
        self.session.update(clean_history, board_size)
        
        # フェーズ判定を実行
        # TODO: 将来的にはDIされたOrchestratorを使用する
        from services.analysis_orchestrator import AnalysisOrchestrator
        orch = AnalysisOrchestrator(board_size=board_size)
        collector = orch.analyze_full(clean_history)
        phase = collector.get_game_phase()
        
        return f"Session synced. Context contains {len(clean_history)} moves. Game phase: {phase}"