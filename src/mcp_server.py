import os
import json
from typing import List
from mcp.server.fastmcp import FastMCP

# 既存のコアサービスを再利用
from services.api_client import api_client
from services.analysis_orchestrator import AnalysisOrchestrator
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer
from core.mcp_types import Move # NEW

# パス設定
KNOWLEDGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
PROMPT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "templates"))

# リポジトリ等の初期化
knowledge_repo = KnowledgeRepository(KNOWLEDGE_ROOT)
term_visualizer = TermVisualizer()

# FastMCP インスタンスの作成
mcp = FastMCP("katago-analyzer")

# --- Resources ---

@mcp.resource("mcp://game/current/sgf")
def get_current_sgf() -> str:
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

@mcp.resource("mcp://analysis/current/ownership-map")
def get_ownership_map() -> str:
    """現在の局面における全19x19マスの所有権（地）の生数値データを取得します。"""
    state = api_client.get_game_state()
    if not state: return "Error: No game state."
    res = api_client.analyze_move(state.get('history', []))
    return json.dumps(res.ownership) if res and res.ownership else "Ownership data unavailable."

@mcp.resource("mcp://analysis/current/influence-map")
def get_influence_map() -> str:
    """現在の局面における全19x19マスの影響力（厚み）の生数値データを取得します。"""
    state = api_client.get_game_state()
    if not state: return "Error: No game state."
    res = api_client.analyze_move(state.get('history', []))
    return json.dumps(res.influence) if res and res.influence else "Influence data unavailable."

@mcp.resource("mcp://analysis/move/{idx}/summary")
def get_move_summary(idx: int) -> str:
    """指定された手数(idx)時点での勝率や目数差の要約を取得します。"""
    state = api_client.get_game_state()
    if not state: return "Error: No state."
    hist = state.get('history', [])
    if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
    
    res = api_client.analyze_move(hist[:idx + 1])
    if not res: return "Analysis data unavailable for this move."
    
    return f"Move {idx} Summary:\n- Winrate(B): {res.winrate_label}\n- Score Lead(B): {res.score_lead:.1f}"

@mcp.resource("mcp://analysis/move/{idx}/regional-stats")
def get_move_regional_stats(idx: int) -> str:
    """指定された手数(idx)時点でのエリア別戦略統計レポートを取得します。"""
    state = api_client.get_game_state()
    if not state: return "Error: No state."
    hist = state.get('history', [])
    if idx < 0 or idx >= len(hist): return f"Error: Move index {idx} is out of range."
    
    orch = AnalysisOrchestrator(board_size=state.get('board_size', 19))
    collector = orch.analyze_full(hist[:idx + 1])
    strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
    
    return f"### Regional Strategic Analysis (Move {idx})\n" + "\n".join([f"- {d}" for d in strat_facts])

# --- System Prompts as Resources ---

@mcp.resource("mcp://prompts/system/instructor-guidelines")
def get_instructor_guidelines() -> str:
    """囲碁インストラクターとしての基本哲学、指導方針、および人格定義を取得します。"""
    filepath = os.path.join(PROMPT_ROOT, "go_instructor_system.md")
    if not os.path.exists(filepath): return "Error: Guideline file not found."
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

# --- Tools ---

@mcp.tool()
def katago_analyze(history: List[Move], board_size: int = 19) -> str:
    """
    囲碁の盤面をKataGoで詳細に解析し、勝率、目数、候補手を取得します。
    
    Args:
        history: 着手履歴 (例: [{"color": "B", "coord": "D4"}])
        board_size: 盤面サイズ (9, 13, 19)
    """
    # 内部形式 [['B', 'D4'], ...] に変換
    clean_history = [m.to_list() for m in history]
    res = api_client.analyze_move(clean_history, board_size)
    if not res: return "Error: Analysis failed."
    from dataclasses import asdict
    return json.dumps(asdict(res), indent=2, ensure_ascii=False)

@mcp.tool()
def detect_shapes(history: List[Move], board_size: int = 19) -> str:
    """現在の盤面から、幾何学的な形状（アキ三角など）を事実として抽出します。"""
    clean_history = [m.to_list() for m in history]
    facts = api_client.detect_shapes(clean_history, board_size)
    return facts

@mcp.tool()
def visualize_urgency(history: List[Move], board_size: int = 19) -> str:
    """『もし今パスをしたら相手にどこを打たれるか』の被害予測図を生成します。"""
    clean_history = [m.to_list() for m in history]
    urgency_data = api_client.analyze_urgency(clean_history, board_size)
    if not urgency_data or not urgency_data.get("opponent_pv"):
        return "被害手順が見つかりませんでした。"
    
    pv = urgency_data["opponent_pv"]
    title = f"Damage Prediction (Loss: {urgency_data['urgency']:.1f} pts)"
    path, err = term_visualizer.visualize_sequence(clean_history, pv, title=title, board_size=board_size)
    return f"図を生成しました: {path}\n相手の連打手順: {pv}"

@mcp.tool()
def simulate_scenario(sequence: List[Move], board_size: int = 19) -> str:
    """
    『もしここに打ったらどうなるか』という仮定のシナリオをシミュレーション解析します。
    現在の対局履歴の末尾に指定の手順を付け足した局面の解析結果を返します。
    
    Args:
        sequence: 付け足したい手順のリスト (例: [{"color": "B", "coord": "D4"}, {"color": "W", "coord": "C10"}])
        board_size: 盤面サイズ
    """
    state = api_client.get_game_state()
    if not state: return "Error: No current game state."
    
    current_history = state.get('history', [])
    sim_history = [m.to_list() for m in sequence]
    
    res = api_client.analyze_simulation(current_history, sim_history, board_size)
    if not res: return "Error: Simulation failed."
    
    from dataclasses import asdict
    return json.dumps(asdict(res), indent=2, ensure_ascii=False)

# --- Prompts ---

@mcp.prompt("go-instructor-system")
def prompt_instructor_system(board_size: str, player: str, knowledge: str) -> str:
    """インストラクターとしての基本人格を定義するプロンプトです。"""
    with open(os.path.join(PROMPT_ROOT, "go_instructor_system.md"), "r", encoding="utf-8") as f:
        template = f.read()
    return template.format(board_size=board_size, player=player, knowledge=knowledge)

@mcp.prompt("analysis-request")
def prompt_analysis_request(move_idx: str, history: str) -> str:
    """特定の局面に対する解説リクエストのテンプレートです。"""
    with open(os.path.join(PROMPT_ROOT, "analysis_request.md"), "r", encoding="utf-8") as f:
        template = f.read()
    return template.format(move_idx=move_idx, history=history)

if __name__ == "__main__":
    mcp.run()
