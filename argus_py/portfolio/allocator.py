from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioAllocationDecision:
    requested_risk_pct: float
    allowed_risk_pct: float
    risk_budget_pct: float
    max_asset_exposure_pct: float
    current_asset_exposure_pct: float
    implied_asset_exposure_pct: float
    blocked: bool
    reason: str


class PortfolioAllocatorV1:
    """
    V1 allocator for single-strategy integration.
    Rules:
    1) Clamp risk by global portfolio risk budget.
    2) Clamp risk by per-asset max exposure using assumed stop distance.
    """

    def __init__(
        self,
        risk_budget_pct: float = 1.0,
        max_asset_exposure_pct: float = 35.0,
        assumed_stop_loss_pct: float = 2.0,
    ):
        self.risk_budget_pct = max(0.0, float(risk_budget_pct))
        self.max_asset_exposure_pct = max(0.0, float(max_asset_exposure_pct))
        # Avoid divide-by-zero; keep a realistic floor.
        self.assumed_stop_loss_pct = max(0.01, float(assumed_stop_loss_pct))

    def allocate_single_asset(
        self,
        requested_risk_pct: float,
        current_asset_exposure_pct: float = 0.0,
    ) -> PortfolioAllocationDecision:
        requested_ratio = max(0.0, float(requested_risk_pct))
        budget_ratio = self.risk_budget_pct / 100.0
        current_exposure = max(0.0, float(current_asset_exposure_pct))
        remaining_exposure_pct = max(0.0, self.max_asset_exposure_pct - current_exposure)

        # Exposure-implied risk cap:
        # risk ~= exposure * stop_loss
        stop_ratio = self.assumed_stop_loss_pct / 100.0
        exposure_cap_ratio = (remaining_exposure_pct / 100.0) * stop_ratio

        allowed_ratio = min(requested_ratio, budget_ratio, exposure_cap_ratio)

        implied_exposure_pct = 0.0
        if stop_ratio > 0 and allowed_ratio > 0:
            implied_exposure_pct = (allowed_ratio / stop_ratio) * 100.0

        blocked = allowed_ratio <= 0.0
        reason = "OK"
        if blocked:
            if remaining_exposure_pct <= 0.0:
                reason = "MAX_ASSET_EXPOSURE_REACHED"
            elif budget_ratio <= 0.0:
                reason = "ZERO_PORTFOLIO_RISK_BUDGET"
            else:
                reason = "NO_ALLOCATABLE_RISK"
        elif allowed_ratio < requested_ratio:
            if allowed_ratio == exposure_cap_ratio:
                reason = "CLAMPED_BY_MAX_ASSET_EXPOSURE"
            elif allowed_ratio == budget_ratio:
                reason = "CLAMPED_BY_RISK_BUDGET"

        return PortfolioAllocationDecision(
            requested_risk_pct=requested_ratio * 100.0,
            allowed_risk_pct=allowed_ratio * 100.0,
            risk_budget_pct=self.risk_budget_pct,
            max_asset_exposure_pct=self.max_asset_exposure_pct,
            current_asset_exposure_pct=current_exposure,
            implied_asset_exposure_pct=implied_exposure_pct,
            blocked=blocked,
            reason=reason,
        )
