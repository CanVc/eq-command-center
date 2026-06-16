from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from eqmarket.api.db import resolve_db_path
from eqmarket.api.routes.dashboard import router as dashboard_router
from eqmarket.api.routes.deals import router as deals_router


LOGGER = logging.getLogger(__name__)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    resolved_db_path = resolve_db_path(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        LOGGER.info("Using SQLite database: %s", app.state.db_path)
        yield

    app = FastAPI(
        title="EQ Command Center API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.db_path = resolved_db_path

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "db_path": str(app.state.db_path),
        }

    app.include_router(dashboard_router)
    app.include_router(deals_router)

    return app


app = create_app()
