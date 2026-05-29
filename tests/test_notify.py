"""Testes da notificação via Discord webhook."""

from __future__ import annotations

import pytest

from src import notify
from src.notify import notify_new_items


@pytest.fixture
def sample_items() -> list[dict]:
    return [
        {
            "id": "8971",
            "url": "https://fccr.sp.gov.br/fccr/noticias/festidanca?categoria=Dança",
            "title": "36º Festidança",
            "published_at": "2026-05-27",
            "categoria": "Dança",
            "summary": "Apresentação no Teatro Municipal.",
            "first_seen": "2026-05-28T03:00:00+00:00",
        },
        {
            "id": "8966",
            "url": "https://fccr.sp.gov.br/fccr/noticias/coro-sinfonico",
            "title": "Coro Sinfônico",
            "published_at": "2026-05-26",
            "categoria": "Música",
            "summary": None,
            "first_seen": "2026-05-28T03:00:01+00:00",
        },
    ]


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.responses:
            return self.responses.pop(0)
        return FakeResponse(204)


def test_no_webhook_is_noop(sample_items):
    session = FakeSession()
    sent = notify_new_items(sample_items, webhook_url=None, session=session)
    assert sent == 0
    assert session.calls == []


def test_empty_items_is_noop():
    session = FakeSession()
    assert notify_new_items([], webhook_url="https://x/y", session=session) == 0
    assert session.calls == []


def test_sends_one_message_with_embeds(sample_items):
    session = FakeSession()
    sent = notify_new_items(sample_items, webhook_url="https://x/y", session=session)
    assert sent == 2
    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert len(payload["embeds"]) == 2
    assert "2 nova(s)" in payload["content"]


def test_embeds_ordered_oldest_first(sample_items):
    session = FakeSession()
    notify_new_items(sample_items, webhook_url="https://x/y", session=session)
    titles = [e["title"] for e in session.calls[0]["json"]["embeds"]]
    assert titles == ["Coro Sinfônico", "36º Festidança"]


def test_embed_fields(sample_items):
    session = FakeSession()
    notify_new_items(sample_items, webhook_url="https://x/y", session=session)
    embeds = {e["title"]: e for e in session.calls[0]["json"]["embeds"]}
    festi = embeds["36º Festidança"]
    assert festi["url"].endswith("Dança") or "festidanca" in festi["url"]
    assert festi["description"] == "Apresentação no Teatro Municipal."
    assert festi["footer"]["text"] == "Dança"
    assert festi["timestamp"] == "2026-05-27T12:00:00-03:00"
    assert festi["color"] == notify.CATEGORY_COLORS["Dança"]


def test_batches_into_messages_of_ten():
    items = [
        {
            "id": str(i),
            "url": f"https://fccr.sp.gov.br/fccr/noticias/item-{i}",
            "title": f"Item {i}",
            "published_at": f"2026-05-{(i % 28) + 1:02d}",
            "categoria": None,
            "summary": None,
            "first_seen": f"2026-05-28T03:00:{i:02d}+00:00",
        }
        for i in range(12)
    ]
    session = FakeSession()
    sent = notify_new_items(items, webhook_url="https://x/y", session=session)
    assert sent == 12
    assert len(session.calls) == 2
    assert len(session.calls[0]["json"]["embeds"]) == 10
    assert len(session.calls[1]["json"]["embeds"]) == 2
    # Apenas a primeira mensagem carrega o cabeçalho.
    assert "content" in session.calls[0]["json"]
    assert "content" not in session.calls[1]["json"]


def test_truncates_above_max_items():
    items = [
        {
            "id": str(i),
            "url": f"https://fccr.sp.gov.br/fccr/noticias/item-{i}",
            "title": f"Item {i}",
            "published_at": f"2026-05-{(i % 28) + 1:02d}",
            "categoria": None,
            "summary": None,
            "first_seen": f"2026-05-28T03:{i:02d}:00+00:00",
        }
        for i in range(30)
    ]
    session = FakeSession()
    sent = notify_new_items(items, webhook_url="https://x/y", session=session)
    assert sent == notify.MAX_ITEMS
    total_embeds = sum(len(c["json"]["embeds"]) for c in session.calls)
    assert total_embeds == notify.MAX_ITEMS
    assert "30 nova(s)" in session.calls[0]["json"]["content"]
    assert f"{notify.MAX_ITEMS} mais recentes" in session.calls[0]["json"]["content"]


def test_http_error_stops_and_returns_partial(sample_items):
    session = FakeSession(responses=[FakeResponse(400)])
    sent = notify_new_items(sample_items, webhook_url="https://x/y", session=session)
    assert sent == 0
    assert len(session.calls) == 1


def test_rate_limit_retries(monkeypatch, sample_items):
    sleeps: list[float] = []
    monkeypatch.setattr(notify.time, "sleep", lambda s: sleeps.append(s))
    session = FakeSession(responses=[FakeResponse(429, {"retry_after": 1.0}), FakeResponse(204)])
    sent = notify_new_items(sample_items, webhook_url="https://x/y", session=session)
    assert sent == 2
    assert sleeps == [1.0]
    assert len(session.calls) == 2


def test_get_webhook_url_from_env(monkeypatch):
    monkeypatch.setenv(notify.WEBHOOK_ENV, "  https://discord/webhook  ")
    assert notify.get_webhook_url() == "https://discord/webhook"
    monkeypatch.setenv(notify.WEBHOOK_ENV, "")
    assert notify.get_webhook_url() is None
