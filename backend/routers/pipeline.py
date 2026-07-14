# backend/routers/pipeline.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

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


@router.post("/preview/{sid}")
def preview(sid: str) -> Dict[str, Any]:
    """大白话讲解即将进行的影像制作流程"""
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    text = sm.memorial_preview(s["form_data"], s["mv_outputs"].get("MV01"))
    return {"text": text}


@router.post("/run-all/{sid}")
def run_all(sid: str) -> Dict[str, Any]:
    """串行运行 MV01→MV02→MV03，返回两段大白话气泡 + 分镜列表"""
    try:
        session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    return sm.run_pipeline_chain(sid)


@router.post("/scene/image/{sid}/{idx}")
def scene_image(sid: str, idx: int, payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """为单个分镜生成首帧图片（ref_b64 可选：传入参考图 base64 则启用图生图）"""
    try:
        session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    ref_b64 = (payload or {}).get("ref_b64", "")
    return sm.gen_scene_image(sid, idx, ref_b64=ref_b64)


@router.get("/characters/{sid}")
def characters(sid: str) -> Dict[str, Any]:
    """返回主角 + 配角档案"""
    try:
        session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    return sm.get_characters(sid)


@router.get("/scenes/{sid}")
def scenes(sid: str) -> Dict[str, Any]:
    """返回 MV04 已生成的分镜列表（含已渲染的图片/视频缓存）"""
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    mv04 = s["mv_outputs"].get("MV04")
    return {"scenes": sm._get_scenes_from_mv04(mv04), "ready": mv04 is not None}


@router.post("/scene/video/{sid}/{idx}")
def scene_video(sid: str, idx: int, payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """为单个分镜生成短视频（image_url 可为 data URL 或 https URL）"""
    try:
        session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    image_url = (payload or {}).get("image_url", "")
    return sm.gen_scene_video(sid, idx, image_url)


@router.post("/final-cut/{sid}")
def final_cut(sid: str, payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    """用 ffmpeg 把各分镜已生成的视频按顺序拼接为一条完整成片。
    payload 可选 {"scene_indices": [0,1,2]} 指定顺序/子集，默认按全部分镜顺序拼接。
    """
    try:
        session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    scene_indices = (payload or {}).get("scene_indices")
    result = sm.merge_scene_videos(sid, scene_indices=scene_indices)
    if result.get("error"):
        raise HTTPException(400, result.get("message") or "拼接失败")
    return result


@router.get("/final-cut/{sid}/file")
def final_cut_file(sid: str):
    """下载/播放最近一次拼接完成的成片 MP4。"""
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    path = s.get("final_cut_path")
    if not path:
        raise HTTPException(404, "尚未生成成片，请先调用 /pipeline/final-cut/{sid}")
    return FileResponse(path, media_type="video/mp4", filename="final_cut.mp4")

