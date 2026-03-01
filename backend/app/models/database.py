"""SQLAlchemy Base 与数据库引擎"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类"""
    pass


engine = create_async_engine(settings.database_url, pool_size=settings.database_pool_size, echo=settings.app_debug)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """获取数据库会话（用于 FastAPI Depends）"""
    async with async_session() as session:
        yield session
