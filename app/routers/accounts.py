from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Platform, SourceMode
from app.schemas import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def validate_source_config(
    platform: Platform,
    source_mode: SourceMode,
    api_base_url: str | None,
    api_token: str | None,
) -> None:
    if source_mode == SourceMode.HTTP:
        # Direct VK mode: no base URL required, but token is required.
        if platform == Platform.VK:
            if not api_token:
                raise HTTPException(status_code=400, detail="VK API mode requires API token")
            return

        if not api_base_url:
            raise HTTPException(status_code=400, detail="HTTP adapter mode requires API base URL")


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.scalars(select(Account).order_by(Account.created_at.desc())).all()
    return accounts


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    api_base_url = payload.api_base_url.strip() if payload.api_base_url else None
    api_token = payload.api_token.strip() if payload.api_token else None
    validate_source_config(payload.platform, payload.source_mode, api_base_url, api_token)

    account = Account(
        platform=payload.platform,
        external_id=payload.external_id.strip(),
        title=payload.title.strip(),
        source_mode=payload.source_mode,
        api_base_url=api_base_url,
        api_token=api_token,
        is_active=True,
    )

    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account with this platform and external_id already exists") from exc

    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        account.title = data["title"].strip()
    if "is_active" in data:
        account.is_active = data["is_active"]
    if "source_mode" in data and data["source_mode"] is not None:
        account.source_mode = data["source_mode"]
    if "api_base_url" in data:
        account.api_base_url = data["api_base_url"].strip() if data["api_base_url"] else None
    if "api_token" in data:
        account.api_token = data["api_token"].strip() if data["api_token"] else None

    validate_source_config(account.platform, account.source_mode, account.api_base_url, account.api_token)

    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(account)
    db.commit()
    return None
