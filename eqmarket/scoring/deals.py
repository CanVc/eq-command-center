from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eqmarket.db import init_db


DEFAULT_PROFILE_NAME = "market_deals"


@dataclass(frozen=True)
class DealScore:
    listing_id: int
    timestamp: str
    server: str
    seller: str | None
    item_id: int
    item_name: str
    price_pp: int
    reference_pp: int | None
    reference_source: str | None
    median_pp: int | None
    p25_pp: int | None
    sample_size: int | None
    confidence: str | None
    discount_pct: float | None
    p25_discount_pct: float | None
    deal_score: float
    alert_level: str
    reason: str
    raw_line: str | None


@dataclass
class ScoreListingsStats:
    listings_seen: int = 0
    scores_written: int = 0
    alerts: int = 0


def score_market_listings(
    db_path: Path,
    server: str,
    *,
    limit: int = 200,
    min_discount_pct: float = 30.0,
    alerts_only: bool = True,
) -> tuple[ScoreListingsStats, list[DealScore]]:
    init_db(db_path)
    db_server = server.lower()
    stats = ScoreListingsStats()
    results: list[DealScore] = []

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        _ensure_default_profile(connection, min_discount_pct)

        rows = connection.execute(
            """
            SELECT
                ml.listing_id,
                ml.timestamp,
                ml.server,
                ml.seller,
                ml.item_id,
                ml.item_name,
                ml.price_pp,
                ml.raw_line,
                mp.median_pp,
                mp.p25_pp,
                mp.sample_size,
                mp.confidence AS market_confidence,
                mp.source AS market_source,
                mpo.price_amount AS override_amount,
                lower(mpo.price_currency) AS override_currency,
                mpo.confidence AS override_confidence,
                kp.price_pp AS krono_price_pp,
                wi.alert_below_pp,
                wi.min_deal_score
            FROM market_listings ml
            LEFT JOIN market_prices mp
                ON mp.item_id = ml.item_id AND lower(mp.server) = lower(ml.server)
            LEFT JOIN market_prices_override mpo
                ON mpo.item_id = ml.item_id AND lower(mpo.server) = lower(ml.server)
            LEFT JOIN krono_prices kp
                ON lower(kp.server) = lower(ml.server)
            LEFT JOIN watchlist_items wi
                ON wi.item_id = ml.item_id AND lower(wi.server) = lower(ml.server) AND wi.enabled = 1
            WHERE lower(ml.server) = ?
              AND ml.item_id IS NOT NULL
              AND ml.price_pp IS NOT NULL
              AND (
                    mp.median_pp IS NOT NULL
                    OR mpo.item_id IS NOT NULL
                    OR wi.watchlist_id IS NOT NULL
                  )
            ORDER BY ml.timestamp DESC, ml.listing_id DESC
            LIMIT ?
            """,
            (db_server, limit),
        ).fetchall()

        for row in rows:
            stats.listings_seen += 1
            score = _score_row(row, min_discount_pct)
            if score is None:
                continue
            _write_score(connection, score)
            stats.scores_written += 1
            if score.alert_level != "none":
                stats.alerts += 1
            if not alerts_only or score.alert_level != "none":
                results.append(score)

    results.sort(key=lambda item: (item.alert_level == "none", -item.deal_score, item.price_pp))
    return stats, results


def format_deal_score(score: DealScore) -> str:
    discount = "n/a" if score.discount_pct is None else f"{score.discount_pct:.0f}%"
    reference = "n/a" if score.reference_pp is None else f"{score.reference_pp:,}pp".replace(",", " ")
    price = f"{score.price_pp:,}pp".replace(",", " ")
    sample = "?" if score.sample_size is None else str(score.sample_size)
    return (
        f"[{score.alert_level.upper()}] {score.item_name} | {price} vs ref {reference} "
        f"({discount} off, n={sample}, {score.confidence or 'unknown'}) | "
        f"seller={score.seller or '?'} | listing_id={score.listing_id} | {score.reason}"
    )


def _score_row(row: sqlite3.Row, min_discount_pct: float) -> DealScore | None:
    price_pp = _as_int(row["price_pp"])
    if price_pp is None or price_pp <= 0:
        return None

    reference_pp, reference_source, confidence = _reference_price(row)
    alert_below_pp = _as_int(row["alert_below_pp"])
    min_deal_score = _as_float(row["min_deal_score"])

    if reference_pp is None and alert_below_pp is None:
        return None

    discount_pct = _discount(price_pp, reference_pp)
    p25_discount_pct = _discount(price_pp, _as_int(row["p25_pp"]))
    deal_score = max(0.0, discount_pct or 0.0)

    alert_level = "none"
    reason_parts: list[str] = []

    if alert_below_pp is not None and price_pp <= alert_below_pp:
        alert_level = "critical"
        reason_parts.append(f"watchlist threshold {alert_below_pp}pp")

    threshold = min_deal_score if min_deal_score is not None else min_discount_pct
    if discount_pct is not None and discount_pct >= threshold:
        if discount_pct >= 70:
            alert_level = _max_alert(alert_level, "critical")
        elif discount_pct >= 50:
            alert_level = _max_alert(alert_level, "high")
        else:
            alert_level = _max_alert(alert_level, "watch")
        reason_parts.append(f"{discount_pct:.1f}% below {reference_source}")

    if p25_discount_pct is not None and p25_discount_pct >= 10:
        alert_level = _max_alert(alert_level, "high")
        reason_parts.append(f"{p25_discount_pct:.1f}% below p25")

    if not reason_parts and reference_pp is not None:
        reason_parts.append(f"below threshold vs {reference_source}")

    return DealScore(
        listing_id=int(row["listing_id"]),
        timestamp=str(row["timestamp"]),
        server=str(row["server"]),
        seller=row["seller"],
        item_id=int(row["item_id"]),
        item_name=str(row["item_name"]),
        price_pp=price_pp,
        reference_pp=reference_pp,
        reference_source=reference_source,
        median_pp=_as_int(row["median_pp"]),
        p25_pp=_as_int(row["p25_pp"]),
        sample_size=_as_int(row["sample_size"]),
        confidence=confidence,
        discount_pct=discount_pct,
        p25_discount_pct=p25_discount_pct,
        deal_score=round(deal_score, 2),
        alert_level=alert_level,
        reason="; ".join(reason_parts),
        raw_line=row["raw_line"],
    )


def _reference_price(row: sqlite3.Row) -> tuple[int | None, str | None, str | None]:
    override_amount = _as_float(row["override_amount"])
    override_currency = row["override_currency"]
    if override_amount is not None and override_amount > 0:
        if override_currency == "pp":
            return round(override_amount), "manual override", row["override_confidence"] or "manual"
        if override_currency == "krono":
            krono_price_pp = _as_int(row["krono_price_pp"])
            if krono_price_pp is not None:
                return round(override_amount * krono_price_pp), "manual override", row["override_confidence"] or "manual"

    median_pp = _as_int(row["median_pp"])
    if median_pp is not None and median_pp > 0:
        return median_pp, row["market_source"] or "market median", row["market_confidence"]

    return None, None, None


def _write_score(connection: sqlite3.Connection, score: DealScore) -> None:
    connection.execute(
        """
        INSERT INTO listing_scores (
            listing_id, profile_name, deal_score, upgrade_score, alert_level, reason, evaluated_at
        ) VALUES (?, ?, ?, NULL, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(listing_id, profile_name) DO UPDATE SET
            deal_score = excluded.deal_score,
            alert_level = excluded.alert_level,
            reason = excluded.reason,
            evaluated_at = CURRENT_TIMESTAMP
        """,
        (score.listing_id, DEFAULT_PROFILE_NAME, score.deal_score, score.alert_level, score.reason),
    )


def _ensure_default_profile(connection: sqlite3.Connection, min_discount_pct: float) -> None:
    config_json = json.dumps({"min_discount_pct": min_discount_pct}, sort_keys=True)
    connection.execute(
        """
        INSERT INTO scoring_profiles (profile_name, profile_type, config_json, enabled, updated_at)
        VALUES (?, 'market_deals', ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(profile_name) DO UPDATE SET
            config_json = excluded.config_json,
            enabled = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (DEFAULT_PROFILE_NAME, config_json),
    )


def _discount(price_pp: int, reference_pp: int | None) -> float | None:
    if reference_pp is None or reference_pp <= 0:
        return None
    return round((reference_pp - price_pp) / reference_pp * 100.0, 2)


def _max_alert(left: str, right: str) -> str:
    order = {"none": 0, "watch": 1, "high": 2, "critical": 3}
    return left if order[left] >= order[right] else right


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
