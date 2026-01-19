import os
from mcp.server.fastmcp import FastMCP

class SystemModule:
    """人格定義、プロンプトテンプレート、システムメタデータを管理するモジュール"""
    
    def __init__(self, mcp: FastMCP, prompt_root: str):
        self.prompt_root = prompt_root
        
        # 1. Resources
        mcp.resource("mcp://prompts/system/instructor-guidelines")(self.get_instructor_guidelines)
        
        # 2. Prompts
        mcp.prompt("go-instructor-system")(self.prompt_instructor_system)
        mcp.prompt("analysis-request")(self.prompt_analysis_request)

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
