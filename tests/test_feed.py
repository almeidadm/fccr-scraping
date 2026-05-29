"""Testes do gerador de feed RSS."""

from __future__ import annotations

from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import pytest

from src.feed import ATOM_NS, build_feed


@pytest.fixture
def sample_items() -> list[dict]:
    return [
        {
            "id": "8971",
            "url": "https://fccr.sp.gov.br/fccr/noticias-destaque-03/fmc-plantao",
            "slug": "fmc-plantao",
            "title": "FMC oferece Plantão de Dúvidas",
            "published_at": "2026-05-27",
            "categoria": None,
            "summary": "Atendimento será no dia 28/05.",
            "first_seen": "2026-05-28T03:00:00+00:00",
        },
        {
            "id": "8966",
            "url": "https://fccr.sp.gov.br/fccr/noticias/festidanca?categoria=Dança",
            "slug": "festidanca",
            "title": "36º Festidança & Ballet <Paraisópolis>",
            "published_at": "2026-05-26",
            "categoria": "Dança",
            "summary": "Apresentação no Teatro Municipal.",
            "first_seen": "2026-05-28T03:00:01+00:00",
        },
        {
            "id": "8669",
            "url": "https://fccr.sp.gov.br/fccr/noticias/coro-sinfonico",
            "slug": "coro-sinfonico",
            "title": "Coro Sinfônico",
            "published_at": "2026-04-17",
            "categoria": "Música",
            "summary": None,
            "first_seen": "2026-05-28T03:00:02+00:00",
        },
    ]


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)


def test_feed_is_well_formed_xml(sample_items, fixed_now):
    payload = build_feed(sample_items, now=fixed_now)
    root = ET.fromstring(payload)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"


def test_channel_has_required_fields(sample_items, fixed_now):
    root = ET.fromstring(build_feed(sample_items, now=fixed_now))
    channel = root.find("channel")
    assert channel is not None
    for tag in ("title", "link", "description", "language", "lastBuildDate"):
        assert channel.find(tag) is not None, f"channel sem <{tag}>"
    atom_link = channel.find(f"{{{ATOM_NS}}}link")
    assert atom_link is not None
    assert atom_link.attrib["rel"] == "self"


def test_items_ordered_by_published_at_desc(sample_items, fixed_now):
    root = ET.fromstring(build_feed(sample_items, now=fixed_now))
    titles = [it.findtext("title") for it in root.find("channel").findall("item")]
    assert titles == [
        "FMC oferece Plantão de Dúvidas",
        "36º Festidança & Ballet <Paraisópolis>",
        "Coro Sinfônico",
    ]


def test_item_fields_present(sample_items, fixed_now):
    root = ET.fromstring(build_feed(sample_items, now=fixed_now))
    items = root.find("channel").findall("item")
    festidanca = items[1]
    assert festidanca.findtext("link").endswith("festidanca?categoria=Dan%C3%A7a") or "festidanca" in festidanca.findtext("link")
    guid = festidanca.find("guid")
    assert guid is not None and guid.attrib.get("isPermaLink") == "true"
    assert festidanca.findtext("pubDate") == "Tue, 26 May 2026 12:00:00 -0300"
    assert festidanca.findtext("category") == "Dança"
    assert festidanca.findtext("description") == "Apresentação no Teatro Municipal."


def test_special_chars_escaped(sample_items, fixed_now):
    payload = build_feed(sample_items, now=fixed_now).decode("utf-8")
    # Texto bruto < e > não pode aparecer dentro do título
    assert "<title>36º Festidança & Ballet <Paraisópolis></title>" not in payload
    # E deve estar escapado
    assert "&lt;Paraisópolis&gt;" in payload
    assert "&amp;" in payload  # o & do título também é escapado
    # Round-trip: ElementTree decodifica de volta para os caracteres originais
    root = ET.fromstring(payload)
    festidanca = root.find("channel").findall("item")[1]
    assert festidanca.findtext("title") == "36º Festidança & Ballet <Paraisópolis>"


def test_limit_respected(fixed_now):
    items = [
        {
            "id": str(i),
            "url": f"https://fccr.sp.gov.br/fccr/noticias/item-{i}",
            "slug": f"item-{i}",
            "title": f"Item {i}",
            "published_at": f"2026-01-{(i % 28) + 1:02d}",
            "categoria": "Teste",
            "summary": None,
            "first_seen": "2026-05-28T03:00:00+00:00",
        }
        for i in range(500)
    ]
    root = ET.fromstring(build_feed(items, limit=200, now=fixed_now))
    assert len(root.find("channel").findall("item")) == 200


def test_dict_input_accepted(sample_items, fixed_now):
    as_dict = {item["id"]: item for item in sample_items}
    root = ET.fromstring(build_feed(as_dict, now=fixed_now))
    assert len(root.find("channel").findall("item")) == 3


def test_items_without_url_skipped(fixed_now):
    items = [
        {"id": "1", "url": "", "title": "sem URL", "published_at": "2026-05-27"},
        {
            "id": "2",
            "url": "https://fccr.sp.gov.br/fccr/noticias/ok",
            "title": "ok",
            "published_at": "2026-05-27",
        },
    ]
    root = ET.fromstring(build_feed(items, now=fixed_now))
    titles = [it.findtext("title") for it in root.find("channel").findall("item")]
    assert titles == ["ok"]
