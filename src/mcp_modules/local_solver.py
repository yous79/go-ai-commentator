from typing import List, Optional, Tuple
from mcp.server.fastmcp import FastMCP
from mcp_modules.base import McpModuleBase
from mcp_modules.session import SessionManager
from services.analysis_orchestrator import AnalysisOrchestrator
from services.api_client import api_client
from core.point import Point
from core.game_board import GameBoard, Color
from core.mcp_types import Move
import json

class LocalSolverModule(McpModuleBase):
    """
    盤面の一部（局所）を切り出して集中解析（証明）を行うモジュール。
    死活（Life & Death）の厳密な判定に特化している。
    """
    
    def __init__(self, mcp: FastMCP, session_manager: SessionManager):
        super().__init__(session_manager)
        
        # Tools
        mcp.tool()(self.solve_local_life_death)

    def solve_local_life_death(self, center_gtp: str, radius: int = 4, visits: int = 500) -> str:
        """
        指定された座標周辺を切り出し、局所的な死活問題を解きます。
        
        Args:
            center_gtp: 中心座標 (e.g., "Q16")
            radius: 切り出す範囲の半径 (デフォルト4 = 9x9程度の範囲)
            visits: 探索数。通常より多めに設定して確度を高める。
            
        Returns:
            JSON string containing local status, ownership map of the region, and best sequence.
        """
        try:
            full_hist, size = self.resolve_context(None, None)
            
            # 1. 現在の盤面を復元
            from core.board_simulator import BoardSimulator
            sim = BoardSimulator(size)
            ctx = sim.reconstruct_to_context(full_hist, size)
            
            center = Point.from_gtp(center_gtp)
            if not ctx.board.is_on_board(center):
                return "Error: Center point is off board."

            # 2. 局所コンテキストの作成 (簡易的アプローチ: 周囲以外を埋めるなど)
            # 本格的な局所解析はエンジンのサポートが必要だが、
            # ここでは「全体解析の結果から局所データを抽出・深掘り」するアプローチをとる。
            # 将来的にはKataGoの 'rectangular ownership' などを活用可能。
            
            # 現段階では、全体解析をHigh Visitsで実行し、局所データをフィルタリングして返す
            # これにより「局所的な証明」に近い精度を担保する
            res = api_client.analyze_move(full_hist, size, visits=visits)
            
            if not res or not res.ownership:
                return "Error: Failed to analyze local situation."

            # 3. 局所データの抽出
            local_ownership = []
            local_points = []
            
            for r in range(center.row - radius, center.row + radius + 1):
                for c in range(center.col - radius, center.col + radius + 1):
                    p = Point(r, c)
                    if ctx.board.is_on_board(p):
                        idx = r * size + c
                        own = res.ownership[idx]
                        local_ownership.append({
                            "coord": p.to_gtp(),
                            "ownership": own,
                            "stone": ctx.board.get(p).key if ctx.board.get(p) else None
                        })
                        local_points.append(p)

            # 4. 判定ロジック
            # 局所エリア内の石の平均Ownershipで判定
            target_color = ctx.board.get(center)
            status = "unknown"
            avg_own = 0
            if target_color:
                relevant_stones = [d["ownership"] for d in local_ownership if d["stone"] == target_color.key]
                if relevant_stones:
                    avg_own = sum(relevant_stones) / len(relevant_stones)
                    # 黒石(+1)がdeadなら低い値、白石(-1)がdeadなら高い値
                    if target_color == Color.BLACK:
                        if avg_own < 0.1: status = "DEAD"
                        elif avg_own > 0.8: status = "ALIVE"
                        else: status = "UNSETTLED (Ko/Seki)"
                    else:
                        if avg_own > -0.1: status = "DEAD"
                        elif avg_own < -0.8: status = "ALIVE"
                        else: status = "UNSETTLED (Ko/Seki)"
            else:
                status = "EMPTY"

            return json.dumps({
                "region_center": center_gtp,
                "status": status,
                "avg_ownership": avg_own,
                "local_data_count": len(local_ownership),
                "proof_level": "Local-High-Visits"
            }, indent=2)

        except Exception as e:
            return f"Error: {str(e)}"
