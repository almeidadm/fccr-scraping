"""Testes da configuração da sessão HTTP (proxy, User-Agent)."""

from __future__ import annotations

from src import fetch
from src.fetch import USER_AGENT, make_session


def test_session_sets_user_agent():
    session = make_session()
    assert session.headers["User-Agent"] == USER_AGENT
    assert session.proxies == {}


def test_no_proxy_by_default(monkeypatch):
    monkeypatch.delenv(fetch.PROXY_ENV, raising=False)
    assert make_session().proxies == {}


def test_proxy_from_env(monkeypatch):
    monkeypatch.setenv(fetch.PROXY_ENV, "http://user:pass@br-proxy:8080")
    session = make_session()
    assert session.proxies == {
        "http": "http://user:pass@br-proxy:8080",
        "https": "http://user:pass@br-proxy:8080",
    }


def test_proxy_argument_overrides_env(monkeypatch):
    monkeypatch.setenv(fetch.PROXY_ENV, "http://env-proxy:8080")
    session = make_session(proxy_url="http://arg-proxy:9090")
    assert session.proxies["https"] == "http://arg-proxy:9090"


def test_blank_env_means_direct(monkeypatch):
    monkeypatch.setenv(fetch.PROXY_ENV, "   ")
    assert make_session().proxies == {}
