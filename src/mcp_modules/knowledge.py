import os
import json
from mcp.server.fastmcp import FastMCP
from services.api_client import api_client
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer
from core.mcp_types import Move
from mcp_modules.session import SessionManager
from typing import List, Optional

from mcp_modules.base import McpModuleBase

class KnowledgeModule(McpModuleBase):
    """ゲーム状態、知識ベース、可視化ツールを管理するモジュール。セッション（コンテキスト・オフローディング）に対応。"""
    
    def __init__(self, mcp: FastMCP, knowledge_repo: KnowledgeRepository, term_visualizer: TermVisualizer, session_manager: SessionManager):
        super().__init__(session_manager)
        self.repo = knowledge_repo
        self.visualizer = term_visualizer
        
        # 1. Resources
        mcp.resource("mcp://game/current/sgf")(self.get_current_sgf)
        mcp.resource("mcp://game/current/relevant-knowledge")(self.get_relevant_knowledge)
        self._register_static_resources(mcp)
        
        # 2. Tools
        mcp.tool()(self.detect_shapes)
        mcp.tool()(self.visualize_urgency)

    def get_current_sgf(self) -> str:
        """現在の対局セッションの要約を取得します。"""
        try:
            hist, size = self.resolve_context(None, None)
            summary = [
                "### Current Session Context (Offloaded)",
                f"- Board Size: {size}",
                f"- Total Context Moves: {len(hist)}",
                "\n--- Recent History (Last 5) ---"
            ]
            start = max(0, len(hist) - 5)
            for i in range(start, len(hist)):
                summary.append(f"Move {i}: {hist[i]}")
            return "\n".join(summary)
        except:
            return "No active session context offloaded yet."

    def get_relevant_knowledge(self) -> str:
        """現在の局面の形状に関連する知識ベース定義を抽出します。"""
        try:
            hist, size = self.resolve_context(None, None)
            detected_ids = api_client.detect_shape_ids(hist, size)
            if not detected_ids: return "特に関連する知識は見つかりませんでした。"
            
            text = ["### 関連知識ベース"]
            for item_id in detected_ids:
                for cat in ["01_bad_shapes", "02_techniques"]:
                    item = next((i for i in self.repo.get_items(cat) if i.id == item_id), None)
                    if item:
                        content = self.repo.get_item_content(cat, item_id)
                        text.append(f"#### 【{item.title}】\n{content}")
                        break
            return "\n\n".join(text)
        except Exception as e:
            return f"Error: {str(e)}"

    def _register_static_resources(self, mcp: FastMCP):
        """静的な定義ファイルをリソースとして一括登録"""
        for cat in ["01_bad_shapes", "02_techniques"]:
            for item in self.repo.get_items(cat):
                uri = f"mcp://knowledge/{cat.replace('01_', '').replace('02_', '')}/{item.id}"
                
                # クロージャの遅延評価を防ぐためのファクトリ関数
                def make_handler(c, i):
                    def _read() -> str:
                        return self.repo.get_item_content(c, i)
                    return _read
                
                mcp.resource(uri)(make_handler(cat, item.id))

    def detect_shapes(self, history: Optional[List[Move]] = None, board_size: Optional[int] = None) -> str:
        """現在の盤面から、幾何学的な形状（アキ三角など）を抽出します。解消地点や局面フェーズ（終盤等）も含みます。"""
        try:
            target_h, target_s = self.resolve_context(history, board_size)
            
            # 詳細な解析（Orchestrator）を実行してフェーズ情報を得る
            from services.analysis_orchestrator import AnalysisOrchestrator
            orch = AnalysisOrchestrator(board_size=target_s)
            collector = orch.analyze_full(target_h)
            
            phase = collector.get_game_phase()
            
            # 形状検知の結果を取得（互換性のため既存の形式を維持しつつ拡張）
            facts = api_client.detect_shapes(target_h, target_s)
            
            # 結果の統合
            response = {
                "game_phase": phase,
                "facts": facts if isinstance(facts, list) else []
            }
            
            if not response["facts"] and phase == "normal":
                return "特筆すべき形状は検出されませんでした。"
                
            return json.dumps(response, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"

    def visualize_urgency(self, history: Optional[List[Move]] = None, board_size: Optional[int] = None) -> str:
        """『もし今パスをしたら相手にどこを打たれるか』の被害予測図を生成します。"""
        try:
            target_h, target_s = self.resolve_context(history, board_size)
            urgency_data = api_client.analyze_urgency(target_h, target_s)
            if not urgency_data or not urgency_data.get("opponent_pv"):
                return "被害手順が見つかりませんでした。"
            pv = urgency_data["opponent_pv"]
            title = f"Damage Prediction (Loss: {urgency_data['urgency']:.1f} pts)"
            path, err = self.visualizer.visualize_sequence(target_h, pv, title=title, board_size=target_s)
            return f"図を生成しました: {path}\n相手の連打手順: {pv}"
        except Exception as e:
            return f"Error: {str(e)}"
