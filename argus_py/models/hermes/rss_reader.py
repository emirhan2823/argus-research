from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Sequence, Tuple

try:
    import feedparser
except ImportError:  # pragma: no cover - optional dependency
    feedparser = None


CRYPTO_RSS_FEEDS: List[Tuple[str, str]] = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
]


@dataclass
class RSSItem:
    title: str
    source: str
    url: str
    published: str


class RSSReader:
    def __init__(
        self,
        feeds: Sequence[Tuple[str, str]] | None = None,
        rate_limit_seconds: float = 0.2,
    ):
        self.feeds = list(feeds) if feeds is not None else list(CRYPTO_RSS_FEEDS)
        self.rate_limit_seconds = rate_limit_seconds

    async def fetch(self, limit: int = 10) -> List[RSSItem]:
        if limit <= 0:
            return []

        if not self.feeds:
            return []

        per_feed = max(1, limit // len(self.feeds))
        items: List[RSSItem] = []

        for idx, (name, url) in enumerate(self.feeds):
            entries = await self._parse_feed(url)
            for entry in entries[:per_feed]:
                title = getattr(entry, "title", None) or entry.get("title", "")
                link = getattr(entry, "link", None) or entry.get("link", "")
                published = getattr(entry, "published", None) or entry.get("published", "")
                if not title:
                    continue
                items.append(
                    RSSItem(
                        title=str(title),
                        source=name,
                        url=str(link),
                        published=str(published),
                    )
                )

            if idx < len(self.feeds) - 1 and self.rate_limit_seconds > 0:
                await asyncio.sleep(self.rate_limit_seconds)

        return items[:limit]

    async def _parse_feed(self, url: str):
        if feedparser is None:
            return []

        parsed = await asyncio.to_thread(feedparser.parse, url)
        return list(getattr(parsed, "entries", []))
