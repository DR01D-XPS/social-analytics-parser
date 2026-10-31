from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Platform, SourceMode, SyncStatus


class AccountCreate(BaseModel):
    platform: Platform
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    source_mode: SourceMode = SourceMode.MOCK
    api_base_url: str | None = Field(default=None, max_length=500)
    api_token: str | None = Field(default=None, max_length=500)


class AccountUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    source_mode: SourceMode | None = None
    api_base_url: str | None = Field(default=None, max_length=500)
    api_token: str | None = Field(default=None, max_length=500)


class AccountRead(BaseModel):
    id: int
    platform: Platform
    external_id: str
    title: str
    source_mode: SourceMode
    api_base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncRunRead(BaseModel):
    id: int
    account_id: int
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None
    message: str | None
    created_posts: int
    captured_metrics: int

    model_config = {"from_attributes": True}


class TimePoint(BaseModel):
    timestamp: datetime
    value: int


class FlowPoint(BaseModel):
    timestamp: datetime
    inflow: int
    outflow: int
    net_growth: int
    total_subscribers: int | None = None


class PostTrendPoint(BaseModel):
    timestamp: datetime
    views: int
    reactions: int
    comments: int
    reposts: int
    reach: int


class TopPost(BaseModel):
    post_id: int
    account_title: str
    platform: Platform
    external_id: str
    published_at: datetime
    content_preview: str
    views: int
    reactions: int
    comments: int
    reposts: int
    reach: int
    engagement_rate: float


class ReportKpis(BaseModel):
    inflow: int
    outflow: int
    net_growth: int
    total_views: int
    total_reactions: int
    total_comments: int
    total_reposts: int
    engagement_rate: float


class OverviewReport(BaseModel):
    kpis: ReportKpis
    post_trend: list[PostTrendPoint]
    audience_flow: list[FlowPoint]
    cumulative_growth: list[TimePoint]
    top_posts: list[TopPost]


class ManualSyncResponse(BaseModel):
    account_id: int | None = None
    started: bool
    message: str
