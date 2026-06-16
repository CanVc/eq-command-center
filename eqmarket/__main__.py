from __future__ import annotations

import argparse
from pathlib import Path

from eqmarket.db import init_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eqmarket")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize the SQLite database")
    init_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        init_db(Path(args.db))
        print(f"Initialized database: {args.db}")


if __name__ == "__main__":
    main()
