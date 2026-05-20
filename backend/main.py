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

from routers import assets, chat, dialogue, intake, pipeline, agent, agent_realtime

app = FastAPI(
    title="念念 NianNian Memorial API",
    version="0.1.0",
    description="念念追思影像平台 — 后端 API（FastAPI），与 Streamlit 共享业务层",
)

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
