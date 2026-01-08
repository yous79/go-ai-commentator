import subprocess
import os
import threading
from config import ANALYZE_SCRIPT, SRC_DIR

class AnalysisManager:
    def __init__(self, queue):
        self.queue = queue
        self.process = None
        self.analyzing = False

    def start_analysis(self, sgf_path):
        if self.process:
            self.stop_analysis()
            
        self.analyzing = True
        threading.Thread(target=self._run_script, args=(sgf_path,), daemon=True).start()

    def stop_analysis(self):
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
            self.process = None
        self.analyzing = False

    def _run_script(self, path):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
        
        cmd = ["python", "-u", ANALYZE_SCRIPT, path]
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                bufsize=1, 
                env=env,
                encoding='utf-8',
                errors='replace'
            )
            
            while True:
                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                
                if "Total Moves:" in line:
                    self.queue.put(("set_max", int(line.split(":")[1])))
                elif "Analyzing Move" in line:
                    self.queue.put(("progress", int(line.split("Move")[1])))
                elif "already exists" in line:
                    self.queue.put(("skip", None))
            
            self.analyzing = False
            self.queue.put(("done", None))
            
        except Exception as e:
            print(f"ERROR in AnalysisManager: {e}")
            self.queue.put(("error", str(e)))
            self.analyzing = False
