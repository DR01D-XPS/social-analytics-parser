from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Account
from app.schemas import ManualSyncResponse
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _run_sync_all_background() -> None:
    db = SessionLocal()
    try:
        SyncService(db).sync_all_active_accounts()
    finally:
        db.close()


def _run_sync_account_background(account_id: int) -> None:
    db = SessionLocal()
    try:
        SyncService(db).sync_account(account_id)
    finally:
        db.close()


@router.post("/run-all", response_model=ManualSyncResponse)
def run_all_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_sync_all_background)
    return ManualSyncResponse(started=True, message="Background sync started for all active accounts")


@router.post("/run/{account_id}", response_model=ManualSyncResponse)
def run_account_sync(account_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    background_tasks.add_task(_run_sync_account_background, account_id)
    return ManualSyncResponse(account_id=account_id, started=True, message="Background sync started")
