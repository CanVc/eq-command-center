from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Lucy exposes item slots as an EQ inventory bitmask. Duplicate wearable slots
# (ear, wrist, finger) have one bit per physical slot but share one compatibility
# label in API payloads.
LUCY_SLOT_BITS: tuple[tuple[int, str], ...] = (
    (1, "CHARM"),
    (2, "EAR"),
    (4, "HEAD"),
    (8, "FACE"),
    (16, "EAR"),
    (32, "NECK"),
    (64, "SHOULDERS"),
    (128, "ARMS"),
    (256, "BACK"),
    (512, "WRIST"),
    (1024, "WRIST"),
    (2048, "RANGE"),
    (4096, "HANDS"),
    (8192, "PRIMARY"),
    (16384, "SECONDARY"),
    (32768, "FINGER"),
    (65536, "FINGER"),
    (131072, "CHEST"),
    (262144, "LEGS"),
    (524288, "FEET"),
    (1048576, "WAIST"),
    (2097152, "POWER_SOURCE"),
    (4194304, "AMMO"),
)

KNOWN_LUCY_SLOT_MASK = sum(bit for bit, _label in LUCY_SLOT_BITS)
KNOWN_LUCY_SLOT_LABELS = tuple(dict.fromkeys(label for _bit, label in LUCY_SLOT_BITS))
KNOWN_LUCY_SLOT_LABEL_SET = set(KNOWN_LUCY_SLOT_LABELS)


@dataclass(frozen=True)
class DecodedLucySlotMask:
    slot_mask: int | None
    slot_labels: tuple[str, ...]
    slot_display: str | None
    unknown_bits: int


def decode_lucy_slot_mask(value: Any) -> DecodedLucySlotMask:
    """Decode a Lucy item slot mask into unique display labels.

    The database column is still named ``items.slot`` for compatibility, but
    Lucy raw imports store the numeric ``slots`` value there. Non-numeric legacy
    values are tolerated so older local databases and fixtures keep returning a
    readable ``slot`` field instead of failing API requests.
    """

    slot_mask = _coerce_non_negative_int(value)
    if slot_mask is None:
        return _decode_legacy_slot_text(value)

    labels: list[str] = []
    seen_labels: set[str] = set()
    for bit, label in LUCY_SLOT_BITS:
        if slot_mask & bit and label not in seen_labels:
            labels.append(label)
            seen_labels.add(label)

    unknown_bits = slot_mask & ~KNOWN_LUCY_SLOT_MASK
    for unknown_bit in _iter_set_bits(unknown_bits):
        labels.append(f"UNKNOWN({unknown_bit})")

    return DecodedLucySlotMask(
        slot_mask=slot_mask,
        slot_labels=tuple(labels),
        slot_display=" / ".join(labels) if labels else None,
        unknown_bits=unknown_bits,
    )


def _coerce_non_negative_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value.is_integer() and value >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(text, 10)
    except ValueError:
        try:
            parsed_float = float(text)
        except ValueError:
            return None
        if not parsed_float.is_integer():
            return None
        parsed = int(parsed_float)
    return parsed if parsed >= 0 else None


def _decode_legacy_slot_text(value: Any) -> DecodedLucySlotMask:
    text = "" if value is None else str(value).strip()
    if not text:
        return DecodedLucySlotMask(slot_mask=None, slot_labels=(), slot_display=None, unknown_bits=0)

    labels: list[str] = []
    for token in re.split(r"\s*(?:/|,|\+)\s*", text):
        normalized_label = _normalize_legacy_label(token)
        if normalized_label and normalized_label not in labels:
            labels.append(normalized_label)

    if not labels:
        labels = [text]

    return DecodedLucySlotMask(
        slot_mask=None,
        slot_labels=tuple(labels),
        slot_display=" / ".join(labels),
        unknown_bits=0,
    )


def _normalize_legacy_label(value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return None

    normalized = re.sub(r"[\s-]+", "_", stripped.upper())
    if normalized in KNOWN_LUCY_SLOT_LABEL_SET or normalized.startswith("UNKNOWN("):
        return normalized
    return stripped


def _iter_set_bits(mask: int) -> tuple[int, ...]:
    bits: list[int] = []
    remaining = mask
    bit = 1
    while remaining:
        if remaining & 1:
            bits.append(bit)
        remaining >>= 1
        bit <<= 1
    return tuple(bits)
