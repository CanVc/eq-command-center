from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"
TestCommand = tuple[str, list[str], Path]


def _local_venv_python() -> Path | None:
    python_path = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return python_path if python_path.exists() else None


def _is_current_python(python_path: Path) -> bool:
    return Path(sys.executable).resolve() == python_path.resolve()


def _windows_nodejs_paths(executable_name: str) -> list[Path]:
    paths: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        install_root = os.environ.get(env_name)
        if install_root:
            paths.append(Path(install_root) / "nodejs" / executable_name)
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.extend(
            [
                Path(appdata) / "npm" / executable_name,
                Path(appdata) / "nvm" / "current" / executable_name,
            ]
        )
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        paths.append(Path(local_appdata) / "Volta" / "bin" / executable_name)
    return paths


def _npm_executable() -> str | None:
    candidates = ["npm.cmd", "npm"] if sys.platform == "win32" else ["npm"]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable is not None:
            return executable

    if sys.platform == "win32":
        for path in _windows_nodejs_paths("npm.cmd"):
            if path.exists():
                return str(path)
    return None


def _node_executable(npm: str | None = None) -> str | None:
    node_name = "node.exe" if sys.platform == "win32" else "node"
    if npm is not None:
        npm_sibling = Path(npm).with_name(node_name)
        if npm_sibling.exists():
            return str(npm_sibling)

    executable = shutil.which(node_name)
    if executable is not None:
        return executable

    if sys.platform == "win32":
        for path in _windows_nodejs_paths(node_name):
            if path.exists():
                return str(path)
    return None


def _prepend_to_path(paths: list[Path]) -> None:
    existing_path = os.environ.get("PATH", "")
    existing_parts = [part for part in existing_path.split(os.pathsep) if part]
    seen = {os.path.normcase(os.path.normpath(part)) for part in existing_parts}
    prepend_parts: list[str] = []

    for path in paths:
        if not path.exists():
            continue
        path_string = str(path)
        path_key = os.path.normcase(os.path.normpath(path_string))
        if path_key in seen:
            continue
        prepend_parts.append(path_string)
        seen.add(path_key)

    if prepend_parts:
        os.environ["PATH"] = os.pathsep.join([*prepend_parts, *existing_parts])


def _local_web_bin(command: str) -> Path:
    suffix = ".cmd" if sys.platform == "win32" else ""
    return WEB_ROOT / "node_modules" / ".bin" / f"{command}{suffix}"


def _frontend_commands() -> list[TestCommand] | None:
    npm = _npm_executable()
    if npm is not None:
        node = _node_executable(npm)
        if node is None:
            print(f"npm found at {npm}, but node executable was not found.", file=sys.stderr)
            return None
        _prepend_to_path([Path(node).parent, Path(npm).parent])
        return [
            ("web_test", [npm, "run", "test"], WEB_ROOT),
            ("web_build", [npm, "run", "build"], WEB_ROOT),
            ("web_e2e", [npm, "run", "test:e2e"], WEB_ROOT),
        ]

    vitest = _local_web_bin("vitest")
    tsc = _local_web_bin("tsc")
    vite = _local_web_bin("vite")
    playwright = _local_web_bin("playwright")
    local_bins = [vitest, tsc, vite, playwright]
    node = _node_executable()
    if node is None or not all(path.exists() for path in local_bins):
        return None

    _prepend_to_path([Path(node).parent, WEB_ROOT / "node_modules" / ".bin"])
    print("npm executable not found; using local web/node_modules/.bin commands.", flush=True)
    return [
        ("web_test", [str(vitest), "run"], WEB_ROOT),
        ("web_typecheck", [str(tsc), "-b"], WEB_ROOT),
        ("web_build", [str(vite), "build"], WEB_ROOT),
        ("web_e2e", [str(playwright), "test"], WEB_ROOT),
    ]


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
        "--no-frontend",
        action="store_true",
        help="Skip frontend npm test/build/e2e commands",
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

    commands: list[TestCommand] = [
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
            PROJECT_ROOT,
        )
    ]

    if not args.no_frontend:
        frontend_commands = _frontend_commands()
        if frontend_commands is None:
            print(
                "npm executable not found and local web/node_modules/.bin tools are missing. "
                "Install Node.js/npm, run `npm install` in web/, or rerun with --no-frontend.",
                file=sys.stderr,
            )
            return 127
        commands.extend(frontend_commands)

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
                PROJECT_ROOT,
            )
        )

    for name, command, cwd in commands:
        print(f"\n==> Running {name}", flush=True)
        print(f"cwd: {cwd}", flush=True)
        print(" ".join(command), flush=True)
        completed = subprocess.run(command, cwd=cwd)
        if completed.returncode != 0:
            print(f"\n{name} failed with exit code {completed.returncode}", file=sys.stderr)
            return completed.returncode

    print("\nAll requested test commands passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
