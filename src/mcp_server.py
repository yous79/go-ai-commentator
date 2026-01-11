import asyncio
import os
import sys
import json

# Add current directory to path for imports
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from drivers.katago_driver import KataGoDriver
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
from config import KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL

# Initialize Components
katago = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
detector = ShapeDetector()
simulator = BoardSimulator()

server = Server("katago-analyzer")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="katago_analyze",
            description="囲碁の盤面をKataGoで解析します。historyを受け取り、勝率、目数差、PV、将来の形状変化を返します。",
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
    
    # History Sanitization: If 1D list of strings, convert to 2D list of pairs
    if history and isinstance(history[0], str):
        # Assuming format ['B', 'D4', 'W', 'Q16', ...]
        new_history = []
        for i in range(0, len(history), 2):
            if i + 1 < len(history):
                new_history.append([history[i], history[i+1]])
        history = new_history

    board_size = arguments.get("board_size", 19)

    if name == "katago_analyze":
        res = katago.analyze_situation(history, board_size=board_size, priority=True)
        if "error" in res: return [types.TextContent(type="text", text=f"Error: {res['error']}")]
        
        curr_b, _, _ = simulator.reconstruct(history)
        player_color = "B" if len(history) % 2 == 0 else "W"
        for cand in res.get('top_candidates', []):
            pv_list = [m.strip() for m in cand.get('future_sequence', "").split("->")]
            all_future_facts = []
            for m_str, sim_b, prev_b, c_color in simulator.simulate_pv(curr_b, pv_list, player_color):
                if not prev_b: continue
                facts = detector.detect_all(sim_b, prev_b, c_color)
                if facts: all_future_facts.append(f"  [{m_str}の局面]:\n{facts}")
            cand["future_shape_analysis"] = "\n".join(all_future_facts) if all_future_facts else "特になし"
        return [types.TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]

    elif name == "detect_shapes":
        curr_b, prev_b, last_c = simulator.reconstruct(history)
        facts = detector.detect_all(curr_b, prev_b, last_c)
        return [types.TextContent(type="text", text=facts if facts else "特筆すべき形状は検出されませんでした。")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_server):
        await server.run(read_stream, write_server, InitializationOptions(
            server_name="katago-analyzer", server_version="1.0.0",
            capabilities=server.get_capabilities(notification_options=NotificationOptions(tools_changed=True), experimental_capabilities={})
        ))

if __name__ == "__main__":
    asyncio.run(main())