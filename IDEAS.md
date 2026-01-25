# Future Development Ideas (MCP & Beyond)

This document outlines high-level ideas to evolve the Go AI Commentator into a next-generation AI-native platform.

## 1. MCP Integration (Model Context Protocol)

### 1.1 Go Engine as MCP Tool
Expose KataGo analysis logic as an MCP server.
- **Tools**: `get_best_moves(sgf)`, `check_life_and_death(position)`.
- **Use Case**: Allows AI agents (like Claude/Gemini) to directly query the local Go engine to perform deep analysis during a conversation.

### 1.2 Analysis Data as MCP Resources
Expose structured analysis data (winrates, candidates) via URI templates.
- **URI**: `sgf://current_game/analysis`.
- **Use Case**: Enables agents to "read" the board state and AI findings as raw data instead of interpreting textual descriptions.

### 1.3 Knowledge Base Tooling
Turn the `knowledge/` JSON patterns into a searchable MCP tool.
- **Tool**: `query_knowledge_base(pattern_name)`.
- **Use Case**: Agents can proactively "look up" shape definitions to provide more accurate pedagogical explanations.

### 1.4 Remote Annotation Protocol
Allow agents to manipulate the UI rendering layers via MCP.
- **Tool**: `draw_board_markup(shapes: List[Shape])`.
- **Use Case**: The AI agent can literally "point" to locations or draw arrows on your screen while explaining a move.

## 2. Collaborative Features

### 2.1 Multi-Agent Replay
Simulate a "TV Commentary" setup with two different AI personas (e.g., a "strict pro" and a "friendly teacher") discussing the same game.

### 2.2 SGF Database Integration
Connect with OGS (Online Go Server) or other databases via MCP clients to automatically fetch and analyze pro games that share similar joseki patterns with the current game.

## 3. Visualization V3
- **Influence Heatmaps**: Visual representation of territory ownership directly on the board.
- **Mistake Heatmaps**: Color-coding sections of the history timeline based on the magnitude of winrate drops.
- **AR View**: Rendering the AI analysis overlays on a physical board via smartphone camera (future mobile concept).
