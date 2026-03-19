# Proposed Folder Structure for Argus Python

This structure is designed to be modular, scalable, and separate concerns strictly.

```text
argus-python/
├── pyproject.toml              # Dependency management (pandas, pytest, etc.)
├── README.md                   # Quick start guide
├── src/
│   └── argus/                  # Main Package
│       ├── __init__.py
│       ├── core/               # Core Engine Loops
│       │   ├── __init__.py
│       │   └── engine.py       # Main Backtest Loop
│       ├── data/               # Data Loading Layer
│       │   ├── __init__.py
│       │   ├── loader.py       # CSV Loading & Validation
│       │   └── feed.py         # Time-step iterator
│       ├── features/           # Indicators & Math
│       │   ├── __init__.py
│       │   ├── indicators.py   # EMA, Slope, etc.
│       │   └── aegean.py       # Specific Aegean Logic
│       ├── strategy/           # Strategy Decisions
│       │   ├── __init__.py
│       │   └── base.py         # Strategy Interface
│       ├── risk/               # Risk Management
│       │   ├── __init__.py
│       │   └── manager.py      # Daily Loss, Drawdown, Sizing
│       ├── broker/             # Execution Simulation
│       │   ├── __init__.py
│       │   ├── account.py      # Equity/Balance Tracking
│       │   └── paper.py        # Order Execution & Brackets
│       └── utils/              # Shared Utilities
│           ├── __init__.py
│           ├── logging.py      # Consistent Logger
│           └── math.py         # Helper math functions
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest configuration
│   ├── unit/                   # Fast, isolated tests
│   │   ├── test_loader.py
│   │   ├── test_indicators.py
│   │   └── test_risk.py
│   └── integration/            # Full loop tests
│       └── test_backtest_parity.py
├── scripts/
│   └── run_backtest.py         # CLI Entry point
├── docs/
│   ├── MasterSpec.md           # System Specification
│   ├── PythonRoadmap.md        # Implementation Plan
│   └── FolderStructure.md      # This file
└── data -> ../data             # Symlink to existing data (Do not commit)
```

## Module Dependencies
`data` -> `features` -> `strategy` -> `risk` -> `broker` -> `core`
