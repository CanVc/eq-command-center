from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from eqmarket.api.db import connect_readonly
from eqmarket.db import init_db
from eqmarket.item_preferences import (
    ItemPreferenceStatusUpdate,
    fetch_item_preference_target,
    fetch_item_preferences,
    fetch_listing_preference_target,
    set_item_preference,
)
from eqmarket.sources.tlp_auctions import TlpAuctionsError, db_server_name


DEFAULT_SERVER = "frostreaver"

PreferenceStatusFilter = Literal["wanted", "ignored"]


class ItemPreferenceUpdate(BaseModel):
    status: ItemPreferenceStatusUpdate
    notes: str | None = None


router = APIRouter()


@router.get("/api/items/preferences")
def list_item_preferences(
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
    status: PreferenceStatusFilter | None = Query(None),
) -> list[dict[str, object]]:
    db_server = _normalize_server(server)

    with closing(_connect_or_503(request.app.state.db_path)) as connection:
        return fetch_item_preferences(connection, db_server, status=status)


@router.put("/api/items/{item_id}/preference")
def update_item_preference(
    item_id: int,
    payload: ItemPreferenceUpdate,
    request: Request,
    server: str = Query(DEFAULT_SERVER, min_length=1),
) -> dict[str, object]:
    db_server = _normalize_server(server)
    notes = _normalize_optional_text(payload.notes)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        target = fetch_item_preference_target(connection, db_server, item_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Item not found")
        preference = set_item_preference(connection, target, payload.status, notes=notes)
        connection.commit()

    return preference


@router.put("/api/listings/{listing_id}/item-preference")
def update_listing_item_preference(
    listing_id: int,
    payload: ItemPreferenceUpdate,
    request: Request,
) -> dict[str, object]:
    notes = _normalize_optional_text(payload.notes)

    with closing(_connect_writable_or_503(request.app.state.db_path)) as connection:
        target = fetch_listing_preference_target(connection, listing_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        preference = set_item_preference(connection, target, payload.status, notes=notes)
        connection.commit()

    return preference


def _normalize_server(server: str) -> str:
    try:
        return db_server_name(server)
    except TlpAuctionsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _connect_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        return connect_readonly(db_path)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not readable: {exc}") from exc


def _connect_writable_or_503(db_path: str | Path) -> sqlite3.Connection:
    try:
        resolved_path = Path(db_path)
        init_db(resolved_path)
        connection = sqlite3.connect(resolved_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"SQLite database is not writable: {exc}") from exc
