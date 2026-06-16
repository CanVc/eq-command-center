from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _local_venv_python() -> Path | None:
    python_path = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return python_path if python_path.exists() else None


venv_python = _local_venv_python()
if "--no-venv" not in sys.argv and venv_python is not None and Path(sys.executable).resolve() != venv_python.resolve():
    print(f"==> Re-running with local virtualenv: {venv_python}", flush=True)
    raise SystemExit(subprocess.run([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=PROJECT_ROOT).returncode)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from eqmarket.api.app import create_app  # noqa: E402


Endpoint = tuple[str, str, dict[str, Any]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test the local FastAPI app against a SQLite DB")
    parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    parser.add_argument("--server", default="frostreaver", help="Server query parameter")
    parser.add_argument("--search", default="stave", help="Item search query")
    parser.add_argument("--no-venv", action="store_true", help="Do not auto-rerun with .venv/Scripts/python.exe")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: database does not exist: {db_path}", file=sys.stderr)
        return 2

    endpoints: list[Endpoint] = [
        ("health", "/api/health", {}),
        ("krono", "/api/krono/latest", {"server": args.server}),
        ("dashboard", "/api/dashboard/summary", {"server": args.server}),
        ("listings", "/api/listings/recent", {"server": args.server, "limit": 5}),
        ("deals", "/api/deals", {"server": args.server, "limit": 5}),
        ("item_search", "/api/items/search", {"q": args.search}),
    ]

    app = create_app(db_path)
    failures: list[str] = []

    with TestClient(app) as client:
        for name, path, params in endpoints:
            response = client.get(path, params=params)
            status = response.status_code
            if status != 200:
                failures.append(f"{name}: HTTP {status} {response.text[:300]}")
                print(f"FAIL {name:<12} HTTP {status}")
                continue

            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                failures.append(f"{name}: invalid JSON: {exc}")
                print(f"FAIL {name:<12} invalid JSON")
                continue

            size = len(payload) if isinstance(payload, list | dict) else "?"
            print(f"OK   {name:<12} HTTP {status} payload_size={size}")

    if failures:
        print("\nSmoke test failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"\nSmoke test OK for DB: {db_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
