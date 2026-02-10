from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import List, Optional

import httpx

from .rss_reader import CRYPTO_RSS_FEEDS, RSSReader


@dataclass(frozen=True)
class HermesCArticle:
    title: str
    source: str
    score: float
    confidence: float


@dataclass(frozen=True)
class HermesCResult:
    sentiment_score: float
    label: str
    reasoning: str
    articles: List[HermesCArticle]


class HermesCEngine:
    """Local-first sentiment engine: RSS -> Ollama -> score."""

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434/api/generate",
        ollama_model: str = "llama3.1:8b",
        timeout: float = 8.0,
        feeds: Optional[list[tuple[str, str]]] = None,
    ) -> None:
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.timeout = timeout
        self.reader = RSSReader(feeds if feeds is not None else CRYPTO_RSS_FEEDS)

    async def analyze(self, symbol: str = "BTC", limit: int = 12) -> HermesCResult:
        items = await self.reader.fetch(limit=limit)
        if symbol:
            symbol_u = symbol.upper()
            filt = [x for x in items if symbol_u in x.title.upper()]
            if filt:
                items = filt

        scored: List[HermesCArticle] = []
        for item in items:
            score, confidence = await self._score_headline(item.title)
            scored.append(
                HermesCArticle(
                    title=item.title,
                    source=item.source,
                    score=score,
                    confidence=confidence,
                )
            )

        if not scored:
            return HermesCResult(
                sentiment_score=0.0,
                label="NEUTRAL",
                reasoning="No articles available.",
                articles=[],
            )

        weighted = sum(a.score * a.confidence for a in scored)
        weights = sum(a.confidence for a in scored)
        sentiment = weighted / weights if weights > 0 else 0.0

        if sentiment > 15:
            label = "POSITIVE"
        elif sentiment < -15:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        reasoning = (
            f"HERMES-C label={label} score={sentiment:.1f} "
            f"articles={len(scored)} model={self.ollama_model}"
        )

        return HermesCResult(
            sentiment_score=float(max(-100.0, min(100.0, sentiment))),
            label=label,
            reasoning=reasoning,
            articles=scored,
        )

    async def _score_headline(self, headline: str) -> tuple[float, float]:
        # Local-first: try Ollama, then deterministic keyword fallback.
        try:
            return await self._score_headline_ollama(headline)
        except Exception:
            return self._score_headline_keyword(headline)

    async def _score_headline_ollama(self, headline: str) -> tuple[float, float]:
        prompt = (
            "Return strict JSON only: {\"score\": number(-100..100), "
            "\"confidence\": number(0..1)} for this crypto headline:\n"
            f"{headline}"
        )
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.ollama_url, json=payload)
            resp.raise_for_status()
            body = resp.json()

        raw = str(body.get("response", "")).strip()
        data = json.loads(raw)
        score = float(data["score"])
        confidence = float(data["confidence"])
        return max(-100.0, min(100.0, score)), max(0.0, min(1.0, confidence))

    @staticmethod
    def _score_headline_keyword(headline: str) -> tuple[float, float]:
        text = headline.lower()
        positive = ["surge", "rally", "approval", "inflow", "record", "adoption", "breakout"]
        negative = ["hack", "lawsuit", "ban", "outflow", "liquidation", "dump", "crash"]

        p = sum(1 for x in positive if x in text)
        n = sum(1 for x in negative if x in text)

        raw = (p - n) * 22.0
        score = float(max(-100.0, min(100.0, raw)))
        confidence = 0.45 + min(0.45, 0.15 * (p + n))
        return score, float(min(0.95, confidence))
