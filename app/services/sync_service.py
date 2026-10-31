from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorPost
from app.connectors.factory import create_connector
from app.models import Account, AudienceSnapshot, Post, PostMetricSnapshot, SyncRun, SyncStatus

logger = logging.getLogger(__name__)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    def sync_all_active_accounts(self) -> list[SyncRun]:
        stmt: Select[tuple[Account]] = select(Account).where(Account.is_active.is_(True))
        accounts = self.db.scalars(stmt).all()

        runs: list[SyncRun] = []
        for account in accounts:
            runs.append(self.sync_account(account.id))
        return runs

    def sync_account(self, account_id: int) -> SyncRun:
        account = self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        run = SyncRun(account_id=account.id, status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        created_posts = 0
        captured_metrics = 0

        try:
            connector = create_connector(account)

            latest_post_time = self.db.scalar(
                select(func.max(Post.published_at)).where(Post.account_id == account.id)
            )
            since = ensure_utc(latest_post_time) - timedelta(days=3) if latest_post_time else None

            fetched_posts = connector.fetch_posts(since=since)
            post_map, created_posts = self._upsert_posts(account.id, fetched_posts)

            recent_posts = self._get_recent_connector_posts(account.id, limit=180)
            if recent_posts:
                fetched_metrics = connector.fetch_post_metrics(recent_posts)
                captured_metrics = self._store_post_metrics(post_map, fetched_metrics)

            audience = connector.fetch_audience()
            self.db.add(
                AudienceSnapshot(
                    account_id=account.id,
                    captured_at=ensure_utc(audience.captured_at),
                    total_subscribers=audience.total_subscribers,
                    inflow=audience.inflow,
                    outflow=audience.outflow,
                )
            )

            run.status = SyncStatus.SUCCESS
            run.message = "Sync completed"
            run.created_posts = created_posts
            run.captured_metrics = captured_metrics
            run.finished_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(run)
            return run

        except Exception as exc:  # noqa: BLE001
            logger.exception("Sync failed for account_id=%s", account_id)
            self.db.rollback()

            failed_run = self.db.get(SyncRun, run.id)
            if failed_run:
                failed_run.status = SyncStatus.FAILED
                failed_run.message = str(exc)
                failed_run.finished_at = datetime.now(timezone.utc)
                failed_run.created_posts = created_posts
                failed_run.captured_metrics = captured_metrics
                self.db.commit()
                self.db.refresh(failed_run)
                return failed_run
            raise

    def _upsert_posts(self, account_id: int, posts: list[ConnectorPost]) -> tuple[dict[str, Post], int]:
        if not posts:
            return {}, 0

        external_ids = [post.external_id for post in posts]
        existing_posts = self.db.scalars(
            select(Post).where(Post.account_id == account_id, Post.external_id.in_(external_ids))
        ).all()
        existing_map = {post.external_id: post for post in existing_posts}
        created_count = 0

        for item in posts:
            if item.external_id in existing_map:
                continue
            db_post = Post(
                account_id=account_id,
                external_id=item.external_id,
                published_at=ensure_utc(item.published_at),
                content_preview=item.content_preview[:2000],
                url=item.url,
            )
            self.db.add(db_post)
            existing_map[item.external_id] = db_post
            created_count += 1

        self.db.flush()

        full_map = self.db.scalars(select(Post).where(Post.account_id == account_id)).all()
        return {post.external_id: post for post in full_map}, created_count

    def _get_recent_connector_posts(self, account_id: int, limit: int = 180) -> list[ConnectorPost]:
        posts = self.db.scalars(
            select(Post)
            .where(Post.account_id == account_id)
            .order_by(Post.published_at.desc())
            .limit(limit)
        ).all()

        return [
            ConnectorPost(
                external_id=post.external_id,
                published_at=ensure_utc(post.published_at),
                content_preview=post.content_preview,
                url=post.url,
            )
            for post in posts
        ]

    def _store_post_metrics(self, post_map: dict[str, Post], metrics: list) -> int:
        captured = 0

        for metric in metrics:
            post = post_map.get(metric.post_external_id)
            if not post:
                continue

            self.db.add(
                PostMetricSnapshot(
                    post_id=post.id,
                    captured_at=ensure_utc(metric.captured_at),
                    views=max(metric.views, 0),
                    reactions=max(metric.reactions, 0),
                    comments=max(metric.comments, 0),
                    reposts=max(metric.reposts, 0),
                    reach=max(metric.reach, 0),
                )
            )
            captured += 1

        return captured
