from __future__ import annotations

from contextlib import closing
import os
import sqlite3
from pathlib import Path


LOG_PATH_SETTING = "eq_log_path"


APP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class LogPathPickerUnavailable(RuntimeError):
    """Raised when the native file picker cannot be opened."""


def get_configured_log_path(db_path: str | Path) -> str | None:
    """Return the locally configured EverQuest log path, if one was saved."""

    try:
        with closing(sqlite3.connect(_readonly_uri(db_path), uri=True)) as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (LOG_PATH_SETTING,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if row is None or not row[0]:
        return None

    return str(row[0])


def set_configured_log_path(db_path: str | Path, log_path: str | None) -> str | None:
    """Persist the local EverQuest log path. Empty values clear the setting."""

    normalized_path = normalize_log_path(log_path)
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        _ensure_app_settings_table(connection)
        if normalized_path is None:
            connection.execute("DELETE FROM app_settings WHERE key = ?", (LOG_PATH_SETTING,))
        else:
            connection.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (LOG_PATH_SETTING, normalized_path),
            )
        connection.commit()

    return normalized_path


def choose_eq_log_path(initial_path: str | None = None) -> str | None:
    """Open a native file picker and return the selected EQ log path, if any."""

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python install
        raise LogPathPickerUnavailable("Native file picker is unavailable on this machine") from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise LogPathPickerUnavailable(str(exc)) from exc

    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    try:
        selected_path = filedialog.askopenfilename(
            parent=root,
            title="Select EverQuest log file",
            initialdir=_initial_log_directory(initial_path),
            filetypes=(
                ("EverQuest logs", "eqlog_*.txt"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ),
        )
    except tk.TclError as exc:
        raise LogPathPickerUnavailable(str(exc)) from exc
    finally:
        root.destroy()

    return normalize_log_path(selected_path)


def normalize_log_path(log_path: str | None) -> str | None:
    if log_path is None:
        return None

    stripped_path = log_path.strip()
    if not stripped_path:
        return None

    return str(Path(stripped_path).expanduser().resolve(strict=False))


def _initial_log_directory(initial_path: str | None) -> str | None:
    if initial_path:
        parent = Path(initial_path).expanduser().parent
        if parent.exists():
            return str(parent)

    public_dir = os.environ.get("PUBLIC")
    if public_dir:
        default_eq_dir = (
            Path(public_dir)
            / "Daybreak Game Company"
            / "Installed Games"
            / "EverQuest"
            / "Logs"
        )
        if default_eq_dir.exists():
            return str(default_eq_dir)

    return None


def _readonly_uri(db_path: str | Path) -> str:
    return f"{Path(db_path).expanduser().resolve().as_uri()}?mode=ro"


def _ensure_app_settings_table(connection: sqlite3.Connection) -> None:
    connection.execute(APP_SETTINGS_SCHEMA)
