from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eqmarket.api.db import connect_readonly
from eqmarket.inventory_importer import import_inventory_dump, infer_character_server_from_inventory_path
from eqmarket.local_settings import get_configured_log_path


LOGGER = logging.getLogger(__name__)
INVENTORY_DIRECTORY_ENV = "EQMARKET_INVENTORY_DIR"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0


@dataclass
class InventoryWatcherStatus:
    running: bool = False
    inventory_directory: str | None = None
    inventory_directory_exists: bool | None = None
    last_checked_at: str | None = None
    last_imported_at: str | None = None
    files_seen: int = 0
    files_imported: int = 0
    files_skipped: int = 0
    latest_import_id: int | None = None
    latest_import_character: str | None = None
    latest_import_server: str | None = None
    latest_import_file: str | None = None
    error: str | None = None


class InventoryWatcher:
    """Polls the EverQuest directory and imports changed ``*-Inventory.txt`` dumps."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        inventory_directory: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.poll_interval_seconds = poll_interval_seconds
        self.inventory_directory = Path(inventory_directory).expanduser().resolve(strict=False) if inventory_directory else None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status = InventoryWatcherStatus()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="eq-inventory-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._status)

    def poll_once(self) -> None:
        checked_at = _utcnow()
        inventory_directory = resolve_inventory_directory(self.db_path, self.inventory_directory)
        if inventory_directory is None:
            self._set_status(
                inventory_directory=None,
                inventory_directory_exists=None,
                last_checked_at=checked_at,
                files_seen=0,
                files_imported=0,
                files_skipped=0,
                error=None,
            )
            return

        if not inventory_directory.is_dir():
            self._set_status(
                inventory_directory=str(inventory_directory),
                inventory_directory_exists=False,
                last_checked_at=checked_at,
                files_seen=0,
                files_imported=0,
                files_skipped=0,
                error="Configured EverQuest inventory directory does not exist",
            )
            return

        files_seen = 0
        files_imported = 0
        files_skipped = 0
        latest_imported_at: str | None = None
        latest_import_id: int | None = None
        latest_import_character: str | None = None
        latest_import_server: str | None = None
        latest_import_file: str | None = None
        errors: list[str] = []

        try:
            inventory_files = load_latest_inventory_dump_files(inventory_directory)
        except OSError as exc:
            LOGGER.warning("EQ inventory watcher scan failed: %s", exc)
            self._set_status(
                inventory_directory=str(inventory_directory),
                inventory_directory_exists=inventory_directory.exists(),
                last_checked_at=checked_at,
                files_seen=0,
                files_imported=0,
                files_skipped=0,
                error=str(exc)[:1000],
            )
            return

        files_seen = len(inventory_files)
        for inventory_file in inventory_files:
            try:
                inferred = infer_character_server_from_inventory_path(inventory_file)
                if inferred is None:
                    files_skipped += 1
                    continue

                character_name, server = inferred
                source_hash = _sha256_file(inventory_file)
                if _latest_inventory_import_matches(self.db_path, character_name, server, source_hash):
                    files_skipped += 1
                    continue

                stats = import_inventory_dump(self.db_path, inventory_file)
                files_imported += 1
                latest_imported_at = _utcnow()
                latest_import_id = stats.inventory_import_id
                latest_import_character = stats.character_name
                latest_import_server = stats.server
                latest_import_file = stats.source_file
            except (OSError, ValueError, sqlite3.Error) as exc:
                LOGGER.warning("EQ inventory watcher failed to import %s: %s", inventory_file, exc)
                errors.append(f"{inventory_file.name}: {exc}"[:1000])

        self._set_status(
            inventory_directory=str(inventory_directory),
            inventory_directory_exists=True,
            last_checked_at=checked_at,
            last_imported_at=latest_imported_at or self._status.last_imported_at,
            files_seen=files_seen,
            files_imported=files_imported,
            files_skipped=files_skipped,
            latest_import_id=latest_import_id if latest_import_id is not None else self._status.latest_import_id,
            latest_import_character=latest_import_character or self._status.latest_import_character,
            latest_import_server=latest_import_server or self._status.latest_import_server,
            latest_import_file=latest_import_file or self._status.latest_import_file,
            error="; ".join(errors)[:1000] if errors else None,
        )

    def _run(self) -> None:
        self._set_status(running=True, error=None)
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self.poll_interval_seconds)
        self._set_status(running=False)

    def _set_status(self, **updates: Any) -> None:
        with self._lock:
            for key, value in updates.items():
                if hasattr(self._status, key):
                    setattr(self._status, key, value)


def resolve_inventory_directory(db_path: str | Path, explicit_directory: str | Path | None = None) -> Path | None:
    """Resolve the EQ directory that contains ``<Character>_<server>-Inventory.txt`` files.

    Priority:
    1. an explicit constructor path,
    2. ``EQMARKET_INVENTORY_DIR``,
    3. the parent of the configured EQ log directory (``.../EverQuest/Logs`` -> ``.../EverQuest``).
    """

    if explicit_directory is not None:
        return Path(explicit_directory).expanduser().resolve(strict=False)

    env_directory = os.environ.get(INVENTORY_DIRECTORY_ENV)
    if env_directory and env_directory.strip():
        return Path(env_directory.strip()).expanduser().resolve(strict=False)

    log_path_text = get_configured_log_path(db_path)
    if log_path_text is None:
        return None

    log_parent = Path(log_path_text).expanduser().resolve(strict=False).parent
    if log_parent.name.casefold() == "logs":
        return log_parent.parent
    return log_parent


def load_latest_inventory_dump_files(inventory_directory: str | Path) -> list[Path]:
    """Return the newest dump per inferred ``(character, server)`` in a directory."""

    latest_files: dict[tuple[str, str], tuple[int, str, Path]] = {}
    for path in Path(inventory_directory).iterdir():
        if not path.is_file():
            continue
        inferred = infer_character_server_from_inventory_path(path)
        if inferred is None:
            continue
        character_name, server = inferred
        stat = path.stat()
        key = (character_name.casefold(), server.casefold())
        candidate = (stat.st_mtime_ns, path.name.casefold(), path)
        previous = latest_files.get(key)
        if previous is None or candidate[:2] > previous[:2]:
            latest_files[key] = candidate

    return [entry[2] for entry in sorted(latest_files.values(), key=lambda entry: entry[2].name.casefold())]


def _latest_inventory_import_matches(
    db_path: str | Path,
    character_name: str,
    server: str,
    source_hash: str,
) -> bool:
    try:
        with closing(connect_readonly(db_path)) as connection:
            row = connection.execute(
                """
                SELECT source_hash
                FROM inventory_imports
                WHERE lower(character_name) = lower(?)
                  AND lower(server) = lower(?)
                  AND status = 'completed'
                ORDER BY datetime(imported_at) DESC, imported_at DESC, inventory_import_id DESC
                LIMIT 1
                """,
                (character_name, server),
            ).fetchone()
    except sqlite3.Error:
        return False

    return bool(row and row["source_hash"] == source_hash)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
