from __future__ import annotations

from pathlib import Path
import sys
import asyncio

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.models.hermes.hermes_c import HermesCEngine
from argus_py.models.hermes.rss_reader import RSSItem


class DummyReader:
    async def fetch(self, limit: int = 10):
        return [
            RSSItem(
                title="BTC sees breakout rally after ETF inflow",
                source="Dummy",
                url="https://example.com/1",
                published="2026-01-01",
            ),
            RSSItem(
                title="BTC hit by exchange hack liquidation rumors",
                source="Dummy",
                url="https://example.com/2",
                published="2026-01-01",
            ),
        ][:limit]


def test_hermes_c_fallback_keyword_pipeline() -> None:
    engine = HermesCEngine()
    engine.reader = DummyReader()

    async def fail_ollama(_: str):
        raise RuntimeError("offline")

    engine._score_headline_ollama = fail_ollama  # type: ignore[method-assign]

    result = asyncio.run(engine.analyze(symbol="BTC", limit=4))
    assert result.articles
    assert -100.0 <= result.sentiment_score <= 100.0
    assert result.label in {"POSITIVE", "NEUTRAL", "NEGATIVE"}
