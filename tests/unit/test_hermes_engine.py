from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.hermes.hermes import HermesEngine, NewsArticle, Sentiment
from argus_py.models.hermes.rss_reader import CRYPTO_RSS_FEEDS, RSSReader
import argus_py.models.hermes.rss_reader as rss_mod


def test_keyword_fallback_positive_negative():
    engine = HermesEngine()
    articles = [
        NewsArticle("Bitcoin rally as ETF approved", "X", "u", "p"),
        NewsArticle("Exchange hack triggers crypto crash", "Y", "u", "p"),
    ]
    out = engine._analyze_with_keywords(articles)

    assert out[0].sentiment == Sentiment.POSITIVE
    assert out[1].sentiment == Sentiment.NEGATIVE


def test_aggregate_sentiment_score_bounds():
    engine = HermesEngine()
    articles = [
        NewsArticle("a", "s", "u", "p", Sentiment.POSITIVE, 0.8),
        NewsArticle("b", "s", "u", "p", Sentiment.NEGATIVE, 0.4),
    ]
    result = engine._aggregate_sentiment(articles)

    assert -100.0 <= result.sentiment_score <= 100.0
    assert result.articles_analyzed == 2


@pytest.mark.anyio
async def test_analyze_without_ai_uses_keyword(monkeypatch):
    engine = HermesEngine()

    async def fake_fetch(limit):
        return [NewsArticle("BTC surge after adoption", "src", "url", "now")]

    monkeypatch.setattr(engine, "_fetch_news", fake_fetch)

    result = await engine.analyze(symbol="BTC", limit=5)
    assert result.overall_sentiment == Sentiment.POSITIVE


@pytest.mark.anyio
async def test_rss_parsing_and_rate_limit(monkeypatch):
    reader = RSSReader(feeds=CRYPTO_RSS_FEEDS, rate_limit_seconds=0.05)

    async def fake_parse(url):
        return [{"title": f"h-{url}", "link": "u", "published": "p"}]

    sleep_calls = []

    async def fake_sleep(sec):
        sleep_calls.append(sec)

    monkeypatch.setattr(reader, "_parse_feed", fake_parse)
    monkeypatch.setattr(rss_mod.asyncio, "sleep", fake_sleep)

    items = await reader.fetch(limit=10)

    assert len(items) >= 5
    assert len(sleep_calls) == len(CRYPTO_RSS_FEEDS) - 1


@pytest.mark.anyio
async def test_ai_integration_when_client_present(monkeypatch):
    engine = HermesEngine()

    class FakeCompletions:
        def create(self, **kwargs):
            content = '{"headlines":[{"index":0,"sentiment":"POSITIVE","confidence":0.9}]}'
            msg = SimpleNamespace(content=content)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeGroq:
        def __init__(self):
            self.chat = FakeChat()

    engine.groq = FakeGroq()
    articles = [NewsArticle("ETF inflow drives rally", "s", "u", "p")]

    out = await engine._analyze_with_ai(articles)
    assert out[0].sentiment == Sentiment.POSITIVE
    assert out[0].confidence == pytest.approx(0.9)


def test_parse_ai_payload_from_code_block():
    engine = HermesEngine()
    payload = engine._parse_ai_payload(
        "```json\n{\"headlines\":[{\"index\":0,\"sentiment\":\"NEUTRAL\",\"confidence\":0.5}]}\n```"
    )
    assert payload[0]["sentiment"] == "NEUTRAL"


def test_overall_negative_sentiment_detection():
    engine = HermesEngine()
    articles = [
        NewsArticle("hack", "s", "u", "p", Sentiment.NEGATIVE, 0.8),
        NewsArticle("ban", "s", "u", "p", Sentiment.NEGATIVE, 0.7),
    ]
    result = engine._aggregate_sentiment(articles)
    assert result.overall_sentiment == Sentiment.NEGATIVE


@pytest.mark.anyio
async def test_symbol_filtering_keeps_relevant_headlines(monkeypatch):
    engine = HermesEngine()

    async def fake_fetch(limit):
        return [
            NewsArticle("BTC rally continues", "s", "u", "p"),
            NewsArticle("ETH network update", "s", "u", "p"),
        ]

    monkeypatch.setattr(engine, "_fetch_news", fake_fetch)
    result = await engine.analyze(symbol="ETH", limit=10)

    assert result.articles_analyzed == 1
    assert result.top_headlines[0].startswith("ETH")
