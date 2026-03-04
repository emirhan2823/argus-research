"""Multi-Asset Capital Rotation module."""

from src.rotation.capital_rotator import (
    AssetTrendScore,
    CapitalRotator,
    RotationDecision,
)

__all__ = ["CapitalRotator", "RotationDecision", "AssetTrendScore"]
