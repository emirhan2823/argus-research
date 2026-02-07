# Delegated Task Definitions

Bu dosya, diğer agentlara (Codex/Gemini/Sonnet) delegate edilecek task tanımlarını içerir.

---

## P20-005: Telemetry Writer ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create a thread-safe, schema-validated telemetry writer for decisions, trades, and rejects.

### Contract (implement exactly)

**File:** `argus_py/telemetry/writer.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class DecisionRow:
    timestamp: int
    bar_ts: int
    symbol: str
    verdict: str      # GO|WAIT|EXIT|SKIP
    direction: str    # LONG|SHORT|FLAT
    score: float
    adx: float
    exp_move: float
    regime: str       # TREND|CHOP|UNCERTAIN
    position_state: str

@dataclass
class TradeRow:
    timestamp: int
    symbol: str
    event: str        # OPEN|CLOSE|REJECTED
    side: str
    price: float
    quantity: float
    commission: float
    pnl: float
    position_id: str
    reject_reason: str  # Required if event=REJECTED

@dataclass
class RejectRow:
    timestamp: int
    bar_ts: int
    symbol: str
    code: str         # REJECT_* enum
    detail: str
    position_state: str
    risk_level: str

class TelemetryWriter:
    def __init__(self, run_dir: Path) -> None: ...
    def write_decision(self, row: DecisionRow) -> None: ...
    def write_trade(self, row: TradeRow) -> None: ...
    def write_reject(self, row: RejectRow) -> None: ...
    def update_heartbeat(self, state: dict) -> None: ...
    def flush(self) -> None: ...
```

### Invariants
1. Schema validation: `event=REJECTED` requires non-empty `reject_reason`
2. Heartbeat writes must be atomic (write temp, then rename)
3. Thread-safe (use threading.Lock)
4. Create CSVs with headers if don't exist

### Acceptance Criteria
- [x] All writes validate schema
- [x] REJECTED trades without reason raise ValueError
- [x] Heartbeat.json never corrupted on crash
- [x] Thread-safe under concurrent access (8 threads, 50 writes each)

### Verification ✅
```bash
pytest tests/unit/test_telemetry_writer.py -v
# Result: 12 tests passed (383 lines of tests)
```

### Files to Create
1. `argus_py/telemetry/writer.py`
2. `argus_py/telemetry/schemas.py` (optional, for validation)
3. `tests/unit/test_telemetry_writer.py`

---

## P20-009: Audit Pipeline ✅ DONE

**Assign to:** Codex  
**Priority:** P1  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create weekly audit report generator that analyzes rejections and conversion rates.

### Contract (implement exactly)

**File:** `argus_py/reporting/audit_pipeline.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from datetime import date

@dataclass
class RejectionBreakdown:
    total_rejects: int
    by_code: Dict[str, int]       # {code: count}
    by_regime: Dict[str, int]
    top_5_codes: List[tuple]      # [(code, count), ...]

@dataclass
class ConversionMetrics:
    total_signals: int            # verdict=GO count
    total_opens: int              # event=OPEN count
    total_rejects: int            # event=REJECTED count
    conversion_rate: float        # opens / signals
    by_regime: Dict[str, float]   # {regime: rate}

@dataclass
class WeeklyAuditReport:
    week: str                     # e.g., "2026-W06"
    period_start: date
    period_end: date
    rejection_breakdown: RejectionBreakdown
    conversion_metrics: ConversionMetrics
    kill_switch_activations: int
    recommendations: List[str]

class AuditPipeline:
    def __init__(self, run_dir: Path) -> None: ...
    def generate_weekly_report(self, week: str) -> WeeklyAuditReport: ...
    def to_markdown(self, report: WeeklyAuditReport) -> str: ...
    def to_json(self, report: WeeklyAuditReport) -> str: ...
```

### Acceptance Criteria
- [x] Reads decisions.csv, trades.csv, rejects.csv
- [x] Handles missing files gracefully
- [x] Rejection counts sum correctly
- [x] Markdown output is readable

### Verification ✅
```bash
pytest tests/unit/test_audit_pipeline.py -v
# Result: 189 lines of tests passed
```

### Files to Create
1. `argus_py/reporting/audit_pipeline.py`
2. `Scripts/weekly_audit.py` (CLI wrapper)
3. `tests/unit/test_audit_pipeline.py`

---

## P20-INTEG: Kill-Switch Integration ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Integrate the new kill-switch into paper_daemon.py

### Changes Required

**File:** `Scripts/paper_daemon.py`

1. Import kill-switch:
```python
from argus_py.risk.kill_switch import KillSwitch, KillSwitchConfig, check_and_activate
```

2. Initialize in `PaperDaemon.__init__`:
```python
self.kill_switch = KillSwitch(KillSwitchConfig(
    soft_daily_loss_pct=self.cfg["daily_loss_limit_pct"],
    halt_dd_pct=self.cfg["kill_switch_dd_pct"]
))
```

3. Check before execution in `process_bar`:
```python
metrics = {
    'daily_pnl_pct': daily_pnl_pct,
    'total_dd_pct': current_dd_pct,
    'consecutive_losses': self.consecutive_losses,
    'api_errors_1h': self.api_errors_1h
}
level = check_and_activate(self.kill_switch, metrics)

if not self.kill_switch.can_trade():
    self.append_reject(bar, "REJECT_KILL_SWITCH", f"Level: {level.value}")
    return
```

4. Save state on shutdown:
```python
self.kill_switch.save_state(self.run_dir / "kill_switch_state.json")
```

### Acceptance Criteria
- [x] Kill-switch state persists across restarts
- [x] SOFT blocks new trades
- [x] HARD closes all positions (call broker.close_all)
- [x] REJECT_KILL_SWITCH appears in rejects.csv
- [x] Level visible in heartbeat.json

### Verification ✅
```bash
pytest tests/unit/test_paper_daemon_kill_switch_integration.py -v
# Result: 4 integration tests passed (92 lines)
```

---

## P20-ENH1: Orion Engine Enhancement

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Enhance OrionEngine with full technical indicator suite matching Swift implementation.

### Current State
```python
# argus_py/models/orion/orion.py (current)
# Only has: ADX(14), SMA(50)
```

### Target State (from Swift TechnicalAnalysisEngine)

**File:** `argus_py/models/orion/indicators.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd

@dataclass
class IndicatorResult:
    value: float
    signal: str  # BULLISH|BEARISH|NEUTRAL
    strength: float  # 0-100

class IndicatorService:
    """Technical indicators matching Swift TechnicalAnalysisEngine"""
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
        """Relative Strength Index"""
        ...
    
    @staticmethod
    def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
            ) -> Tuple[List[float], List[float], List[float]]:
        """MACD (line, signal, histogram)"""
        ...
    
    @staticmethod
    def bollinger(closes: List[float], period: int = 20, std_mult: float = 2.0
                 ) -> Tuple[List[float], List[float], List[float]]:
        """Bollinger Bands (upper, middle, lower)"""
        ...
    
    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float],
                   k_period: int = 14, d_period: int = 3
                  ) -> Tuple[List[float], List[float]]:
        """Stochastic (%K, %D)"""
        ...
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], 
            period: int = 14) -> List[Optional[float]]:
        """Average True Range"""
        ...
    
    @staticmethod
    def cci(highs: List[float], lows: List[float], closes: List[float],
            period: int = 20) -> List[Optional[float]]:
        """Commodity Channel Index"""
        ...
```

**File:** `argus_py/models/orion/orion.py` (MODIFY)

```python
@dataclass
class OrionScoreComponents:
    structure: float   # 0-35 (price vs MAs, channel position)
    trend: float       # 0-25 (ADX strength, EMA alignment)  
    momentum: float    # 0-25 (RSI, MACD, Stochastic)
    pattern: float     # 0-15 (divergence detection)

class OrionEngine:
    def calculate(self, history: List[Bar]) -> Optional[Vote]:
        # 1. Structure Score (35 max)
        sma50 = IndicatorService.sma(closes, 50)
        sma200 = IndicatorService.sma(closes, 200)
        bb = IndicatorService.bollinger(closes)
        structure_score = self._score_structure(price, sma50, sma200, bb)
        
        # 2. Trend Score (25 max)
        adx = IndicatorService.adx(highs, lows, closes)
        ema12 = IndicatorService.ema(closes, 12)
        ema26 = IndicatorService.ema(closes, 26)
        trend_score = self._score_trend(adx, ema12, ema26, price)
        
        # 3. Momentum Score (25 max)
        rsi = IndicatorService.rsi(closes)
        macd = IndicatorService.macd(closes)
        stoch = IndicatorService.stochastic(highs, lows, closes)
        momentum_score = self._score_momentum(rsi, macd, stoch)
        
        # 4. Pattern Score (15 max)
        pattern_score = self._detect_divergence(closes, rsi)
        
        total = structure_score + trend_score + momentum_score + pattern_score
        return Vote(...)
```

### Scoring Logic (from Swift OrionAnalysisService)

```python
def _score_structure(self, price, sma50, sma200, bb) -> float:
    score = 0
    # Price above both MAs: +15
    if price > sma50[-1] and price > sma200[-1]:
        score += 15
    # Golden Cross (SMA50 > SMA200): +10
    if sma50[-1] > sma200[-1]:
        score += 10
    # Price in lower Bollinger band: +10 (oversold opportunity)
    if price < bb.lower[-1]:
        score += 10
    return min(35, score)

def _score_momentum(self, rsi, macd, stoch) -> float:
    score = 0
    # RSI 30-70 normal, <30 oversold (+10), >70 overbought (-5)
    if rsi[-1] < 30:
        score += 10
    elif rsi[-1] > 70:
        score -= 5
    # MACD histogram positive: +8
    if macd.histogram[-1] > 0:
        score += 8
    # Stochastic %K > %D (bullish crossover): +7
    if stoch.k[-1] > stoch.d[-1]:
        score += 7
    return max(0, min(25, score))
```

### Acceptance Criteria
- [ ] RSI matches Swift output (test with known values)
- [ ] MACD crossover detection works
- [ ] Bollinger squeeze detection works
- [ ] Total score 0-100 with 4 components
- [ ] Backward compatible with existing Vote interface

### Verification
```bash
pytest tests/unit/test_orion_indicators.py -v
# Expected: 15+ indicator tests pass

python -c "
from argus_py.models.orion.orion import OrionEngine
from argus_py.data.loader import load_csv
bars = load_csv('argus_py/data/BTCUSDT.csv')[-200:]
engine = OrionEngine()
vote = engine.calculate(bars)
print(f'Score: {vote.score}, Direction: {vote.direction}')
print(f'Components: structure={vote.metadata.get(\"structure\")}, trend={vote.metadata.get(\"trend\")}')
"
```

### Files to Create/Modify
1. `argus_py/models/orion/indicators.py` (NEW - 200 lines)
2. `argus_py/models/orion/orion.py` (MODIFY - add scoring)
3. `tests/unit/test_orion_indicators.py` (NEW - 150 lines)

---

## P20-ENH2: Aether-C Crypto Macro Engine

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Create crypto-native macro regime detector (Aether-C) using free APIs.

### Data Sources (All Free)

| Source | API | Data |
|--------|-----|------|
| Alternative.me | `https://api.alternative.me/fng/` | Fear & Greed Index |
| CoinGecko | `https://api.coingecko.com/api/v3/global` | Market Cap, BTC Dominance |
| Yahoo Finance | yfinance library | DXY (Dollar Index) |
| Binance | Public API | Funding Rates |

### Contract

**File:** `argus_py/models/aether/__init__.py` (NEW)
**File:** `argus_py/models/aether/aether.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import httpx

class MacroRegime(Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"  
    NEUTRAL = "NEUTRAL"

@dataclass
class AetherComponents:
    fear_greed: float         # 0-100 (from Alternative.me)
    btc_dominance: float      # 0-100 (from CoinGecko)
    total_mcap_change: float  # % change 24h
    dxy_trend: str            # UP|DOWN|FLAT
    funding_rate: float       # Perpetual funding (from Binance)

@dataclass
class AetherResult:
    regime: MacroRegime
    score: float              # 0-100
    components: AetherComponents
    reasoning: str

class AetherEngine:
    """Crypto macro environment detector"""
    
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: Optional[AetherResult] = None
        self._cache_time: float = 0
    
    async def evaluate(self, force_refresh: bool = False) -> AetherResult:
        """Main evaluation - returns cached if fresh"""
        ...
    
    async def _fetch_fear_greed(self) -> int:
        """Fetch from Alternative.me API"""
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.alternative.me/fng/?limit=1")
            data = r.json()
            return int(data["data"][0]["value"])
    
    async def _fetch_global_metrics(self) -> Dict:
        """Fetch from CoinGecko"""
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.coingecko.com/api/v3/global")
            return r.json()["data"]
    
    async def _fetch_dxy(self) -> float:
        """Fetch DXY from Yahoo Finance"""
        import yfinance as yf
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="5d")
        return hist["Close"].iloc[-1]
    
    async def _fetch_funding_rate(self, symbol: str = "BTCUSDT") -> float:
        """Fetch from Binance public API"""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
            )
            data = r.json()
            return float(data[0]["fundingRate"])
```

### Scoring Logic

```python
def _calculate_score(self, components: AetherComponents) -> float:
    score = 50  # Neutral baseline
    
    # Fear & Greed (weight: 30%)
    # <25 = Extreme Fear (+15), >75 = Extreme Greed (-10)
    if components.fear_greed < 25:
        score += 15  # Contrarian - good to buy
    elif components.fear_greed > 75:
        score -= 10  # Overheated
    elif components.fear_greed > 50:
        score += 5   # Mild greed = momentum
    
    # BTC Dominance (weight: 20%)
    # >50% = Risk-off (money flowing to BTC), <40% = Alt season
    if components.btc_dominance > 50:
        score -= 5   # Conservative market
    elif components.btc_dominance < 40:
        score += 10  # Alt season = risk-on
    
    # Total Market Cap Change (weight: 20%)
    if components.total_mcap_change > 3:
        score += 10  # Strong inflow
    elif components.total_mcap_change < -3:
        score -= 10  # Outflow
    
    # DXY Trend (weight: 15%)
    if components.dxy_trend == "DOWN":
        score += 8   # Weak dollar = risk-on
    elif components.dxy_trend == "UP":
        score -= 5   # Strong dollar = headwind
    
    # Funding Rate (weight: 15%)
    if components.funding_rate > 0.001:
        score -= 5   # Overleveraged longs
    elif components.funding_rate < -0.001:
        score += 8   # Shorts paying = bullish
    
    return max(0, min(100, score))

def _determine_regime(self, score: float) -> MacroRegime:
    if score >= 60:
        return MacroRegime.RISK_ON
    elif score <= 40:
        return MacroRegime.RISK_OFF
    return MacroRegime.NEUTRAL
```

### Acceptance Criteria
- [ ] Fear & Greed API works (no API key needed)
- [ ] CoinGecko rate limit handled (10 req/min)
- [ ] DXY fetch works via yfinance
- [ ] Funding rate from Binance public API
- [ ] Cache prevents excessive API calls
- [ ] Returns MacroRegime enum

### Verification
```bash
pytest tests/unit/test_aether_engine.py -v

python -c "
import asyncio
from argus_py.models.aether.aether import AetherEngine

async def test():
    engine = AetherEngine()
    result = await engine.evaluate()
    print(f'Regime: {result.regime.value}')
    print(f'Score: {result.score}')
    print(f'Fear/Greed: {result.components.fear_greed}')
    print(f'BTC Dom: {result.components.btc_dominance}%')

asyncio.run(test())
"
```

### Files to Create
1. `argus_py/models/aether/__init__.py` (NEW)
2. `argus_py/models/aether/aether.py` (NEW - 200 lines)
3. `argus_py/models/aether/data_sources.py` (NEW - 100 lines)
4. `tests/unit/test_aether_engine.py` (NEW - 100 lines)

### Dependencies to Add
```bash
pip install httpx yfinance
```

---

## P20-ENH3: Hermes-C Crypto Sentiment Engine

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Port RSS + AI sentiment analysis for crypto news.

### RSS Sources (Crypto-Focused)

```python
CRYPTO_RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
]
```

### Contract

**File:** `argus_py/models/hermes/__init__.py` (NEW)
**File:** `argus_py/models/hermes/hermes.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import feedparser
from groq import Groq

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
    sentiment_score: float      # -100 to +100
    articles_analyzed: int
    top_headlines: List[str]
    reasoning: str

class HermesEngine:
    """Crypto news sentiment analyzer"""
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq = Groq(api_key=groq_api_key) if groq_api_key else None
    
    async def analyze(self, symbol: str = "BTC", limit: int = 10) -> HermesResult:
        """Fetch and analyze recent crypto news"""
        articles = await self._fetch_news(limit)
        
        if self.groq:
            articles = await self._analyze_with_ai(articles)
        else:
            articles = self._analyze_with_keywords(articles)
        
        return self._aggregate_sentiment(articles)
    
    async def _fetch_news(self, limit: int) -> List[NewsArticle]:
        """Fetch from RSS feeds"""
        articles = []
        for name, url in CRYPTO_RSS_FEEDS:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit // len(CRYPTO_RSS_FEEDS)]:
                articles.append(NewsArticle(
                    title=entry.title,
                    source=name,
                    url=entry.link,
                    published=entry.get("published", "")
                ))
        return articles[:limit]
    
    async def _analyze_with_ai(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Use Groq (Llama 3.1) for sentiment"""
        prompt = self._build_prompt([a.title for a in articles])
        
        response = self.groq.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Parse response and update articles
        ...
        return articles
    
    def _analyze_with_keywords(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Fallback keyword-based sentiment"""
        BULLISH = ["surge", "rally", "bullish", "rise", "gain", "adoption", "etf approved"]
        BEARISH = ["crash", "dump", "bearish", "fall", "hack", "ban", "regulation"]
        
        for article in articles:
            title_lower = article.title.lower()
            bull_count = sum(1 for w in BULLISH if w in title_lower)
            bear_count = sum(1 for w in BEARISH if w in title_lower)
            
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
```

### AI Prompt Template

```python
SENTIMENT_PROMPT = '''
Analyze the sentiment of these crypto news headlines.
Return JSON: {"headlines": [{"index": 0, "sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "confidence": 0.0-1.0}]}

Headlines:
{headlines}
'''
```

### Acceptance Criteria
- [ ] RSS parsing works for all 5 sources
- [ ] Keyword fallback works without API key
- [ ] Groq integration works when key provided
- [ ] Overall sentiment aggregated correctly
- [ ] Rate limiting for RSS fetches

### Verification
```bash
pytest tests/unit/test_hermes_engine.py -v

# Without AI (keyword only)
python -c "
import asyncio
from argus_py.models.hermes.hermes import HermesEngine

async def test():
    engine = HermesEngine()  # No API key
    result = await engine.analyze()
    print(f'Sentiment: {result.overall_sentiment.value}')
    print(f'Score: {result.sentiment_score}')
    print(f'Headlines: {len(result.top_headlines)}')

asyncio.run(test())
"
```

### Files to Create
1. `argus_py/models/hermes/__init__.py` (NEW)
2. `argus_py/models/hermes/hermes.py` (NEW - 150 lines)
3. `argus_py/models/hermes/rss_reader.py` (NEW - 50 lines)
4. `tests/unit/test_hermes_engine.py` (NEW - 80 lines)

### Dependencies
```bash
pip install feedparser groq
```

---

## Agent Work Log Template

Her agent tamamladığında bu formatı kullanmalı:

```markdown
# Agent Work Log

## Metadata
- **Agent:** [Codex/Gemini/Sonnet]
- **Task ID:** [P20-XXX]
- **Date:** YYYY-MM-DD HH:MM UTC
- **Duration:** Xh Xm

## Files Changed
| File | Action | Lines |
|------|--------|-------|
| path/file.py | CREATE | 150 |

## Verification
\`\`\`bash
[commands run + output]
\`\`\`

## Risks / Follow-ups
- [Any issues encountered]

---
**Agent Signature:** [Agent] @ [Timestamp]
```
