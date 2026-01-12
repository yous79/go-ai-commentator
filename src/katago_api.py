from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
import json
import time
import traceback

# Core imports
from drivers.katago_driver import KataGoDriver
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator
from config import KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL

app = FastAPI(title="KataGo Intelligence Service")

# Singleton engine in this process
katago = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
detector = ShapeDetector()
simulator = BoardSimulator()

class AnalysisRequest(BaseModel):
    history: list
    board_size: int = 19

def sanitize_history(history):
    """どんな形式の履歴が来ても [[color, coord], ...] に整える"""
    if not history: return []
    # 1D list ['B', 'D4', ...] -> 2D list
    if isinstance(history[0], str):
        new_h = []
        for i in range(0, len(history), 2):
            if i+1 < len(history): new_h.append([history[i], history[i+1]])
        return new_h
    # 既に2Dの場合も、各要素がペアであることを保証
    return [m for m in history if isinstance(m, (list, tuple)) and len(m) >= 2]

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "running" if katago.process else "stopped"}

@app.post("/analyze")
async def analyze(req: AnalysisRequest):
    try:
        clean_history = sanitize_history(req.history)
        
        # Retry logic
        res = {"error": "Engine initialization failed"}
        for attempt in range(3):
            res = katago.analyze_situation(clean_history, board_size=req.board_size, priority=True)
            if "error" not in res: break
            if res.get("error") not in ["Engine busy", "Lock timeout"]: break
            time.sleep(0.5 * (attempt + 1))

        # Normalize response to explicit Black Perspective keys
        normalized_res = {
            "winrate_black": res.get('winrate', 0.5),
            "score_lead_black": res.get('score', 0.0),
            "top_candidates": []
        }
        
        for cand in res.get('top_candidates', []):
            pv_str = cand.get('future_sequence', "")
            pv_list = [m.strip() for m in pv_str.split("->")] if pv_str else []
            all_future_facts = []
            for m_str, sim_b, prev_b, c_color in simulator.simulate_pv(curr_b, pv_list, player_color):
                if not prev_b: continue
                facts = detector.detect_all(sim_b, prev_b, c_color)
                if facts: all_future_facts.append(f"  [{m_str}の局面]:\n{facts}")
            
            normalized_res["top_candidates"].append({
                "move": cand['move'],
                "winrate_black": cand.get('winrate', 0.5),
                "score_lead_black": cand.get('score', 0.0),
                "future_sequence": pv_str,
                "future_shape_analysis": "\n".join(all_future_facts) if all_future_facts else "特になし"
            })
            
        return normalized_res
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/detect")
async def detect(req: AnalysisRequest):
    try:
        clean_history = sanitize_history(req.history)
        curr_b, prev_b, last_c = simulator.reconstruct(clean_history)
        facts = detector.detect_all(curr_b, prev_b, last_c)
        return {"facts": facts if facts else "特筆すべき形状は検出されませんでした。"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")