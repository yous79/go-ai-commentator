# Go AI Commentator - Codebase Map

This document provides a comprehensive overview of the project structure to ensure all components are recognized.

## Top-Level Entry Points (`src/`)
- `main.py`: Primary application entry point. Launches the Unified GUI Launcher.
- `mcp_server.py`: Entry point for the Model Context Protocol (MCP) server. Exposes analysis tools to AI agents.
- `verify_mcp_client.py`: Verification utility to test the MCP server connection.
- `katago_api.py`: FastAPI server wrapper for the KataGo engine (Internal API).
- `config.py`: Global configuration settings.

## Core Logic (`src/core/`)
_Domain-specific logic for Go rules and analysis._
- `game_state.py`: Manages the current game state (board, history, variations).
- `game_board.py`: Data structure representing the Go board grid.
- `shape_detector.py` & `shapes/`: Logic for detecting patterns like "Pon-nuki" or "Aki-sankaku".
- `board_simulator.py`: Handles "what-if" scenario branching and state reconstruction.
- `knowledge_manager.py` & `knowledge_repository.py`: Interface for accessing static strategy knowledge (`knowledge/*.json`).

## Services & Infrastructure (`src/services/`)
_Business logic and external integrations._
- `analysis_service.py`: **[Unified]** Central orchestration for both batch SGF analysis and interactive review.
- `api_client.py`: Client for communicating with the local `katago_api.py`.
- `ai_commentator.py`: Interface for Gemini (cloud LLM) to generate text commentary.
- `term_visualizer.py`: Service for generating static diagrams of specific terms.
- `async_task_manager.py`: Thread pool manager for background tasks to prevent GUI freezing.

## GUI Layer (`src/gui/`)
_Tkinter-based User Interface._
- `launcher.py`: Dashboard for selecting modes (Replay / Test Play).
- `master.py`: Main container managing frame switching.
- `app.py` (`GoReplayApp`): Application definition for the SGF Replay Mode.
- `test_play_app.py` (`TestPlayApp`): Application definition for the Interactive Board Mode.
- `base_app.py`: Shared base class implementing event subscriptions and cleanup.
- `info_view.py`: Side panel containing analysis stats, graphs, and commentary.

## Utilities & Rendering (`src/utils/`)
- `event_bus.py`: Pub/Sub system for decoupling components.
- `check_startup.py`: Diagnostic script for verifying import integrity and startup stability.
- `renderer/` (**Renderer V2**):
    - `renderer.py`: Main `LayeredBoardRenderer` class.
    - `theme.py`: Theme management (Classic/Dark).
    - `layers/`: Modular drawing layers (`stone_layer.py`, `grid_layer.py`, etc.).

## MCP Modules (`src/mcp_modules/`)
_Modular implementation of MCP tools and resources._
- `analysis.py`: Tools for KataGo analysis and simulation.
- `knowledge.py`: Tools for shape detection and knowledge retrieval.
- `session.py`: Context management for MCP sessions.
