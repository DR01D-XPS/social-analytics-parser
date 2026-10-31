from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Platform, SourceMode
from app.services.sync_service import SyncService


def seed_demo_accounts(db: Session, with_initial_sync: bool = True) -> None:
    has_accounts = db.scalar(select(Account.id).limit(1))
    if has_accounts:
        return

    now = datetime.now(timezone.utc)
    demo_accounts = [
        Account(
            platform=Platform.VK,
            external_id="demo_vk_group",
            title="VK Demo Group",
            source_mode=SourceMode.MOCK,
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        Account(
            platform=Platform.TELEGRAM,
            external_id="demo_tg_channel",
            title="Telegram Demo Channel",
            source_mode=SourceMode.MOCK,
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        Account(
            platform=Platform.MAX,
            external_id="demo_max_channel",
            title="MAX Demo Channel",
            source_mode=SourceMode.MOCK,
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]

    db.add_all(demo_accounts)
    db.commit()

    if with_initial_sync:
        sync_service = SyncService(db)
        for account in demo_accounts:
            sync_service.sync_account(account.id)
