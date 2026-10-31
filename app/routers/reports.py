from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Platform
from app.schemas import OverviewReport
from app.services.report_service import build_overview_csv, build_overview_report, normalize_filters

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/overview", response_model=OverviewReport)
def get_overview(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    interval: str = Query(default="day"),
    platform: Platform | None = Query(default=None),
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        filters = normalize_filters(start=start, end=end, interval=interval, platform=platform, account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return build_overview_report(db, filters)


@router.get("/overview.csv")
def export_overview_csv(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    interval: str = Query(default="day"),
    platform: Platform | None = Query(default=None),
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        filters = normalize_filters(start=start, end=end, interval=interval, platform=platform, account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = build_overview_report(db, filters)
    csv_payload = build_overview_csv(report)

    return Response(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics-report.csv"},
    )
