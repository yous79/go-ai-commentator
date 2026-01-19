from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import os
import json
import time
import traceback
import asyncio

# Core imports
from drivers.katago_driver import KataGoDriver
from core.shape_detector import ShapeDetector
from core.board_simulator import BoardSimulator, SimulationContext
from config import KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL

app = FastAPI(title="KataGo Intelligence Service")

# Singleton engine
katago = KataGoDriver(KATAGO_EXE, KATAGO_CONFIG, KATAGO_MODEL)
detector = ShapeDetector()
simulator = BoardSimulator()

# Request Queue Lock
engine_lock = asyncio.Lock()

class AnalysisRequest(BaseModel):
    history: list
    board_size: int = 19
    visits: int = 100
    include_pv_shapes: bool = True
    include_ownership: bool = True
    include_influence: bool = True

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
    async with engine_lock:
        try:
            print(f"DEBUG: Starting analysis for {len(req.history)} moves (PV shapes: {req.include_pv_shapes}, influence: {req.include_influence})")
            clean_history = sanitize_history(req.history)
            
            # KataGo Analysis
            res = {"error": "Engine initialization failed"}
            for attempt in range(3):
                # include_influence パラメータをドライバに渡す
                res = katago.analyze_situation(
                    clean_history, 
                    board_size=req.board_size, 
                    priority=True, 
                    visits=req.visits,
                    include_ownership=req.include_ownership,
                    include_influence=req.include_influence
                )
                if "error" not in res: break
                await asyncio.sleep(0.5 * (attempt + 1))

            if "error" in res:
                return JSONResponse(status_code=503, content=res)
            
            final_wr = res.get('winrate', 0.5)
            final_score = res.get('score', 0.0)
            final_own = res.get('ownership', [])
            final_inf = res.get('influence', [])
            
            # Future Shape Analysis (PV解析)
            top_candidates = res.get('top_candidates', [])
            if req.include_pv_shapes:
                # 基点となるコンテキストを復元
                curr_ctx = simulator.reconstruct_to_context(clean_history, req.board_size)
                
                for cand in top_candidates:
                    pv_str = cand.get('future_sequence', "")
                    # "D16 -> E17" のような形式をパース
                    pv_list = [m.strip() for m in pv_str.split(" -> ")] if pv_str else []
                    all_future_facts = []
                    
                    # 1手ずつシミュレートして形状検知
                    for i in range(1, len(pv_list) + 1):
                        sub_pv = pv_list[:i]
                        # SimulationContextを使用して未来の盤面を構築
                        future_ctx = simulator.simulate_sequence(curr_ctx, sub_pv)
                        
                        # 形状検知を実行
                        facts = detector.detect_facts(future_ctx.board, future_ctx.prev_board)
                        if facts:
                            fact_text = "\n".join([f"    - {f.description}" for f in facts])
                            last_move = pv_list[i-1]
                            all_future_facts.append(f"  [{last_move}の局面]:\n{fact_text}")
                    
                    cand["future_shape_analysis"] = "\n".join(all_future_facts) if all_future_facts else "特になし"
            else:
                for cand in top_candidates:
                    cand["future_shape_analysis"] = "（高速解析モード：個別検討で表示）"
                
            print(f"DEBUG: Analysis complete. Winrate(B): {final_wr:.1%}, Influence: {len(final_inf) > 0}")
            return {
                "winrate_black": final_wr,
                "score_lead_black": final_score,
                "ownership": final_own,
                "influence": final_inf,
                "top_candidates": top_candidates
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
        ctx = simulator.reconstruct_to_context(clean_history, req.board_size)
        facts = detector.detect_facts(ctx.board, ctx.prev_board)
        
        # 構造化データとして返す
        fact_list = []
        for f in facts:
            fact_list.append({
                "description": f.description,
                "severity": f.severity,
                "category": f.category.name,
                "metadata": f.metadata
            })
            
        return {"facts": fact_list}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})

@app.post("/detect/ids")
async def detect_ids(req: AnalysisRequest):
    try:
        clean_history = sanitize_history(req.history)
        ctx = simulator.reconstruct_to_context(clean_history, req.board_size)
        facts = detector.detect_facts(ctx.board, ctx.prev_board)
        # 属性からIDを抽出
        ids = list(set([f.metadata.get("key", "unknown") for f in facts]))
        return {"ids": ids}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
