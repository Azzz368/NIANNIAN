# backend/main.py — FastAPI 入口
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent        # backend/ 的绝对路径
_ROOT    = _BACKEND.parent                         # 项目根的绝对路径

# 同时注入 backend/ 和项目根，兼容「cd backend; uvicorn main:app」和「uvicorn backend.main:app」
for _p in (_BACKEND, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from routers import assets, chat, dialogue, intake, pipeline, agent, agent_realtime, auth, memorials, uploads, voice, admin, biography, diary, memory, video_projects
from core import oss_sync, storage as _storage  # noqa: F401

app = FastAPI(
    title="念念 NianNian Memorial API",
    version="0.1.0",
    description="念念追思影像平台 — 后端 API（FastAPI），与 Streamlit 共享业务层",
)

# 启动：自检 + OSS 拉回 + 本地快照恢复（多重保险，确保数据不丢）
@app.on_event("startup")
def _nian_bootstrap():
    from core import storage as _s
    import os, json
    data_dir = _s.DATA_DIR
    print(f"[storage] DATA_DIR = {data_dir}")
    print(f"[storage] NIAN_DATA_DIR env = {os.environ.get('NIAN_DATA_DIR', '(unset)')}")
    try:
        # pathlib exposes is_mount on Windows, but its implementation raises
        # NotImplementedError there. This is diagnostics only, never startup logic.
        is_mount = data_dir.is_mount()
    except NotImplementedError:
        is_mount = False
    print(f"[storage] DATA_DIR exists = {data_dir.exists()}, is mount = {is_mount}")

    # 1) OSS 镜像拉回（最强保险）
    try:
        if oss_sync.enabled():
            print("[oss] enabled, bootstrap pulling from OSS...")
            oss_sync.bootstrap_pull()
        else:
            print("[oss] DISABLED — 数据仅靠本地 Disk，强烈建议接 OSS 防丢失")
    except Exception as e:
        print(f"[oss] bootstrap failed: {e}")

    # 2) 启动后清点数据，方便用户立刻在 Render Logs 看到
    try:
        _s._ensure()
        users = _s.list_users()
        total_mem = 0
        for u in users:
            try:
                total_mem += len(_s.list_memorials(u.get("user_id", "")))
            except Exception:
                pass
        print(f"[storage] 启动清点：{len(users)} 用户，{total_mem} 个纪念对象")

        # 3) 数据丢失检测：上次有用户、这次没了 → 写报警标记
        marker = data_dir / ".last_user_count"
        if marker.exists():
            try:
                prev = int(marker.read_text(encoding="utf-8").strip() or "0")
            except Exception:
                prev = 0
            if prev > 0 and len(users) == 0:
                print(f"⚠️⚠️⚠️ [DATA LOSS DETECTED] 上次启动有 {prev} 个用户，本次为 0！")
                print(f"⚠️ 请立刻检查 Render Disk 挂载状态和 OSS 配置")
                # 写一个看得到的报警文件
                (data_dir / "DATA_LOSS_WARNING.txt").write_text(
                    f"启动时检测到数据丢失！上次={prev} 当前=0\nDATA_DIR={data_dir}\nNIAN_DATA_DIR={os.environ.get('NIAN_DATA_DIR','')}",
                    encoding="utf-8"
                )
        try:
            marker.write_text(str(len(users)), encoding="utf-8")
        except Exception:
            pass

        # 4) 启动自动快照（保留最近 10 份），写到 DATA_DIR/_backups/
        try:
            _create_startup_snapshot(data_dir)
        except Exception as e:
            print(f"[snapshot] failed: {e}")
    except Exception as e:
        print(f"[storage] bootstrap diag failed: {e}")


def _create_startup_snapshot(data_dir):
    """启动时打个 zip 快照，保留最近 10 份。"""
    import zipfile, time
    from pathlib import Path
    backups = Path(data_dir) / "_backups"
    backups.mkdir(parents=True, exist_ok=True)
    snap = backups / f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    n = 0
    with zipfile.ZipFile(snap, "w", zipfile.ZIP_DEFLATED) as z:
        for p in Path(data_dir).rglob("*"):
            # 排除自己的备份目录，避免雪球
            if "_backups" in p.parts:
                continue
            if p.is_file():
                z.write(p, arcname=str(p.relative_to(data_dir)))
                n += 1
    print(f"[snapshot] created {snap.name} ({n} files)")
    # 清理：只保留最近 10 份
    snaps = sorted(backups.glob("snapshot_*.zip"))
    for old in snaps[:-10]:
        try:
            old.unlink()
        except Exception:
            pass

# CORS（开发阶段全开，生产收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(intake.router,   prefix="/api")
app.include_router(chat.router,     prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(assets.router,   prefix="/api")
app.include_router(dialogue.router, prefix="/api")
app.include_router(agent.router,    prefix="/api")
app.include_router(agent_realtime.router, prefix="/api")
app.include_router(auth.router,     prefix="/api")
app.include_router(memorials.router, prefix="/api")
app.include_router(uploads.router,  prefix="/api")
app.include_router(voice.router,    prefix="/api")
app.include_router(admin.router,    prefix="/api")
app.include_router(biography.router, prefix="/api")
app.include_router(diary.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(video_projects.router, prefix="/api")

# 前端静态文件（开发期直接由后端托管，生产可分离至 Nginx/CDN）
_FRONTEND = _BACKEND.parent / "frontend"
if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

    # 根路径直接跳转到首页（让 http://localhost:8000 = 主程序）
    @app.get("/")
    def root_index():
        return RedirectResponse(url="/static/index.html", status_code=307)

    # 便捷路径：/memorial /deep_search /dialogue → 对应 HTML
    @app.get("/memorial")
    def page_memorial():
        return RedirectResponse(url="/static/memorial.html", status_code=307)

    @app.get("/deep_search")
    def page_deep_search():
        return RedirectResponse(url="/static/deep_search.html", status_code=307)

    @app.get("/dialogue")
    def page_dialogue():
        return RedirectResponse(url="/static/dialogue.html", status_code=307)

    @app.get("/pipeline")
    def page_pipeline():
        return RedirectResponse(url="/static/pipeline.html", status_code=307)

    @app.get("/studio")
    def page_studio():
        return RedirectResponse(url="/static/studio.html", status_code=307)

    @app.get("/login")
    def page_login():
        return RedirectResponse(url="/static/login.html", status_code=307)

    @app.get("/library")
    def page_library():
        return RedirectResponse(url="/static/library.html", status_code=307)

    @app.get("/voice")
    def page_voice():
        return RedirectResponse(url="/static/voice_studio.html", status_code=307)

    @app.get("/diary")
    def page_diary():
        return RedirectResponse(url="/static/diary.html", status_code=307)

    @app.get("/video-project")
    def page_video_project():
        return RedirectResponse(url="/static/video_project.html", status_code=307)
else:
    @app.get("/")
    def root_no_frontend() -> JSONResponse:
        return JSONResponse({"service": "念念 NianNian Memorial API", "docs": "/docs"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "niannian-backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
