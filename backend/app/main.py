"""
LexDeepResearch — FastAPI 入口
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.bootstrap import bootstrap_runtime_data
from app.config import settings
from app.scheduler.scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 测试环境不启动调度器，避免后台任务影响测试隔离性。
    if not os.getenv("PYTEST_CURRENT_TEST"):
        await bootstrap_runtime_data()
        init_scheduler()
    yield
    if not os.getenv("PYTEST_CURRENT_TEST"):
        shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="自动化信息获取与深度研究平台",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "LexDeepResearch"}
