from __future__ import annotations

from typing import List

from .manager import CorrelationBucket, SymbolConfig


DEFAULT_CRYPTO_SYMBOLS: List[SymbolConfig] = [
    SymbolConfig("BTCUSDT", bucket=CorrelationBucket.BTC_ECOSYSTEM, priority=1, max_position_pct=30),
    SymbolConfig("ETHUSDT", bucket=CorrelationBucket.ETH_ECOSYSTEM, priority=1, max_position_pct=25),
    SymbolConfig("SOLUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=2, max_position_pct=15),
    SymbolConfig("BNBUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=2, max_position_pct=15),
    SymbolConfig("XRPUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=3, max_position_pct=10),
    SymbolConfig("LINKUSDT", bucket=CorrelationBucket.ALTCOIN_MID, priority=3, max_position_pct=10),
    SymbolConfig("AVAXUSDT", bucket=CorrelationBucket.ALTCOIN_MID, priority=3, max_position_pct=10),
]
