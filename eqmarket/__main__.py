from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from eqmarket.db import init_db
from eqmarket.enrichment import enrich_pending_items
from eqmarket.log_importer import import_log_file, parse_log_file
from eqmarket.price_importer import import_tlp_prices
from eqmarket.scoring.deals import format_deal_score, score_market_listings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eqmarket")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize the SQLite database")
    init_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")

    log_parser = subparsers.add_parser("import-log", help="Parse an EverQuest log file into market listings")
    log_parser.add_argument("--log", required=True, help="Path to eqlog_*.txt")
    log_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    log_parser.add_argument("--server", default="frostreaver", help="Server name to store with listings")
    log_parser.add_argument("--limit", type=int, help="Stop after N auction lines (useful for tests)")
    log_parser.add_argument("--dry-run", action="store_true", help="Parse and print listings without writing SQLite")
    log_parser.add_argument("--full-rescan", action="store_true", help="Ignore saved log cursor and scan from the beginning")

    enrich_parser = subparsers.add_parser("enrich-pending", help="Resolve pending item names into full Lucy item/spell data")
    enrich_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    enrich_parser.add_argument("--limit", type=int, default=25, help="Maximum pending items to enrich")
    enrich_parser.add_argument("--source-server", default="Live", help="Lucy source server: Live or Test")

    tlp_parser = subparsers.add_parser("import-tlp-prices", help="Import TLP Auctions prices into market_prices")
    tlp_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    tlp_parser.add_argument("--server", default="frostreaver", help="TLP Auctions server name")
    tlp_parser.add_argument("--limit", type=int, help="Maximum target item ids to refresh")
    tlp_parser.add_argument("--item-id", action="append", type=int, help="Specific item id to refresh; repeatable")
    tlp_parser.add_argument("--all-catalog", action="store_true", help="Seed all TLP catalog items/prices instead of only local targets")
    tlp_parser.add_argument("--no-history", action="store_true", help="Only import cached catalog medians; skip per-item history stats")
    tlp_parser.add_argument("--history-days", type=int, default=3, help="Only use TLP sales from the last N days for history stats")

    score_parser = subparsers.add_parser("score-listings", help="Score resolved listings against market_prices")
    score_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    score_parser.add_argument("--server", default="frostreaver", help="Server name")
    score_parser.add_argument("--limit", type=int, default=200, help="Recent resolved/priced listings to score")
    score_parser.add_argument("--min-discount", type=float, default=30.0, help="Minimum discount percent for watch alerts")
    score_parser.add_argument("--all", action="store_true", help="Print non-alert scores too")

    alerts_parser = subparsers.add_parser("run-alerts", help="Run the full pipeline and print deal alerts")
    alerts_parser.add_argument("--db", default="data/eqmarket.sqlite", help="SQLite database path")
    alerts_parser.add_argument("--server", default="frostreaver", help="Server name")
    alerts_parser.add_argument("--log", help="Optional eqlog_*.txt to import before scoring")
    alerts_parser.add_argument("--log-limit", type=int, help="Stop log import after N auction lines")
    alerts_parser.add_argument("--full-log-rescan", action="store_true", help="Ignore saved log cursor and scan the log from the beginning")
    alerts_parser.add_argument("--enrich-limit", type=int, default=25, help="Maximum pending items to resolve before scoring")
    alerts_parser.add_argument("--skip-enrich", action="store_true", help="Skip Lucy pending item enrichment")
    alerts_parser.add_argument("--price-limit", type=int, default=500, help="Maximum recent item ids to refresh from TLP history")
    alerts_parser.add_argument("--price-max-age-hours", type=float, help="Only refresh recent item prices that are missing or older than N hours")
    alerts_parser.add_argument("--skip-price-refresh", action="store_true", help="Do not call TLP Auctions; score with cached prices/manual overrides only")
    alerts_parser.add_argument("--history-days", type=int, default=3, help="Only use TLP sales from the last N days")
    alerts_parser.add_argument("--no-history", action="store_true", help="Use cached TLP catalog medians instead of recent history")
    alerts_parser.add_argument("--score-limit", type=int, default=500, help="Recent resolved/priced listings to score")
    alerts_parser.add_argument("--min-discount", type=float, default=30.0, help="Minimum discount percent for watch alerts")
    alerts_parser.add_argument("--all", action="store_true", help="Print non-alert scores too")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        init_db(Path(args.db))
        print(f"Initialized database: {args.db}")
    elif args.command == "import-log":
        log_path = Path(args.log)
        if args.dry_run:
            listings = parse_log_file(log_path, limit=args.limit)
            for listing in listings[:25]:
                if listing.price_raw is None:
                    price = "NO PRICE"
                else:
                    pp = f" / {listing.price_pp}pp" if listing.price_pp is not None else ""
                    price = f"{listing.price_raw}{pp}"
                print(f"{listing.timestamp} | {listing.seller} | {listing.item_name} | {price} | {listing.confidence}")
            if len(listings) > 25:
                print(f"... {len(listings) - 25} more listings")
            print(f"Parsed listings: {len(listings)}")
        else:
            stats = import_log_file(
                Path(args.db),
                log_path,
                args.server,
                limit=args.limit,
                incremental=not args.full_rescan,
            )
            print(
                "Imported log: "
                f"lines={stats.lines_read}, auctions={stats.auction_lines}, "
                f"start_pos={stats.resumed_from_position}, end_pos={stats.last_position}, "
                f"sale_messages={stats.sale_messages}, listings_found={stats.listings_found}, "
                f"listings_inserted={stats.listings_inserted}, "
                f"pending_items={stats.pending_items_upserted}"
            )
    elif args.command == "enrich-pending":
        stats = enrich_pending_items(Path(args.db), limit=args.limit, source_server=args.source_server)
        print(
            "Enriched pending items: "
            f"seen={stats.pending_seen}, local_items_resolved={stats.local_items_resolved}, "
            f"items_imported={stats.items_imported}, spells_imported={stats.spells_imported}, "
            f"item_effects={stats.item_effects_imported}, "
            f"listings_linked={stats.listings_linked}, not_found={stats.not_found}, failed={stats.failed}"
        )
    elif args.command == "import-tlp-prices":
        stats = import_tlp_prices(
            Path(args.db),
            args.server,
            limit=args.limit,
            item_ids=args.item_id,
            all_catalog=args.all_catalog,
            fetch_history=not args.no_history,
            history_days=args.history_days,
        )
        print(
            "Imported TLP Auctions prices: "
            f"catalog_items_seen={stats.catalog_items_seen}, items_upserted={stats.items_upserted}, "
            f"listings_linked={stats.listings_linked}, catalog_prices={stats.catalog_prices_upserted}, "
            f"history_checked={stats.history_items_checked}, history_prices={stats.history_prices_upserted}, "
            f"no_price_data={stats.no_price_data}, price_refresh_failed={stats.price_refresh_failed}, "
            f"krono_updated={stats.krono_updated}, "
            f"krono_price_pp={stats.krono_price_pp}, krono_listings_converted={stats.krono_listings_converted}"
        )
    elif args.command == "score-listings":
        stats, scores = score_market_listings(
            Path(args.db),
            args.server,
            limit=args.limit,
            min_discount_pct=args.min_discount,
            alerts_only=not args.all,
        )
        print(
            "Scored listings: "
            f"seen={stats.listings_seen}, scores_written={stats.scores_written}, alerts={stats.alerts}"
        )
        for score in scores[:50]:
            print(format_deal_score(score))
        if len(scores) > 50:
            print(f"... {len(scores) - 50} more")
    elif args.command == "run-alerts":
        db_path = Path(args.db)
        if args.log:
            log_stats = import_log_file(
                db_path,
                Path(args.log),
                args.server,
                limit=args.log_limit,
                incremental=not args.full_log_rescan,
            )
            print(
                "Imported log: "
                f"start_pos={log_stats.resumed_from_position}, end_pos={log_stats.last_position}, "
                f"auctions={log_stats.auction_lines}, listings_inserted={log_stats.listings_inserted}, "
                f"pending_items={log_stats.pending_items_upserted}"
            )

        if not args.skip_enrich:
            enrich_stats = enrich_pending_items(db_path, limit=args.enrich_limit)
            print(
                "Enriched pending items: "
                f"seen={enrich_stats.pending_seen}, items_imported={enrich_stats.items_imported}, "
                f"listings_linked={enrich_stats.listings_linked}, not_found={enrich_stats.not_found}, failed={enrich_stats.failed}"
            )

        if args.skip_price_refresh:
            print("Skipped TLP Auctions price refresh; scoring with cached prices/manual overrides")
        else:
            if args.price_max_age_hours is not None and args.price_max_age_hours < 0:
                parser.error("--price-max-age-hours must be >= 0")
            recent_item_ids = _recent_listing_item_ids(
                db_path,
                args.server,
                args.price_limit,
                max_age_hours=args.price_max_age_hours,
            )
            if recent_item_ids:
                price_stats = import_tlp_prices(
                    db_path,
                    args.server,
                    item_ids=recent_item_ids,
                    fetch_history=not args.no_history,
                    history_days=args.history_days,
                )
                price_window = "catalog" if args.no_history else f"last_{args.history_days}_days"
                print(
                    "Imported TLP Auctions prices: "
                    f"window={price_window}, target_items={len(recent_item_ids)}, "
                    f"history_checked={price_stats.history_items_checked}, "
                    f"history_prices={price_stats.history_prices_upserted}, catalog_prices={price_stats.catalog_prices_upserted}, "
                    f"no_price_data={price_stats.no_price_data}, price_refresh_failed={price_stats.price_refresh_failed}, "
                    f"krono_price_pp={price_stats.krono_price_pp}, "
                    f"krono_listings_converted={price_stats.krono_listings_converted}"
                )
            else:
                freshness = (
                    "no recent priced/resolved listings"
                    if args.price_max_age_hours is None
                    else f"no missing/stale prices older than {args.price_max_age_hours:g}h"
                )
                print(f"Skipped TLP Auctions price refresh; {freshness}")

        score_stats, scores = score_market_listings(
            db_path,
            args.server,
            limit=args.score_limit,
            min_discount_pct=args.min_discount,
            alerts_only=not args.all,
        )
        print(
            "Scored listings: "
            f"seen={score_stats.listings_seen}, scores_written={score_stats.scores_written}, alerts={score_stats.alerts}"
        )
        for score in scores[:50]:
            print(format_deal_score(score))
        if len(scores) > 50:
            print(f"... {len(scores) - 50} more")


def _recent_listing_item_ids(
    db_path: Path,
    server: str,
    limit: int,
    *,
    max_age_hours: float | None = None,
) -> list[int]:
    db_server = server.strip().lower()
    params: list[object] = [db_server]
    freshness_filter = ""
    if max_age_hours is not None:
        freshness_filter = """
              AND (
                    mp.item_id IS NULL
                    OR mp.last_refresh_at IS NULL
                    OR datetime(mp.last_refresh_at) <= datetime('now', ?)
                  )
        """
        params.append(f"-{max_age_hours:g} hours")
    params.append(limit)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT ml.item_id
            FROM market_listings ml
            LEFT JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            WHERE lower(ml.server) = ?
              AND ml.item_id IS NOT NULL
              AND ml.price_pp IS NOT NULL
{freshness_filter}
            GROUP BY ml.item_id
            ORDER BY max(ml.timestamp) DESC, max(ml.listing_id) DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [int(row[0]) for row in rows]


if __name__ == "__main__":
    main()
