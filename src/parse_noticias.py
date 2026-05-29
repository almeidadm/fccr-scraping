"""Parser da listagem paginada de notícias da FCCR.

Cada notícia na listagem aparece como::

    <div class="row margin-top40">
      <div id="imagem_pequena_{ID}" ...>
        <a href="/fccr/noticias/{slug}?categoria={cat}">...</a>
      </div>
      <div class="col-md-9">
        <span id="data_noticia_{ID}">
          <p>26/05/2026</p>
        </span>
        <h4><a href="/fccr/noticias/{slug}?categoria={cat}">{título}</a></h4>
        <p>{resumo curto}</p>
      </div>
    </div>

Algumas chamadas usam ``/fccr/noticias-destaque-03/{slug}`` em vez de ``/fccr/noticias/``.
O ID numérico (``data_noticia_{ID}``) é a chave primária estável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://fccr.sp.gov.br"
DATA_NOTICIA_RE = re.compile(r"^data_noticia_(\d+)$")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


@dataclass(frozen=True)
class NoticiaItem:
    id: str
    url: str
    slug: str
    title: str
    published_at: date | None
    categoria: str | None
    summary: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "slug": self.slug,
            "title": self.title,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "categoria": self.categoria,
            "summary": self.summary,
        }


def parse_listing(html: str) -> list[NoticiaItem]:
    """Extrai todos os itens de notícia de uma página de listagem."""
    soup = BeautifulSoup(html, "lxml")
    items: list[NoticiaItem] = []

    for date_span in soup.find_all("span", id=DATA_NOTICIA_RE):
        match = DATA_NOTICIA_RE.match(date_span.get("id", ""))
        if not match:
            continue
        item_id = match.group(1)

        container = date_span.parent
        if container is None:
            continue

        item = _parse_item(item_id, date_span, container)
        if item is not None:
            items.append(item)

    return items


def _parse_item(item_id: str, date_span: Tag, container: Tag) -> NoticiaItem | None:
    published_at = _parse_date(date_span.get_text(" ", strip=True))

    title_link = None
    h4 = container.find("h4")
    if isinstance(h4, Tag):
        title_link = h4.find("a", href=True)
    if title_link is None:
        title_link = container.find("a", href=re.compile(r"/fccr/noticias"))
    if not isinstance(title_link, Tag):
        return None

    href = title_link.get("href")
    if not isinstance(href, str) or not href:
        return None

    url = urljoin(BASE_URL, href)
    title = title_link.get_text(" ", strip=True)
    slug, categoria = _split_url(url)
    summary = _extract_summary(container, title_link)

    return NoticiaItem(
        id=item_id,
        url=url,
        slug=slug,
        title=title,
        published_at=published_at,
        categoria=categoria,
        summary=summary,
    )


def _parse_date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()
    except ValueError:
        return None


def _split_url(url: str) -> tuple[str, str | None]:
    parsed = urlparse(url)
    slug = parsed.path.rsplit("/", 1)[-1] or parsed.path
    categoria = None
    qs = parse_qs(parsed.query)
    if "categoria" in qs:
        value = qs["categoria"][0].strip()
        categoria = value or None
    return slug, categoria


def _extract_summary(container: Tag, title_link: Tag) -> str | None:
    h4 = title_link.find_parent("h4")
    anchor = h4 if isinstance(h4, Tag) else title_link
    for sibling in anchor.find_next_siblings():
        if isinstance(sibling, Tag) and sibling.name == "p":
            text = sibling.get_text(" ", strip=True)
            if text:
                return text
    return None


def detect_last_page(html: str) -> int | None:
    """Lê o link 'Última página' para descobrir o total de páginas."""
    soup = BeautifulSoup(html, "lxml")
    last = 0
    for a in soup.find_all("a", href=True):
        match = re.search(r"pagina_atual_lista_noticias=(\d+)", a["href"])
        if match:
            n = int(match.group(1))
            if n > last:
                last = n
    return last or None
