from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
import csv

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from app.models import Account, AudienceSnapshot, Platform, Post, PostMetricSnapshot
from app.schemas import FlowPoint, OverviewReport, PostTrendPoint, ReportKpis, TimePoint, TopPost


ALLOWED_INTERVALS = {"hour", "day", "week", "month"}


@dataclass(slots=True)
class ReportFilters:
    start: datetime
    end: datetime
    interval: str
    platform: Platform | None = None
    account_id: int | None = None


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_filters(
    start: datetime | None,
    end: datetime | None,
    interval: str,
    platform: Platform | None = None,
    account_id: int | None = None,
) -> ReportFilters:
    now = datetime.now(timezone.utc)
    normalized_end = ensure_utc(end) if end else now
    normalized_start = ensure_utc(start) if start else normalized_end - timedelta(days=30)

    if normalized_start >= normalized_end:
        raise ValueError("start must be earlier than end")
    if interval not in ALLOWED_INTERVALS:
        raise ValueError(f"interval must be one of: {', '.join(sorted(ALLOWED_INTERVALS))}")

    return ReportFilters(
        start=normalized_start,
        end=normalized_end,
        interval=interval,
        platform=platform,
        account_id=account_id,
    )


def bucket_datetime(dt: datetime, interval: str) -> datetime:
    dt = ensure_utc(dt)
    if interval == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if interval == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == "week":
        monday = dt - timedelta(days=dt.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == "month":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported interval: {interval}")


def _account_conditions(filters: ReportFilters) -> list:
    conditions: list = []
    if filters.platform:
        conditions.append(Account.platform == filters.platform)
    if filters.account_id:
        conditions.append(Account.id == filters.account_id)
    return conditions


def _load_post_rows(db: Session, filters: ReportFilters):
    conditions = [
        PostMetricSnapshot.captured_at >= filters.start,
        PostMetricSnapshot.captured_at <= filters.end,
    ]
    conditions.extend(_account_conditions(filters))

    stmt: Select = (
        select(PostMetricSnapshot, Post, Account)
        .join(Post, Post.id == PostMetricSnapshot.post_id)
        .join(Account, Account.id == Post.account_id)
        .where(and_(*conditions))
    )
    return db.execute(stmt).all()


def _load_audience_rows(db: Session, filters: ReportFilters):
    conditions = [
        AudienceSnapshot.captured_at >= filters.start,
        AudienceSnapshot.captured_at <= filters.end,
    ]
    conditions.extend(_account_conditions(filters))

    stmt: Select = (
        select(AudienceSnapshot, Account)
        .join(Account, Account.id == AudienceSnapshot.account_id)
        .where(and_(*conditions))
    )
    return db.execute(stmt).all()


def build_overview_report(db: Session, filters: ReportFilters) -> OverviewReport:
    post_rows = _load_post_rows(db, filters)
    audience_rows = _load_audience_rows(db, filters)

    trend_bucket = defaultdict(lambda: {"views": 0, "reactions": 0, "comments": 0, "reposts": 0, "reach": 0})
    latest_by_post: dict[int, tuple[PostMetricSnapshot, Post, Account]] = {}

    for snapshot, post, account in post_rows:
        ts = bucket_datetime(snapshot.captured_at, filters.interval)
        trend_bucket[ts]["views"] += snapshot.views
        trend_bucket[ts]["reactions"] += snapshot.reactions
        trend_bucket[ts]["comments"] += snapshot.comments
        trend_bucket[ts]["reposts"] += snapshot.reposts
        trend_bucket[ts]["reach"] += snapshot.reach

        existing = latest_by_post.get(post.id)
        if not existing or ensure_utc(snapshot.captured_at) > ensure_utc(existing[0].captured_at):
            latest_by_post[post.id] = (snapshot, post, account)

    audience_bucket = defaultdict(lambda: {"inflow": 0, "outflow": 0, "total_subscribers": None, "latest_ts": None})
    for snapshot, _account in audience_rows:
        ts = bucket_datetime(snapshot.captured_at, filters.interval)
        bucket = audience_bucket[ts]
        bucket["inflow"] += snapshot.inflow
        bucket["outflow"] += snapshot.outflow

        latest_ts = bucket["latest_ts"]
        if latest_ts is None or ensure_utc(snapshot.captured_at) > latest_ts:
            bucket["latest_ts"] = ensure_utc(snapshot.captured_at)
            bucket["total_subscribers"] = snapshot.total_subscribers

    sorted_trend_keys = sorted(trend_bucket.keys())
    post_trend = [
        PostTrendPoint(
            timestamp=key,
            views=trend_bucket[key]["views"],
            reactions=trend_bucket[key]["reactions"],
            comments=trend_bucket[key]["comments"],
            reposts=trend_bucket[key]["reposts"],
            reach=trend_bucket[key]["reach"],
        )
        for key in sorted_trend_keys
    ]

    sorted_audience_keys = sorted(audience_bucket.keys())
    audience_flow: list[FlowPoint] = []
    cumulative_growth: list[TimePoint] = []
    cumulative = 0
    for key in sorted_audience_keys:
        inflow = audience_bucket[key]["inflow"]
        outflow = audience_bucket[key]["outflow"]
        net = inflow - outflow
        cumulative += net

        audience_flow.append(
            FlowPoint(
                timestamp=key,
                inflow=inflow,
                outflow=outflow,
                net_growth=net,
                total_subscribers=audience_bucket[key]["total_subscribers"],
            )
        )
        cumulative_growth.append(TimePoint(timestamp=key, value=cumulative))

    top_posts: list[TopPost] = []
    total_views = 0
    total_reactions = 0
    total_comments = 0
    total_reposts = 0

    for snapshot, post, account in sorted(
        latest_by_post.values(), key=lambda item: item[0].views, reverse=True
    )[:10]:
        total_views += snapshot.views
        total_reactions += snapshot.reactions
        total_comments += snapshot.comments
        total_reposts += snapshot.reposts

        engagement = (
            ((snapshot.reactions + snapshot.comments + snapshot.reposts) / snapshot.views) * 100
            if snapshot.views
            else 0.0
        )

        top_posts.append(
            TopPost(
                post_id=post.id,
                account_title=account.title,
                platform=account.platform,
                external_id=post.external_id,
                published_at=ensure_utc(post.published_at),
                content_preview=post.content_preview,
                views=snapshot.views,
                reactions=snapshot.reactions,
                comments=snapshot.comments,
                reposts=snapshot.reposts,
                reach=snapshot.reach,
                engagement_rate=round(engagement, 2),
            )
        )

    total_inflow = sum(point.inflow for point in audience_flow)
    total_outflow = sum(point.outflow for point in audience_flow)
    total_views_all = sum(item[0].views for item in latest_by_post.values())
    total_reactions_all = sum(item[0].reactions for item in latest_by_post.values())
    total_comments_all = sum(item[0].comments for item in latest_by_post.values())
    total_reposts_all = sum(item[0].reposts for item in latest_by_post.values())

    all_engagement = total_reactions_all + total_comments_all + total_reposts_all
    engagement_rate = (all_engagement / total_views_all * 100) if total_views_all else 0.0

    kpis = ReportKpis(
        inflow=total_inflow,
        outflow=total_outflow,
        net_growth=total_inflow - total_outflow,
        total_views=total_views_all,
        total_reactions=total_reactions_all,
        total_comments=total_comments_all,
        total_reposts=total_reposts_all,
        engagement_rate=round(engagement_rate, 2),
    )

    return OverviewReport(
        kpis=kpis,
        post_trend=post_trend,
        audience_flow=audience_flow,
        cumulative_growth=cumulative_growth,
        top_posts=top_posts,
    )


def build_overview_csv(report: OverviewReport) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["section", "timestamp", "views", "reactions", "comments", "reposts", "reach"])
    for row in report.post_trend:
        writer.writerow(
            [
                "post_trend",
                row.timestamp.isoformat(),
                row.views,
                row.reactions,
                row.comments,
                row.reposts,
                row.reach,
            ]
        )

    writer.writerow([])
    writer.writerow(["section", "timestamp", "inflow", "outflow", "net_growth", "total_subscribers"])
    for row in report.audience_flow:
        writer.writerow(
            [
                "audience_flow",
                row.timestamp.isoformat(),
                row.inflow,
                row.outflow,
                row.net_growth,
                row.total_subscribers,
            ]
        )

    writer.writerow([])
    writer.writerow(["section", "timestamp", "value"])
    for row in report.cumulative_growth:
        writer.writerow(["cumulative_growth", row.timestamp.isoformat(), row.value])

    writer.writerow([])
    writer.writerow(
        [
            "section",
            "account",
            "platform",
            "post_external_id",
            "published_at",
            "views",
            "reactions",
            "comments",
            "reposts",
            "reach",
            "engagement_rate",
        ]
    )
    for row in report.top_posts:
        writer.writerow(
            [
                "top_post",
                row.account_title,
                row.platform.value,
                row.external_id,
                row.published_at.isoformat(),
                row.views,
                row.reactions,
                row.comments,
                row.reposts,
                row.reach,
                row.engagement_rate,
            ]
        )

    writer.writerow([])
    writer.writerow(["kpi", "value"])
    writer.writerow(["inflow", report.kpis.inflow])
    writer.writerow(["outflow", report.kpis.outflow])
    writer.writerow(["net_growth", report.kpis.net_growth])
    writer.writerow(["total_views", report.kpis.total_views])
    writer.writerow(["total_reactions", report.kpis.total_reactions])
    writer.writerow(["total_comments", report.kpis.total_comments])
    writer.writerow(["total_reposts", report.kpis.total_reposts])
    writer.writerow(["engagement_rate", report.kpis.engagement_rate])

    return buffer.getvalue()
