from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


LUCY_BASE_URL = "https://lucy.allakhazam.com"
PARSER_VERSION = "lucy_raw_v1"


@dataclass(frozen=True)
class LucyItem:
    item_id: int
    fields: dict[str, str]


@dataclass(frozen=True)
class LucySpell:
    spell_id: int
    fields: dict[str, str]


class LucyLookupError(RuntimeError):
    pass


class LucyNotFoundError(LucyLookupError):
    pass


class LucyClient:
    def __init__(self, source: str = "Live", timeout_seconds: int = 30) -> None:
        self.source = source
        self.timeout_seconds = timeout_seconds
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))

    def lookup_item_id_by_exact_name(self, item_name: str) -> int | None:
        html_text = self._get(
            "/itemlist.html",
            {"searchtext": item_name, "source": self.source},
        )

        title_match = re.search(r"<title>\s*Item Details for\s+(.*?)\s*</title>", html_text, re.IGNORECASE | re.DOTALL)
        ids = [int(value) for value in re.findall(r"item(?:raw)?\.html\?id=(\d+)", html_text, re.IGNORECASE)]
        if title_match and ids:
            title_name = _normalize_space(_strip_tags(title_match.group(1)))
            if _normalize_name(title_name) == _normalize_name(item_name):
                return ids[0]

        # If Lucy returns a result list, take only an exact name match. This avoids
        # importing a similarly named item by accident.
        for item_id, linked_name in re.findall(
            r"item\.html\?id=(\d+)[^>]*>(.*?)</a>",
            html_text,
            re.IGNORECASE | re.DOTALL,
        ):
            if _normalize_name(_strip_tags(linked_name)) == _normalize_name(item_name):
                return int(item_id)

        return None

    def fetch_item_raw(self, item_id: int) -> LucyItem:
        html_text = self._get("/itemraw.html", {"id": str(item_id), "source": self.source})
        fields = _parse_lucy_raw_fields(html_text)
        if not fields:
            raise LucyNotFoundError(f"Lucy item {item_id} returned no raw fields")
        fields.setdefault("id", str(item_id))
        return LucyItem(item_id=item_id, fields=fields)

    def fetch_spell_raw(self, spell_id: int) -> LucySpell:
        html_text = self._get("/spellraw.html", {"id": str(spell_id), "source": self.source})
        fields = _parse_lucy_raw_fields(html_text)
        if not fields:
            raise LucyNotFoundError(f"Lucy spell {spell_id} returned no raw fields")
        fields.setdefault("id", str(spell_id))
        return LucySpell(spell_id=spell_id, fields=fields)

    def _get(self, path: str, params: dict[str, str]) -> str:
        params = {**params, "cachebust": str(int(time.time()))}
        url = f"{LUCY_BASE_URL}{path}?{urlencode(params)}"
        text = self._request(url)
        if "setcookie=1" in text or "No cookies for Lucy" in text:
            separator = "&" if "?" in url else "?"
            text = self._request(f"{url}{separator}setcookie=1")
        return text

    def _request(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "eq-command-center/0.1",
                "Cache-Control": "no-cache",
            },
        )
        with self.opener.open(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")


def _parse_lucy_raw_fields(html_text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    cell_re = re.compile(
        r'<td[^>]*class="spelllabel"[^>]*>\s*(?P<key>.*?)\s*</td>\s*'
        r'<td[^>]*>\s*(?P<value>.*?)\s*</td>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in cell_re.finditer(html_text):
        key = _normalize_space(_strip_tags(match.group("key"))).lower()
        value = _normalize_space(_strip_tags(match.group("value")))
        if key:
            pairs[key] = value
    return pairs


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_name(value: str) -> str:
    return _normalize_space(value).lower().replace("`", "'")


def raw_payload(fields: dict[str, str]) -> str:
    return json.dumps(fields, ensure_ascii=False, sort_keys=True)


def as_int(fields: dict[str, str], key: str) -> int | None:
    value = fields.get(key)
    if value in {None, "", "NULL"}:
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except ValueError:
        return None


def as_float(fields: dict[str, str], key: str) -> float | None:
    value = fields.get(key)
    if value in {None, "", "NULL"}:
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None
