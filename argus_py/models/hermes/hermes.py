from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency
    Groq = None

from .rss_reader import CRYPTO_RSS_FEEDS, RSSReader


class Sentiment(Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    published: str
    sentiment: Optional[Sentiment] = None
    confidence: float = 0.0


@dataclass
class HermesResult:
    overall_sentiment: Sentiment
    sentiment_score: float  # -100 to +100
    articles_analyzed: int
    top_headlines: List[str]
    reasoning: str


SENTIMENT_PROMPT = """
Analyze the sentiment of these crypto news headlines.
Return JSON: {{"headlines": [{{"index": 0, "sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "confidence": 0.0-1.0}}]}}

Headlines:
{headlines}
""".strip()


class HermesEngine:
    """Crypto news sentiment analyzer."""

    def __init__(self, groq_api_key: Optional[str] = None):
        self.reader = RSSReader(CRYPTO_RSS_FEEDS)
        if groq_api_key and Groq is not None:
            self.groq = Groq(api_key=groq_api_key)
        else:
            self.groq = None

    async def analyze(self, symbol: str = "BTC", limit: int = 10) -> HermesResult:
        """Fetch and analyze recent crypto news."""
        articles = await self._fetch_news(limit)

        # Keep headlines relevant while not hard-filtering too aggressively.
        symbol_upper = symbol.upper().strip()
        if symbol_upper:
            narrowed = [a for a in articles if symbol_upper in a.title.upper()]
            if narrowed:
                articles = narrowed

        if self.groq:
            try:
                articles = await self._analyze_with_ai(articles)
            except Exception:
                articles = self._analyze_with_keywords(articles)
        else:
            articles = self._analyze_with_keywords(articles)

        return self._aggregate_sentiment(articles)

    async def _fetch_news(self, limit: int) -> List[NewsArticle]:
        """Fetch from RSS feeds."""
        raw_items = await self.reader.fetch(limit)
        return [
            NewsArticle(
                title=item.title,
                source=item.source,
                url=item.url,
                published=item.published,
            )
            for item in raw_items
        ]

    async def _analyze_with_ai(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Use Groq (Llama 3.1) for sentiment."""
        if not articles:
            return articles

        if self.groq is None:
            return self._analyze_with_keywords(articles)

        prompt = self._build_prompt([a.title for a in articles])

        response = await asyncio.to_thread(
            self.groq.chat.completions.create,
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content if response and response.choices else ""
        parsed = self._parse_ai_payload(content)

        for item in parsed:
            idx = item.get("index")
            if not isinstance(idx, int):
                continue
            if idx < 0 or idx >= len(articles):
                continue

            raw_sentiment = str(item.get("sentiment", "NEUTRAL")).upper()
            sentiment = Sentiment.NEUTRAL
            if raw_sentiment == Sentiment.POSITIVE.value:
                sentiment = Sentiment.POSITIVE
            elif raw_sentiment == Sentiment.NEGATIVE.value:
                sentiment = Sentiment.NEGATIVE

            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            articles[idx].sentiment = sentiment
            articles[idx].confidence = confidence

        # Fill any missing labels with neutral.
        for article in articles:
            if article.sentiment is None:
                article.sentiment = Sentiment.NEUTRAL
                article.confidence = 0.4

        return articles

    def _analyze_with_keywords(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Fallback keyword-based sentiment."""
        bullish = [
            "surge",
            "rally",
            "bullish",
            "rise",
            "gain",
            "adoption",
            "etf approved",
            "approval",
            "inflow",
        ]
        bearish = [
            "crash",
            "dump",
            "bearish",
            "fall",
            "hack",
            "ban",
            "regulation",
            "outflow",
            "lawsuit",
        ]

        for article in articles:
            title_lower = article.title.lower()
            bull_count = sum(1 for word in bullish if word in title_lower)
            bear_count = sum(1 for word in bearish if word in title_lower)

            if bull_count > bear_count:
                article.sentiment = Sentiment.POSITIVE
                article.confidence = 0.6
            elif bear_count > bull_count:
                article.sentiment = Sentiment.NEGATIVE
                article.confidence = 0.6
            else:
                article.sentiment = Sentiment.NEUTRAL
                article.confidence = 0.4

        return articles

    def _aggregate_sentiment(self, articles: List[NewsArticle]) -> HermesResult:
        if not articles:
            return HermesResult(
                overall_sentiment=Sentiment.NEUTRAL,
                sentiment_score=0.0,
                articles_analyzed=0,
                top_headlines=[],
                reasoning="No articles available.",
            )

        weighted = 0.0
        total_conf = 0.0
        counts = {Sentiment.POSITIVE: 0, Sentiment.NEGATIVE: 0, Sentiment.NEUTRAL: 0}

        for article in articles:
            sentiment = article.sentiment or Sentiment.NEUTRAL
            confidence = max(0.0, min(1.0, article.confidence))
            counts[sentiment] += 1

            val = 0.0
            if sentiment == Sentiment.POSITIVE:
                val = 1.0
            elif sentiment == Sentiment.NEGATIVE:
                val = -1.0

            weighted += val * confidence
            total_conf += confidence

        normalized = (weighted / total_conf) if total_conf > 0 else 0.0
        sentiment_score = max(-100.0, min(100.0, normalized * 100.0))

        if sentiment_score > 15.0:
            overall = Sentiment.POSITIVE
        elif sentiment_score < -15.0:
            overall = Sentiment.NEGATIVE
        else:
            overall = Sentiment.NEUTRAL

        reasoning = (
            f"POS={counts[Sentiment.POSITIVE]} NEG={counts[Sentiment.NEGATIVE]} "
            f"NEU={counts[Sentiment.NEUTRAL]} score={sentiment_score:.1f}"
        )

        return HermesResult(
            overall_sentiment=overall,
            sentiment_score=sentiment_score,
            articles_analyzed=len(articles),
            top_headlines=[a.title for a in articles[:5]],
            reasoning=reasoning,
        )

    def _build_prompt(self, headlines: List[str]) -> str:
        lines = [f"{idx}. {title}" for idx, title in enumerate(headlines)]
        return SENTIMENT_PROMPT.format(headlines="\n".join(lines))

    def _parse_ai_payload(self, content: str) -> List[dict]:
        if not content:
            return []

        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()

        try:
            payload = json.loads(raw)
            headlines = payload.get("headlines", [])
            if isinstance(headlines, list):
                return headlines
        except Exception:
            return []

        return []
