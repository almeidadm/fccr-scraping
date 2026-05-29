"""HTTP fetch com retry, timeout e User-Agent identificável."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "fccr-scraping/0.1 "
    "(+https://github.com/AlmeidaDM/fccr-scraping; contato: roda.diegoam@gmail.com)"
)
DEFAULT_TIMEOUT = 20.0
NOTICIAS_LISTING_URL = "https://fccr.sp.gov.br/fccr/home/noticias"
NOTICIAS_LISTING_SECAO_ID = 75


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
    retry = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get(session: requests.Session, url: str, params: dict | None = None) -> FetchResult:
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    return FetchResult(url=response.url, status_code=response.status_code, text=response.text)


def fetch_noticias_page(
    session: requests.Session, page: int, sleep_seconds: float = 1.0
) -> FetchResult:
    """Busca uma página da listagem de notícias.

    O servidor da FCCR é catch-all: nunca confiar em status_code sozinho.
    O parser valida o conteúdo.
    """
    result = get(
        session,
        NOTICIAS_LISTING_URL,
        params={
            "secao_id": NOTICIAS_LISTING_SECAO_ID,
            "pagina_atual_lista_noticias": page,
        },
    )
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return result
