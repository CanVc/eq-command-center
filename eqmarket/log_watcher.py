from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eqmarket.api.db import connect_readonly
from eqmarket.log_importer import import_log_file
from eqmarket.local_settings import get_configured_log_path


LOGGER = logging.getLogger(__name__)
DEFAULT_SERVER = "frostreaver"
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_MAX_AUCTION_LINES_PER_TICK = 1000
_EQ_LOG_FILENAME_RE = re.compile(r"^eqlog_.+_(?P<server>[^_]+)$", re.IGNORECASE)


@dataclass
class LogWatcherStatus:
    running: bool = False
    log_path: str | None = None
    log_exists: bool | None = None
    server: str | None = None
    last_position: int | None = None
    last_checked_at: str | None = None
    last_imported_at: str | None = None
    latest_sale_at: str | None = None
    lines_read: int = 0
    auction_lines: int = 0
    listings_found: int = 0
    listings_inserted: int = 0
    error: str | None = None


class LogWatcher:
    """Small polling watcher that tails the configured EQ log into market_listings."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_auction_lines_per_tick: int = DEFAULT_MAX_AUCTION_LINES_PER_TICK,
        default_server: str = DEFAULT_SERVER,
    ) -> None:
        self.db_path = Path(db_path)
        self.poll_interval_seconds = poll_interval_seconds
        self.max_auction_lines_per_tick = max_auction_lines_per_tick
        self.default_server = default_server
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status = LogWatcherStatus()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="eq-log-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._status)

    def _run(self) -> None:
        self._set_status(running=True, error=None)
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self.poll_interval_seconds)
        self._set_status(running=False)

    def poll_once(self) -> None:
        checked_at = _utcnow()
        log_path_text = get_configured_log_path(self.db_path)
        if log_path_text is None:
            self._set_status(
                log_path=None,
                log_exists=None,
                server=None,
                last_checked_at=checked_at,
                error=None,
            )
            return

        log_path = Path(log_path_text)
        server = infer_server_from_log_path(log_path) or self.default_server
        latest_sale_at = _fetch_latest_log_sale_at(self.db_path, server)
        if not log_path.exists():
            self._set_status(
                log_path=str(log_path),
                log_exists=False,
                server=server,
                last_checked_at=checked_at,
                latest_sale_at=latest_sale_at,
                error="Configured EQ log file does not exist",
            )
            return

        try:
            stats = import_log_file(
                self.db_path,
                log_path,
                server,
                limit=self.max_auction_lines_per_tick,
                incremental=True,
                start_at_end_if_new=True,
            )
            latest_sale_at = stats.latest_sale_timestamp or _fetch_latest_log_sale_at(self.db_path, server)
            self._set_status(
                log_path=str(log_path),
                log_exists=True,
                server=server,
                last_position=stats.last_position,
                last_checked_at=checked_at,
                last_imported_at=_utcnow(),
                latest_sale_at=latest_sale_at,
                lines_read=stats.lines_read,
                auction_lines=stats.auction_lines,
                listings_found=stats.listings_found,
                listings_inserted=stats.listings_inserted,
                error=None,
            )
        except (OSError, sqlite3.Error) as exc:
            LOGGER.warning("EQ log watcher poll failed: %s", exc)
            self._set_status(
                log_path=str(log_path),
                log_exists=log_path.exists(),
                server=server,
                last_checked_at=checked_at,
                latest_sale_at=latest_sale_at,
                error=str(exc)[:1000],
            )

    def _set_status(self, **updates: Any) -> None:
        with self._lock:
            for key, value in updates.items():
                if hasattr(self._status, key):
                    setattr(self._status, key, value)


def infer_server_from_log_path(log_path: str | Path) -> str | None:
    stem = Path(log_path).stem
    match = _EQ_LOG_FILENAME_RE.match(stem)
    if match is None:
        return None
    return match.group("server").strip().lower() or None


def _fetch_latest_log_sale_at(db_path: str | Path, server: str) -> str | None:
    try:
        with closing(connect_readonly(db_path)) as connection:
            row = connection.execute(
                """
                SELECT max(timestamp)
                FROM market_listings
                WHERE lower(server) = lower(?)
                  AND source = 'eq_log'
                """,
                (server,),
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row and row[0] else None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
