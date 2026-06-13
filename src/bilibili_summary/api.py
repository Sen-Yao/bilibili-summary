from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .config import Settings
from .logging_utils import configure_logging
from .pipeline import Pipeline
from .store import JobStore

logger = logging.getLogger(__name__)


class ProcessVideoRequest(BaseModel):
    video: str = Field(min_length=1)
    run_now: bool = False
    dry_run: bool = False
    force: bool = False


class ProcessVideoResponse(BaseModel):
    job_id: int
    bvid: str
    created: bool
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    store = JobStore(settings.db_path)
    store.init_db()
    pipeline = Pipeline(settings, store)
    app = FastAPI(title="bilibili-summary API", version="0.1.0")

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        if not settings.api_token:
            logger.error("api token missing in configuration")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API token is not configured")
        expected = f"Bearer {settings.api_token}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    @app.get("/health")
    def health() -> dict[str, object]:
        try:
            with store.connect() as conn:
                conn.execute("SELECT 1").fetchone()
        except Exception as exc:  # pragma: no cover - defensive health path
            logger.exception("health check failed")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from exc
        return {"ok": True, "database": "ok"}

    @app.post("/api/videos/process", response_model=ProcessVideoResponse, dependencies=[Depends(require_token)])
    def process_video(request: ProcessVideoRequest) -> dict[str, object]:
        logger.info(
            "api process request run_now=%s dry_run=%s force=%s",
            request.run_now,
            request.dry_run,
            request.force,
        )
        try:
            return pipeline.process_video(
                request.video,
                dry_run=request.dry_run,
                run_now=request.run_now,
                force=request.force,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    configure_logging(settings.log_level)
    uvicorn.run(create_app(settings), host="0.0.0.0", port=8000, log_level=settings.log_level.lower())

