"""用户与偏好设置 API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.user import User
from app.schemas.user import UserMeResponse
from app.schemas.user import UserSettingsResponse
from app.schemas.user import UserSettingsUpdate

router = APIRouter()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


@router.get("/me", response_model=UserMeResponse)
async def get_me(db: AsyncSession = Depends(get_db)):
    """获取当前用户信息（P0）"""
    user = await _get_or_create_default_user(db)
    return UserMeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        plan="Free Plan",
        settings=user.settings or {},
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/me/settings", response_model=UserSettingsResponse)
async def update_settings(payload: UserSettingsUpdate, db: AsyncSession = Depends(get_db)):
    """更新用户偏好设置（P0）"""
    user = await _get_or_create_default_user(db)
    merged = {
        "default_time_period": payload.default_time_period or (user.settings or {}).get("default_time_period", "daily"),
        "default_depth": payload.default_depth or (user.settings or {}).get("default_depth", "brief"),
        "default_sink": payload.default_sink or (user.settings or {}).get("default_sink", "notion"),
    }
    user.settings = merged
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()
    return UserSettingsResponse(**merged)


async def _get_or_create_default_user(db: AsyncSession) -> User:
    user = await db.get(User, DEFAULT_USER_ID)
    if user:
        return user

    now = datetime.now(timezone.utc)
    user = User(
        id=DEFAULT_USER_ID,
        email="admin@lexmount.com",
        name="Lex Researcher",
        settings={"default_time_period": "daily", "default_depth": "brief", "default_sink": "notion"},
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
