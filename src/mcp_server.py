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

KNOWLEDGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge"))

server = Server("katago-analyzer")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    resources = [
        types.Resource(
            uri="mcp://game/current/sgf",
            name="Current Game State",
            description="Real-time metadata, history, and current move information for the active game session.",
            mimeType="application/json"
        )
    ]
    # (既存のリソース走査ロジック)
    # 01_bad_shapes
    shapes_dir = os.path.join(KNOWLEDGE_ROOT, "01_bad_shapes")
    if os.path.exists(shapes_dir):
        for shape in os.listdir(shapes_dir):
            if os.path.isdir(os.path.join(shapes_dir, shape)):
                resources.append(types.Resource(
                    uri=f"mcp://knowledge/shapes/{shape}",
                    name=f"Shape Definition: {shape}",
                    description=f"Definition and examples for Go shape: {shape}",
                    mimeType="text/plain"
                ))
    # 02_techniques
    techs_dir = os.path.join(KNOWLEDGE_ROOT, "02_techniques")
    if os.path.exists(techs_dir):
        for tech in os.listdir(techs_dir):
            if os.path.isdir(os.path.join(techs_dir, tech)):
                resources.append(types.Resource(
                    uri=f"mcp://knowledge/techniques/{tech}",
                    name=f"Technique Definition: {tech}",
                    description=f"Explanation for Go technique: {tech}",
                    mimeType="text/plain"
                ))
    return resources

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "mcp://game/current/sgf":
        state = api_client.get_game_state()
        if not state:
            return "Error: Could not fetch game state from API server."
        
        summary = [
            "### Current Game Session Summary",
            f"- Current Move Index: {state.get('current_move_index', 0)}",
            f"- Total Moves: {state.get('total_moves', 0)}",
            f"- Metadata: {json.dumps(state.get('metadata', {}), ensure_ascii=False)}",
            "\n--- Recent Move History (Up to last 5) ---"
        ]
        # (履歴要約ロジック)
        hist = state.get('history', [])
        curr_idx = state.get('current_move_index', 0)
        start = max(0, curr_idx - 5)
        for i in range(start, min(len(hist), curr_idx + 1)):
            summary.append(f"Move {i}: {hist[i]}")
        return "\n".join(summary)

    # (既存の知識ベース読み込みロジック)

    if uri.startswith("mcp://knowledge/shapes/"):
        item_id = uri.replace("mcp://knowledge/shapes/", "")
        base_path = os.path.join(KNOWLEDGE_ROOT, "01_bad_shapes", item_id)
    elif uri.startswith("mcp://knowledge/techniques/"):
        item_id = uri.replace("mcp://knowledge/techniques/", "")
        base_path = os.path.join(KNOWLEDGE_ROOT, "02_techniques", item_id)
    else:
        raise ValueError(f"Unknown resource URI: {uri}")

    if not os.path.isdir(base_path):
        return f"Resource not found: {base_path}"

    content = []
    files = sorted(os.listdir(base_path))
    if "definition.txt" in files:
        files.remove("definition.txt")
        files.insert(0, "definition.txt")
        
    for f in files:
        if f.endswith(".txt"):
            with open(os.path.join(base_path, f), "r", encoding="utf-8") as file:
                content.append(f"=== {f} ===\n{file.read()}")
    
    return "\n\n".join(content) if content else "No commentary text found."

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
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if not arguments: raise ValueError("Args required")
    history = arguments.get("history", [])
    
    # 履歴データのサニタイズ（1次元リストを2次元ペアに変換）
    if history and isinstance(history[0], str):
        new_h = []
        for i in range(0, len(history), 2):
            if i + 1 < len(history): new_h.append([history[i], history[i+1]])
        history = new_h

    if name == "katago_analyze":
        res = api_client.analyze_move(history)
        if res:
            return [types.TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
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
