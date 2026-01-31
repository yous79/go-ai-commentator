import subprocess
import json
import os
import sys
import threading
import time
import queue

class KataGoDriver:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(KataGoDriver, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, katago_path=None, config_path=None, model_path=None):
        if self._initialized: return
        self.katago_path = katago_path
        self.config_path = config_path
        self.model_path = model_path
        self.process = None
        self.comm_lock = threading.Lock() 
        self.priority_mode = threading.Event() 
        self.start_engine()
        self._initialized = True

    def start_engine(self):
        if self.process and self.process.poll() is None: return
        cmd = [self.katago_path, "analysis", "-config", self.config_path, "-model", self.model_path]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, bufsize=1, startupinfo=startupinfo, encoding='utf-8', env=env)
            threading.Thread(target=self._consume_stderr, daemon=True).start()
            print("DEBUG: KataGo Engine started.")
        except Exception as e: print(f"Error starting KataGo: {e}")

    def _consume_stderr(self):
        with open("katago_debug.log", "w", encoding="utf-8") as f:
            while self.process and self.process.poll() is None:
                line = self.process.stderr.readline()
                if not line: break
                f.write(line); f.flush()

    def query(self, moves, board_size=19, visits=500, priority=False, include_ownership=True, include_influence=True):
        if not self.process or self.process.poll() is not None: self.start_engine()
        if priority: self.priority_mode.set()
        query_id = f"q_{int(time.time() * 1000)}"
        
        # KataGo Analysis Query Format
        query = {
            "id": query_id,
            "moves": moves,
            "rules": "japanese",
            "komi": 6.5,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "includePolicy": False,
            "includeOwnership": include_ownership,
            "includeInfluence": include_influence,
            "includeOwnershipStdev": False,
            "maxVisits": visits
        }
        
        lock_timeout = 60 if priority else 1
        try:
            lock_acquired = self.comm_lock.acquire(timeout=lock_timeout)
            if not lock_acquired: return {"error": "Engine busy"}
            try:
                self.process.stdin.write(json.dumps(query) + "\n"); self.process.stdin.flush()
                start_time = time.time()
                while True:
                    if self.process.poll() is not None: return {"error": "Engine crashed"}
                    line = self.process.stdout.readline()
                    if not line:
                        if time.time() - start_time > 30: return {"error": "Read timeout"}
                        time.sleep(0.05); continue
                    try:
                        resp = json.loads(line)
                        if resp.get("id") == query_id:
                            return resp
                    except: continue
            finally:
                self.comm_lock.release()
                if priority: self.priority_mode.clear()
        except Exception as e:
            if priority: self.priority_mode.clear()
            return {"error": str(e)}
        return {"error": "Unknown error"}

    def analyze_situation(self, moves, board_size=19, priority=False, visits=500, include_ownership=True, include_influence=True):
        clean_moves = []
        for m in moves:
            if isinstance(m, (list, tuple)) and len(m) >= 2:
                clean_moves.append([str(m[0]).upper(), str(m[1]).lower()])

        data = self.query(
            clean_moves, 
            board_size=board_size, 
            priority=priority, 
            visits=visits,
            include_ownership=include_ownership,
            include_influence=include_influence
        )
        if "error" in data: return data

        root = data.get('rootInfo', {})
        cands = data.get('moveInfos', [])
        if not cands and not root: return {"error": "Empty analysis results"}

        # 手番の特定 (次に打つのが白か黒か)
        is_white_turn = (len(clean_moves) % 2 != 0)
        
        # 基本評価値の正規化 (黒番視点)
        current_winrate = root.get('winrate', 0.5)
        current_score = root.get('scoreLead', 0.0)
        
        final_winrate = 1.0 - current_winrate if is_white_turn else current_winrate
        final_score = -current_score if is_white_turn else current_score
        
        # Ownershipの抽出と正規化 (data直下にある場合とrootInfoにある場合の両対応)
        raw_ownership = data.get('ownership') or root.get('ownership')
        if raw_ownership:
            final_ownership = [-v for v in raw_ownership] if is_white_turn else raw_ownership
        else:
            final_ownership = []

        # Influenceの抽出と正規化
        raw_influence = data.get('influence') or root.get('influence')
        if raw_influence:
            final_influence = [-v for v in raw_influence] if is_white_turn else raw_influence
        else:
            final_influence = []

        res = {
            "winrate": final_winrate, 
            "score": final_score, 
            "ownership": final_ownership, 
            "influence": final_influence,
            "top_candidates": []
        }

        # 候補手の正規化
        for cand in cands[:3]:
            pv = cand.get('pv', [])
            c_win = cand.get('winrate', 0.5)
            c_score = cand.get('scoreLead', 0.0)
            res["top_candidates"].append({
                "move": cand['move'],
                "winrate": 1.0 - c_win if is_white_turn else c_win,
                "score": -c_score if is_white_turn else c_score,
                "pv": pv[:10],
                "future_sequence": " -> ".join(pv[:6])
            })
        return res

    def close(self):
        if self.process: self.process.terminate()
