from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, Enum):
    VK = "vk"
    TELEGRAM = "telegram"
    MAX = "max"


class SourceMode(str, Enum):
    MOCK = "mock"
    HTTP = "http"


class SyncStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_platform_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    platform: Mapped[Platform] = mapped_column(SqlEnum(Platform), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_mode: Mapped[SourceMode] = mapped_column(SqlEnum(SourceMode), nullable=False, default=SourceMode.MOCK)
    api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    posts: Mapped[list["Post"]] = relationship("Post", back_populates="account", cascade="all, delete-orphan")
    audience_snapshots: Mapped[list["AudienceSnapshot"]] = relationship(
        "AudienceSnapshot", back_populates="account", cascade="all, delete-orphan"
    )
    sync_runs: Mapped[list["SyncRun"]] = relationship("SyncRun", back_populates="account", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("account_id", "external_id", name="uq_account_post_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped[Account] = relationship("Account", back_populates="posts")
    metric_snapshots: Mapped[list["PostMetricSnapshot"]] = relationship(
        "PostMetricSnapshot", back_populates="post", cascade="all, delete-orphan"
    )


class PostMetricSnapshot(Base):
    __tablename__ = "post_metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reposts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reach: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    post: Mapped[Post] = relationship("Post", back_populates="metric_snapshots")


class AudienceSnapshot(Base):
    __tablename__ = "audience_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_subscribers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inflow: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outflow: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    account: Mapped[Account] = relationship("Account", back_populates="audience_snapshots")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[SyncStatus] = mapped_column(SqlEnum(SyncStatus), nullable=False, default=SyncStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_metrics: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    account: Mapped[Account] = relationship("Account", back_populates="sync_runs")
