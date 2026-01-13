from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

# Singleton engine
katago = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
detector = ShapeDetector()
simulator = BoardSimulator()

class AnalysisRequest(BaseModel):
    history: list
    board_size: int = 19
    visits: int = 500

class GameState(BaseModel):
    history: list = []
    current_move_index: int = 0
    total_moves: int = 0
    metadata: dict = {}
    last_update: float = 0

# In-memory session state
current_game_state = GameState()

def sanitize_history(history):
    if not history: return []
    if isinstance(history[0], str):
        new_h = []
        for i in range(0, len(history), 2):
            if i+1 < len(history): new_h.append([history[i], history[i+1]])
        return new_h
    return [m for m in history if isinstance(m, (list, tuple)) and len(m) >= 2]

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc), "traceback": traceback.format_exc()},
    )

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "running" if katago.process else "stopped"}

@app.post("/analyze")
async def analyze(req: AnalysisRequest):
    try:
        clean_history = sanitize_history(req.history)
        
        # KataGo Analysis
        res = {"error": "Engine initialization failed"}
        for attempt in range(3):
            res = katago.analyze_situation(clean_history, board_size=req.board_size, priority=True, visits=req.visits)
            if "error" not in res: break
            time.sleep(0.5 * (attempt + 1))

        if "error" in res:
            return JSONResponse(status_code=503, content=res)
        
        # 確実に実データを変数に保持
        final_wr = res.get('winrate', 0.5)
        final_score = res.get('score', 0.0)
        final_own = res.get('ownership', [])
        
        # Future Shape Analysis (PV解析)
        curr_b, _, _ = simulator.reconstruct(clean_history)
        player_color = "B" if len(clean_history) % 2 == 0 else "W"
        
        top_cands = res.get('top_candidates', [])
        for cand in top_cands:
            pv_str = cand.get('future_sequence', "")
            pv_list = [m.strip() for m in pv_str.split(" -> ")] if pv_str else []
            all_future_facts = []
            for m_str, sim_b, prev_b, c_color in simulator.simulate_pv(curr_b, pv_list, player_color):
                if not prev_b: continue
                facts = detector.detect_all(sim_b, prev_b, c_color)
                if facts: all_future_facts.append(f"  [{m_str}の局面]:\n{facts}")
            cand["future_shape_analysis"] = "\n".join(all_future_facts) if all_future_facts else "特になし"
            
        # 最終的なレスポンスの構築
        return {
            "winrate_black": final_wr,
            "score_lead_black": final_score,
            "ownership_black": final_own,
            "top_candidates": top_cands
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})

@app.post("/game/state")
async def update_game_state(state: GameState):
    global current_game_state
    current_game_state = state
    current_game_state.last_update = time.time()
    return {"status": "updated"}

@app.get("/game/state")
async def get_game_state():
    return current_game_state

@app.post("/detect")
async def detect(req: AnalysisRequest):
    try:
        clean_history = sanitize_history(req.history)
        curr_b, prev_b, last_c = simulator.reconstruct(clean_history)
        facts = detector.detect_all(curr_b, prev_b, last_c)
        return {"facts": facts if facts else "特筆すべき形状は検出されませんでした。"}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")