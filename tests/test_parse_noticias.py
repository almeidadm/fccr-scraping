"""Testes do parser de notícias sobre fixture HTML congelada.

A fixture é uma cópia real da página 1 da listagem em 2026-05-28. Se o template
mudar, estes testes quebram em CI — antes do scraper falhar silencioso em produção.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.parse_noticias import detect_last_page, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "noticias_page_1.html"


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def items(html: str):
    return parse_listing(html)


def test_extracts_expected_item_count(items):
    # A página da FCCR mostra 50 itens por página de listagem.
    assert len(items) == 50


def test_all_items_have_required_fields(items):
    for item in items:
        assert item.id.isdigit(), f"id deve ser numérico: {item.id}"
        assert item.url.startswith("https://fccr.sp.gov.br/fccr/"), item.url
        assert item.slug, f"slug vazio para {item.id}"
        assert item.title, f"título vazio para {item.id}"


def test_ids_are_unique(items):
    ids = [item.id for item in items]
    assert len(ids) == len(set(ids))


def test_dates_parse_as_iso(items):
    for item in items:
        assert isinstance(item.published_at, date), (
            f"data não parseada para {item.id} / {item.title}"
        )


def test_known_item_present(items):
    by_slug = {item.slug: item for item in items}
    target = by_slug.get("36-festidanca-ballet-paraisopolis-apresenta-tres-obras-na-noite-desta-quinta")
    assert target is not None, "Item conhecido da fixture sumiu"
    assert target.published_at == date(2026, 5, 26)
    assert target.categoria == "Dança"
    assert target.title.startswith("36º Festidança")
    assert "Teatro Municipal" in (target.summary or "")


def test_categories_recognized(items):
    categorias = {item.categoria for item in items if item.categoria}
    # Garantia frouxa: pelo menos algumas das categorias conhecidas aparecem.
    assert categorias & {"Dança", "Música", "Teatro", "Fomento"}


def test_detect_last_page(html):
    assert detect_last_page(html) == 50
