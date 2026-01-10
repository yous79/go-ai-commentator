import os
import threading
import time
import json
from sgfmill import sgf, boards
from config import OUTPUT_BASE_DIR

class AnalysisManager:
    def __init__(self, queue, katago_driver, board_renderer):
        self.queue = queue
        self.katago = katago_driver
        self.renderer = board_renderer
        self.analyzing = False
        self.stop_requested = threading.Event()

    def start_analysis(self, sgf_path):
        self.stop_analysis()
        self.stop_requested.clear()
        self.analyzing = True
        threading.Thread(target=self._run_analysis_loop, args=(sgf_path,), daemon=True).start()

    def stop_analysis(self):
        self.stop_requested.set()
        self.analyzing = False

    def _run_analysis_loop(self, path):
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            out_dir = os.path.join(OUTPUT_BASE_DIR, name)
            os.makedirs(out_dir, exist_ok=True)
            
            with open(path, "rb") as f:
                game = sgf.Sgf_game.from_bytes(f.read())
            
            board_size = game.get_size()
            total_moves = 0
            temp_node = game.get_root()
            while True:
                try:
                    temp_node = temp_node[0]
                    total_moves += 1
                except: break
            self.queue.put(("set_max", total_moves))

            json_path = os.path.join(out_dir, "analysis.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        data = json.load(f)
                    if len(data.get("moves", [])) >= total_moves + 1:
                        self.queue.put(("skip", None))
                        self.analyzing = False
                        return
                except: pass

            node = game.get_root()
            board = boards.Board(board_size)
            history = []
            m_num = 0
            log = {"board_size": board_size, "moves": []}
            
            while not self.stop_requested.is_set():
                # --- YIELD STRATEGY ---
                # Check more frequently if agent needs priority
                while self.katago.priority_mode.is_set():
                    time.sleep(0.5)
                
                # Background analysis (priority=False)
                ans = self.katago.analyze_situation(history, board_size=board_size, priority=False)
                
                if "error" in ans:
                    # Likely lock busy or engine busy, wait and retry
                    time.sleep(1.0)
                    continue

                data = {"move_number": m_num, "winrate": ans.get('winrate', 0.5), "score": ans.get('score', 0.0), "candidates": []}
                for c in ans.get('top_candidates', []):
                    data["candidates"].append({
                        "move": c['move'], 
                        "winrate": c['winrate'], 
                        "scoreLead": c['score'], 
                        "pv": c['future_sequence'].split(" -> ")
                    })
                
                log["moves"].append(data)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(log, f, indent=2, ensure_ascii=False)
                
                last_move = None
                if m_num > 0:
                    c, m = node.get_move()
                    if m: last_move = (c, m)
                
                img_text = f"Move {m_num} | Winrate(B): {data['winrate']:.1%} | Score(B): {data['score']:.1f}"
                img = self.renderer.render(board, last_move=last_move, analysis_text=img_text, history=history)
                img.save(os.path.join(out_dir, f"move_{m_num:03d}.png"))
                
                self.queue.put(("progress", m_num))
                
                try:
                    node = node[0]
                    m_num += 1
                    color, move = node.get_move()
                    if color:
                        c_str = "B" if color == 'b' else "W"
                        if move:
                            board.play(move[0], move[1], color)
                            cols = "ABCDEFGHJKLMNOPQRST"
                            history.append([c_str, cols[move[1]] + str(move[0]+1)])
                        else:
                            history.append([c_str, "pass"])
                except:
                    break
            
            self.analyzing = False
            self.queue.put(("done", None))
            
        except Exception as e:
            print(f"ERROR in AnalysisManager Loop: {e}")
            self.analyzing = False