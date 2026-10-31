from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.database import Base, SessionLocal, engine
from app.routers.accounts import router as accounts_router
from app.routers.reports import router as reports_router
from app.routers.sync import router as sync_router
from app.services.bootstrap import seed_demo_accounts
from app.services.sync_service import SyncService

settings = get_settings()
static_dir = BASE_DIR / "app" / "static"
scheduler = BackgroundScheduler(timezone="UTC")


def run_scheduled_sync() -> None:
    db = SessionLocal()
    try:
        SyncService(db).sync_all_active_accounts()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if settings.seed_demo_data:
            seed_demo_accounts(db, with_initial_sync=True)
    finally:
        db.close()

    if not scheduler.running:
        scheduler.add_job(
            run_scheduled_sync,
            "interval",
            minutes=settings.sync_interval_minutes,
            max_instances=1,
            replace_existing=True,
            id="scheduled-social-sync",
        )
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router)
app.include_router(sync_router)
app.include_router(reports_router)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def dashboard_page():
    return FileResponse(static_dir / "index.html")


@app.get("/sources")
def sources_page():
    return FileResponse(static_dir / "sources.html")


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
