import json
from typing import List, Any
from mcp.server.fastmcp import FastMCP
from services.api_client import api_client
from services.analysis_orchestrator import AnalysisOrchestrator
from core.mcp_types import Move

class AnalysisModule:
    """解析、シミュレーション、統計関連のツールとリソースを管理するモジュール"""
    
    def __init__(self, mcp: FastMCP):
        # 1. Resources
        mcp.resource("mcp://analysis/current/ownership-map")(self.get_ownership_map)
        mcp.resource("mcp://analysis/current/influence-map")(self.get_influence_map)
        mcp.resource("mcp://analysis/current/regional-stats")(self.get_regional_stats)
        mcp.resource("mcp://analysis/move/{idx}/summary")(self.get_move_summary)
        mcp.resource("mcp://analysis/move/{idx}/regional-stats")(self.get_move_regional_stats)
        
        # 2. Tools
        mcp.tool()(self.katago_analyze)
        mcp.tool()(self.simulate_scenario)

    def get_ownership_map(self) -> str:
        """現在の局面における全19x19マスの所有権（地）の生数値データを取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No game state."
        res = api_client.analyze_move(state.get('history', []))
        return json.dumps(res.ownership) if res and res.ownership else "Ownership data unavailable."

    def get_influence_map(self) -> str:
        """現在の局面における全19x19マスの影響力（厚み）の生数値データを取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No game state."
        res = api_client.analyze_move(state.get('history', []))
        return json.dumps(res.influence) if res and res.influence else "Influence data unavailable."

    def get_regional_stats(self) -> str:
        """盤面を9エリアに分割した、地と勢力の詳細な戦略統計レポートを取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No game state."
        orch = AnalysisOrchestrator(board_size=state.get('board_size', 19))
        collector = orch.analyze_full(state.get('history', []))
        strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
        return "### Regional Strategic Analysis\n" + "\n".join([f"- {d}" for d in strat_facts])

    def get_move_summary(self, idx: int) -> str:
        """指定された手数(idx)時点での勝率や目数差の要約を取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No state."
        hist = state.get('history', [])
        if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
        res = api_client.analyze_move(hist[:idx + 1])
        if not res: return "Analysis data unavailable for this move."
        return f"Move {idx} Summary:\n- Winrate(B): {res.winrate_label}\n- Score Lead(B): {res.score_lead:.1f}"

    def get_move_regional_stats(self, idx: int) -> str:
        """指定された手数(idx)時点でのエリア別戦略統計レポートを取得します。"""
        state = api_client.get_game_state()
        if not state: return "Error: No state."
        hist = state.get('history', [])
        if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
        orch = AnalysisOrchestrator(board_size=state.get('board_size', 19))
        collector = orch.analyze_full(hist[:idx + 1])
        strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
        return f"### Regional Strategic Analysis (Move {idx})\n" + "\n".join([f"- {d}" for d in strat_facts])

    def katago_analyze(self, history: List[Move], board_size: int = 19) -> str:
        """
        囲碁の盤面をKataGoで詳細に解析し、勝率、目数、候補手を取得します。
        """
        clean_history = [m.to_list() for m in history]
        res = api_client.analyze_move(clean_history, board_size)
        if not res: return "Error: Analysis failed."
        from dataclasses import asdict
        return json.dumps(asdict(res), indent=2, ensure_ascii=False)

    def simulate_scenario(self, sequence: List[Move], board_size: int = 19) -> str:
        """
        『もしここに打ったらどうなるか』という仮定のシナリオをシミュレーション解析します。
        """
        state = api_client.get_game_state()
        if not state: return "Error: No current game state."
        current_history = state.get('history', [])
        sim_history = [m.to_list() for m in sequence]
        res = api_client.analyze_simulation(current_history, sim_history, board_size)
        if not res: return "Error: Simulation failed."
        from dataclasses import asdict
        return json.dumps(asdict(res), indent=2, ensure_ascii=False)

