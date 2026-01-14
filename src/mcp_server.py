import asyncio
import os
import sys
import json

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Use the centralized API client
from services.api_client import api_client
from core.knowledge_repository import KnowledgeRepository

KNOWLEDGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))
PROMPT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "templates"))
knowledge_repo = KnowledgeRepository(KNOWLEDGE_ROOT)

server = Server("katago-analyzer")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    resources = [
        types.Resource(
            uri="mcp://game/current/sgf",
            name="Current Game State",
            description="Real-time metadata, history, and current move information for the active game session.",
            mimeType="application/json"
        ),
        types.Resource(
            uri="mcp://game/current/relevant-knowledge",
            name="Relevant Knowledge for Current Board",
            description="Dynamically aggregated definitions and commentary for shapes and techniques detected in the current board position.",
            mimeType="text/plain"
        )
    ]
    
    for item in knowledge_repo.get_items("01_bad_shapes"):
        resources.append(types.Resource(
            uri=f"mcp://knowledge/shapes/{item.id}",
            name=f"Shape Definition: {item.id}",
            description=f"Definition and examples for Go shape: {item.title}",
            mimeType="text/plain"
        ))
    
    for item in knowledge_repo.get_items("02_techniques"):
        resources.append(types.Resource(
            uri=f"mcp://knowledge/techniques/{item.id}",
            name=f"Technique Definition: {item.id}",
            description=f"Explanation for Go technique: {item.title}",
            mimeType="text/plain"
        ))
    return resources

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "mcp://game/current/sgf":
        state = api_client.get_game_state()
        if not state: return "Error: Could not fetch game state from API server."
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

    if uri == "mcp://game/current/relevant-knowledge":
        state = api_client.get_game_state()
        if not state: return "Error: Could not fetch game state."
        history = state.get('history', [])
        curr_idx = state.get('current_move_index', 0)
        current_history = history[:curr_idx + 1]
        detected_ids = api_client.detect_shape_ids(current_history)
        if not detected_ids: return "現在の局面に該当する特定の悪形や手筋は検知されていません。"
        relevant_text = ["### 現在の局面に関連する知識ベース"]
        for item_id in detected_ids:
            content = knowledge_repo.get_item_content("01_bad_shapes", item_id)
            if "Resource not found" in content:
                content = knowledge_repo.get_item_content("02_techniques", item_id)
            if "Resource not found" not in content:
                relevant_text.append(f"#### 【{item_id.replace('_', ' ').title()}】\n{content}")
        return "\n\n".join(relevant_text)

    if uri.startswith("mcp://knowledge/shapes/"):
        item_id = uri.replace("mcp://knowledge/shapes/", "")
        return knowledge_repo.get_item_content("01_bad_shapes", item_id)
    elif uri.startswith("mcp://knowledge/techniques/"):
        item_id = uri.replace("mcp://knowledge/techniques/", "")
        return knowledge_repo.get_item_content("02_techniques", item_id)
    raise ValueError(f"Unknown resource URI: {uri}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="go-instructor-system",
            description="囲碁インストラクターとしてのシステム定義",
            arguments=[
                types.PromptArgument(name="board_size", description="盤面サイズ (例: 19)", required=True),
                types.PromptArgument(name="player", description="手番の色 (黒/白)", required=True),
                types.PromptArgument(name="knowledge", description="提供する知識テキスト", required=True)
            ]
        ),
        types.Prompt(
            name="analysis-request",
            description="現在の局面の解析・解説リクエスト",
            arguments=[
                types.PromptArgument(name="move_idx", description="現在の手数", required=True),
                types.PromptArgument(name="history", description="直近の着手履歴", required=True)
            ]
        )
    ]

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict | None) -> types.GetPromptResult:
    if not arguments: arguments = {}
    filename = name.replace("-", "_") + ".md"
    filepath = os.path.join(PROMPT_ROOT, filename)
    
    if not os.path.exists(filepath):
        raise ValueError(f"Prompt template not found: {name}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        template = f.read()
    
    # テンプレート内の {key} を arguments の値で置換
    try:
        content = template.format(**arguments)
    except KeyError as e:
        content = f"Error: Missing required argument {e} for prompt {name}"

    return types.GetPromptResult(
        description=f"Prompt: {name}",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=content)
            )
        ]
    )

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="katago_analyze",
            description="囲碁の盤面をKataGoで解析します。履歴(history)を渡してください。",
            inputSchema={
                "type": "OBJECT",
                "properties": {
                    "history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "string"}}}
                },
                "required": ["history"]
            }
        ),
        types.Tool(
            name="detect_shapes",
            description="現在の盤面から、アキ三角やサカレ形などの幾何学的な特徴を検知します。",
            inputSchema={
                "type": "OBJECT",
                "properties": {
                    "history": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "string"}}}
                },
                "required": ["history"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if not arguments: raise ValueError("Args required")
    history = arguments.get("history", [])
    if history and isinstance(history[0], str):
        new_h = []
        for i in range(0, len(history), 2):
            if i + 1 < len(history): new_h.append([history[i], history[i+1]])
        history = new_h

    if name == "katago_analyze":
        res = api_client.analyze_move(history)
        if res: return [types.TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
        return [types.TextContent(type="text", text="API Error: Analysis failed.")]
    elif name == "detect_shapes":
        facts = api_client.detect_shapes(history)
        return [types.TextContent(type="text", text=facts)]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_server):
        await server.run(read_stream, write_server, InitializationOptions(
            server_name="katago-analyzer", server_version="1.0.0",
            capabilities=server.get_capabilities(notification_options=NotificationOptions(tools_changed=True), experimental_capabilities={})
        ))

if __name__ == "__main__":
    asyncio.run(main())
