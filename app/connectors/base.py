from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ConnectorPost:
    external_id: str
    published_at: datetime
    content_preview: str
    url: str | None = None


@dataclass(slots=True)
class ConnectorPostMetric:
    post_external_id: str
    captured_at: datetime
    views: int
    reactions: int
    comments: int
    reposts: int
    reach: int


@dataclass(slots=True)
class ConnectorAudience:
    captured_at: datetime
    total_subscribers: int
    inflow: int
    outflow: int


class BaseConnector(ABC):
    @abstractmethod
    def fetch_posts(self, since: datetime | None = None) -> list[ConnectorPost]:
        raise NotImplementedError

    @abstractmethod
    def fetch_post_metrics(self, posts: list[ConnectorPost]) -> list[ConnectorPostMetric]:
        raise NotImplementedError

    @abstractmethod
    def fetch_audience(self) -> ConnectorAudience:
        raise NotImplementedError
