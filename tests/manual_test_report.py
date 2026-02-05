import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Adjust path to find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from services.report_generator import ReportGenerator
from services.api_client import api_client
from core.inference_fact import TemporalScope

async def test_report_generation():
    print("Setting up Mocks...")
    
    # Mock GameState
    mock_game = MagicMock()
    mock_game.board_size = 19
    # (score_drop, winrate_drop, move_idx)
    mock_game.calculate_mistakes.return_value = ([
        (2.0, 0.15, 2), # Rank 1 (Big drop) - Index 2 corresponds to Move 2 (White?) Wait, calculate mistakes returns move indices.
                        # Usually user is Black. But mistakes can be for Black.
                        # Move 2 is White. Move 3 is Black.
                        # let's use 3.
        (1.0, 0.05, 3), # Rank 2
    ], [])
    mock_game.get_history_up_to.return_value = [["B", "aa"], ["W", "bb"], ["B", "cc"]]
    mock_game.get_board_at.return_value = MagicMock()
    
    # Mock moves for Good Move Detection
    # 0: Setup, 1: Black(Safe), 2: White, 3: Black(Good), ...
    mock_game.moves = [
        {'move': 'aa'}, # 0
        {'winrate': 0.5, 'move': 'bb'}, # 1 (Black initial)
        {'winrate': 0.5, 'move': 'cc'}, # 2 (White response)
        {'winrate_black': 0.52, 'move': 'dd'}, # 3 (Black Good Move? Gain +2%)
        {'winrate': 0.52, 'move': 'ee'}
    ]
    
    # Mock Commentator
    mock_commentator = MagicMock()
    mock_commentator.knowledge_manager.get_all_knowledge_text.return_value = "Knowledge Base"
    mock_commentator._load_prompt.return_value = "Prompt Content"
    
    # Mock Client Response
    mock_resp = MagicMock()
    mock_resp.text = "Generated Commentary Text"
    mock_commentator.client.models.generate_content.return_value = mock_resp
    
    # Mock Orchestrator
    mock_collector = MagicMock()
    mock_collector.get_prioritized_text.return_value = "Existing Facts: Aki-sankaku on board"
    
    # Create fake facts
    # Fact 1: Immediate Warning (Aki-sankaku created by last move)
    mock_fact_imm = MagicMock()
    mock_fact_imm.severity = 5
    mock_fact_imm.scope = TemporalScope.IMMEDIATE
    mock_fact_imm.format_for_ai.return_value = "⚠️ Aki-sankaku (Empty Triangle) created at D4"
    
    # Fact 2: Existing fact
    mock_fact_ex = MagicMock()
    mock_fact_ex.severity = 3
    mock_fact_ex.scope = TemporalScope.EXISTING
    mock_fact_ex.format_for_ai.return_value = "• Reasonable efficiency elsewhere"
    
    # Fact 3: Predicted Warning (Aki-sankaku in PV)
    mock_fact_pred = MagicMock()
    mock_fact_pred.severity = 5
    mock_fact_pred.scope = TemporalScope.PREDICTED
    mock_fact_pred.format_for_ai.return_value = "⚠️ Predicted Aki-sankaku (Empty Triangle) if this sequence continues"
    
    mock_collector.facts = [mock_fact_imm, mock_fact_ex, mock_fact_pred]
    
    # Mocking helper methods
    mock_collector.get_last_move_summary.return_value = "⚠️ Aki-sankaku (Empty Triangle) created at D4"
    mock_collector.get_scope_summary.side_effect = lambda scope: {
        TemporalScope.IMMEDIATE: "⚠️ Aki-sankaku (Empty Triangle) created at D4",
        TemporalScope.PREDICTED: "⚠️ Predicted Aki-sankaku (Empty Triangle) if this sequence continues"
    }.get(scope, "")
    
    # Use AsyncMock for analyze_full
    mock_commentator.orchestrator.analyze_full = AsyncMock(return_value=mock_collector)

    # Mock Renderer
    mock_renderer = MagicMock()
    mock_renderer.render_pv.return_value = MagicMock()
    mock_renderer.render.return_value = MagicMock() # For good move image
    # Mock image.save
    mock_renderer.render_pv.return_value.save = MagicMock()
    mock_renderer.render.return_value.save = MagicMock()

    # Mock API Client
    # Match Move 3 ('cc') to test Tier 1 logic
    api_client.analyze_move = MagicMock(return_value=MagicMock(candidates=[MagicMock(pv=["cc"], move="cc")]))

    # Instantiate ReportGenerator
    generator = ReportGenerator(mock_game, mock_renderer, mock_commentator)
    
    # Mock PDFGenerator inside the method is hard without patching. 
    # But since we import it in the file `from utils.pdf_generator import PDFGenerator`,
    # we can patch sys.modules or just let it fail/run.
    # Actually, ReportGenerator imports PDFGenerator at top level.
    # We can patch 'services.report_generator.PDFGenerator'
    
    # Run Generate
    print("Running generate()...")
    # ReportGenerator.generate calls file I/O operations (os.makedirs, open).
    # We should let them happen or mock them. 
    # For this test, let's use a temp dir.
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path, err = await generator.generate("TestGame", tmpdir)
        
        print(f"Result Path: {pdf_path}")
        print(f"Error: {err}")
        
        # Verify calls
        print("Verifying interactions...")
        if mock_game.calculate_mistakes.called:
            print("[OK] calculate_mistakes called")
        else:
            print("[FAIL] calculate_mistakes NOT called")

        if mock_commentator.orchestrator.analyze_full.called:
             print(f"[OK] analyze_full called {mock_commentator.orchestrator.analyze_full.call_count} times")
        
        # Check if Good Move was processed
        # We set moves[3] to have small gain/loss. Code checks loss < 0.01.
        # prev(2):wr=0.5, curr(3):wr=0.52. Loss = -0.02. < 0.01 holds.
        # And curr=0.52 is in 0.05..0.95.
        # So Index 3 should be candidate.
        # Then it calls analyze_full. If high urgency (severity >= 4) -> Selected.
        # We mocked severity=5. So it shoud be selected.
        
        # Check generated files
        md_path = os.path.join(tmpdir, "report", "report.md")
        if os.path.exists(md_path):
             print("[OK] report.md created")
             with open(md_path, 'r', encoding='utf-8') as f:
                 content = f.read()
                 if "決定機" in content: print("[OK] Rank 1 title found")
                 if "ナイスプレー" in content: print("[OK] Good Move section found")
                 if "![勝率グラフ]" in content: print("[OK] Graph image linked")
        else:
             print("[FAIL] report.md NOT created")

if __name__ == "__main__":
    asyncio.run(test_report_generation())
