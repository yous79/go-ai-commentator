import tkinter as tk
import sys
import os
import argparse
from services.bootstrap_service import BootstrapService
from utils.logger import logger

# Add src directory to sys.path to handle modular imports
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

def main():
    parser = argparse.ArgumentParser(description="Go AI Commentator Entry Point")
    parser.add_argument("sgf_file", nargs="?", help="Path to an SGF file to load immediately")
    parser.add_argument("-t", "--test-play", action="store_true", help="Launch in Test Play / Interactive Debug Mode")
    parser.add_argument("--verify", action="store_true", help="Run auto-verification scenario")
    
    args = parser.parse_args()

    # Determine mode
    mode_name = "Test Play" if (args.test_play or args.verify) else "Replay/Analysis"
    logger.info(f"Launching application in {mode_name} Mode...", layer="STARTUP")

    # Start API Server
    api_proc = BootstrapService.start_api_server(SRC_DIR)
    
    root = tk.Tk()
    
    if args.test_play or args.verify:
        from gui.test_play_app import TestPlayApp
        app = TestPlayApp(root, api_proc=api_proc)
        
        if args.verify:
            logger.info("Auto-verification mode enabled.", layer="STARTUP")
            # Wait for server startup then verify
            root.after(4000, lambda: app.run_auto_verify("test.sgf"))
    elif args.sgf_file and os.path.exists(args.sgf_file):
        # Direct file open (Drag & Drop support)
        from gui.app import GoReplayApp
        app = GoReplayApp(root, api_proc=api_proc)
        logger.info(f"Auto-loading SGF: {args.sgf_file}", layer="STARTUP")
        root.after(3000, lambda: app.start_analysis(args.sgf_file))
    else:
        # Default: Master Launcher
        from gui.master import MasterApp
        app = MasterApp(root, api_proc=api_proc)

    root.mainloop()

if __name__ == "__main__":
    main()
