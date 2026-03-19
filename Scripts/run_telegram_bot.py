#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
VENDOR_DIR = REPO_ROOT / ".vendor"
if VENDOR_DIR.exists() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from argus_py.bot.telegram_bot import ArgusTelegramBot


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Argus Telegram control bot")
    parser.add_argument("--token", default=os.getenv("ARGUS_TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--run-dir", type=Path, default=Path("runs/phase19_twin/STRICT"))
    parser.add_argument("--allowed-user", action="append", default=[], help="Telegram user id (repeatable)")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("Telegram token missing. Provide --token or ARGUS_TELEGRAM_BOT_TOKEN")

    if not args.allowed_user:
        raise SystemExit("At least one --allowed-user is required")

    allowed = [int(x) for x in args.allowed_user]
    bot = ArgusTelegramBot(token=args.token, run_dir=args.run_dir, allowed_users=allowed)
    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
