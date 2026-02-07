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

## P20-ENH4: Council Weighted Voting System

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 5 hours

### Objective
Implement weighted voting aggregator that combines all engine outputs (matching Swift ArgusGrandCouncil).

### Current State
```python
# argus_py/council/aggregator.py (current)
# Only aggregates Aegean + Orion with fixed weights
```

### Target State

**File:** `argus_py/council/council.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from argus_py.models.orion.orion import OrionVote
from argus_py.models.aether.aether import AetherResult
from argus_py.models.hermes.hermes import HermesResult

class CouncilAction(Enum):
    AGGRESSIVE_BUY = "AGGRESSIVE_BUY"  # 80%+ allocation
    ACCUMULATE = "ACCUMULATE"          # 50% allocation
    HOLD = "HOLD"
    TRIM = "TRIM"                      # Sell 50%
    LIQUIDATE = "LIQUIDATE"            # Sell 100%

class SignalStrength(Enum):
    STRONG = "STRONG"
    NORMAL = "NORMAL"
    WEAK = "WEAK"  
    VETOED = "VETOED"

@dataclass
class ModuleVote:
    module: str           # "orion", "aether", "hermes", "phoenix"
    score: float          # 0-100
    direction: str        # LONG|SHORT|FLAT
    confidence: float     # 0-1
    reasons: List[str]

@dataclass
class CouncilDecision:
    action: CouncilAction
    strength: SignalStrength
    confidence: float             # 0-100
    reasoning: str
    votes: List[ModuleVote]
    weights_used: Dict[str, float]

class CouncilWeights:
    """Dynamic weights based on regime"""
    
    TREND_WEIGHTS = {
        "orion": 0.35,     # Technical dominates
        "aether": 0.20,
        "hermes": 0.15,
        "phoenix": 0.20,
        "aegean": 0.10
    }
    
    CHOP_WEIGHTS = {
        "orion": 0.15,     # Reduce technical
        "aether": 0.30,    # Macro more important
        "hermes": 0.20,
        "phoenix": 0.25,   # Reversion works in chop
        "aegean": 0.10
    }
    
    RISK_OFF_WEIGHTS = {
        "orion": 0.10,
        "aether": 0.40,    # Macro dominates
        "hermes": 0.30,    # News critical
        "phoenix": 0.10,
        "aegean": 0.10
    }
    
    @classmethod
    def get_for_regime(cls, regime: str) -> Dict[str, float]:
        if regime == "TREND":
            return cls.TREND_WEIGHTS
        elif regime == "CHOP":
            return cls.CHOP_WEIGHTS
        elif regime == "RISK_OFF":
            return cls.RISK_OFF_WEIGHTS
        return cls.TREND_WEIGHTS  # Default


class GrandCouncil:
    """Aggregates all engine votes into final decision"""
    
    def convene(
        self,
        orion_vote: Optional[OrionVote],
        aether_result: Optional[AetherResult],
        hermes_result: Optional[HermesResult],
        phoenix_score: Optional[float],
        aegean_vote: Optional[ModuleVote],
        regime: str = "TREND"
    ) -> CouncilDecision:
        
        # 1. Get regime-aware weights
        weights = CouncilWeights.get_for_regime(regime)
        
        # 2. Collect votes
        votes = self._collect_votes(orion_vote, aether_result, hermes_result, 
                                     phoenix_score, aegean_vote)
        
        # 3. Calculate weighted score
        weighted_score = self._calculate_weighted_score(votes, weights)
        
        # 4. Determine action
        action = self._determine_action(weighted_score, votes)
        
        # 5. Check for vetoes
        strength = self._check_vetoes(votes, action)
        
        return CouncilDecision(
            action=action,
            strength=strength,
            confidence=weighted_score,
            reasoning=self._generate_reasoning(votes, action),
            votes=votes,
            weights_used=weights
        )
    
    def _calculate_weighted_score(self, votes: List[ModuleVote], 
                                   weights: Dict[str, float]) -> float:
        total_weight = 0
        weighted_sum = 0
        
        for vote in votes:
            if vote.module in weights:
                w = weights[vote.module]
                weighted_sum += vote.score * w
                total_weight += w
        
        return weighted_sum / total_weight if total_weight > 0 else 50.0
    
    def _determine_action(self, score: float, votes: List[ModuleVote]) -> CouncilAction:
        # Count directions
        long_count = sum(1 for v in votes if v.direction == "LONG")
        short_count = sum(1 for v in votes if v.direction == "SHORT")
        
        if score >= 75 and long_count >= 3:
            return CouncilAction.AGGRESSIVE_BUY
        elif score >= 60 and long_count >= 2:
            return CouncilAction.ACCUMULATE
        elif score <= 35 and short_count >= 3:
            return CouncilAction.LIQUIDATE
        elif score <= 45 and short_count >= 2:
            return CouncilAction.TRIM
        return CouncilAction.HOLD
    
    def _check_vetoes(self, votes: List[ModuleVote], action: CouncilAction) -> SignalStrength:
        # Aether RISK_OFF vetoes buys
        aether = next((v for v in votes if v.module == "aether"), None)
        if aether and aether.score < 30 and action in [CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE]:
            return SignalStrength.VETOED
        
        # Hermes extreme negative vetoes buys
        hermes = next((v for v in votes if v.module == "hermes"), None)
        if hermes and hermes.score < 20 and action in [CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE]:
            return SignalStrength.VETOED
        
        # Strong consensus
        if all(v.confidence > 0.7 for v in votes if v.confidence > 0):
            return SignalStrength.STRONG
        
        return SignalStrength.NORMAL
```

### Acceptance Criteria
- [ ] Regime-based weight selection works
- [ ] Weighted score calculation correct
- [ ] Veto logic blocks inappropriate actions
- [ ] All module votes collected correctly
- [ ] Output matches CouncilDecision schema

### Verification
```bash
pytest tests/unit/test_council.py -v

python -c "
from argus_py.council.council import GrandCouncil, ModuleVote

council = GrandCouncil()
decision = council.convene(
    orion_vote=ModuleVote('orion', 75, 'LONG', 0.8, ['Trend up']),
    aether_result=None,
    hermes_result=None,
    phoenix_score=65,
    aegean_vote=ModuleVote('aegean', 70, 'LONG', 0.7, ['Momentum']),
    regime='TREND'
)
print(f'Action: {decision.action.value}')
print(f'Strength: {decision.strength.value}')
print(f'Confidence: {decision.confidence:.1f}')
"
```

### Files to Create
1. `argus_py/council/council.py` (NEW - 250 lines)
2. `argus_py/council/weights.py` (NEW - 50 lines)
3. `tests/unit/test_council.py` (NEW - 100 lines)

---

## P20-ENH5: Chiron Regime Detection Engine

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Implement regime detector that adjusts engine weights dynamically (matching Swift ChironRegimeEngine).

### Contract

**File:** `argus_py/models/chiron/__init__.py` (NEW)
**File:** `argus_py/models/chiron/chiron.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
import json
from pathlib import Path

class MarketRegime(Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    RISK_OFF = "RISK_OFF"
    NEWS_SHOCK = "NEWS_SHOCK"
    NEUTRAL = "NEUTRAL"

@dataclass
class RegimeContext:
    orion_score: Optional[float]
    aether_score: Optional[float]
    hermes_score: Optional[float]
    adx: float
    chop_index: float        # Choppiness Index
    recent_volatility: float  # ATR / Price %

@dataclass
class ChironResult:
    regime: MarketRegime
    core_weights: Dict[str, float]    # Long-term components
    pulse_weights: Dict[str, float]   # Short-term components
    explanation: str
    confidence: float

class ChironRegimeEngine:
    """Detects market regime and adjusts weights"""
    
    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path
        self._last_regime: MarketRegime = MarketRegime.NEUTRAL
    
    def evaluate(self, context: RegimeContext) -> ChironResult:
        regime = self._detect_regime(context)
        core, pulse = self._get_base_weights(regime)
        
        # Adjust for missing data
        core = self._adjust_for_missing(core, context)
        pulse = self._adjust_for_missing(pulse, context)
        
        return ChironResult(
            regime=regime,
            core_weights=core,
            pulse_weights=pulse,
            explanation=self._explain(regime, context),
            confidence=self._calculate_confidence(context)
        )
    
    def _detect_regime(self, ctx: RegimeContext) -> MarketRegime:
        aether = ctx.aether_score or 50
        orion = ctx.orion_score or 50
        hermes = ctx.hermes_score or 50
        
        # 1. Check for News Shock
        if hermes < 20 or hermes > 85:
            return MarketRegime.NEWS_SHOCK
        
        # 2. Check for Risk-Off
        if aether < 35:
            return MarketRegime.RISK_OFF
        
        # 3. Check for Trend
        if ctx.adx >= 25 and ctx.chop_index < 45:
            return MarketRegime.TREND
        
        # 4. Check for Chop
        if ctx.chop_index > 60 or (ctx.adx < 20 and 40 < orion < 60):
            return MarketRegime.CHOP
        
        return MarketRegime.NEUTRAL
    
    def _get_base_weights(self, regime: MarketRegime) -> tuple:
        WEIGHT_TABLE = {
            MarketRegime.TREND: (
                {"orion": 0.35, "aether": 0.20, "hermes": 0.15, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.40, "phoenix": 0.30, "hermes": 0.15, "aegean": 0.15}
            ),
            MarketRegime.CHOP: (
                {"orion": 0.15, "aether": 0.30, "hermes": 0.20, "phoenix": 0.25, "aegean": 0.10},
                {"phoenix": 0.40, "hermes": 0.25, "orion": 0.20, "aegean": 0.15}
            ),
            MarketRegime.RISK_OFF: (
                {"aether": 0.40, "hermes": 0.30, "orion": 0.10, "phoenix": 0.10, "aegean": 0.10},
                {"hermes": 0.50, "aether": 0.30, "phoenix": 0.10, "orion": 0.10}
            ),
            MarketRegime.NEWS_SHOCK: (
                {"hermes": 0.50, "aether": 0.25, "orion": 0.10, "phoenix": 0.05, "aegean": 0.10},
                {"hermes": 0.60, "aether": 0.20, "phoenix": 0.10, "orion": 0.10}
            ),
            MarketRegime.NEUTRAL: (
                {"orion": 0.25, "aether": 0.25, "hermes": 0.20, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.25, "phoenix": 0.25, "hermes": 0.25, "aegean": 0.25}
            )
        }
        return WEIGHT_TABLE.get(regime, WEIGHT_TABLE[MarketRegime.NEUTRAL])
    
    def _adjust_for_missing(self, weights: Dict[str, float], ctx: RegimeContext) -> Dict[str, float]:
        """Zero out weights for missing modules, redistribute"""
        adjusted = weights.copy()
        
        if ctx.orion_score is None:
            adjusted["orion"] = 0
        if ctx.aether_score is None:
            adjusted["aether"] = 0
        if ctx.hermes_score is None:
            adjusted["hermes"] = 0
        
        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            return {k: v/total for k, v in adjusted.items()}
        return adjusted
    
    def save_state(self, path: Path):
        state = {"last_regime": self._last_regime.value}
        path.write_text(json.dumps(state))
    
    def load_state(self, path: Path):
        if path.exists():
            state = json.loads(path.read_text())
            self._last_regime = MarketRegime(state.get("last_regime", "NEUTRAL"))
```

### Choppiness Index Calculation

```python
def calculate_chop_index(highs: List[float], lows: List[float], 
                          closes: List[float], period: int = 14) -> float:
    """Choppiness Index: 0-100, higher = more choppy"""
    import math
    
    atr_sum = 0
    for i in range(1, period + 1):
        tr = max(highs[-i] - lows[-i], 
                 abs(highs[-i] - closes[-i-1]),
                 abs(lows[-i] - closes[-i-1]))
        atr_sum += tr
    
    highest = max(highs[-period:])
    lowest = min(lows[-period:])
    
    if highest == lowest:
        return 50.0
    
    chop = 100 * math.log10(atr_sum / (highest - lowest)) / math.log10(period)
    return max(0, min(100, chop))
```

### Acceptance Criteria
- [ ] All 5 regimes detected correctly
- [ ] Weight tables match Swift implementation
- [ ] Missing module adjustment works
- [ ] State persistence works
- [ ] Choppiness Index calculation correct

### Verification
```bash
pytest tests/unit/test_chiron.py -v

python -c "
from argus_py.models.chiron.chiron import ChironRegimeEngine, RegimeContext

engine = ChironRegimeEngine()
result = engine.evaluate(RegimeContext(
    orion_score=45,
    aether_score=30,
    hermes_score=50,
    adx=15,
    chop_index=65,
    recent_volatility=2.5
))
print(f'Regime: {result.regime.value}')
print(f'Core Weights: {result.core_weights}')
"
```

### Files to Create
1. `argus_py/models/chiron/__init__.py` (NEW)
2. `argus_py/models/chiron/chiron.py` (NEW - 200 lines)
3. `argus_py/models/chiron/indicators.py` (NEW - choppiness calc - 50 lines)
4. `tests/unit/test_chiron.py` (NEW - 80 lines)

---

## P20-ENH6: Phoenix Channel Reversion Strategy

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Port linear regression channel reversion strategy (matching Swift PhoenixLogic).

### Contract

**File:** `argus_py/models/phoenix/__init__.py` (NEW)
**File:** `argus_py/models/phoenix/phoenix.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

@dataclass
class ChannelLevels:
    upper: float
    middle: float
    lower: float
    slope: float
    r_squared: float  # Channel validity

@dataclass
class PhoenixSignals:
    touch_lower_band: bool
    rsi_reversal: bool
    bullish_divergence: bool
    trend_ok: bool

@dataclass
class PhoenixAdvice:
    score: float           # 0-100
    entry_price: float
    stop_loss: float       # Invalidation level
    target_1: float        # Mid-band
    target_2: float        # Upper-band
    channel: ChannelLevels
    signals: PhoenixSignals
    reason: str
    r_squared: float

class PhoenixEngine:
    """Linear Regression Channel Mean Reversion"""
    
    def __init__(self, lookback: int = 60, channel_k: float = 2.0):
        self.lookback = lookback
        self.channel_k = channel_k
    
    def analyze(self, closes: List[float], highs: List[float], 
                lows: List[float]) -> Optional[PhoenixAdvice]:
        
        if len(closes) < self.lookback:
            return None
        
        # 1. Calculate Linear Regression Channel
        channel = self._calculate_channel(closes[-self.lookback:])
        
        # 2. Check R-Squared validity (must be > 0.25)
        if channel.r_squared < 0.25:
            return PhoenixAdvice(
                score=0, entry_price=closes[-1], stop_loss=0, target_1=0, target_2=0,
                channel=channel, signals=PhoenixSignals(False, False, False, False),
                reason="Channel weak (R² < 0.25)", r_squared=channel.r_squared
            )
        
        # 3. Calculate RSI
        rsi = self._calculate_rsi(closes, 14)
        current_rsi = rsi[-1] if rsi else 50
        
        # 4. Detect signals
        price = closes[-1]
        signals = PhoenixSignals(
            touch_lower_band=price <= channel.lower * 1.005,
            rsi_reversal=current_rsi < 35 and rsi[-2] < current_rsi if len(rsi) > 1 else False,
            bullish_divergence=self._check_divergence(closes, rsi),
            trend_ok=channel.slope > -(channel.middle * 0.0005)
        )
        
        # 5. Calculate score
        score = self._calculate_score(signals, current_rsi, channel)
        
        # 6. Calculate levels
        atr = self._calculate_atr(highs, lows, closes, 14)
        stop_loss = channel.lower - (1.25 * atr) if signals.touch_lower_band else price - (2 * atr)
        
        return PhoenixAdvice(
            score=score,
            entry_price=price,
            stop_loss=stop_loss,
            target_1=channel.middle,
            target_2=channel.upper if channel.slope > 0 else channel.middle + (channel.upper - channel.middle) * 0.5,
            channel=channel,
            signals=signals,
            reason=self._generate_reason(score, signals, channel.slope),
            r_squared=channel.r_squared
        )
    
    def _calculate_channel(self, closes: List[float]) -> ChannelLevels:
        """Linear Regression Channel with R-squared"""
        n = len(closes)
        x = np.arange(n)
        y = np.array(closes)
        
        # Linear regression
        x_mean = x.mean()
        y_mean = y.mean()
        
        slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        intercept = y_mean - slope * x_mean
        
        # Calculate regression line values
        y_pred = slope * x + intercept
        
        # Standard deviation of residuals
        residuals = y - y_pred
        sigma = np.std(residuals)
        
        # R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        mid = y_pred[-1]
        upper = mid + (self.channel_k * sigma)
        lower = mid - (self.channel_k * sigma)
        
        return ChannelLevels(upper, mid, lower, slope, r_squared)
    
    def _calculate_score(self, signals: PhoenixSignals, rsi: float, 
                          channel: ChannelLevels) -> float:
        score = 50.0
        
        # Mean reversion signals
        if signals.touch_lower_band:
            score += 20
        if signals.rsi_reversal:
            score += 15
        if signals.bullish_divergence:
            score += 15
        if rsi < 35:
            score += 10
        if signals.trend_ok:
            score += 5
        
        # Penalties
        if channel.slope < 0:
            score -= 15
        sigma_pct = (channel.upper - channel.lower) / channel.middle / 2
        if sigma_pct > 0.08:  # High volatility
            score -= 10
        if rsi > 50:
            score -= 15
        
        return max(0, min(100, score))
```

### Acceptance Criteria
- [ ] Linear regression channel calculation matches Swift
- [ ] R-squared filter works (reject weak channels)
- [ ] RSI divergence detection works
- [ ] Scoring logic matches Swift PhoenixLogic
- [ ] Stop loss and targets calculated correctly

### Verification
```bash
pytest tests/unit/test_phoenix.py -v

python -c "
from argus_py.models.phoenix.phoenix import PhoenixEngine
from argus_py.data.loader import load_csv

bars = load_csv('argus_py/data/BTCUSDT.csv')[-100:]
closes = [b.close for b in bars]
highs = [b.high for b in bars]
lows = [b.low for b in bars]

engine = PhoenixEngine()
advice = engine.analyze(closes, highs, lows)
print(f'Score: {advice.score}')
print(f'R²: {advice.r_squared:.3f}')
print(f'Entry: {advice.entry_price:.2f}, SL: {advice.stop_loss:.2f}')
print(f'T1: {advice.target_1:.2f}, T2: {advice.target_2:.2f}')
"
```

### Files to Create
1. `argus_py/models/phoenix/__init__.py` (NEW)
2. `argus_py/models/phoenix/phoenix.py` (NEW - 200 lines)
3. `tests/unit/test_phoenix.py` (NEW - 80 lines)

---

## P20-ENH7: AutoPilot Position Management

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 5 hours

### Objective
Implement automated position entry/exit logic (matching Swift ArgusAutoPilotEngine).

### Contract

**File:** `argus_py/autopilot/__init__.py` (NEW)
**File:** `argus_py/autopilot/autopilot.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class AutoPilotMode(Enum):
    CORSE = "CORSE"   # Swing: wider stops, longer holds
    PULSE = "PULSE"   # Scalp: tight stops, quick exits

@dataclass
class TradePosition:
    symbol: str
    entry_price: float
    quantity: float
    mode: AutoPilotMode
    entry_time: float
    high_water_mark: float  # For trailing stop
    engine: str             # Which engine triggered

@dataclass
class AutoPilotSignal:
    action: str             # BUY|SELL|TRIM|HOLD
    quantity: float
    reason: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    trim_percentage: Optional[float]

@dataclass
class AutoPilotConfig:
    # Risk limits
    max_risk_per_trade_pct: float = 1.0   # 1% of portfolio
    max_equity_exposure: float = 1.0       # 100%
    
    # Corse (Swing) settings
    corse_stop_pct: float = 8.0
    corse_trim_threshold_pct: float = 20.0
    corse_trailing_activation_pct: float = 5.0
    corse_trailing_distance_pct: float = 2.5
    
    # Pulse (Scalp) settings
    pulse_stop_pct: float = 5.0
    pulse_trim_threshold_pct: float = 10.0
    pulse_trailing_activation_pct: float = 3.0
    pulse_trailing_distance_pct: float = 1.5
    
    # Entry
    min_score_for_entry: float = 65.0
    min_confidence_pct: float = 40.0


class AutoPilotEngine:
    """Handles position entry and exit logic"""
    
    def __init__(self, config: AutoPilotConfig = None):
        self.config = config or AutoPilotConfig()
    
    def evaluate(
        self,
        symbol: str,
        current_price: float,
        council_score: float,
        council_action: str,
        existing_position: Optional[TradePosition],
        portfolio_equity: float,
        cash_available: float
    ) -> AutoPilotSignal:
        
        if existing_position:
            return self._manage_existing(symbol, current_price, council_score, existing_position)
        else:
            return self._evaluate_entry(symbol, current_price, council_score, council_action,
                                        portfolio_equity, cash_available)
    
    def _manage_existing(self, symbol: str, price: float, score: float,
                          pos: TradePosition) -> AutoPilotSignal:
        """The Harvester - manage open positions"""
        pnl_pct = ((price - pos.entry_price) / pos.entry_price) * 100
        mode = pos.mode
        cfg = self.config
        
        # Get mode-specific thresholds
        if mode == AutoPilotMode.CORSE:
            stop_pct = cfg.corse_stop_pct
            trim_pct = cfg.corse_trim_threshold_pct
            trail_activate = cfg.corse_trailing_activation_pct
            trail_distance = cfg.corse_trailing_distance_pct
        else:  # PULSE
            stop_pct = cfg.pulse_stop_pct
            trim_pct = cfg.pulse_trim_threshold_pct
            trail_activate = cfg.pulse_trailing_activation_pct
            trail_distance = cfg.pulse_trailing_distance_pct
        
        # 1. HARD STOP
        if pnl_pct < -stop_pct:
            return AutoPilotSignal("SELL", pos.quantity, f"Stop Loss ({pnl_pct:.1f}%)", None, None, None)
        
        # 2. TRIM PROFITS
        if pnl_pct > trim_pct:
            return AutoPilotSignal("TRIM", pos.quantity * 0.3, f"Profit Taking ({pnl_pct:.1f}%)", None, None, 0.3)
        
        # 3. TRAILING STOP
        drawdown_from_high = ((pos.high_water_mark - price) / pos.high_water_mark) * 100
        if pnl_pct > trail_activate and drawdown_from_high > trail_distance:
            return AutoPilotSignal("SELL", pos.quantity, f"Trailing Stop (DD: {drawdown_from_high:.1f}%)", None, None, None)
        
        # 4. THESIS BROKEN
        score_threshold = 55 if mode == AutoPilotMode.CORSE else 50
        if score < score_threshold and pnl_pct < 0:
            return AutoPilotSignal("SELL", pos.quantity, f"Thesis Broken (Score: {score:.0f})", None, None, None)
        
        return AutoPilotSignal("HOLD", 0, "Position OK", None, None, None)
    
    def _evaluate_entry(self, symbol: str, price: float, score: float, action: str,
                         equity: float, cash: float) -> AutoPilotSignal:
        """The Hunter - find new entries"""
        
        if score < self.config.min_score_for_entry:
            return AutoPilotSignal("HOLD", 0, f"Score too low ({score:.0f})", None, None, None)
        
        if action not in ["AGGRESSIVE_BUY", "ACCUMULATE"]:
            return AutoPilotSignal("HOLD", 0, f"No buy signal ({action})", None, None, None)
        
        # Calculate position size (1% risk)
        risk_amount = equity * (self.config.max_risk_per_trade_pct / 100)
        assumed_stop_pct = 5.0  # Default 5% stop
        position_value = risk_amount / (assumed_stop_pct / 100)
        
        # Cap by available cash
        position_value = min(position_value, cash * 0.95)
        quantity = position_value / price
        
        if quantity <= 0:
            return AutoPilotSignal("HOLD", 0, "Insufficient cash", None, None, None)
        
        stop_loss = price * (1 - assumed_stop_pct / 100)
        take_profit = price * 1.15  # 15% target
        
        return AutoPilotSignal("BUY", quantity, f"Entry Signal (Score: {score:.0f})", stop_loss, take_profit, None)
    
    def update_high_water_mark(self, position: TradePosition, current_price: float) -> TradePosition:
        """Update position's high water mark for trailing stop"""
        if current_price > position.high_water_mark:
            position.high_water_mark = current_price
        return position
```

### Acceptance Criteria
- [ ] Corse vs Pulse mode differences work
- [ ] Stop loss triggers at correct thresholds
- [ ] Trim profits at correct thresholds
- [ ] Trailing stop activates and triggers correctly
- [ ] Position sizing respects 1% risk rule
- [ ] High water mark updates correctly

### Verification
```bash
pytest tests/unit/test_autopilot.py -v

python -c "
from argus_py.autopilot.autopilot import AutoPilotEngine, TradePosition, AutoPilotMode

engine = AutoPilotEngine()

# Test new entry
signal = engine.evaluate(
    symbol='BTCUSDT',
    current_price=50000,
    council_score=72,
    council_action='ACCUMULATE',
    existing_position=None,
    portfolio_equity=10000,
    cash_available=5000
)
print(f'Entry: {signal.action}, Qty: {signal.quantity:.4f}, Reason: {signal.reason}')

# Test exit
pos = TradePosition('BTCUSDT', 50000, 0.1, AutoPilotMode.PULSE, 0, 52000, 'orion')
signal = engine.evaluate('BTCUSDT', 48000, 45, 'HOLD', pos, 10000, 0)
print(f'Exit: {signal.action}, Reason: {signal.reason}')
"
```

### Files to Create
1. `argus_py/autopilot/__init__.py` (NEW)
2. `argus_py/autopilot/autopilot.py` (NEW - 250 lines)
3. `argus_py/autopilot/config.py` (NEW - 50 lines)
4. `tests/unit/test_autopilot.py` (NEW - 120 lines)

---

# PHASE 21: Infrastructure & Quality (Weeks 7-12)

---

## P21-001: Walk-Forward Enhancements

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Make walk-forward backtest robust: no NO_DATA errors, proper windowing, 12-month baseline.

### Current State
```python
# argus_py/lab/walk_forward.py exists but has issues:
# - Some windows fail with NO_DATA
# - Windowing logic not clear
# - No proper result aggregation
```

### Contract

**File:** `argus_py/lab/walk_forward.py` (ENHANCE)

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import date, timedelta
import pandas as pd
from pathlib import Path

@dataclass
class WFWindow:
    start: date
    end: date
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    
@dataclass
class WFResult:
    window: WFWindow
    train_trades: int
    test_trades: int
    train_sharpe: float
    test_sharpe: float
    test_pnl: float
    test_dd: float
    test_wr: float

@dataclass
class WFReport:
    windows: List[WFResult]
    aggregate_sharpe: float
    aggregate_pnl: float
    aggregate_dd: float
    no_data_windows: List[int]  # Should be empty

class WalkForwardEngine:
    """Walk-forward optimization engine with proper error handling."""
    
    def __init__(self, data_path: Path, output_dir: Path):
        self.data_path = data_path
        self.output_dir = output_dir
    
    def create_windows(
        self,
        start_date: date,
        end_date: date,
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1
    ) -> List[WFWindow]:
        """
        Create non-overlapping test windows with rolling training.
        
        Args:
            start_date: Overall start
            end_date: Overall end
            train_months: Training window size
            test_months: Test window size
            step_months: Step between windows
        
        Returns:
            List of WFWindow objects
        """
        ...
    
    def validate_data(self, window: WFWindow) -> Tuple[bool, str]:
        """
        Check if sufficient data exists for window.
        
        Returns:
            (is_valid, error_message)
        """
        ...
    
    def run_window(self, window: WFWindow) -> WFResult:
        """
        Run single window: train, then test.
        
        Raises:
            ValueError: If data validation fails
        """
        ...
    
    def run_full(
        self,
        start_date: date,
        end_date: date,
        symbols: List[str] = ["BTCUSDT"],
        skip_invalid: bool = True
    ) -> WFReport:
        """
        Run full walk-forward simulation.
        
        Args:
            skip_invalid: If True, skip windows with no data instead of failing
        
        Returns:
            Complete report with all window results
        """
        ...
    
    def save_report(self, report: WFReport, filename: str) -> Path:
        """Save report as JSON and CSV."""
        ...
```

### Window Creation Logic

```python
def create_windows(self, start_date, end_date, train_months=6, test_months=1, step_months=1):
    windows = []
    current_test_start = start_date + timedelta(days=train_months * 30)
    
    while current_test_start + timedelta(days=test_months * 30) <= end_date:
        train_start = current_test_start - timedelta(days=train_months * 30)
        train_end = current_test_start - timedelta(days=1)
        test_end = current_test_start + timedelta(days=test_months * 30) - timedelta(days=1)
        
        windows.append(WFWindow(
            start=train_start,
            end=test_end,
            train_start=train_start,
            train_end=train_end,
            test_start=current_test_start,
            test_end=test_end
        ))
        
        current_test_start += timedelta(days=step_months * 30)
    
    return windows
```

### Acceptance Criteria
- [ ] 12-month run completes without NO_DATA errors
- [ ] Each window produces train + test metrics
- [ ] Aggregate metrics calculated correctly
- [ ] Report saves to JSON and CSV
- [ ] Invalid windows logged but don't crash

### Verification
```bash
pytest tests/unit/test_walk_forward.py -v

python -c "
from argus_py.lab.walk_forward import WalkForwardEngine
from datetime import date
from pathlib import Path

engine = WalkForwardEngine(
    data_path=Path('argus_py/data'),
    output_dir=Path('runs/wf_test')
)

windows = engine.create_windows(
    start_date=date(2025, 1, 1),
    end_date=date(2026, 1, 1),
    train_months=6,
    test_months=1
)
print(f'Created {len(windows)} windows')
for w in windows[:3]:
    print(f'  Train: {w.train_start} to {w.train_end}')
    print(f'  Test:  {w.test_start} to {w.test_end}')
"
```

### Files to Modify/Create
1. `argus_py/lab/walk_forward.py` (ENHANCE - 300 lines)
2. `Scripts/sprint1_walkforward_12m.py` (ENHANCE)
3. `tests/unit/test_walk_forward.py` (NEW - 100 lines)

---

## P21-002: Deterministic Backtest Module

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Guarantee reproducibility: same seed → identical results.

### Contract

**File:** `argus_py/lab/determinism.py` (NEW)

```python
from dataclasses import dataclass
from typing import Any, Dict, List
import hashlib
import json
from pathlib import Path
import random
import numpy as np

@dataclass
class RunManifest:
    run_id: str
    seed: int
    timestamp: str
    git_commit: str
    config_hash: str
    data_hash: str
    result_hash: str

class DeterminismManager:
    """Ensures reproducible backtest runs."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def initialize(self) -> None:
        """
        Set all random seeds for reproducibility.
        Must be called before any randomness is used.
        """
        random.seed(self.seed)
        np.random.seed(self.seed)
        # If using torch: torch.manual_seed(self.seed)
    
    def hash_config(self, config: Dict[str, Any]) -> str:
        """Generate hash of configuration."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def hash_data(self, data_path: Path) -> str:
        """Generate hash of input data."""
        if data_path.is_file():
            return hashlib.sha256(data_path.read_bytes()).hexdigest()[:16]
        else:
            # Hash all CSV files in directory
            file_hashes = []
            for f in sorted(data_path.glob("*.csv")):
                file_hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
            return hashlib.sha256("".join(file_hashes).encode()).hexdigest()[:16]
    
    def hash_results(self, trades_csv: Path) -> str:
        """Generate hash of trade results."""
        if trades_csv.exists():
            return hashlib.sha256(trades_csv.read_bytes()).hexdigest()[:16]
        return "NO_TRADES"
    
    def get_git_commit(self) -> str:
        """Get current git commit hash."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True
            )
            return result.stdout.strip()[:8]
        except:
            return "UNKNOWN"
    
    def create_manifest(
        self,
        run_id: str,
        config: Dict[str, Any],
        data_path: Path,
        trades_csv: Path
    ) -> RunManifest:
        """Create manifest for a completed run."""
        from datetime import datetime
        return RunManifest(
            run_id=run_id,
            seed=self.seed,
            timestamp=datetime.now().isoformat(),
            git_commit=self.get_git_commit(),
            config_hash=self.hash_config(config),
            data_hash=self.hash_data(data_path),
            result_hash=self.hash_results(trades_csv)
        )
    
    def save_manifest(self, manifest: RunManifest, path: Path) -> None:
        """Save manifest to JSON file."""
        path.write_text(json.dumps({
            "run_id": manifest.run_id,
            "seed": manifest.seed,
            "timestamp": manifest.timestamp,
            "git_commit": manifest.git_commit,
            "config_hash": manifest.config_hash,
            "data_hash": manifest.data_hash,
            "result_hash": manifest.result_hash
        }, indent=2))
    
    def compare_runs(self, manifest1: RunManifest, manifest2: RunManifest) -> Dict[str, bool]:
        """Compare two runs for determinism."""
        return {
            "same_seed": manifest1.seed == manifest2.seed,
            "same_config": manifest1.config_hash == manifest2.config_hash,
            "same_data": manifest1.data_hash == manifest2.data_hash,
            "same_result": manifest1.result_hash == manifest2.result_hash,
            "is_deterministic": manifest1.result_hash == manifest2.result_hash
        }
```

### Verification Script

**File:** `Scripts/verify_determinism.py` (ENHANCE)

```python
#!/usr/bin/env python3
"""Verify backtest determinism by running twice and comparing."""

import argparse
from pathlib import Path
from argus_py.lab.determinism import DeterminismManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    dm = DeterminismManager(seed=args.seed)
    manifests = []
    
    for i in range(args.runs):
        dm.initialize()  # Reset seeds
        
        # Run backtest
        run_id = f"determinism_check_{i}"
        run_dir = Path(f"runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # ... run backtest ...
        
        manifest = dm.create_manifest(
            run_id=run_id,
            config={"seed": args.seed},
            data_path=Path("argus_py/data"),
            trades_csv=run_dir / "trades.csv"
        )
        dm.save_manifest(manifest, run_dir / "manifest.json")
        manifests.append(manifest)
    
    # Compare
    for i in range(1, len(manifests)):
        comparison = dm.compare_runs(manifests[0], manifests[i])
        result = "DETERMINISTIC" if comparison["is_deterministic"] else "NON-DETERMINISTIC"
        print(f"Run 0 vs Run {i}: {result}")
        if not comparison["is_deterministic"]:
            print(f"  Config match: {comparison['same_config']}")
            print(f"  Data match: {comparison['same_data']}")
            print(f"  Result match: {comparison['same_result']}")

if __name__ == "__main__":
    main()
```

### Acceptance Criteria
- [ ] DeterminismManager.initialize() sets all seeds
- [ ] Config hashing is stable (same config → same hash)
- [ ] Data hashing works for files and directories
- [ ] Manifest captures all relevant metadata
- [ ] Two runs with same seed produce identical trades.csv

### Verification
```bash
pytest tests/unit/test_determinism.py -v

python Scripts/verify_determinism.py --runs 2 --seed 42
# Expected: "Run 0 vs Run 1: DETERMINISTIC"
```

### Files to Create
1. `argus_py/lab/determinism.py` (NEW - 150 lines)
2. `Scripts/verify_determinism.py` (ENHANCE - 100 lines)
3. `tests/unit/test_determinism.py` (NEW - 80 lines)

---

## P21-003: CI & Packaging

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Pre-commit hooks, Makefile, reproducible environment.

### Deliverables

**File:** `.pre-commit-config.yaml` (NEW)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-merge-conflict
      - id: detect-private-key
  
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100', '--ignore=E203,W503']
  
  - repo: local
    hooks:
      - id: no-print-statements
        name: No print() in production code
        entry: bash -c 'git diff --cached --name-only | xargs grep -l "print(" argus_py/ 2>/dev/null && exit 1 || exit 0'
        language: system
        pass_filenames: false
      
      - id: no-large-csv
        name: No CSV files > 1MB
        entry: bash -c 'find . -name "*.csv" -size +1M | head -1 | grep . && exit 1 || exit 0'
        language: system
        pass_filenames: false
```

**File:** `Makefile` (NEW)

```makefile
.PHONY: install test lint format clean run-daemon stop-daemon status

PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

# Installation
install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	$(VENV)/bin/pre-commit install

# Testing
test:
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

test-all:
	$(PYTEST) tests/ -v --tb=short

test-coverage:
	$(PYTEST) tests/unit/ --cov=argus_py --cov-report=html

# Linting
lint:
	$(VENV)/bin/flake8 argus_py/ Scripts/
	$(VENV)/bin/mypy argus_py/ --ignore-missing-imports

format:
	$(VENV)/bin/black argus_py/ Scripts/ tests/
	$(VENV)/bin/isort argus_py/ Scripts/ tests/

# Pre-commit
pre-commit:
	$(VENV)/bin/pre-commit run --all-files

# Daemon control
run-daemon:
	./Scripts/phase19ctl.sh start

stop-daemon:
	./Scripts/phase19ctl.sh stop

status:
	./Scripts/phase19ctl.sh status

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov

# Development
dev-sync:
	$(PIP) freeze > requirements-frozen.txt
```

**File:** `pyproject.toml` (NEW)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "argus-terminal"
version = "0.21.0"
description = "Autonomous crypto trading system"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

[tool.black]
line-length = 100
target-version = ['py310', 'py311']
include = '\.pyi?$'

[tool.isort]
profile = "black"
line_length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

**File:** `requirements-dev.txt` (NEW)

```
# Development dependencies
pytest>=7.4.0
pytest-cov>=4.1.0
black>=24.1.0
isort>=5.13.0
flake8>=7.0.0
mypy>=1.8.0
pre-commit>=3.6.0
```

### Acceptance Criteria
- [ ] `make install` creates venv and installs deps
- [ ] `make test` runs all unit tests
- [ ] `make lint` checks code quality
- [ ] `make format` formats all code
- [ ] `pre-commit run --all-files` passes
- [ ] Fresh clone → make install → make test works

### Verification
```bash
# Fresh setup
rm -rf venv
make install
make test
make lint
make pre-commit

# Expected: All pass
```

### Files to Create
1. `.pre-commit-config.yaml` (NEW)
2. `Makefile` (NEW)
3. `pyproject.toml` (NEW)
4. `requirements-dev.txt` (NEW)

---

## P21-004: Fee & Slippage Realism Model

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 3 hours

### Objective
Accurate fee and slippage modeling for realistic P&L estimates.

### Contract

**File:** `argus_py/broker/realism.py` (NEW)

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class FeeModel:
    """Exchange fee configuration."""
    taker_bps: float = 4.0     # 0.04% Binance Futures
    maker_bps: float = 2.0     # 0.02%
    funding_bps: float = 1.0   # Avg 0.01% per 8h

@dataclass
class SlippageModel:
    """Market impact configuration."""
    base_bps: float = 2.0      # Base slippage
    size_impact_bps: float = 1.0  # Per sqrt($1000)
    volatility_mult: float = 1.5  # ATR multiplier

@dataclass
class RealismConfig:
    fees: FeeModel = None
    slippage: SlippageModel = None
    
    def __post_init__(self):
        self.fees = self.fees or FeeModel()
        self.slippage = self.slippage or SlippageModel()

class RealismEngine:
    """Realistic fee and slippage calculator."""
    
    def __init__(self, config: RealismConfig = None):
        self.config = config or RealismConfig()
    
    def calculate_commission(
        self,
        quantity: float,
        price: float,
        is_taker: bool = True
    ) -> float:
        """Calculate trading commission."""
        fee_bps = self.config.fees.taker_bps if is_taker else self.config.fees.maker_bps
        notional = quantity * price
        return notional * (fee_bps / 10000)
    
    def calculate_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None,
        volume_24h: Optional[float] = None
    ) -> float:
        """
        Calculate market impact slippage.
        
        Returns:
            Slippage amount (positive = adverse, subtract from price for buys)
        """
        cfg = self.config.slippage
        notional = quantity * price
        
        # Base slippage
        base = price * (cfg.base_bps / 10000)
        
        # Size impact (sqrt scaling)
        size_impact = price * (cfg.size_impact_bps / 10000) * np.sqrt(notional / 1000)
        
        # Volatility adjustment
        vol_adj = 1.0
        if atr:
            atr_pct = atr / price * 100
            vol_adj = 1.0 + (atr_pct - 1.0) * (cfg.volatility_mult - 1.0)  # Scale around 1% ATR
        
        total = (base + size_impact) * max(0.5, vol_adj)
        
        # Adverse direction
        return total if side == "BUY" else -total
    
    def calculate_funding(
        self,
        position_value: float,
        hours_held: float,
        avg_funding_rate: Optional[float] = None
    ) -> float:
        """
        Calculate funding cost for futures position.
        
        Args:
            position_value: Notional value
            hours_held: How long position held
            avg_funding_rate: Override default rate
        
        Returns:
            Funding cost (positive = paid, negative = received)
        """
        rate_bps = avg_funding_rate or self.config.fees.funding_bps
        funding_periods = hours_held / 8.0
        return position_value * (rate_bps / 10000) * funding_periods
    
    def get_effective_price(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None
    ) -> float:
        """Get effective fill price including slippage."""
        slip = self.calculate_slippage(price, quantity, side, atr)
        if side == "BUY":
            return price + slip  # Pay more
        else:
            return price - abs(slip)  # Receive less
    
    def estimate_round_trip_cost(
        self,
        price: float,
        quantity: float,
        hold_hours: float = 24.0,
        atr: Optional[float] = None
    ) -> dict:
        """Estimate total round-trip trading costs."""
        notional = quantity * price
        
        # Entry
        entry_commission = self.calculate_commission(quantity, price, is_taker=True)
        entry_slippage = abs(self.calculate_slippage(price, quantity, "BUY", atr))
        
        # Exit
        exit_commission = self.calculate_commission(quantity, price, is_taker=True)
        exit_slippage = abs(self.calculate_slippage(price, quantity, "SELL", atr))
        
        # Funding
        funding = self.calculate_funding(notional, hold_hours)
        
        total = entry_commission + exit_commission + entry_slippage + exit_slippage + funding
        
        return {
            "notional": notional,
            "entry_commission": entry_commission,
            "exit_commission": exit_commission,
            "entry_slippage": entry_slippage,
            "exit_slippage": exit_slippage,
            "funding": funding,
            "total_cost": total,
            "cost_bps": (total / notional) * 10000
        }
```

### Integration with Paper Broker

Modify `argus_py/broker/paper.py`:

```python
from argus_py.broker.realism import RealismEngine, RealismConfig

class PaperBroker:
    def __init__(self, ...):
        self.realism = RealismEngine(RealismConfig())
    
    def execute_order(self, symbol, side, quantity, price, atr=None):
        # Get realistic fill price
        fill_price = self.realism.get_effective_price(price, quantity, side, atr)
        
        # Calculate commission
        commission = self.realism.calculate_commission(quantity, fill_price)
        
        # Execute at realistic price
        ...
```

### Acceptance Criteria
- [ ] Commission calculation matches Binance (0.04% taker)
- [ ] Slippage scales with position size
- [ ] Funding calculated correctly for 8h periods
- [ ] Round-trip cost estimation accurate
- [ ] Paper broker uses realism engine

### Verification
```bash
pytest tests/unit/test_realism.py -v

python -c "
from argus_py.broker.realism import RealismEngine

engine = RealismEngine()

# Test $1000 BTC trade
costs = engine.estimate_round_trip_cost(
    price=50000,
    quantity=0.02,  # $1000 notional
    hold_hours=24,
    atr=500
)
print(f'Notional: \${costs[\"notional\"]:.2f}')
print(f'Entry Commission: \${costs[\"entry_commission\"]:.2f}')
print(f'Entry Slippage: \${costs[\"entry_slippage\"]:.2f}')
print(f'Funding (24h): \${costs[\"funding\"]:.2f}')
print(f'Total Cost: \${costs[\"total_cost\"]:.2f} ({costs[\"cost_bps\"]:.1f} bps)')
"
# Expected: ~$1.50 total ($0.40 comm x2 + ~$0.30 slip x2 + ~$0.30 funding)
```

### Files to Create
1. `argus_py/broker/realism.py` (NEW - 150 lines)
2. `argus_py/broker/paper.py` (MODIFY - integrate realism)
3. `tests/unit/test_realism.py` (NEW - 60 lines)

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
