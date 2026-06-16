from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


AUCTION_LINE_RE = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+"
    r"(?P<seller>[A-Za-z][A-Za-z`'_-]*)\s+auctions,\s+'(?P<message>.*)'\s*$"
)

SALE_PREFIX_RE = re.compile(
    r"^\s*(?:wtsell|wts|wtt/sell|want\s+to\s+sell|selling|sell)\b[:\s,-]*",
    re.IGNORECASE,
)
BUY_PREFIX_RE = re.compile(r"^\s*(?:wtbuy|wtb|buying|want\s+to\s+buy)\b", re.IGNORECASE)
LEADING_NOISE_RE = re.compile(r"^(?:[-,;/|<>~\\=`\[\]{}()\s.]+|(?:ea|each|obo|pst|firm|cheap|stack|for)\b\s*)+", re.IGNORECASE)
TRAILING_NOISE_RE = re.compile(r"(?:[-,;/|<>~\\=`\[\]{}()\s.]+|\b(?:ea|each|obo|pst|firm|wts|stack|for)\b\s*)+$", re.IGNORECASE)
ITEM_SEPARATOR_RE = re.compile(r"\s*(?:<>|\.{2,}|[,;/|<>~\\=]|[\[\]{}()]|\s+-+\s+|\s+I\s+)\s*")
EQ_ITEM_LINK_PREFIX_RE = re.compile(r"(?:Q[0-9A-F]{91}|[0-9A-F]{91})")
ZERO_LINK_TRAILER_RE = re.compile(r"\b0+\s*(?:pp|p|plats?|platinums?)\b$", re.IGNORECASE)
PAREN_PRICE_RE = re.compile(r"\(\s*(\d+(?:[.,]\d+)?\s*(?:kronos?|kr|k|pp|p|plats?|platinums?))\s*\)", re.IGNORECASE)
PAREN_CONTENT_RE = re.compile(r"\([^)]*\)")
BUNDLE_LABEL_RE = re.compile(r"^(?:wis|int|str|sta|agi|dex|cha|resist)\s+sets?\b\s*", re.IGNORECASE)
LEADING_QUANTITY_RE = re.compile(r"^\d+\s*x\s+", re.IGNORECASE)
LEADING_I_SEPARATOR_RE = re.compile(r"^I\s+")
TRAILING_QUANTITY_RE = re.compile(r"\s+x\s*\d+\s*(?:for|each|ea|stack)?$", re.IGNORECASE)
TRAILING_MQ_RE = re.compile(r"\s+MQ$", re.IGNORECASE)
PRICE_RE = re.compile(
    r"(?:(?<![\w.])|(?<=[a-z)'`]))"
    r"(?P<amount>\d+(?:[.,]\d+)?)"
    r"\s*(?P<unit>kronos?|kr|kpp|kp|k|pp|p|plats?|platinums?)?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AuctionMessage:
    timestamp_raw: str
    timestamp: str
    seller: str
    message: str
    raw_line: str


@dataclass(frozen=True)
class ParsedListing:
    timestamp: str
    seller: str
    item_name: str
    price_raw: str | None
    price_amount: float | None
    price_currency: str | None
    price_pp: int | None
    raw_line: str
    confidence: str = "parsed"


def parse_eq_timestamp(timestamp_raw: str) -> str:
    """Convert an EQ log timestamp to a SQLite-friendly ISO-ish string."""
    try:
        return datetime.strptime(timestamp_raw, "%a %b %d %H:%M:%S %Y").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Keep importing even if Daybreak changes/localizes the timestamp format.
        return timestamp_raw


def parse_auction_line(line: str) -> AuctionMessage | None:
    """Return an auction message only for lines shaped like: <name> auctions, '...'"""
    raw_line = line.rstrip("\r\n")
    match = AUCTION_LINE_RE.match(raw_line)
    if not match:
        return None

    timestamp_raw = match.group("timestamp")
    return AuctionMessage(
        timestamp_raw=timestamp_raw,
        timestamp=parse_eq_timestamp(timestamp_raw),
        seller=match.group("seller"),
        message=match.group("message"),
        raw_line=raw_line,
    )


def is_sale_message(message: str) -> bool:
    # In /auction, everything with a price is treated as a sale unless it is
    # explicitly a buy order. WTS/selling are optional noise, not required.
    return not bool(BUY_PREFIX_RE.match(message))


def normalize_item_name(name: str) -> str:
    return " ".join(name.lower().replace("`", "'").split())


def _prepare_message_text(text: str) -> str:
    text = SALE_PREFIX_RE.sub("", text).strip()
    text = EQ_ITEM_LINK_PREFIX_RE.sub("", text)
    # Keep parenthesized prices like "Ink x96 (25pp)", but drop descriptive
    # parentheticals like "(WAR - 16ac/80hp)" before separator parsing.
    text = PAREN_PRICE_RE.sub(r" \1 ", text)
    text = PAREN_CONTENT_RE.sub(" ", text)
    return text


def _clean_item_text(text: str) -> str:
    text = SALE_PREFIX_RE.sub("", text)
    text = EQ_ITEM_LINK_PREFIX_RE.sub("", text)
    text = LEADING_NOISE_RE.sub("", text.strip())
    text = BUNDLE_LABEL_RE.sub("", text.strip())
    text = LEADING_QUANTITY_RE.sub("", text.strip())
    text = LEADING_I_SEPARATOR_RE.sub("", text.strip())
    text = TRAILING_NOISE_RE.sub("", text.strip())
    text = TRAILING_QUANTITY_RE.sub("", text.strip())
    text = TRAILING_MQ_RE.sub("", text.strip())
    text = ZERO_LINK_TRAILER_RE.sub("", text.strip())
    text = TRAILING_NOISE_RE.sub("", text.strip())
    text = re.sub(r"\s+", " ", text).strip()
    if re.fullmatch(r"\d+\s+kronos?", text, re.IGNORECASE) or re.fullmatch(r"kronos?", text, re.IGNORECASE):
        return "Krono"
    return text


def _split_item_text(text: str) -> list[str]:
    text = _prepare_message_text(text)
    return [item for part in ITEM_SEPARATOR_RE.split(text) if (item := _clean_item_text(part))]


def _price_from_match(match: re.Match[str], following_text: str) -> tuple[str, float, str, int | None] | None:
    amount_raw = match.group("amount")
    unit = (match.group("unit") or "").lower()

    try:
        amount = float(amount_raw.replace(",", "."))
    except ValueError:
        return None

    before = match.string[: match.start()].rstrip()
    if before and before[-1].lower() == "x":
        # Quantity suffixes/prefixes: Cobalt Drake Hide x4, Spider Silk x 500.
        return None

    if amount <= 0:
        return None

    if not unit:
        # Bare numbers are common in auction spam ("Item 200 Next Item 400"),
        # but item names can also contain small numbers ("10 Dose Potion").
        # Require a minimum value unless the seller wrote an explicit unit.
        if amount < 20:
            return None
        unit = "pp"

    price_raw = match.group(0).strip()

    if unit in {"k", "kp", "kpp", "pp", "p", "plat", "plats", "platinum", "platinums"}:
        # k/K/kp/kpp mean thousands of platinum: 4k => 4000pp.
        multiplier = 1000 if unit in {"k", "kp", "kpp"} else 1
        price_pp = int(round(amount * multiplier))
        return price_raw, amount, "pp", price_pp

    if unit in {"krono", "kronos", "kr"}:
        return price_raw, amount, "krono", None

    return None


def parse_sale_listings(auction: AuctionMessage) -> list[ParsedListing]:
    """Extract sale listing candidates from one auction message.

    Callers must feed auction lines only. Within auction chat, WTB/buying lines
    are ignored; WTS/selling are optional and stripped when present.
    """
    if not is_sale_message(auction.message):
        return []

    message = _prepare_message_text(auction.message)
    listings: list[ParsedListing] = []
    cursor = 0
    saw_price_candidate = False

    for match in PRICE_RE.finditer(message):
        price = _price_from_match(match, message[match.end() :])
        if price is None:
            amount_text = match.group("amount").replace(",", ".")
            unit_text = (match.group("unit") or "").lower()
            if unit_text and float(amount_text) <= 0:
                for item_name in _split_item_text(message[cursor : match.start()]):
                    listings.append(
                        ParsedListing(
                            timestamp=auction.timestamp,
                            seller=auction.seller,
                            item_name=item_name,
                            price_raw=None,
                            price_amount=None,
                            price_currency=None,
                            price_pp=None,
                            raw_line=auction.raw_line,
                            confidence="no_price",
                        )
                    )
                cursor = match.end()
            continue

        saw_price_candidate = True

        item_names = _split_item_text(message[cursor : match.start()])
        if not item_names:
            continue

        price_raw, price_amount, price_currency, price_pp = price
        for item_name in item_names:
            listings.append(
                ParsedListing(
                    timestamp=auction.timestamp,
                    seller=auction.seller,
                    item_name=item_name,
                    price_raw=price_raw,
                    price_amount=price_amount,
                    price_currency=price_currency,
                    price_pp=price_pp,
                    raw_line=auction.raw_line,
                )
            )
        cursor = match.end()

    if listings:
        return listings

    # No usable price in a sale-looking auction: keep each advertised item with
    # null price so we can still tell the seller and potentially negotiate.
    if not saw_price_candidate:
        for item_name in _split_item_text(auction.message):
            listings.append(
                ParsedListing(
                    timestamp=auction.timestamp,
                    seller=auction.seller,
                    item_name=item_name,
                    price_raw=None,
                    price_amount=None,
                    price_currency=None,
                    price_pp=None,
                    raw_line=auction.raw_line,
                    confidence="no_price",
                )
            )

    return listings


def iter_auction_messages(path: Path) -> Iterator[AuctionMessage]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            auction = parse_auction_line(line)
            if auction is not None:
                yield auction
