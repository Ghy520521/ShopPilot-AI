"""FastAPI 入口。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.database import init_db

FRONTEND_INDEX = Path(__file__).parent / "frontend" / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 开发期自动建表；生产环境请使用 Alembic 迁移
    init_db()
    yield


app = FastAPI(title="ShopPilot AI", version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    # 前端控制台（原生 JS 单文件，直接调用 /api）
    return FileResponse(FRONTEND_INDEX)
