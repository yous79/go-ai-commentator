import os
import json
from mcp.server.fastmcp import FastMCP
from services.api_client import api_client
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer
from core.mcp_types import Move
from typing import List

class KnowledgeModule:
    """ゲーム状態、知識ベース、可視化ツールを管理するモジュール"""
    
    def __init__(self, mcp: FastMCP, knowledge_repo: KnowledgeRepository, term_visualizer: TermVisualizer):
        self.repo = knowledge_repo
        self.visualizer = term_visualizer
        
        # 1. Resources
        mcp.resource("mcp://game/current/sgf")(self.get_current_sgf)
        mcp.resource("mcp://game/current/relevant-knowledge")(self.get_relevant_knowledge)
        
        # ダイナミックリソースの登録
        # FastMCPでは正規表現風のURIも扱えるが、ここでは既存のリストアップを維持
        self._register_static_resources(mcp)
        
        # 2. Tools
        mcp.tool()(self.detect_shapes)
        mcp.tool()(self.visualize_urgency)

    def get_current_sgf(self) -> str:
        """現在の対局セッションの履歴、手数、メタデータの要約を取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: Could not fetch game state."
        summary = [
            "### Current Game Session Summary",
            f"- Current Move Index: {state.get('current_move_index', 0)}",
            f"- Total Moves: {state.get('total_moves', 0)}",
            f"- Metadata: {json.dumps(state.get('metadata', {}), ensure_ascii=False)}",
            "\n--- Recent Move History (Up to last 5) ---"
        ]
        hist = state.get('history', [])
        curr_idx = state.get('current_move_index', 0)
        start = max(0, curr_idx - 5)
        for i in range(start, min(len(hist), curr_idx + 1)):
            summary.append(f"Move {i}: {hist[i]}")
        return "\n".join(summary)

    def get_relevant_knowledge(self) -> str:
        """現在の局面に現れている形状や手筋に関連する知識ベースの定義を抽出します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No state."
        history = state.get('history', [])
        curr_idx = state.get('current_move_index', 0)
        detected_ids = api_client.detect_shape_ids(history[:curr_idx + 1])
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

    def _register_static_resources(self, mcp: FastMCP):
        """静的な定義ファイルをリソースとして一括登録"""
        for cat in ["01_bad_shapes", "02_techniques"]:
            for item in self.repo.get_items(cat):
                uri = f"mcp://knowledge/{cat.replace('01_', '').replace('02_', '')}/{item.id}"
                # クロージャの問題を避けるため、デフォルト引数を使用
                @mcp.resource(uri)
                def _read(c=cat, i=item.id) -> str:
                    return self.repo.get_item_content(c, i)

    def detect_shapes(self, history: List[Move], board_size: int = 19) -> str:
        """現在の盤面から、幾何学的な形状（アキ三角など）を構造化された事実として抽出します。解消地点などのメタデータも含みます。"""
        clean_history = [m.to_list() for m in history]
        facts = api_client.detect_shapes(clean_history, board_size)
        if not facts or (is_list := isinstance(facts, list) and len(facts) == 0):
            return "特筆すべき形状は検出されませんでした。"
        return json.dumps(facts, indent=2, ensure_ascii=False)

    def visualize_urgency(self, history: List[Move], board_size: int = 19) -> str:
        ""『もし今パスをしたら相手にどこを打たれるか』の被害予測図を生成します。"""
        clean_history = [m.to_list() for m in history]
        urgency_data = api_client.analyze_urgency(clean_history, board_size)
        if not urgency_data or not urgency_data.get("opponent_pv"):
            return "被害手順が見つかりませんでした。"
        pv = urgency_data["opponent_pv"]
        title = f"Damage Prediction (Loss: {urgency_data['urgency']:.1f} pts)"
        path, err = self.visualizer.visualize_sequence(clean_history, pv, title=title, board_size=board_size)
        return f"図を生成しました: {path}\n相手の連打手順: {pv}"