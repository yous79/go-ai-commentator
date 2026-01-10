import os
import threading
import time
import json
import queue
from sgfmill import sgf, boards
from config import OUTPUT_BASE_DIR

class ImageWriter(threading.Thread):
    def __init__(self, output_dir, renderer):
        super().__init__(daemon=True)
        self.queue = queue.Queue()
        self.output_dir = output_dir
        self.renderer = renderer
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                task = self.queue.get(timeout=0.1)
                if task is None: break
                
                board, last_move, analysis_text, history, m_num = task
                try:
                    img = self.renderer.render(board, last_move=last_move, analysis_text=analysis_text, history=history)
                    img.save(os.path.join(self.output_dir, f"move_{m_num:03d}.png"))
                except Exception as e:
                    print(f"ERROR: Image write failed for move {m_num}: {e}")
                finally:
                    self.queue.task_done()
            except queue.Empty:
                continue

    def add_task(self, board, last_move, analysis_text, history, m_num):
        self.queue.put((board, last_move, analysis_text, history, m_num))

    def stop(self):
        self.stop_event.set()

class AnalysisManager:
    def __init__(self, queue, katago_driver, board_renderer):
        self.app_queue = queue
        self.katago = katago_driver
        self.renderer = board_renderer
        self.analyzing = False
        self.stop_requested = threading.Event()
        self.image_writer = None

    def start_analysis(self, sgf_path):
        self.stop_analysis()
        self.stop_requested.clear()
        self.analyzing = True
        threading.Thread(target=self._run_analysis_loop, args=(sgf_path,), daemon=True).start()

    def stop_analysis(self):
        self.stop_requested.set()
        self.analyzing = False
        if self.image_writer:
            self.image_writer.stop()
            self.image_writer = None

    def _run_analysis_loop(self, path):
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            out_dir = os.path.join(OUTPUT_BASE_DIR, name)
            os.makedirs(out_dir, exist_ok=True)
            
            # Init Image Writer
            self.image_writer = ImageWriter(out_dir, self.renderer)
            self.image_writer.start()

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
            self.app_queue.put(("set_max", total_moves))

            json_path = os.path.join(out_dir, "analysis.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        data = json.load(f)
                    if len(data.get("moves", [])) >= total_moves + 1:
                        self.app_queue.put(("skip", None))
                        self.analyzing = False
                        self.image_writer.stop()
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
                
                # Atomic Write
                temp_json_path = json_path + ".tmp"
                with open(temp_json_path, "w", encoding="utf-8") as f:
                    json.dump(log, f, indent=2, ensure_ascii=False)
                os.replace(temp_json_path, json_path)
                
                last_move = None
                if m_num > 0:
                    c, m = node.get_move()
                    if m: last_move = (c, m)
                
                img_text = f"Move {m_num} | Winrate(B): {data['winrate']:.1%} | Score(B): {data['score']:.1f}"
                
                # Async Image Write (Clone board to avoid race conditions if board is mutated later)
                board_copy = board.copy()
                self.image_writer.add_task(board_copy, last_move, img_text, list(history), m_num)
                
                self.app_queue.put(("progress", m_num))
                
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
            self.app_queue.put(("done", None))
            if self.image_writer:
                self.image_writer.stop()
            
        except Exception as e:
            print(f"ERROR in AnalysisManager Loop: {e}")
            self.analyzing = False
            if self.image_writer:
                self.image_writer.stop()
