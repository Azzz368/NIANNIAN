# backend/main.py — FastAPI 入口
import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，使 routers 可以 `from services import ...`
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from routers import assets, chat, intake, pipeline

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

# 前端静态文件（开发期直接由后端托管，生产可分离至 Nginx/CDN）
_FRONTEND = _BACKEND.parent / "frontend"
if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

    @app.get("/")
    def root_index() -> JSONResponse:
        return JSONResponse({
            "service": "念念 NianNian Memorial API",
            "frontend": "/static/index.html",
            "docs":     "/docs",
            "health":   "/api/health",
        })
else:
    @app.get("/")
    def root_index() -> JSONResponse:
        return JSONResponse({"service": "念念 NianNian Memorial API", "docs": "/docs"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "niannian-backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
