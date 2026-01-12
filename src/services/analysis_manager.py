import os
import threading
import time
import json
import queue
import requests
import traceback
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
            except Exception as e:
                print(f"ImageWriter Error: {e}")

    def add_task(self, board, last_move, analysis_text, history, m_num):
        self.queue.put((board, last_move, analysis_text, history, m_num))

    def stop(self):
        self.stop_event.set()

class AnalysisManager:
    def __init__(self, app_queue, board_renderer):
        self.app_queue = app_queue
        self.renderer = board_renderer
        self.analyzing = False
        self.stop_requested = threading.Event()
        self.image_writer = None
        self.api_url = "http://127.0.0.1:8000/analyze"

    def start_analysis(self, sgf_path):
        self.stop_analysis()
        self.stop_requested.clear()
        self.analyzing = True
        threading.Thread(target=self._run_analysis_loop, args=(sgf_path,), daemon=True).start()

    def stop_analysis(self):
        self.stop_requested.set()
        self.analyzing = False
        if self.image_writer: self.image_writer.stop()

    def _run_analysis_loop(self, path):
        try:
            name = os.path.splitext(os.path.basename(path))[0]
            out_dir = os.path.join(OUTPUT_BASE_DIR, name)
            os.makedirs(out_dir, exist_ok=True)
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

            node = game.get_root()
            board = boards.Board(board_size)
            history = []
            m_num = 0
            log = {"board_size": board_size, "moves": []}
            
            while not self.stop_requested.is_set():
                # --- API 解析 (リトライ付き) ---
                ans = None
                for attempt in range(5): # 最大5回リトライ
                    try:
                        resp = requests.post(self.api_url, 
                                             json={"history": history, "board_size": board_size}, 
                                             timeout=40)
                        if resp.status_code == 200:
                            ans = resp.json()
                            break
                        else:
                            print(f"DEBUG: Analysis API returned {resp.status_code}, retrying {attempt+1}...")
                            print(f"DEBUG API RESPONSE: {resp.text}") # エラー詳細を表示
                    except Exception as e:
                        print(f"DEBUG: Analysis API request error: {e}, retrying {attempt+1}...")
                    
                    if self.stop_requested.is_set(): break
                    time.sleep(2.0 * (attempt + 1)) # 指数バックオフ

                if ans is None:
                    print(f"CRITICAL: Failed to analyze move {m_num} after multiple retries. Skipping...")
                    # 止まらないように、デフォルト値で進めるか、再接続を待つ
                    time.sleep(5.0)
                    continue

                # データの整理
                data = {
                    "move_number": m_num, 
                    "winrate": ans.get('winrate_black', 0.5), 
                    "score": ans.get('score_lead_black', 0.0), 
                    "candidates": []
                }
                for c in ans.get('top_candidates', []):
                    data["candidates"].append({
                        "move": c['move'], "winrate": c.get('winrate_black', 0.5), 
                        "scoreLead": c.get('score_lead_black', 0.0), 
                        "pv": [m.strip() for m in c.get('future_sequence', "").split("->")]
                    })
                
                log["moves"].append(data)
                json_path = os.path.join(out_dir, "analysis.json")
                try:
                    with open(json_path + ".tmp", "w", encoding="utf-8") as f:
                        json.dump(log, f, indent=2, ensure_ascii=False)
                    os.replace(json_path + ".tmp", json_path)
                except Exception as e:
                    print(f"JSON Write Error: {e}")
                
                img_text = f"Move {m_num} | Winrate(B): {data['winrate']:.1%} | Score(B): {data['score']:.1f}"
                self.image_writer.add_task(board.copy(), None, img_text, list(history), m_num)
                self.app_queue.put(("progress", m_num))
                
                # 次の手に進む
                try:
                    node = node[0]
                    m_num += 1
                    color, move = node.get_move()
                    if color:
                        if move:
                            board.play(move[0], move[1], color)
                            cols = "ABCDEFGHJKLMNOPQRST"
                            history.append(["B" if color == 'b' else "W", cols[move[1]] + str(move[0]+1)])
                        else:
                            history.append(["B" if color == 'b' else "W", "pass"])
                except:
                    break
            
            self.analyzing = False
            self.app_queue.put(("done", None))
        except Exception as e:
            print(f"FATAL ERROR in AnalysisManager: {e}")
            traceback.print_exc()
            self.analyzing = False
