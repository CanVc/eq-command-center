from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from eqmarket.price_importer import (
    TlpPriceImportStats,
    import_tlp_prices,
    load_recent_listing_item_ids,
    refresh_krono_price,
)
from eqmarket.sales_importer import TlpSalesSyncStats, sales_stats_payload, sync_tlp_sales
from eqmarket.sources.tlp_auctions import TlpAuctionsError, db_server_name


DEFAULT_STALE_PRICE_HOURS = 6.0
DEFAULT_REFRESH_LIMIT = 500
DEFAULT_HISTORY_DAYS = 3
DEFAULT_REFRESH_CONCURRENCY = 5
MAX_REFRESH_CONCURRENCY = 10


router = APIRouter()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class PriceRefreshJob:
    job_id: str
    db_path: Path
    server: str
    limit: int
    max_age_hours: float
    history_days: int
    concurrency: int
    refresh_krono_when_empty: bool
    sales_max_pages: int | None
    status: str = "queued"
    phase: str = "queued"
    completed: int = 0
    total: int | None = None
    current_item_id: int | None = None
    target_item_ids: list[int] = field(default_factory=list)
    sales_stats: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=_utcnow)
    started_at: str | None = None
    finished_at: str | None = None


_PRICE_REFRESH_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tlp-price-refresh")
_PRICE_REFRESH_JOBS: dict[str, PriceRefreshJob] = {}
_PRICE_REFRESH_JOBS_LOCK = Lock()


@router.post("/api/krono/refresh")
def refresh_krono(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    stats = _refresh_krono_or_502(Path(request.app.state.db_path), db_server)

    return {
        "server": db_server,
        "krono_updated": stats.krono_updated,
        "krono_price_pp": stats.krono_price_pp,
        "krono_listings_converted": stats.krono_listings_converted,
    }


@router.post("/api/tlp-sales/sync")
def sync_tlp_sales_route(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    max_pages: int | None = Query(None, gt=0, le=500),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    stats = _sync_sales_or_502(Path(request.app.state.db_path), db_server, max_pages)
    payload = sales_stats_payload(stats) or {}
    payload.update({"server": db_server, "max_pages": max_pages})
    return payload


@router.post("/api/tlp-prices/refresh")
def refresh_tlp_prices(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    limit: int = Query(DEFAULT_REFRESH_LIMIT, gt=0, le=2000),
    max_age_hours: float = Query(DEFAULT_STALE_PRICE_HOURS, ge=0, le=24 * 30),
    history_days: int = Query(DEFAULT_HISTORY_DAYS, ge=0, le=365),
    concurrency: int = Query(DEFAULT_REFRESH_CONCURRENCY, ge=1, le=MAX_REFRESH_CONCURRENCY),
    refresh_krono_when_empty: bool = Query(True),
    sales_max_pages: int | None = Query(None, gt=0, le=500),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    db_path = Path(request.app.state.db_path)
    sales_stats = _sync_sales_or_502(db_path, db_server, sales_max_pages)
    item_ids = _load_item_ids_or_503(db_path, db_server, limit, max_age_hours)

    if item_ids:
        stats = _import_prices_or_502(
            db_path,
            db_server,
            item_ids=item_ids,
            fetch_history=True,
            history_days=history_days,
            concurrency=concurrency,
        )
    elif refresh_krono_when_empty:
        stats = _refresh_krono_or_502(db_path, db_server)
    else:
        stats = TlpPriceImportStats()

    return _refresh_payload(
        db_server,
        stats,
        item_ids=item_ids,
        limit=limit,
        max_age_hours=max_age_hours,
        history_days=history_days,
        concurrency=concurrency,
        sales_stats=sales_stats,
    )


@router.post("/api/tlp-prices/refresh-jobs")
def start_tlp_price_refresh_job(
    request: Request,
    server: str = Query("frostreaver", min_length=1),
    limit: int = Query(DEFAULT_REFRESH_LIMIT, gt=0, le=2000),
    max_age_hours: float = Query(DEFAULT_STALE_PRICE_HOURS, ge=0, le=24 * 30),
    history_days: int = Query(DEFAULT_HISTORY_DAYS, ge=0, le=365),
    concurrency: int = Query(DEFAULT_REFRESH_CONCURRENCY, ge=1, le=MAX_REFRESH_CONCURRENCY),
    refresh_krono_when_empty: bool = Query(True),
    sales_max_pages: int | None = Query(None, gt=0, le=500),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    job = PriceRefreshJob(
        job_id=uuid4().hex,
        db_path=Path(request.app.state.db_path),
        server=db_server,
        limit=limit,
        max_age_hours=max_age_hours,
        history_days=history_days,
        concurrency=concurrency,
        refresh_krono_when_empty=refresh_krono_when_empty,
        sales_max_pages=sales_max_pages,
    )

    with _PRICE_REFRESH_JOBS_LOCK:
        _PRICE_REFRESH_JOBS[job.job_id] = job

    _PRICE_REFRESH_EXECUTOR.submit(_run_tlp_price_refresh_job, job.job_id)
    return _job_payload(job)


@router.get("/api/tlp-prices/refresh-jobs/{job_id}")
def get_tlp_price_refresh_job(job_id: str) -> dict[str, Any]:
    job = _get_job_or_404(job_id)
    return _job_payload(job)


@router.post("/api/tlp-prices/items/{item_id}/refresh")
def refresh_tlp_item_price(
    request: Request,
    item_id: int,
    server: str = Query("frostreaver", min_length=1),
    history_days: int = Query(DEFAULT_HISTORY_DAYS, ge=0, le=365),
) -> dict[str, Any]:
    db_server = _normalize_server(server)
    stats = _import_prices_or_502(
        Path(request.app.state.db_path),
        db_server,
        item_ids=[item_id],
        fetch_history=True,
        history_days=history_days,
        concurrency=1,
    )

    return _refresh_payload(
        db_server,
        stats,
        item_ids=[item_id],
        limit=1,
        max_age_hours=None,
        history_days=history_days,
        concurrency=1,
    )


def _run_tlp_price_refresh_job(job_id: str) -> None:
    job = _get_job(job_id)
    if job is None:
        return

    _update_job(job_id, status="running", phase="sales", started_at=_utcnow())

    try:
        sales_stats = sync_tlp_sales(job.db_path, job.server, max_pages=job.sales_max_pages)
        _update_job(
            job_id,
            sales_stats=sales_stats_payload(sales_stats),
            phase="selecting",
            completed=0,
            total=None,
            current_item_id=None,
        )

        item_ids = load_recent_listing_item_ids(
            job.db_path,
            job.server,
            job.limit,
            max_age_hours=job.max_age_hours,
        )
        _update_job(
            job_id,
            phase="selected",
            completed=0,
            total=len(item_ids),
            target_item_ids=item_ids,
            current_item_id=None,
        )

        if item_ids:
            def update_progress(progress: dict[str, object]) -> None:
                total = _optional_int(progress.get("total"))
                if total is None:
                    total = len(item_ids)
                _update_job(
                    job_id,
                    phase=str(progress.get("phase") or "refreshing"),
                    completed=_optional_int(progress.get("completed")) or 0,
                    total=total,
                    current_item_id=_optional_int(progress.get("item_id")),
                )

            stats = import_tlp_prices(
                job.db_path,
                job.server,
                item_ids=item_ids,
                fetch_history=True,
                history_days=job.history_days,
                progress_callback=update_progress,
                concurrency=job.concurrency,
            )
        elif job.refresh_krono_when_empty:
            _update_job(job_id, phase="krono", completed=0, total=0)
            stats = refresh_krono_price(job.db_path, job.server)
        else:
            stats = TlpPriceImportStats()

        payload = _refresh_payload(
            job.server,
            stats,
            item_ids=item_ids,
            limit=job.limit,
            max_age_hours=job.max_age_hours,
            history_days=job.history_days,
            concurrency=job.concurrency,
            sales_stats=sales_stats,
        )
        _update_job(
            job_id,
            status="completed",
            phase="completed",
            completed=len(item_ids),
            total=len(item_ids),
            current_item_id=None,
            stats=payload,
            finished_at=_utcnow(),
        )
    except Exception as exc:  # pragma: no cover - covered through API payload behavior
        _update_job(
            job_id,
            status="failed",
            phase="failed",
            error=str(exc)[:1000],
            finished_at=_utcnow(),
        )


def _normalize_server(server: str) -> str:
    try:
        return db_server_name(server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _refresh_krono_or_502(db_path: Path, db_server: str) -> TlpPriceImportStats:
    try:
        return refresh_krono_price(db_path, db_server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions Krono refresh failed: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions Krono refresh failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite Krono refresh failed: {exc}") from exc


def _sync_sales_or_502(db_path: Path, db_server: str, max_pages: int | None) -> TlpSalesSyncStats:
    try:
        return sync_tlp_sales(db_path, db_server, max_pages=max_pages)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions sales sync failed: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions sales sync failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite sales sync failed: {exc}") from exc


def _load_item_ids_or_503(
    db_path: Path,
    db_server: str,
    limit: int,
    max_age_hours: float,
) -> list[int]:
    try:
        return load_recent_listing_item_ids(db_path, db_server, limit, max_age_hours=max_age_hours)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite item selection failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite item selection failed: {exc}") from exc


def _import_prices_or_502(
    db_path: Path,
    db_server: str,
    *,
    item_ids: list[int],
    fetch_history: bool,
    history_days: int,
    concurrency: int = 1,
) -> TlpPriceImportStats:
    try:
        return import_tlp_prices(
            db_path,
            db_server,
            item_ids=item_ids,
            fetch_history=fetch_history,
            history_days=history_days,
            concurrency=concurrency,
        )
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions price refresh failed: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"TLP Auctions price refresh failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite price refresh failed: {exc}") from exc


def _get_job(job_id: str) -> PriceRefreshJob | None:
    with _PRICE_REFRESH_JOBS_LOCK:
        return _PRICE_REFRESH_JOBS.get(job_id)


def _get_job_or_404(job_id: str) -> PriceRefreshJob:
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="TLP price refresh job not found")
    return job


def _update_job(job_id: str, **updates: Any) -> None:
    with _PRICE_REFRESH_JOBS_LOCK:
        job = _PRICE_REFRESH_JOBS.get(job_id)
        if job is None:
            return
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)


def _job_payload(job: PriceRefreshJob) -> dict[str, Any]:
    with _PRICE_REFRESH_JOBS_LOCK:
        return {
            "job_id": job.job_id,
            "server": job.server,
            "status": job.status,
            "phase": job.phase,
            "completed": job.completed,
            "total": job.total,
            "current_item_id": job.current_item_id,
            "target_item_ids": list(job.target_item_ids),
            "target_count": len(job.target_item_ids),
            "limit": job.limit,
            "max_age_hours": job.max_age_hours,
            "history_days": job.history_days,
            "concurrency": job.concurrency,
            "sales_max_pages": job.sales_max_pages,
            "sales_stats": job.sales_stats,
            "stats": job.stats,
            "error": job.error,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }


def _refresh_payload(
    db_server: str,
    stats: TlpPriceImportStats,
    *,
    item_ids: list[int],
    limit: int,
    max_age_hours: float | None,
    history_days: int,
    concurrency: int,
    sales_stats: TlpSalesSyncStats | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = asdict(stats)
    payload.update(
        {
            "server": db_server,
            "target_item_ids": item_ids,
            "target_count": len(item_ids),
            "limit": limit,
            "max_age_hours": max_age_hours,
            "history_days": history_days,
            "concurrency": concurrency,
            "sales_sync": sales_stats_payload(sales_stats),
        }
    )
    return payload


def _optional_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
