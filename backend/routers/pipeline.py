# backend/routers/pipeline.py
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from services import service_manager as sm
from services import session_store

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run/{step}/{sid}")
def run_step(step: str, sid: str) -> Dict[str, Any]:
    step = step.upper()
    if step not in sm.MV_FILES:
        raise HTTPException(400, f"unknown step: {step}")
    return sm.run_pipeline_step(sid, step)


@router.get("/status/{sid}")
def status(sid: str) -> Dict[str, Any]:
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    return {
        "pipeline_state": s["pipeline_state"],
        "gate_status":    s["gate"]["gate_status"],
        "mv_outputs":     list(s["mv_outputs"].keys()),
    }


@router.get("/output/{sid}/{step}")
def output(sid: str, step: str) -> Dict[str, Any]:
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    step = step.upper()
    out = s["mv_outputs"].get(step)
    if out is None:
        raise HTTPException(404, "output not ready")
    return {"step": step, "result": out}
