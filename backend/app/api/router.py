"""总 API 路由注册"""

from fastapi import APIRouter

from app.api.v1 import articles, destinations, feed, monitors, providers, reports, sources, tasks, users

api_router = APIRouter()

# V1 路由
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(sources.router, prefix="/sources", tags=["信息源"])
v1_router.include_router(monitors.router, prefix="/monitors", tags=["监控任务"])
v1_router.include_router(articles.router, prefix="/articles", tags=["文章"])
v1_router.include_router(reports.router, prefix="/reports", tags=["报告"])
v1_router.include_router(users.router, prefix="/users", tags=["用户"])
v1_router.include_router(tasks.router, prefix="/tasks", tags=["采集任务"])
v1_router.include_router(destinations.router, prefix="/destinations", tags=["落盘目标"])
v1_router.include_router(providers.router, prefix="/providers", tags=["执行器"])
v1_router.include_router(feed.router, tags=["RSS"])

api_router.include_router(v1_router)
