"""Gera um feed RSS 2.0 a partir do índice de publicações.

A FCCR não publica feed nativo — este módulo expõe um que pode ser servido via
GitHub Pages. Ordena por ``published_at`` desc (com ``first_seen`` como
tie-breaker para itens da mesma data) e limita a ``DEFAULT_LIMIT`` itens, o que
basta para qualquer leitor de RSS capturar publicações recentes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
BRT = timezone(timedelta(hours=-3))
CHANNEL_TITLE = "FCCR — Publicações"
CHANNEL_LINK = "https://fccr.sp.gov.br/fccr/portal/"
CHANNEL_DESCRIPTION = (
    "Publicações da Fundação Cultural Cassiano Ricardo (São José dos Campos) — "
    "feed não-oficial gerado por scraping."
)
DEFAULT_SELF_URL = "https://almeidadm.github.io/fccr-scraping/feed.xml"
DEFAULT_LIMIT = 200
FEED_PATH = Path("public/feed.xml")


def build_feed(
    items: dict[str, dict] | list[dict],
    self_url: str = DEFAULT_SELF_URL,
    limit: int = DEFAULT_LIMIT,
    now: datetime | None = None,
) -> bytes:
    """Constrói o feed RSS a partir do índice. Retorna bytes UTF-8 com XML declaration."""
    item_list = list(items.values()) if isinstance(items, dict) else list(items)
    ordered = sorted(item_list, key=_sort_key, reverse=True)[:limit]
    now = now or datetime.now(timezone.utc)

    ET.register_namespace("atom", ATOM_NS)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    _text(channel, "title", CHANNEL_TITLE)
    _text(channel, "link", CHANNEL_LINK)
    _text(channel, "description", CHANNEL_DESCRIPTION)
    _text(channel, "language", "pt-br")
    _text(channel, "lastBuildDate", format_datetime(now))
    _text(channel, "generator", "fccr-scraping")
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {"href": self_url, "rel": "self", "type": "application/rss+xml"},
    )

    for item in ordered:
        _append_item(channel, item)

    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def write_feed(
    items: dict[str, dict] | list[dict],
    path: Path = FEED_PATH,
    **kwargs,
) -> Path:
    payload = build_feed(items, **kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload + b"\n")
    return path


def _append_item(channel: ET.Element, item: dict) -> None:
    url = item.get("url") or ""
    if not url:
        return
    el = ET.SubElement(channel, "item")
    _text(el, "title", item.get("title") or "(sem título)")
    _text(el, "link", url)
    guid = ET.SubElement(el, "guid", {"isPermaLink": "true"})
    guid.text = url
    pub_date = _format_pub_date(item.get("published_at"))
    if pub_date:
        _text(el, "pubDate", pub_date)
    summary = item.get("summary")
    if summary:
        _text(el, "description", summary)
    categoria = item.get("categoria")
    if categoria:
        _text(el, "category", categoria)


def _text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = value
    return el


def _sort_key(item: dict) -> tuple[str, str]:
    return (item.get("published_at") or "", item.get("first_seen") or "")


def _format_pub_date(published_at: str | None) -> str | None:
    if not published_at:
        return None
    try:
        d = date.fromisoformat(published_at)
    except ValueError:
        return None
    dt = datetime.combine(d, time(12, 0), tzinfo=BRT)
    return format_datetime(dt)
