import tkinter as tk
from gui.launcher import Launcher
from utils.logger import logger

class MasterApp:
    def __init__(self, root, api_proc):
        self.root = root
        self.api_proc = api_proc
        self.current_app = None
        self.root.title("Go AI Commentator - Master Suite")
        self.root.geometry("1200x950")
        
        # Menu bar (Global)
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        self._setup_global_menu()

        # Start with Launcher
        self.show_launcher()

    def _setup_global_menu(self):
        filemenu = tk.Menu(self.menubar, tearoff=0)
        filemenu.add_command(label="Home / Switch Mode...", command=self.show_launcher)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_close)
        self.menubar.add_cascade(label="System", menu=filemenu)

    def show_launcher(self):
        self._clear_current_app()
        self.root.title("Go AI Commentator - Select Mode")
        self.current_app = Launcher(self.root, self.switch_app)

    def switch_app(self, mode_name):
        self._clear_current_app()
        
        if mode_name == "replay":
            from gui.app import GoReplayApp
            logger.info("Switching to Replay Mode...", layer="GUI")
            self.root.title("Go AI Commentator - Replay Mode")
            # GoReplayApp expects to be the root app, so we might need adjustments
            # For now, passing root works as it attaches to it.
            self.current_app = GoReplayApp(self.root, self.api_proc, is_child=True)
            
        elif mode_name == "test_play":
            from gui.test_play_app import TestPlayApp
            logger.info("Switching to Test Play Mode...", layer="GUI")
            self.root.title("Go AI Commentator - Test Play Mode")
            self.current_app = TestPlayApp(self.root, self.api_proc, is_child=True)

    def _clear_current_app(self):
        if self.current_app:
            if hasattr(self.current_app, "cleanup"):
                self.current_app.cleanup()
            elif hasattr(self.current_app, "destroy"):
                self.current_app.destroy()
            elif hasattr(self.current_app, "on_close") and not isinstance(self.current_app, Launcher):
                 # Manually clean up app resources without killing the process
                 # GoAppBase.on_close kills the process, so we need a softer close
                 if hasattr(self.current_app, "stop_threads"):
                     self.current_app.stop_threads()

        # Destroy all widgets in root except menu
        for widget in self.root.winfo_children():
            if not isinstance(widget, tk.Menu):
                 widget.destroy()
        
        self.current_app = None

    def on_close(self):
        """Global shutdown"""
        logger.info("MasterApp shutting down...", layer="GUI")
        if self.api_proc:
            try:
                self.api_proc.kill()
            except: pass
        self.root.destroy()
