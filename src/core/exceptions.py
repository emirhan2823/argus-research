"""ARGUS v2.0 — Custom exception hierarchy."""


class ArgusError(Exception):
    """Base exception for all ARGUS errors."""


class DataStaleError(ArgusError):
    """Raised when data exceeds staleness threshold."""


class SentinelHaltError(ArgusError):
    """Raised when Sentinel score falls below halt threshold."""


class KillSwitchActiveError(ArgusError):
    """Raised when kill switch level prevents trading."""


class NaNPropagationError(ArgusError):
    """Raised when NaN is detected past Layer 0."""


class SLPlacementFailedError(ArgusError):
    """Raised when exchange-side stop loss placement fails."""


class ReconciliationError(ArgusError):
    """Raised when local and exchange state diverge significantly."""


class HermesBlockError(ArgusError):
    """Raised when HERMES blocks a trade due to negative news."""


class AdvisoryOnlyError(ArgusError):
    """Raised when attempting auto-execution on an advisory-only asset."""
