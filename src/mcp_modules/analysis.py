import json
from typing import List, Any, Optional
from mcp.server.fastmcp import FastMCP
from services.api_client import api_client
from services.analysis_orchestrator import AnalysisOrchestrator
from core.mcp_types import Move
from mcp_modules.session import SessionManager

class AnalysisModule:
    """解析、シミュレーション、統計関連のツールとリソースを管理するモジュール。セッション（コンテキスト・オフローディング）に対応。"""
    
    def __init__(self, mcp: FastMCP, session_manager: SessionManager):
        self.session = session_manager
        
        # 1. Resources
        mcp.resource("mcp://analysis/current/ownership-map")(self.get_ownership_map)
        mcp.resource("mcp://analysis/current/influence-map")(self.get_influence_map)
        mcp.resource("mcp://analysis/current/regional-stats")(self.get_regional_stats)
        mcp.resource("mcp://analysis/move/{idx}/summary")(self.get_move_summary)
        mcp.resource("mcp://analysis/move/{idx}/regional-stats")(self.get_move_regional_stats)
        
        # 2. Tools
        mcp.tool()(self.katago_analyze)
        mcp.tool()(self.simulate_scenario)
        mcp.tool()(self.compare_scenarios)

    def _get_context(self, history: Optional[List[Move]], board_size: Optional[int]) -> tuple:
        """引数またはセッションから現在の解析コンテキスト（履歴, サイズ）を確定させる"""
        if history is None:
            if not self.session.is_initialized:
                raise ValueError("No active session. Please call sync_session first or provide history.")
            return self.session.history, board_size or self.session.board_size
        
        return [m.to_list() for m in history], board_size or 19

    def get_ownership_map(self) -> str:
        """現在の局面における全19x19マスの所有権（地）の生数値データを取得します。"""
        # リソースは最新の同期済み状態を優先
        hist, size = self._get_context(None, None)
        res = api_client.analyze_move(hist, size)
        return json.dumps(res.ownership) if res and res.ownership else "Ownership data unavailable."

    def get_influence_map(self) -> str:
        """現在の局面における全19x19マスの影響力（厚み）の生数値データを取得します。"""
        hist, size = self._get_context(None, None)
        res = api_client.analyze_move(hist, size)
        return json.dumps(res.influence) if res and res.influence else "Influence data unavailable."

    def get_regional_stats(self) -> str:
        """盤面を9エリアに分割した、地と勢力の詳細な戦略統計レポートを取得します。"""
        hist, size = self._get_context(None, None)
        orch = AnalysisOrchestrator(board_size=size)
        collector = orch.analyze_full(hist)
        strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
        return "### Regional Strategic Analysis\n" + "\n".join([f"- {d}" for d in strat_facts])

    def get_move_summary(self, idx: int) -> str:
        """指定された手数(idx)時点での勝率や目数差の要約を取得します。"""
        hist, size = self._get_context(None, None)
        if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
        res = api_client.analyze_move(hist[:idx + 1], size)
        if not res: return "Analysis data unavailable for this move."
        return f"Move {idx} Summary:\n- Winrate(B): {res.winrate_label}\n- Score Lead(B): {res.score_lead:.1f}"

    def get_move_regional_stats(self, idx: int) -> str:
        """指定された手数(idx)時点でのエリア別戦略統計レポートを取得します。"""
        hist, size = self._get_context(None, None)
        if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
        orch = AnalysisOrchestrator(board_size=size)
        collector = orch.analyze_full(hist[:idx + 1])
        strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
        return f"### Regional Strategic Analysis (Move {idx})\n" + "\n".join([f"- {d}" for d in strat_facts])

    def katago_analyze(self, history: Optional[List[Move]] = None, board_size: Optional[int] = None) -> str:
        """
        囲碁の盤面をKataGoで詳細に解析し、勝率、目数、候補手を取得します。
        局面フェーズ（終盤等）の情報も含みます。
        """
        try:
            target_history, target_size = self._get_context(history, board_size)
            res = api_client.analyze_move(target_history, target_size)
            if not res: return "Error: Analysis failed."
            
            # 局面フェーズの判定
            orch = AnalysisOrchestrator(board_size=target_size)
            collector = orch.analyze_full(target_history)
            phase = collector.get_game_phase()
            
            from dataclasses import asdict
            data = asdict(res)
            data["game_phase"] = phase
            
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"

    def simulate_scenario(self, sequence: List[Move], board_size: Optional[int] = None) -> str:
        """
        現在のセッション局面（または提供されたコンテキスト）から追加の手順をシミュレート解析します。
        sequence: 追加したい手順のリスト
        """
        try:
            base_history, target_size = self._get_context(None, board_size)
            add_moves = [m.to_list() for m in sequence]
            res = api_client.analyze_simulation(base_history, add_moves, target_size)
            if not res: return "Error: Simulation failed."
            from dataclasses import asdict
            return json.dumps(asdict(res), indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"

    def compare_scenarios(self, scenarios: List[List[Move]], board_size: Optional[int] = None) -> str:
        """
        現在のセッション局面をベースに、複数の仮定シナリオを同時に解析し比較します。
        """
        try:
            base_history, target_size = self._get_context(None, board_size)
            results = []
            for i, seq in enumerate(scenarios):
                add_moves = [m.to_list() for m in seq]
                res = api_client.analyze_simulation(base_history, add_moves, target_size)
                if res:
                    from dataclasses import asdict
                    results.append({
                        "scenario_index": i,
                        "winrate": res.winrate,
                        "winrate_label": res.winrate_label,
                        "score_lead": res.score_lead,
                        "data": asdict(res)
                    })
            
            if len(results) >= 2:
                base = results[0]
                for other in results[1:]:
                    other["diff_winrate"] = other["winrate"] - base["winrate"]
                    other["diff_score"] = other["score_lead"] - base["score_lead"]
            
            return json.dumps(results, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"