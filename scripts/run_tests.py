from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _local_venv_python() -> Path | None:
    python_path = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return python_path if python_path.exists() else None


def _is_current_python(python_path: Path) -> bool:
    return Path(sys.executable).resolve() == python_path.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the EQ Command Center test suite")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Also run the local API smoke test against --db",
    )
    parser.add_argument(
        "--db",
        default="data/eqmarket.sqlite",
        help="SQLite database path for --smoke (default: data/eqmarket.sqlite)",
    )
    parser.add_argument(
        "--server",
        default="frostreaver",
        help="Server parameter for --smoke (default: frostreaver)",
    )
    parser.add_argument(
        "--search",
        default="stave",
        help="Item search query for --smoke (default: stave)",
    )
    parser.add_argument(
        "--failfast",
        "-f",
        action="store_true",
        help="Stop unittest suite on first failure/error",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Run unittest suite in verbose mode",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        default="test*.py",
        help="unittest discovery pattern (default: test*.py)",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Do not auto-rerun with .venv/Scripts/python.exe when it exists",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    venv_python = _local_venv_python()
    if not args.no_venv and venv_python is not None and not _is_current_python(venv_python):
        print(f"==> Re-running with local virtualenv: {venv_python}", flush=True)
        completed = subprocess.run([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=PROJECT_ROOT)
        return completed.returncode

    commands: list[tuple[str, list[str]]] = [
        (
            "unittest",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                args.pattern,
                *( ["--failfast"] if args.failfast else [] ),
                *( ["--verbose"] if args.verbose else [] ),
            ],
        )
    ]

    if args.smoke:
        commands.append(
            (
                "smoke_api",
                [
                    sys.executable,
                    "scripts/smoke_api.py",
                    "--db",
                    args.db,
                    "--server",
                    args.server,
                    "--search",
                    args.search,
                ],
            )
        )

    for name, command in commands:
        print(f"\n==> Running {name}", flush=True)
        print(" ".join(command), flush=True)
        completed = subprocess.run(command, cwd=PROJECT_ROOT)
        if completed.returncode != 0:
            print(f"\n{name} failed with exit code {completed.returncode}", file=sys.stderr)
            return completed.returncode

    print("\nAll requested test commands passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
