from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ListingSignature:
    listing_id: int
    server: str
    seller: str | None
    item_id: int | None
    price_currency: str | None
    price_amount: float | None
    price_pp: int | None


@dataclass(frozen=True)
class DiscardRule:
    rule_id: int
    enabled: bool
    server: str
    seller: str | None
    item_id: int
    price_currency: str | None
    price_amount: float | None
    price_pp: int | None
    reason_code: str | None
    note: str | None
    source_listing_id: int | None
    created_at: str
    updated_at: str
    disabled_at: str | None


class SimilarRuleError(ValueError):
    """Raised when a listing cannot be represented by a persistent similar rule."""


def fetch_listing_signature(connection: sqlite3.Connection, listing_id: int) -> ListingSignature | None:
    row = connection.execute(
        """
        SELECT listing_id, server, seller, item_id, price_currency, price_amount, price_pp
        FROM market_listings
        WHERE listing_id = ?
        """,
        (listing_id,),
    ).fetchone()
    if row is None:
        return None

    return ListingSignature(
        listing_id=int(row[0]),
        server=str(row[1]),
        seller=_optional_text(row[2]),
        item_id=_optional_int(row[3]),
        price_currency=_normalize_price_currency(row[4]),
        price_amount=_optional_float(row[5]),
        price_pp=_optional_int(row[6]),
    )


def create_or_update_discard_rule_for_listing(
    connection: sqlite3.Connection,
    listing_id: int,
    *,
    reason_code: str | None,
    note: str | None,
) -> DiscardRule:
    signature = _require_rule_signature(connection, listing_id)
    existing_rules = fetch_enabled_discard_rules_for_signature(connection, signature)

    if existing_rules:
        rule_id = existing_rules[0].rule_id
        connection.execute(
            """
            UPDATE market_listing_discard_rules
            SET reason_code = ?,
                note = ?,
                source_listing_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE rule_id = ?
            """,
            (reason_code, note, listing_id, rule_id),
        )
        rule = fetch_discard_rule(connection, rule_id)
        if rule is None:  # Defensive: the row was just updated.
            raise SimilarRuleError("Discard rule was not found after update")
        return rule

    cursor = connection.execute(
        """
        INSERT INTO market_listing_discard_rules (
            enabled, server, seller, item_id, price_currency, price_amount, price_pp,
            reason_code, note, source_listing_id, updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            signature.server,
            signature.seller,
            signature.item_id,
            signature.price_currency,
            signature.price_amount,
            _rule_price_pp(signature),
            reason_code,
            note,
            listing_id,
        ),
    )
    rule = fetch_discard_rule(connection, int(cursor.lastrowid))
    if rule is None:  # Defensive: the row was just inserted.
        raise SimilarRuleError("Discard rule was not found after insert")
    return rule


def fetch_discard_rule(connection: sqlite3.Connection, rule_id: int) -> DiscardRule | None:
    row = connection.execute(
        """
        SELECT
            rule_id,
            enabled,
            server,
            seller,
            item_id,
            price_currency,
            price_amount,
            price_pp,
            reason_code,
            note,
            source_listing_id,
            created_at,
            updated_at,
            disabled_at
        FROM market_listing_discard_rules
        WHERE rule_id = ?
        """,
        (rule_id,),
    ).fetchone()
    return _discard_rule_from_row(row) if row is not None else None


def fetch_enabled_discard_rules_for_signature(
    connection: sqlite3.Connection,
    signature: ListingSignature,
) -> list[DiscardRule]:
    if signature.item_id is None:
        return []

    where_sql, params = _rule_signature_match_clause("r", signature)
    rows = connection.execute(
        f"""
        SELECT
            r.rule_id,
            r.enabled,
            r.server,
            r.seller,
            r.item_id,
            r.price_currency,
            r.price_amount,
            r.price_pp,
            r.reason_code,
            r.note,
            r.source_listing_id,
            r.created_at,
            r.updated_at,
            r.disabled_at
        FROM market_listing_discard_rules r
        WHERE r.enabled = 1
          AND {where_sql}
        ORDER BY r.rule_id DESC
        """,
        params,
    ).fetchall()
    return [_discard_rule_from_row(row) for row in rows]


def apply_discard_rule_to_matching_listings(
    connection: sqlite3.Connection,
    rule: DiscardRule,
    *,
    override_active_reviews: bool,
) -> int:
    listing_ids = fetch_listing_ids_for_rule(
        connection,
        rule,
        include_active_reviews=override_active_reviews,
    )
    _upsert_listing_reviews(
        connection,
        listing_ids,
        status="discarded",
        reason_code=rule.reason_code,
        note=rule.note,
    )
    return len(listing_ids)


def apply_active_discard_rules_to_listing(connection: sqlite3.Connection, listing_id: int) -> int:
    signature = fetch_listing_signature(connection, listing_id)
    if signature is None or signature.item_id is None:
        return 0

    existing_review = connection.execute(
        """
        SELECT status
        FROM market_listing_reviews
        WHERE listing_id = ?
        """,
        (listing_id,),
    ).fetchone()
    if existing_review is not None and str(existing_review[0]) == "active":
        return 0

    rules = fetch_enabled_discard_rules_for_signature(connection, signature)
    if not rules:
        return 0

    rule = rules[0]
    _upsert_listing_reviews(
        connection,
        [listing_id],
        status="discarded",
        reason_code=rule.reason_code,
        note=rule.note,
    )
    return 1


def apply_active_discard_rules(connection: sqlite3.Connection, server: str | None = None) -> int:
    rows = connection.execute(
        """
        SELECT
            rule_id,
            enabled,
            server,
            seller,
            item_id,
            price_currency,
            price_amount,
            price_pp,
            reason_code,
            note,
            source_listing_id,
            created_at,
            updated_at,
            disabled_at
        FROM market_listing_discard_rules
        WHERE enabled = 1
          AND (? IS NULL OR lower(server) = lower(?))
        ORDER BY rule_id
        """,
        (server, server),
    ).fetchall()

    applied = 0
    for row in rows:
        applied += apply_discard_rule_to_matching_listings(
            connection,
            _discard_rule_from_row(row),
            override_active_reviews=False,
        )
    return applied


def fetch_listing_ids_for_rule(
    connection: sqlite3.Connection,
    rule: DiscardRule,
    *,
    include_active_reviews: bool = True,
) -> list[int]:
    where_sql, params = _listing_rule_match_clause("ml", rule)
    active_review_filter = "" if include_active_reviews else "AND COALESCE(mlr.status, '') != 'active'"
    rows = connection.execute(
        f"""
        SELECT ml.listing_id
        FROM market_listings ml
        LEFT JOIN market_listing_reviews mlr
            ON mlr.listing_id = ml.listing_id
        WHERE {where_sql}
          {active_review_filter}
        ORDER BY ml.listing_id
        """,
        params,
    ).fetchall()
    return [int(row[0]) for row in rows]


def fetch_listing_ids_for_signature(connection: sqlite3.Connection, signature: ListingSignature) -> list[int]:
    if signature.item_id is None:
        return []
    where_sql, params = _listing_signature_match_clause("ml", signature)
    rows = connection.execute(
        f"""
        SELECT ml.listing_id
        FROM market_listings ml
        WHERE {where_sql}
        ORDER BY ml.listing_id
        """,
        params,
    ).fetchall()
    return [int(row[0]) for row in rows]


def disable_discard_rules_for_signature(
    connection: sqlite3.Connection,
    signature: ListingSignature,
) -> list[DiscardRule]:
    rules = fetch_enabled_discard_rules_for_signature(connection, signature)
    if not rules:
        return []

    rule_ids = [rule.rule_id for rule in rules]
    placeholders = ", ".join("?" for _ in rule_ids)
    connection.execute(
        f"""
        UPDATE market_listing_discard_rules
        SET enabled = 0,
            disabled_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE rule_id IN ({placeholders})
        """,
        rule_ids,
    )
    return [rule for rule_id in rule_ids if (rule := fetch_discard_rule(connection, rule_id)) is not None]


def restore_listing_ids(connection: sqlite3.Connection, listing_ids: list[int]) -> int:
    _upsert_listing_reviews(
        connection,
        listing_ids,
        status="active",
        reason_code=None,
        note=None,
    )
    return len(listing_ids)


def _upsert_listing_reviews(
    connection: sqlite3.Connection,
    listing_ids: list[int],
    *,
    status: str,
    reason_code: str | None,
    note: str | None,
) -> None:
    if not listing_ids:
        return

    connection.executemany(
        """
        INSERT INTO market_listing_reviews (listing_id, status, reason_code, note, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(listing_id) DO UPDATE SET
            status = excluded.status,
            reason_code = excluded.reason_code,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        [(listing_id, status, reason_code, note) for listing_id in listing_ids],
    )


def _require_rule_signature(connection: sqlite3.Connection, listing_id: int) -> ListingSignature:
    signature = fetch_listing_signature(connection, listing_id)
    if signature is None:
        raise SimilarRuleError("Listing not found")
    if signature.item_id is None:
        raise SimilarRuleError("Similar discard rules require a resolved item_id")
    return signature


def _listing_signature_match_clause(alias: str, signature: ListingSignature) -> tuple[str, list[Any]]:
    params: list[Any] = []
    clauses = [
        _text_match_clause(f"{alias}.server", signature.server, params),
        _text_match_clause(f"{alias}.seller", signature.seller, params),
        f"{alias}.item_id = ?",
    ]
    params.append(signature.item_id)
    clauses.extend(
        [
            _text_match_clause(f"{alias}.price_currency", signature.price_currency, params),
            _numeric_match_clause(f"{alias}.price_amount", signature.price_amount, params),
        ]
    )
    if signature.price_currency != "krono":
        clauses.append(_numeric_match_clause(f"{alias}.price_pp", signature.price_pp, params))
    return " AND ".join(clauses), params


def _rule_signature_match_clause(alias: str, signature: ListingSignature) -> tuple[str, list[Any]]:
    params: list[Any] = []
    clauses = [
        _text_match_clause(f"{alias}.server", signature.server, params),
        _text_match_clause(f"{alias}.seller", signature.seller, params),
        f"{alias}.item_id = ?",
        _text_match_clause(f"{alias}.price_currency", signature.price_currency, params),
        _numeric_match_clause(f"{alias}.price_amount", signature.price_amount, params),
        _numeric_match_clause(f"{alias}.price_pp", _rule_price_pp(signature), params),
    ]
    params.insert(_count_params_before_item_id(clauses), signature.item_id)
    return " AND ".join(clauses), params


def _listing_rule_match_clause(alias: str, rule: DiscardRule) -> tuple[str, list[Any]]:
    params: list[Any] = []
    clauses = [
        _text_match_clause(f"{alias}.server", rule.server, params),
        _text_match_clause(f"{alias}.seller", rule.seller, params),
        f"{alias}.item_id = ?",
        _text_match_clause(f"{alias}.price_currency", rule.price_currency, params),
        _numeric_match_clause(f"{alias}.price_amount", rule.price_amount, params),
        f"(? IS NULL OR {alias}.price_pp = ?)",
    ]
    params.insert(_count_params_before_item_id(clauses), rule.item_id)
    params.extend([rule.price_pp, rule.price_pp])
    return " AND ".join(clauses), params


def _text_match_clause(column: str, value: str | None, params: list[Any]) -> str:
    params.extend([value, value])
    return f"(({column} IS NULL AND ? IS NULL) OR lower({column}) = lower(?))"


def _numeric_match_clause(column: str, value: int | float | None, params: list[Any]) -> str:
    params.extend([value, value])
    return f"(({column} IS NULL AND ? IS NULL) OR {column} = ?)"


def _count_params_before_item_id(clauses: list[str]) -> int:
    # The first two generated clauses are server/seller text matches, each with two parameters.
    return 4


def _rule_price_pp(signature: ListingSignature) -> int | None:
    # Krono listings are matched on the seen Krono amount. The converted PP value
    # depends on the current Krono cache and should not make future same-Krono
    # listings miss an otherwise identical rule.
    if signature.price_currency == "krono":
        return None
    return signature.price_pp


def _discard_rule_from_row(row: sqlite3.Row | tuple[Any, ...]) -> DiscardRule:
    return DiscardRule(
        rule_id=int(row[0]),
        enabled=bool(row[1]),
        server=str(row[2]),
        seller=_optional_text(row[3]),
        item_id=int(row[4]),
        price_currency=_normalize_price_currency(row[5]),
        price_amount=_optional_float(row[6]),
        price_pp=_optional_int(row[7]),
        reason_code=_optional_text(row[8]),
        note=_optional_text(row[9]),
        source_listing_id=_optional_int(row[10]),
        created_at=str(row[11]),
        updated_at=str(row[12]),
        disabled_at=_optional_text(row[13]),
    )


def _normalize_price_currency(value: Any) -> str | None:
    text = _optional_text(value)
    return text.lower() if text is not None else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
