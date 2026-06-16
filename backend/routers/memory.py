from typing import Any, Dict

from fastapi import APIRouter, Query

from services import long_memory

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/health")
def memory_health() -> Dict[str, Any]:
    long_memory.init_db()
    return {
        "ok": True,
        "db_path": str(long_memory.MEMORY_DB),
    }


@router.get("/recent")
def memory_recent(
    user_id: str = Query("local"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    items = long_memory.recent_memories(user_id=user_id, limit=limit)
    return {"ok": True, "user_id": user_id, "items": items}


@router.get("/search")
def memory_search(
    q: str = Query(""),
    user_id: str = Query("local"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    items = long_memory.search_memories(user_id=user_id, query=q, limit=limit)
    return {"ok": True, "user_id": user_id, "query": q, "items": items}


@router.get("/stats")
def memory_stats(user_id: str = Query("local")) -> Dict[str, Any]:
    return {"ok": True, **long_memory.memory_stats(user_id=user_id)}


@router.get("/pyramid")
def memory_pyramid() -> Dict[str, Any]:
    return {"ok": True, **long_memory.pyramid_levels()}


@router.get("/forget/preview")
def memory_forget_preview(
    user_id: str = Query("local"),
    as_of: str = Query("", description="模拟当前日期，例如 2026-08-01"),
) -> Dict[str, Any]:
    return {"ok": True, **long_memory.forgetting_report(user_id=user_id, as_of=as_of, apply=False)}


@router.post("/forget/apply")
def memory_forget_apply(
    user_id: str = Query("local"),
    as_of: str = Query("", description="模拟当前日期，例如 2026-08-01"),
) -> Dict[str, Any]:
    return {"ok": True, **long_memory.forgetting_report(user_id=user_id, as_of=as_of, apply=True)}
