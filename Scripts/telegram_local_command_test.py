#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.bot.telegram_bot import ArgusTelegramBot


class _FakeUser:
    def __init__(self, uid: int):
        self.id = uid


class _FakeMessage:
    def __init__(self):
        self.calls = []

    async def reply_text(self, text, **kwargs):
        self.calls.append((text, kwargs))


class _FakeUpdate:
    def __init__(self, uid: int):
        self.effective_user = _FakeUser(uid)
        self.message = _FakeMessage()


class _FakeCtx:
    def __init__(self, args=None):
        self.args = args or []


async def _invoke(bot: ArgusTelegramBot, uid: int, command: str, args=None):
    update = _FakeUpdate(uid)
    ctx = _FakeCtx(args=args)
    handler = {
        "status": bot.cmd_status,
        "trades": bot.cmd_trades,
        "report": bot.cmd_report,
        "balance": bot.cmd_balance,
        "killswitch": bot.cmd_killswitch,
    }[command]
    await handler(update, ctx)
    if update.message.calls:
        return update.message.calls[-1][0]
    return "<no response>"


async def main_async(run_dir: Path, uid: int) -> int:
    bot = ArgusTelegramBot(token="local-test", run_dir=run_dir, allowed_users=[uid])

    print(f"Run dir: {run_dir}")
    print("\n/status")
    print(await _invoke(bot, uid, "status"))

    print("\n/balance")
    print(await _invoke(bot, uid, "balance"))

    print("\n/trades")
    print(await _invoke(bot, uid, "trades"))

    print("\n/report")
    print(await _invoke(bot, uid, "report"))

    print("\n/killswitch soft")
    print(await _invoke(bot, uid, "killswitch", args=["soft"]))

    print("\n/killswitch off")
    print(await _invoke(bot, uid, "killswitch", args=["off"]))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local command smoke test for Argus Telegram bot")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    if not args.run_dir.exists():
        raise SystemExit(f"Run directory not found: {args.run_dir}")

    return asyncio.run(main_async(args.run_dir, args.user_id))


if __name__ == "__main__":
    raise SystemExit(main())
