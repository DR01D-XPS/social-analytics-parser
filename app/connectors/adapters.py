from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

import requests

from app.config import get_settings
from app.connectors.base import BaseConnector, ConnectorAudience, ConnectorPost, ConnectorPostMetric
from app.models import Account, Platform


def _seed_from_account(account: Account) -> int:
    digest = hashlib.md5(f"{account.platform.value}:{account.external_id}".encode("utf-8"), usedforsecurity=False)
    return int(digest.hexdigest(), 16) % (2**31 - 1)


class MockConnector(BaseConnector):
    def __init__(self, account: Account):
        self.account = account
        self._seed = _seed_from_account(account)

    def fetch_posts(self, since: datetime | None = None) -> list[ConnectorPost]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=90)
        posts: list[ConnectorPost] = []
        rng = random.Random(self._seed)

        current = start
        index = 1
        while current <= now:
            # Around 4-5 posts per week.
            if rng.random() < 0.68:
                minute_offset = rng.randint(0, 60 * 12)
                published_at = current + timedelta(minutes=minute_offset)
                external_id = f"{self.account.external_id}-{published_at.strftime('%Y%m%d')}-{index}"
                posts.append(
                    ConnectorPost(
                        external_id=external_id,
                        published_at=published_at,
                        content_preview=self._build_text(index),
                        url=self._build_url(external_id),
                    )
                )
                index += 1
            current += timedelta(days=1)

        if since:
            posts = [p for p in posts if p.published_at >= since]

        return posts

    def fetch_post_metrics(self, posts: list[ConnectorPost]) -> list[ConnectorPostMetric]:
        captured_at = datetime.now(timezone.utc)
        metrics: list[ConnectorPostMetric] = []

        for post in posts:
            age_hours = max(1, int((captured_at - post.published_at).total_seconds() // 3600))
            post_seed = int(hashlib.md5(post.external_id.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
            rng = random.Random(self._seed + post_seed)
            growth = rng.uniform(12.0, 28.0)
            base = rng.randint(180, 3000)
            views = int(base + age_hours * growth)
            reactions = int(views * rng.uniform(0.03, 0.12))
            comments = int(reactions * rng.uniform(0.08, 0.25))
            reposts = int(reactions * rng.uniform(0.04, 0.16))
            reach = int(views * rng.uniform(1.05, 1.4))

            metrics.append(
                ConnectorPostMetric(
                    post_external_id=post.external_id,
                    captured_at=captured_at,
                    views=max(views, 0),
                    reactions=max(reactions, 0),
                    comments=max(comments, 0),
                    reposts=max(reposts, 0),
                    reach=max(reach, 0),
                )
            )

        return metrics

    def fetch_audience(self) -> ConnectorAudience:
        now = datetime.now(timezone.utc)
        day_index = (now.date() - datetime(2024, 1, 1, tzinfo=timezone.utc).date()).days

        rng = random.Random(self._seed + day_index)
        base = 3_500 + (self._seed % 6_000)

        cumulative = 0
        for i in range(max(1, day_index - 90), day_index + 1):
            local_rng = random.Random(self._seed + i)
            inflow = local_rng.randint(10, 110)
            outflow = local_rng.randint(5, 90)
            cumulative += inflow - outflow

        inflow_today = rng.randint(10, 120)
        outflow_today = rng.randint(5, 95)
        total = max(base + cumulative, 100)

        return ConnectorAudience(
            captured_at=now,
            total_subscribers=total,
            inflow=inflow_today,
            outflow=outflow_today,
        )

    def _build_text(self, idx: int) -> str:
        if self.account.platform == Platform.VK:
            return f"VK пост #{idx}: обзор, полезные материалы и опрос аудитории."
        if self.account.platform == Platform.TELEGRAM:
            return f"Telegram пост #{idx}: дайджест, инсайты и ссылка на обсуждение."
        return f"MAX пост #{idx}: обновление продукта, кейсы и статистика недели."

    def _build_url(self, external_id: str) -> str:
        if self.account.platform == Platform.VK:
            return f"https://vk.com/{self.account.external_id}?w=wall-{external_id}"
        if self.account.platform == Platform.TELEGRAM:
            return f"https://t.me/{self.account.external_id}/{abs(hash(external_id)) % 7000 + 1}"
        return f"https://max.ru/channel/{self.account.external_id}/post/{abs(hash(external_id)) % 9000 + 1}"


class HttpConnector(BaseConnector):
    """
    Generic connector for integrating real sources via adapter endpoints.

    Expected upstream API contract:
    - GET {base_url}/posts?since=<iso>
    - POST {base_url}/post-metrics  body: {"posts": [{...}]}
    - GET {base_url}/audience
    """

    def __init__(self, account: Account):
        self.account = account
        if not account.api_base_url:
            raise ValueError("HTTP mode requires api_base_url")

        self.base_url = account.api_base_url.rstrip("/")
        self.headers = {}
        if account.api_token:
            self.headers["Authorization"] = f"Bearer {account.api_token}"

    def fetch_posts(self, since: datetime | None = None) -> list[ConnectorPost]:
        params = {}
        if since:
            params["since"] = since.isoformat()

        response = requests.get(f"{self.base_url}/posts", headers=self.headers, params=params, timeout=25)
        response.raise_for_status()

        posts: list[ConnectorPost] = []
        for item in response.json().get("items", []):
            posts.append(
                ConnectorPost(
                    external_id=str(item["external_id"]),
                    published_at=datetime.fromisoformat(item["published_at"]),
                    content_preview=item.get("content_preview", ""),
                    url=item.get("url"),
                )
            )
        return posts

    def fetch_post_metrics(self, posts: list[ConnectorPost]) -> list[ConnectorPostMetric]:
        payload = {
            "posts": [
                {
                    "external_id": post.external_id,
                    "published_at": post.published_at.isoformat(),
                    "url": post.url,
                }
                for post in posts
            ]
        }
        response = requests.post(f"{self.base_url}/post-metrics", headers=self.headers, json=payload, timeout=30)
        response.raise_for_status()

        metrics: list[ConnectorPostMetric] = []
        for item in response.json().get("items", []):
            metrics.append(
                ConnectorPostMetric(
                    post_external_id=str(item["post_external_id"]),
                    captured_at=datetime.fromisoformat(item["captured_at"]),
                    views=int(item.get("views", 0)),
                    reactions=int(item.get("reactions", 0)),
                    comments=int(item.get("comments", 0)),
                    reposts=int(item.get("reposts", 0)),
                    reach=int(item.get("reach", 0)),
                )
            )

        return metrics

    def fetch_audience(self) -> ConnectorAudience:
        response = requests.get(f"{self.base_url}/audience", headers=self.headers, timeout=25)
        response.raise_for_status()
        item = response.json()
        return ConnectorAudience(
            captured_at=datetime.fromisoformat(item["captured_at"]),
            total_subscribers=int(item.get("total_subscribers", 0)),
            inflow=int(item.get("inflow", 0)),
            outflow=int(item.get("outflow", 0)),
        )


class VkApiConnector(BaseConnector):
    """
    Real VK connector via official API.

    Expected account settings:
    - account.platform = vk
    - account.external_id = shortname or numeric group id
    - account.api_token = VK user token with access to required methods
    """

    def __init__(self, account: Account):
        if account.platform != Platform.VK:
            raise ValueError("VkApiConnector can be used only for VK platform")

        settings = get_settings()
        token = account.api_token or settings.default_vk_token
        if not token:
            raise ValueError("VK API mode requires api_token")

        self.account = account
        self.token = token
        self.version = "5.199"
        self.base_url = "https://api.vk.com/method"
        self._group_id: int | None = None
        self._last_wall_items: dict[str, dict] = {}

    def fetch_posts(self, since: datetime | None = None) -> list[ConnectorPost]:
        posts: list[ConnectorPost] = []
        self._last_wall_items = {}

        offset = 0
        limit = 100
        max_pages = 10

        for _ in range(max_pages):
            wall_params: dict[str, int | str] = {
                "count": limit,
                "offset": offset,
                "filter": "owner",
            }
            if self.account.external_id.isdigit():
                # Community owner_id must be negative group id in wall methods.
                wall_params["owner_id"] = -int(self.account.external_id)
            else:
                wall_params["domain"] = self.account.external_id

            payload = self._call(
                "wall.get",
                wall_params,
            )
            items = payload.get("items", [])
            if not items:
                break

            stop_on_old = False
            for item in items:
                unix_date = int(item.get("date", 0))
                if not unix_date:
                    continue

                published_at = datetime.fromtimestamp(unix_date, tz=timezone.utc)
                if since and published_at < since:
                    stop_on_old = True
                    continue

                owner_id = int(item.get("owner_id", 0))
                post_id = int(item.get("id", 0))
                if not owner_id or not post_id:
                    continue

                external_post_id = f"{owner_id}_{post_id}"
                preview = self._build_preview(item)
                post_url = f"https://vk.com/wall{owner_id}_{post_id}"

                post = ConnectorPost(
                    external_id=external_post_id,
                    published_at=published_at,
                    content_preview=preview,
                    url=post_url,
                )
                posts.append(post)
                self._last_wall_items[external_post_id] = item

            if stop_on_old or len(items) < limit:
                break
            offset += limit

        return posts

    def fetch_post_metrics(self, posts: list[ConnectorPost]) -> list[ConnectorPostMetric]:
        captured_at = datetime.now(timezone.utc)
        metrics: list[ConnectorPostMetric] = []

        missing_ids: list[str] = []
        for post in posts:
            item = self._last_wall_items.get(post.external_id)
            if not item:
                missing_ids.append(post.external_id)
                continue
            metrics.append(self._metric_from_wall_item(post.external_id, captured_at, item))

        if missing_ids:
            for chunk in _chunked(missing_ids, size=80):
                payload = self._call("wall.getById", {"posts": ",".join(chunk)})
                for item in payload:
                    owner_id = int(item.get("owner_id", 0))
                    post_id = int(item.get("id", 0))
                    external_post_id = f"{owner_id}_{post_id}"
                    metrics.append(self._metric_from_wall_item(external_post_id, captured_at, item))

        return metrics

    def fetch_audience(self) -> ConnectorAudience:
        captured_at = datetime.now(timezone.utc)
        total_subscribers = self._fetch_total_subscribers()
        inflow, outflow = self._fetch_daily_flow_safe(captured_at)

        return ConnectorAudience(
            captured_at=captured_at,
            total_subscribers=total_subscribers,
            inflow=inflow,
            outflow=outflow,
        )

    def _fetch_total_subscribers(self) -> int:
        payload = self._call(
            "groups.getById",
            {
                "group_id": self.account.external_id,
                "fields": "members_count",
            },
        )
        if not payload:
            return 0

        group = payload[0]
        self._group_id = int(group.get("id", 0)) or None
        members_count = int(group.get("members_count", 0))
        if members_count:
            return members_count

        if self._group_id:
            members_payload = self._call(
                "groups.getMembers",
                {
                    "group_id": self._group_id,
                    "count": 1,
                },
            )
            return int(members_payload.get("count", 0))
        return 0

    def _fetch_daily_flow_safe(self, now: datetime) -> tuple[int, int]:
        group_id = self._group_id or self._resolve_group_id()
        if not group_id:
            return 0, 0

        day = now.strftime("%Y-%m-%d")
        try:
            payload = self._call(
                "stats.get",
                {
                    "group_id": group_id,
                    "date_from": day,
                    "date_to": day,
                    "interval": "day",
                },
            )
        except Exception:
            return 0, 0

        if not payload:
            return 0, 0

        period = payload[0]
        activity = period.get("activity", {}) if isinstance(period, dict) else {}

        inflow = int(activity.get("subscribed", 0))
        outflow = int(activity.get("unsubscribed", 0))
        return inflow, outflow

    def _resolve_group_id(self) -> int | None:
        if self._group_id:
            return self._group_id

        if self.account.external_id.isdigit():
            self._group_id = int(self.account.external_id)
            return self._group_id

        payload = self._call("utils.resolveScreenName", {"screen_name": self.account.external_id})
        if not payload:
            return None
        if payload.get("type") != "group":
            return None

        object_id = int(payload.get("object_id", 0))
        self._group_id = object_id or None
        return self._group_id

    def _metric_from_wall_item(
        self, external_post_id: str, captured_at: datetime, item: dict
    ) -> ConnectorPostMetric:
        views = int((item.get("views") or {}).get("count", 0))
        reactions = int((item.get("likes") or {}).get("count", 0))
        comments = int((item.get("comments") or {}).get("count", 0))
        reposts = int((item.get("reposts") or {}).get("count", 0))
        reach = int((item.get("views") or {}).get("count", 0))

        return ConnectorPostMetric(
            post_external_id=external_post_id,
            captured_at=captured_at,
            views=max(views, 0),
            reactions=max(reactions, 0),
            comments=max(comments, 0),
            reposts=max(reposts, 0),
            reach=max(reach, 0),
        )

    def _build_preview(self, item: dict) -> str:
        text = (item.get("text") or "").strip()
        if text:
            return text[:2000]
        attachments = item.get("attachments") or []
        if attachments:
            first_type = attachments[0].get("type", "attachment")
            return f"[{first_type}]"
        return "[пустой пост]"

    def _call(self, method: str, params: dict) -> dict | list:
        payload = {
            **params,
            "access_token": self.token,
            "v": self.version,
        }
        response = requests.get(f"{self.base_url}/{method}", params=payload, timeout=30)
        response.raise_for_status()
        body = response.json()

        error = body.get("error")
        if error:
            code = error.get("error_code")
            message = error.get("error_msg", "VK API error")
            raise ValueError(f"VK API error {code}: {message}")

        return body.get("response")


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
