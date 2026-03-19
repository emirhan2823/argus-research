# ARGUS As-Is Architecture (2026-03-15)

## System Overview

Argus is an autonomous crypto/multi-asset trading system with a multi-engine, regime-routed signal pipeline.

## Pipeline Flow

```
SONAR scan (15min cycle, paper/live only)
  └── For each symbol:
      1. Load OHLCV + Sentinel validation
      2. Build FeatureVector (ADX, EMA, ATR, Hurst, RSI, BB, CCI, etc.)
      3. Regime classification (Rule-based + ML consensus + State Machine)
      4. v6 Regime Validation + Trend Gate
      5. Engine Orchestrator → OrchestratorDecision (enable/disable engines)
      6. Signal routing (run enabled engines, pick best by confidence)
         6.05  High-liquidity policy (BTC/ETH overrides)
         6.1   AEGEAN confirmation boost for TITAN (TRENDING)
         6.45  Directional bias filter
         6.5   Signal quality filter (7 factors, min 0.55)
         6.7   Precision entry filter (5 factors, grades A-F)
         6.55  Regime alignment scoring (per-engine multiplier 0.70-1.15)
         6.8   Confluence filter (6 factors, need 4/6 + score >= 0.60)
         6.9   Trade quality classifier (composite grade A/B/C/D)
      7. Gates (9 sequential: Sentinel, Crisis, HERMES, RSL, Signal, Confidence, Expected Return, RR, Fee Edge)
      8. Position sizing (multiplicative: base_risk x atlas x sentinel x regime x dd x rsl x hermes x leverage)
      9. Risk checks (DRM, kill switch, pre-trade)
      10. Execution (advisory or auto mode)
```

## Engine Inventory

| Engine | Type | Regime | Status | Config Binding |
| --- | --- | --- | --- | --- |
| TITAN v2 | Trend (dual: REVERSAL + CONTINUATION) | TRENDING | Active, 0 trades | 2/14 params bound |
| POSEIDON | MR Consortium (9 indicators) | VOLATILE, RANGING | Active | 0/40+ params bound |
| NAUTILUS | Ranging MR (BB + funding + micro) | RANGING | Active | 0/5 params bound |
| AEGEAN | Hybrid RSI + MOM-LRC | ALL (confirmation for TITAN) | Active | 0/2+7 dicts bound |
| HYDRA | Scalp BB + RSI | RANGING | Active | 0/15 params bound |
| HERMES | Sentiment overlay | ALL (overlay) | Active | 0/1 params bound |
| GEMINI | Pairs trading (correlation) | RANGING | Active (optional) | 3/3 params bound |
| PHOENIX | Carry / funding harvest | N/A | QUARANTINED (never instantiated) | 0/1 |

## Orchestration Layers (3-layer, redundant)

1. **Engine Instantiation** (main.py:335-388) -- static engine creation
2. **v6 Engine Orchestrator** (regime/engine_orchestrator.py) -- dynamic enable/disable per regime
3. **OrionOrchestrator** (orchestration/orion.py) -- meta-engine weighting with PAF state machine
4. **RegimeRouter** (mde/router.py) -- runs enabled engines, picks best, applies HERMES overlay

## Filter Chain Location

All filters are centralized in `src/mde/`:

| Filter | File | Step | Key Threshold |
| --- | --- | --- | --- |
| Signal Quality | signal_quality.py | 6.5 | MIN_QUALITY_SCORE = 0.55 |
| Precision Entry | precision_filter.py | 6.7 | Grades A-F, min passing = D |
| Regime Alignment | regime_alignment.py | 6.55 | Multiplier 0.70-1.15 |
| Confluence | confluence_filter.py | 6.8 | 4/6 factors + score >= 0.60 |
| Trade Quality | trade_quality.py | 6.9 | Grades A/B/C/D |
| Gates | gates.py | 7 | 9 sequential gates |
| Sizing | sizing.py | 8 | Multiplicative risk model |

## Exit Logic Location

| Component | File | Scope |
| --- | --- | --- |
| Exit Policy (backtest) | backtest/exit_policy.py | Engine-specific configs (hardcoded) |
| Break-Even Lock | risk/breakeven_lock.py | TITAN only (disabled for MR) |
| Dynamic Risk Manager | risk/dynamic_risk_manager.py | Backtest-safe leverage/trailing |
| Kill Switch | risk/kill_switch.py | Drawdown-based de-escalation |

Exit configs per engine (hardcoded in exit_policy.py:67-88):

- HYDRA: trailing=False, be_lock=False, max_hold=6 candles
- NAUTILUS: trailing=False, be_lock=False, max_hold=12 candles
- AEGEAN: trailing=False, be_lock=False, max_hold=8 candles
- POSEIDON: trailing=False, be_lock=False, max_hold=24 candles
- TITAN: trailing=True (2.5x ATR), partial TP (1R->33%, 2R->33%), BE after TP1

**Paper/live has NO time-exit mechanism** (backtest has it). This is a known parity gap.

## Config Structure

| File | Purpose | Loaded By |
| --- | --- | --- |
| config/base.yaml | System settings, asset classes, timeframes | config.py |
| config/regimes.yaml | Regime thresholds, hysteresis, confirmation | config.py |
| config/engines.yaml | Engine params, filter configs, crypto fee mode | config.py |
| config/risk.yaml | Sizing, stop-loss, drawdown, kill switch, guards | config.py |
| config/telemetry.yaml | Logging, alerts, advisory | config.py |

Config is loaded by `src/core/config.py:load_config()` into typed `ArgusConfig` pydantic model.

## Pain Points

1. **main.py monolith** -- ~4862 lines, all pipeline logic in one file
2. **Config binding gap** -- only TITAN (2 params) and GEMINI (3 params) are config-driven; other 5 engines ignore their YAML blocks entirely
3. **Config/code drift** -- TITAN min_adx has 3 different values across YAML/pydantic/engine
4. **PHOENIX dead code** -- imported but never instantiated, still referenced in 20+ locations
5. **RSL2 gate bug** -- gates.py:103 allows only PHOENIX at RSL level 2, but PHOENIX is never instantiated, so ALL signals are blocked at RSL 2
6. **3-layer orchestration redundancy** -- EngineOrchestrator + Orion + Router overlap
7. **No coin bucketing** -- all symbols treated identically
8. **No time-exit in paper/live** -- backtest has it, paper/live does not
9. **Exit configs hardcoded** -- not config-driven (except TITAN partial TP tiers)
