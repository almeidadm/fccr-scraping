"""Entry point: busca a listagem da FCCR, parseia e atualiza o índice persistido.

Uso::

    python -m src.main                  # incremental: página 1, persiste, para quando
                                        # bater em itens já conhecidos
    python -m src.main --no-persist     # incremental sem gravar (debug)
    python -m src.main --page 3         # uma página específica
    python -m src.main --backfill       # todas as páginas (usar uma vez)
    python -m src.main --backfill --max-pages 5  # limita backfill (debug)

A cada persistência o feed RSS em ``public/feed.xml`` é regenerado. No modo
incremental, itens inéditos também são notificados via Discord webhook quando a
variável de ambiente ``DISCORD_WEBHOOK_URL`` está definida (ver ``src.notify``).
Snapshot de seções hierárquicas vem em etapa seguinte.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import requests

from src.feed import write_feed
from src.fetch import fetch_noticias_page, make_session
from src.notify import notify_new_items
from src.parse_noticias import NoticiaItem, detect_last_page, parse_listing
from src.store import load_index, merge_new, save_index

BACKFILL_SLEEP_SECONDS = 1.5


def _format_item(item: NoticiaItem) -> str:
    date_str = item.published_at.isoformat() if item.published_at else "????-??-??"
    cat = f" [{item.categoria}]" if item.categoria else ""
    return f"  {date_str}  #{item.id:>6}{cat}  {item.title}"


def _fetch_and_parse(
    session: requests.Session, page: int, sleep_seconds: float
) -> tuple[list[NoticiaItem], str]:
    result = fetch_noticias_page(session, page=page, sleep_seconds=sleep_seconds)
    if result.status_code != 200:
        print(f"  HTTP {result.status_code} ao buscar página {page}", file=sys.stderr)
        return [], ""
    return parse_listing(result.text), result.text


def run_single(page: int, persist: bool) -> int:
    session = make_session()
    items, _ = _fetch_and_parse(session, page, sleep_seconds=0)
    if not items:
        print(f"Página {page}: nenhum item extraído", file=sys.stderr)
        return 2

    print(f"Página {page}: {len(items)} itens extraídos")
    for item in items[:5]:
        print(_format_item(item))
    if len(items) > 5:
        print(f"  ... (+{len(items) - 5} itens)")

    if persist:
        _persist(items)
    return 0


def run_incremental(persist: bool) -> int:
    """Página 1 → reporta novidades em relação ao índice persistido."""
    session = make_session()
    items, _ = _fetch_and_parse(session, 1, sleep_seconds=0)
    if not items:
        print("Página 1: nenhum item extraído", file=sys.stderr)
        return 2

    print(f"Página 1: {len(items)} itens extraídos")
    if persist:
        new_items = _persist(items)
        for item in new_items[:10]:
            print(_format_item_dict(item))
        if len(new_items) > 10:
            print(f"  ... (+{len(new_items) - 10} novos)")
        sent = notify_new_items(new_items)
        if sent:
            print(f"Discord: {sent} item(ns) notificado(s)")
    return 0


def run_backfill(persist: bool, max_pages: int | None) -> int:
    session = make_session()
    first_items, first_html = _fetch_and_parse(session, 1, sleep_seconds=0)
    if not first_items:
        print("Página 1: nenhum item extraído", file=sys.stderr)
        return 2

    last_page = detect_last_page(first_html) or 1
    if max_pages is not None:
        last_page = min(last_page, max_pages)
    print(f"Backfill: páginas 1..{last_page} (sleep {BACKFILL_SLEEP_SECONDS}s entre requests)")

    initial_size = len(load_index()) if persist else 0
    all_items: list[NoticiaItem] = list(first_items)
    print(f"  página  1: {len(first_items):>3} itens")
    if persist:
        _persist(all_items, verbose=False, regenerate_feed=False)

    for page in range(2, last_page + 1):
        page_items, _ = _fetch_and_parse(session, page, sleep_seconds=BACKFILL_SLEEP_SECONDS)
        print(f"  página {page:>2}: {len(page_items):>3} itens")
        if not page_items:
            print(f"  -> página {page} vazia, encerrando backfill", file=sys.stderr)
            break
        all_items.extend(page_items)
        if persist:
            _persist(all_items, verbose=False, regenerate_feed=False)

    print(f"\nBackfill: {len(all_items)} itens coletados no total")
    if persist:
        # Regenera o feed uma única vez ao final, com todo o índice consolidado.
        _persist(all_items, verbose=False, regenerate_feed=True)
        final_size = len(load_index())
        print(f"  índice: {initial_size} → {final_size} itens (+{final_size - initial_size} novos)")
    return 0


def _persist(
    items: list[NoticiaItem], verbose: bool = True, regenerate_feed: bool = True
) -> list[dict]:
    existing = load_index()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    merged, new_items = merge_new(existing, [i.to_dict() for i in items], now_iso)
    save_index(merged)
    if regenerate_feed:
        write_feed(merged)
    if verbose:
        print(
            f"\nÍndice: {len(merged)} itens conhecidos "
            f"(+{len(new_items)} novos nesta execução)"
        )
    return new_items


def _format_item_dict(item: dict) -> str:
    date_str = item.get("published_at") or "????-??-??"
    cat = f" [{item['categoria']}]" if item.get("categoria") else ""
    return f"  {date_str}  #{item['id']:>6}{cat}  {item['title']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scraper de notícias da FCCR")
    parser.add_argument("--page", type=int, help="Buscar uma página específica")
    parser.add_argument("--backfill", action="store_true", help="Percorre todas as páginas")
    parser.add_argument("--max-pages", type=int, help="Limita backfill (útil para debug)")
    parser.add_argument(
        "--no-persist",
        dest="persist",
        action="store_false",
        help="Não atualiza data/index.json",
    )
    parser.set_defaults(persist=True)
    args = parser.parse_args(argv)

    if args.backfill:
        return run_backfill(persist=args.persist, max_pages=args.max_pages)
    if args.page is not None:
        return run_single(page=args.page, persist=args.persist)
    return run_incremental(persist=args.persist)


if __name__ == "__main__":
    raise SystemExit(main())
