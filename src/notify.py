"""Notificação de publicações novas via Discord webhook.

A URL do webhook vem da variável de ambiente ``DISCORD_WEBHOOK_URL`` (no GitHub
Actions, configurada como secret). Sem a variável definida o envio é pulado
silenciosamente, de modo que execuções locais não precisam de configuração.

Cada item vira um *embed* do Discord; uma mensagem comporta até 10 embeds, então
itens novos são enviados em lotes. Falhas de rede são reportadas em stderr mas
nunca propagam: o índice e o feed já foram persistidos antes da notificação.
"""

from __future__ import annotations

import os
import sys
import time

import requests

WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
MAX_EMBEDS_PER_MESSAGE = 10
MAX_ITEMS = 20  # teto de segurança: evita flood se houver um lote grande de novidades
POST_TIMEOUT = 15.0
RATE_LIMIT_MAX_WAIT = 10.0  # espera no máximo isto em um 429 antes de desistir

# Cores (decimal) por categoria, para a barra lateral do embed.
CATEGORY_COLORS = {
    "Dança": 0xE91E63,
    "Música": 0x9B59B6,
    "Teatro": 0xE67E22,
    "Fomento": 0x2ECC71,
}
DEFAULT_COLOR = 0x3498DB


def get_webhook_url() -> str | None:
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    return url or None


def _build_embed(item: dict) -> dict:
    embed: dict = {
        "title": (item.get("title") or "(sem título)")[:256],
        "url": item.get("url") or None,
        "color": CATEGORY_COLORS.get(item.get("categoria") or "", DEFAULT_COLOR),
    }
    summary = item.get("summary")
    if summary:
        embed["description"] = summary[:600]
    categoria = item.get("categoria")
    if categoria:
        embed["footer"] = {"text": categoria}
    published_at = item.get("published_at")
    if published_at:
        # Discord exige ISO 8601; assume meio-dia em horário de Brasília.
        embed["timestamp"] = f"{published_at}T12:00:00-03:00"
    return embed


def _ordered(items: list[dict]) -> list[dict]:
    """Mais antigos primeiro, para que o mais recente apareça por último no chat."""
    return sorted(
        items,
        key=lambda i: (i.get("published_at") or "", i.get("first_seen") or ""),
    )


def _post(url: str, payload: dict, session: requests.Session | None) -> bool:
    poster = session.post if session is not None else requests.post
    try:
        resp = poster(url, json=payload, timeout=POST_TIMEOUT)
    except requests.RequestException as exc:
        print(f"  Discord: falha ao enviar webhook: {exc}", file=sys.stderr)
        return False

    if resp.status_code == 429:
        retry_after = _retry_after(resp)
        if 0 < retry_after <= RATE_LIMIT_MAX_WAIT:
            time.sleep(retry_after)
            return _post(url, payload, session)
        print(f"  Discord: rate-limited (retry_after={retry_after}s), pulando", file=sys.stderr)
        return False

    if resp.status_code >= 300:
        print(f"  Discord: HTTP {resp.status_code} ao enviar webhook", file=sys.stderr)
        return False
    return True


def _retry_after(resp: requests.Response) -> float:
    try:
        return float(resp.json().get("retry_after", 0))
    except (ValueError, AttributeError, requests.JSONDecodeError):
        return 0.0


def notify_new_items(
    items: list[dict],
    webhook_url: str | None = None,
    session: requests.Session | None = None,
) -> int:
    """Envia os itens novos ao Discord em lotes. Retorna quantos foram enviados.

    Sem webhook configurado (ou lista vazia) é um no-op que retorna 0.
    """
    if not items:
        return 0
    url = webhook_url or get_webhook_url()
    if not url:
        return 0

    ordered = _ordered(items)
    truncated = len(ordered) > MAX_ITEMS
    if truncated:
        ordered = ordered[-MAX_ITEMS:]

    sent = 0
    for start in range(0, len(ordered), MAX_EMBEDS_PER_MESSAGE):
        batch = ordered[start : start + MAX_EMBEDS_PER_MESSAGE]
        payload: dict = {"embeds": [_build_embed(i) for i in batch]}
        if start == 0:
            total = len(items)
            header = f"📢 {total} nova(s) publicação(ões) da FCCR"
            if truncated:
                header += f" (mostrando as {MAX_ITEMS} mais recentes)"
            payload["content"] = header
        if not _post(url, payload, session):
            break
        sent += len(batch)

    return sent
