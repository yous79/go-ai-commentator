import os
import threading
import time
import json
import queue
import requests
import traceback
import concurrent.futures
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
                task = self.queue.get(timeout=0.5)
                if task is None: break
                board, last_move, analysis_text, history, m_num = task
                img = self.renderer.render(board, last_move=last_move, analysis_text=analysis_text, history=history)
                img.save(os.path.join(self.output_dir, f"move_{m_num:03d}.png"))
                self.queue.task_done()
            except queue.Empty: continue
            except Exception as e: print(f"ImageWriter Error: {e}")

    def add_task(self, board, last_move, analysis_text, history, m_num):
        self.queue.put((board, last_move, analysis_text, history, m_num))

    def stop(self): self.stop_event.set()

class AnalysisManager:
    def __init__(self, app_queue, board_renderer):
        self.app_queue = app_queue
        self.renderer = board_renderer
        self.analyzing = False
        self.stop_requested = threading.Event()
        self.image_writer = None
        self.api_url = "http://127.0.0.1:8000/analyze"
        self.batch_size = 2 # 安定性のために並列数を2に下げる

    def start_analysis(self, sgf_path):
        self.stop_analysis()
        self.stop_requested.clear()
        self.analyzing = True
        threading.Thread(target=self._run_batch_analysis, args=(sgf_path,), daemon=True).start()

    def stop_analysis(self):
        self.stop_requested.set()
        self.analyzing = False
        if self.image_writer: self.image_writer.stop()

    def _analyze_single_move(self, m_num, history, board_size):
        # 0手目（初期状態）は解析をスキップして固定値を返す
        if m_num == 0:
            return 0, {
                "winrate_black": 0.47, # コミありの初期勝率
                "score_lead_black": 0.0,
                "ownership_black": [0.0] * (board_size * board_size),
                "top_candidates": []
            }

        for attempt in range(5):
            if self.stop_requested.is_set(): return m_num, None
            try:
                resp = requests.post(self.api_url, 
                                     json={"history": history, "board_size": board_size, "visits": 500}, 
                                     timeout=60)
                if resp.status_code == 200:
                    return m_num, resp.json()
            except: pass
            time.sleep(1.0 * (attempt + 1))
        return m_num, None

    def _run_batch_analysis(self, path):
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            out_dir = os.path.join(OUTPUT_BASE_DIR, name)
            os.makedirs(out_dir, exist_ok=True)
            self.image_writer = ImageWriter(out_dir, self.renderer)
            self.image_writer.start()

            with open(path, "rb") as f:
                game = sgf.Sgf_game.from_bytes(f.read())
            board_size = game.get_size()
            
            nodes = []
            curr_node = game.get_root()
            while True:
                nodes.append(curr_node)
                try: curr_node = curr_node[0]
                except: break
            
            total_moves = len(nodes)
            self.app_queue.put(("set_max", total_moves))
            
            all_tasks = []
            history = []
            temp_board = boards.Board(board_size)
            for m_num, node in enumerate(nodes):
                color, move = node.get_move()
                if color and move:
                    temp_board.play(move[0], move[1], color)
                    cols = "ABCDEFGHJKLMNOPQRST"
                    history.append(["B" if color == 'b' else "W", cols[move[1]] + str(move[0]+1)])
                elif color: # pass
                    history.append(["B" if color == 'b' else "W", "pass"])
                
                all_tasks.append({
                    "m_num": m_num,
                    "history": list(history),
                    "board": temp_board.copy()
                })

            log = {"board_size": board_size, "moves": [None] * total_moves}
            completed_count = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                future_to_move = {executor.submit(self._analyze_single_move, t["m_num"], t["history"], board_size): t for t in all_tasks}
                
                for future in concurrent.futures.as_completed(future_to_move):
                    if self.stop_requested.is_set(): break
                    
                    res = future.result()
                    if not res: continue
                    m_num, ans = res
                    if ans:
                        move_data = ans
                        move_data["move_number"] = m_num
                        # Alias for UI
                        move_data["winrate"] = ans.get("winrate_black")
                        move_data["score"] = ans.get("score_lead_black")
                        move_data["candidates"] = ans.get("top_candidates", [])
                        
                        log["moves"][m_num] = move_data
                        
                        task_info = all_tasks[m_num]
                        img_text = f"Move {m_num} | Winrate(B): {move_data['winrate']:.1%} | Score(B): {move_data['score']:.1f}"
                        self.image_writer.add_task(task_info["board"], None, img_text, task_info["history"], m_num)
                        
                        completed_count += 1
                        self.app_queue.put(("progress", completed_count))
                        
                        # Save
                        json_path = os.path.join(out_dir, "analysis.json")
                        with open(json_path + ".tmp", "w", encoding="utf-8") as f:
                            json.dump(log, f, indent=2, ensure_ascii=False)
                        
                        for _ in range(5):
                            try:
                                os.replace(json_path + ".tmp", json_path)
                                break
                            except PermissionError: time.sleep(0.1)

            self.analyzing = False
            self.app_queue.put(("done", None))
        except Exception as e:
            traceback.print_exc()
            self.analyzing = False
