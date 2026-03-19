# ARGUS Year-2+ Backlog (Step 0)

Source of truth scanned: `Docs/FUTURE_VISION.md` (Section `5` onward, after Year-1 summary).

## Scope Mapping Rules
- Priority labels: `P0` (must-have), `P1` (high), `P2` (optional/advanced).
- Sprint labels follow requested sequence: `A`..`F`.
- Every item includes module targets, runtime wiring points, tests, and Definition of Done.
- Default runtime safety: `MODE=legacy` stays default; all new behavior behind `MODE=v2`.

## Master Backlog (Year-2 and beyond)

| Backlog ID | FUTURE_VISION Section | Implementation Task | Priority | Sprint | Files / Modules | Wiring Points | Tests | Definition of Done |
|---|---|---|---|---|---|---|---|---|
| Y2P-001 | 5. Phase 25 Advanced Trading | Add advanced strategy hooks (options/arb/grid/dca/copy placeholders with paper adapters) | P1 | B | `argus_py/strategy/advanced/*`, `argus_py/adapters/*` | `Scripts/paper_daemon.py` strategy registry + mode router | unit+integration | Strategies registerable, paper-executable, telemetry-tagged |
| Y2P-002 | 5. Phase 26 AI/ML Evolution | RL/NLP/AutoML scaffolding with guardrails | P2 | F | `argus_py/learning/rl/*`, `argus_py/models/hermes/*`, `argus_py/lab/automl/*` | nightly research loop + model promotion gate | unit+offline integration | Enabled only when data volume + KPI gate passes |
| Y2P-003 | 5. Phase 27 Ecosystem Expansion | CEX/DEX hybrid routing and DeFi plugin layer | P0 | B | `argus_py/exchanges/*`, `argus_py/adapters/defi/*`, `argus_py/asset_router/*` | execution route selection in daemon | integration | At least 1 simulated stock + 1 simulated defi backend runnable |
| Y2P-004 | 5. Phase 28 Enterprise Features | Multi-portfolio tenancy + investor/report interfaces | P2 | E | `argus_py/portfolio/tenancy/*`, `argus_py/reporting/investor/*` | reporting pipeline + ctl commands | integration | Separate portfolios isolated + auditable outputs |
| Y2P-005 | 6. Reference Integration Plan | Keep reference-derived modules productionized (validator/window/vectorized/factor) | P0 | A | existing Phase1 modules | paper+nightly runtime hooks | integration | Runtime actually consumes these modules or their outputs |
| Y2P-006 | 7. Technology Roadmap | Redis/warehouse contracts + future infra compatibility | P1 | E | `argus_py/telemetry/metrics_warehouse.py`, ops deploy docs | telemetry writer + ops scripts | integration | hot/warm/cold metrics path validated |
| Y2P-007 | 8. Scaling Milestones | Add AUM-tier runtime profiles | P1 | E | `config/profiles/*.yaml`, `Scripts/phase19ctl.sh` | ctl profile selection | integration | profile switch updates risk/execution/alerts safely |
| Y2P-008 | 9. Risk Evolution | Progressive risk caps by stage | P0 | C | `argus_py/risk/*`, `argus_py/goals/allocator.py` | pre-trade risk gate | unit+integration | stage-based caps enforceable and logged |
| Y2P-009 | 10. Next Actions Post Year-1 | Automate performance + architecture review artifacts | P1 | A | `Scripts/nightly_eval.py`, `Scripts/gate_recheck.py`, reports | nightly pipeline | integration | daily reports include pass/fail trend + blockers |
| Y2P-010 | 11. 24/7 Otonom Mimari | Beast+Soldier dual runtime + monitoring | P0 | E | `scripts/soak_*`, `argus_py/ops/watchdog*` | daemon + supervisor | integration | unattended operation + restart policy + health checks |
| Y2P-011 | 12. Capital Growth Roadmap | Capital growth constraints as machine rules | P0 | C | `argus_py/goals/*`, `argus_py/allocator/*` | allocation and risk sizing | unit+integration | compounding rules encoded + daily limits enforced |
| Y2P-012 | 13. Strategy Portfolio Lifecycle | Promote/freeze/retire fully wired | P0 | A | `argus_py/strategy/lifecycle.py` | runtime strategy gating + reports | integration | lifecycle actions affect runtime decisions |
| Y2P-013 | 14. Market Regime Engine | v2 regime classifier as runtime source | P0 | A | `argus_py/regime/classifier.py` | paper daemon regime selection | integration | MODE=v2 decisions carry regime snapshot |
| Y2P-014 | 15. 7 Motor Crypto Adaptasyonu | Atlas/Aether/Hermes/Chiron runtime integration | P0 | A | `argus_py/models/atlas/*`, `argus_py/models/aether/*`, `argus_py/models/hermes/*`, `argus_py/learning/chiron.py` | decision enrichment + weighting + telemetry | integration | scores visible in metrics/events and influence decision policy |
| Y2P-015 | 16. Paper→Micro→Live Gates | Operational gates as executable checks | P0 | A | `Scripts/gate_recheck.py`, `argus_py/strategy/lifecycle.py` | nightly gate reports | integration | explicit PASS/FAIL with reasons and thresholds |
| Y2P-016 | 17. Iron Risk | Correlation + kill-switch + cooldown hardening | P0 | A | `argus_py/risk/correlation.py`, `argus_py/risk/kill_switch.py` | pre-trade + post-trade risk loop | integration | breaches auto-logged and block trades |
| Y2P-017 | 18. Alpha Factory | Experiment orchestration and factor scoring | P1 | D | `argus_py/alpha_factory/*`, `argus_py/ml/factor_pipeline.py` | lab runner + nightly research | unit+integration | reproducible experiment report with ranking/pruning |
| Y2P-018 | 19. 4-Year Master Plan | Stage-by-stage profile automation | P1 | E | `config/stages/*`, ctl adapters | startup config selection | integration | stage transitions auditable and reversible |
| Y2P-019 | 20. Failure Modes + Prevention | Incident drills + automated mitigations | P1 | E | `argus_py/ops/incident_manager.py`, drill scripts | watchdog + ops flow | integration | drill execution creates incident artifacts |
| Y2P-020 | 21. Hydra/Argo/Titan New Strategies | Add three strategy modules with guards | P1 | B | `argus_py/strategy/hydra.py`, `argo.py`, `titan.py` | strategy registry | unit+integration | paper mode strategies selectable and measured |
| Y2P-021 | 22. Repo Research Features | Backlog extraction into implementable tasks | P2 | D | `Docs/research_backlog/*.md` | research CI/reporting | doc+tests | each imported feature has acceptance test |
| Y2P-022 | 23. ML/AI Engine RTX Plan | Chronos + ensemble + sequence model gates | P2 | F | `argus_py/ml/chronos_*`, model runners | nightly training loop | integration | only enabled after KPI/data gate pass |
| Y2P-023 | 24. Mac→Windows Transfer | Cross-host deploy playbook + scripts | P0 | E | `Docs/WINDOWS_DEPLOY_RUNBOOK.md`, `scripts/win_*` | ops bootstrap | smoke tests | Windows node can run paper soak unattended |
| Y2P-024 | 25. Sprint Plan (legacy roadmap) | Align historical roadmap to A–F incremental model | P1 | A | `Docs/VISION_YEAR2_PLUS_BACKLOG.md` | project planning | doc check | backlog is decision-complete and traceable |
| Y2P-025 | 26. Institutional Architecture | Runtime adapters to align current repo with target architecture | P0 | A | `argus_py/runner/v2_runtime.py`, adapters | paper daemon pipeline | integration | v2 path follows documented chain with telemetry |
| Y2P-026 | 27. Hostile Audit v2 Redesign | Implement MDE/RSL improvements incrementally | P0 | A | `argus_py/core/event_bus.py`, `argus_py/risk/*`, routing hooks | decision + risk chain | integration | measurable decision quality/risk behavior improvements |
| Y2P-027 | 28. Consolidated v2 Spec | Execute core contracts (data/feature/regime/engines/MDE/RSL/execution) | P0 | A | mixed existing v2 modules + runtime wiring | paper daemon + nightly | integration | spec elements visible in runtime artifacts |
| Y2P-028 | 29. Phase-1 Sprint Board | Backfill month1-2 spec gaps with tests | P1 | A | tests/integration + docs | CI test pack | unit+integration | sprint board items mapped to actual code/test |
| Y2P-029 | 30. Data Contracts & Interfaces | Enforce schema/version contracts at runtime | P0 | A | telemetry schemas + validation | append_decision/reject/trade + warehouse | unit+integration | malformed payloads rejected + logged |
| Y2P-030 | 31. Mathematical Foundations | Parameterized formulas encoded and versioned | P1 | C | `argus_py/risk/*`, `argus_py/goals/*` | sizing/allocation decisions | unit | formulas match documented thresholds |
| Y2P-031 | 32A-32D Chief Architect Package | Pipeline orchestrator + regime state machine alignment | P0 | A | `argus_py/runner/v2_runtime.py`, future `argus_py/regime/state_machine.py` | daemon decision path | integration+stress | critical transition rules covered by tests |

## Sprint Sequence Commitments
- **Sprint A (P0)**: Integration Hardening (`MODE=v2` runtime + nightly + integration report)
- **Sprint B (P0)**: Multi-Asset Expansion Layer
- **Sprint C (P0)**: Capital & Goal Allocation Engine
- **Sprint D (P1)**: Alpha Factory / Research OS
- **Sprint E (P1)**: Production Operations
- **Sprint F (P2)**: Advanced AI/Chronos only if KPI/data gate passes

## Decision Log References
- See `Docs/DECISION_LOG.md` for ambiguity handling and safe assumptions applied during implementation.
