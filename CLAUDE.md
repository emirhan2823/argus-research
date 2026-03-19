# Argus project rules

## Project intent

Argus is an autonomous crypto trading and research system.
Safety, correctness, and controlled iteration matter more than speed.

## Communication

- User communicates in Turkish. Respond in Turkish or mixed Turkish/English as appropriate.

## Collaboration style

- Treat me as an active research partner, not a passive approver.
- If strategy design, risk logic, exits, filters, pair selection, or regime behavior are unclear, stop and brainstorm with me before choosing a path.
- Do not silently fill gaps in trading logic.
- If multiple valid approaches exist, present options with tradeoffs and ask for my decision.
- Prefer discussion first for architecture-affecting or PnL-affecting choices.

## Decision policy

- Ask me before locking in strategy logic, risk logic, sizing, TP/SL behavior, pair selection, signal thresholds, or exchange assumptions.
- Do not invent trading assumptions to move faster.
- Never treat silence as approval.

## Workflow

- First identify whether the task is research, backtest, execution, risk, reporting, or infrastructure.
- For any strategy or risk change, explain the expected effect on drawdown, trade frequency, regime behavior, and implementation complexity.
- Prefer isolated experiments over broad refactors.
- Keep live config separate from research config.
- Use `/strategy-brainstorm` for strategy design, TP/SL ideas, filter choices, regime handling, and ambiguity in trading logic.
- Use `/backtest-review` when analyzing backtest results, comparing experiments, or interpreting metrics.

## Risk & leakage awareness

- Before changing leverage, sizing, stop logic, capital allocation, or max-open-trades behavior: explain the expected impact on drawdown, max loss, and trade frequency. Ask for confirmation before implementing.
- When backtest results look unusually strong, or when modifying filters, features, dataset ranges, or pair admission rules: flag potential data leakage, overfitting, or survivorship bias. Walk through the logic with me before proceeding.

## Safety

- Never silently modify production or paper-trading defaults.
- Never hardcode secrets.
- Ask before changing leverage, stop logic, or capital allocation.

## Protected files & areas

Changes to these require explicit confirmation before editing:

- `config/engines.yaml`, `config/risk.yaml`, `config/base.yaml` — production engine/risk config
- `src/main.py` — pipeline entry point
- `src/risk/` — risk management core
- `src/mde/sizing.py`, `src/mde/gates.py` — position sizing and gate logic
- `Scripts/soak_*.sh`, `Scripts/win_soak_*.ps1` — paper soak infrastructure
- `.env`, `.env.*` — secrets and environment variables
- `start_paper.sh`, `start_paper.bat` — live/paper launch scripts

## Architecture (quick reference)

- **Engines**: POSEIDON (primary MR), TITAN v2 (primary trend), AEGEAN (secondary, confirmation-only)
- **Pipeline**: signal quality → directional bias → precision → regime alignment → confluence → trade quality → gates → sizing
- **SONAR**: universe scanner (Binance + BingX), discovers and ranks trading pairs
- **Regime routing**: engine orchestrator selects engines based on market regime
- **Data**: 15m OHLCV parquets in `data/binance/{SYMBOL}/15m/`

## Current priorities

- TITAN inactivity investigation (zero trades in real pipeline)
- Filter chain / acceptance rate tuning
- Paper/live exit parity (time-exit gap)
- Config clarity / remaining partial config binding

## Current known issues

- TITAN produces zero trades — regime strictness + continuation funnel + pullback rejection
- Filter chain cascading penalties may over-reject borderline signals
- Paper/live execution has no time-exit mechanism (backtest does)
- Partial config-code binding: some engine params config-driven, many still hardcoded

## Detailed context

For audit findings, profitability analysis, and experiment history:

- `docs/argus-audit/current-state.md` — validated findings, open issues, architecture notes
- `docs/argus-audit/profitability-findings.md` — scenario-specific performance analysis
- `docs/argus-audit/experiment-log.md` — experiment history with results and interpretations

## Knowledge Base (Second Brain)

Persistent project knowledge lives in the Obsidian vault at `E:/vault/`.

### MCP Tools (configured in `.vscode/mcp.json`)
- `obsidian-vault` — read/list vault notes via mcp-obsidian
- `smart-connections` — semantic search across vault
- `qmd` — hybrid search (BM25 + vector) via `@tobilu/qmd`

### Vault Skills (in `.claude/skills/`)
- `/vault-search` — search vault by topic or tag
- `/vault-write` — create/update atomic notes
- `/brain-ingest` — ingest raw content (meeting notes, transcripts, URLs) into atomic vault notes
- `/vault-ingest` — same as brain-ingest, alternative entry

### Key Vault Notes
- `1-Projects/Project - argus-terminal.md` — project hub
- `2-Areas/Signal pipeline terminal 9 asama.md` — pipeline architecture
- `3-Resources/Engine roster terminal 8 engine.md` — engine reference
- `2-Areas/Config binding durumu terminal vs core.md` — config status
- `2-Areas/Paper live execution gap.md` — known execution gaps

### Memory Rules
- MEMORY.md at vault root — max 200 lines, auto-updated
- Before creating knowledge in MEMORY.md, check if a vault note already exists
- Prefer vault notes for persistent knowledge; use CLAUDE.md only for rules/instructions
- Every checkpoint/milestone → update vault with atomic notes
- Hallucination prevention: NEVER invent facts, only use provided info or vault content
