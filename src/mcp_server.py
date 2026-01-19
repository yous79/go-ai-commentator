import os
import json
from mcp.server.fastmcp import FastMCP

# 既存のコアサービスを再利用
from services.api_client import api_client
from services.analysis_orchestrator import AnalysisOrchestrator
from core.knowledge_repository import KnowledgeRepository
from services.term_visualizer import TermVisualizer

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

@mcp.resource("mcp://analysis/current/regional-stats")
def get_regional_stats() -> str:
    """盤面を9エリアに分割した、地と勢力の詳細な戦略統計レポートを取得します。"""
    state = api_client.get_game_state()
    if not state: return "Error: No game state."
    orch = AnalysisOrchestrator(board_size=state.get('board_size', 19))
    collector = orch.analyze_full(state.get('history', []))
    strat_facts = [f.description for f in collector.facts if f.category.name == "STRATEGY"]
    return "### Regional Strategic Analysis\n" + "\n".join([f"- {d}" for d in strat_facts])

@mcp.resource("mcp://game/current/relevant-knowledge")
def get_relevant_knowledge() -> str:
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
            item = next((i for i in knowledge_repo.get_items(cat) if i.id == item_id), None)
            if item:
                content = knowledge_repo.get_item_content(cat, item_id)
                text.append(f"#### 【{item.title}】\n{content}")
                break
    return "\n\n".join(text)

# --- Tools ---

@mcp.tool()
def katago_analyze(history: list, board_size: int = 19) -> str:
    """
    囲碁の盤面をKataGoで詳細に解析します。
    
    Args:
        history: 着手履歴 (例: [['B', 'D4'], ['W', 'Q16']])
        board_size: 盤面サイズ (デフォルト19)
    """
    res = api_client.analyze_move(history, board_size)
    if not res: return "Error: Analysis failed."
    # DTOを辞書に変換してJSON化
    from dataclasses import asdict
    return json.dumps(asdict(res), indent=2, ensure_ascii=False)

@mcp.tool()
def detect_shapes(history: list, board_size: int = 19) -> str:
    """現在の盤面から、幾何学的な形状（アキ三角など）を事実として抽出します。"""
    facts = api_client.detect_shapes(history, board_size)
    return facts

@mcp.tool()
def visualize_urgency(history: list, board_size: int = 19) -> str:
    """『もし今パスをしたら相手にどこを打たれるか』の被害予測図を生成します。"""
    urgency_data = api_client.analyze_urgency(history, board_size)
    if not urgency_data or not urgency_data.get("opponent_pv"):
        return "被害手順が見つかりませんでした。"
    
    pv = urgency_data["opponent_pv"]
    title = f"Damage Prediction (Loss: {urgency_data['urgency']:.1f} pts)"
    path, err = term_visualizer.visualize_sequence(history, pv, title=title, board_size=board_size)
    return f"図を生成しました: {path}\n相手の連打手順: {pv}"

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
