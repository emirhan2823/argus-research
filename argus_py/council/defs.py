from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Vote:
    module: str
    direction: str # LONG, SHORT, FLAT
    confidence: float # 0.0 - 1.0
    score: float # 0-100 (Legacy/Visual)
    reasons: List[str]
    metadata: dict = field(default_factory=dict)

@dataclass
class ConsensusVerdict:
    timestamp: float
    decision: str # GO, NO_GO
    direction: str # BUY, SELL, HOLD
    conviction: float # 0.0 - 100.0 (Weighted Average)
    regime: str # TREND, CHOP, UNKNOWN
    rationale: str
    votes: List[Vote] = field(default_factory=list)
    metadata: dict = field(default_factory=dict) # For block_reason, raw signals
