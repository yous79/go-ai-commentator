import subprocess
import json
import os
import sys
import threading
import time

class KataGoDriver:
    def __init__(self, katago_path, config_path, model_path):
        self.process = None
        self.katago_path = katago_path
        self.config_path = config_path
        self.model_path = model_path
        self.lock = threading.Lock()
        self.start_engine()

    def start_engine(self):
        cmd = [
            self.katago_path, "analysis",
            "-config", self.config_path,
            "-model", self.model_path
        ]
        # Force utf-8 for subprocess
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, # Suppress stderr to keep console clean
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
                encoding='utf-8',
                env=env
            )
        except Exception as e:
            print(f"Error starting KataGo: {e}")

    def query(self, moves, board_size=19, visits=500):
        """
        Send a query to KataGo and return the raw response.
        moves: list of [color, vertex] e.g. [["B", "Q16"], ["W", "D4"]]
        """
        if not self.process or self.process.poll() is not None:
            self.start_engine()

        query = {
            "id": f"query_{int(time.time())}",
            "moves": moves,
            "rules": "japanese",
            "komi": 6.5,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "includePolicy": False,
            "maxVisits": visits
        }

        with self.lock:
            try:
                self.process.stdin.write(json.dumps(query) + "\n")
                self.process.stdin.flush()

                while True:
                    line = self.process.stdout.readline()
                    if not line: break
                    try:
                        resp = json.loads(line)
                        if resp.get("id") == query["id"]:
                            return resp
                    except: continue
            except Exception as e:
                print(f"KataGo communication error: {e}")
                return None
        return None

    def analyze_situation(self, moves, board_size=19):
        """
        Gemini用の「解説に必要な情報」だけを抽出して返す関数。
        現在の局面と、そこからの「最善手」および「読み筋（PV）」を取得する。
        """
        data = self.query(moves, board_size=board_size)
        if not data or 'moveInfos' not in data:
            return {"error": "Failed to analyze"}

        root_info = data.get('rootInfo', {})
        candidates = data['moveInfos']
        
        # Current situation
        result = {
            "current_winrate_black": root_info.get('winrate', 0.5),
            "current_score_lead_black": root_info.get('scoreLead', 0.0),
            "top_candidates": []
        }

        # Extract top 3 candidates with their "Principal Variation" (PV)
        # PV is the sequence of moves KataGo thinks will happen next.
        for cand in candidates[:3]:
            # Convert GTP moves in PV to a readable string
            pv_moves = cand.get('pv', [])
            pv_str = " -> ".join(pv_moves[:6]) # First 6 moves of the sequence
            
            result["top_candidates"].append({
                "move": cand['move'],
                "winrate": cand.get('winrate', 0.0),
                "score_lead": cand.get('scoreLead', 0.0),
                "future_sequence": pv_str, # 重要：この先の変化図
                "visits": cand.get('visits', 0)
            })
            
        return result

    def close(self):
        if self.process:
            self.process.terminate()
