"""用户订阅关系模型"""

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean, DateTime, Index, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class UserSubscription(Base):
    """用户订阅关系（用户 ↔ 信息源）"""

    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    custom_config: Mapped[dict] = mapped_column(JSON, default=dict, comment="用户级别个性化配置")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "source_id", name="idx_user_sub_unique"),
        Index("idx_user_sub_source", "source_id", postgresql_where="enabled = TRUE"),
    )
