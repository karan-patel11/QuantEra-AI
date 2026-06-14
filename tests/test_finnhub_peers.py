from __future__ import annotations

import json

from quantera.news import finnhub_source


class MockResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_get_peers_fetches_cleans_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(finnhub_source.config, "CACHE_DIR", tmp_path)
    monkeypatch.setenv(finnhub_source.config.NEWS_API_KEY_ENV, "token")
    calls = {"urlopen": 0}

    def fake_urlopen(request, timeout):
        calls["urlopen"] += 1
        return MockResponse(["AAPL", "MSFT", "msft", "GOOG", "BRK.B", ""])

    monkeypatch.setattr(finnhub_source, "urlopen", fake_urlopen)

    first = finnhub_source.get_peers("aapl")
    second = finnhub_source.get_peers("AAPL")

    assert first == ["MSFT", "GOOG"]
    assert second == ["MSFT", "GOOG"]
    assert calls["urlopen"] == 1


def test_get_peers_returns_empty_when_key_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(finnhub_source.config, "CACHE_DIR", tmp_path)
    monkeypatch.delenv(finnhub_source.config.NEWS_API_KEY_ENV, raising=False)

    assert finnhub_source.get_peers("AAPL") == []
