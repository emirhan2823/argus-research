from __future__ import annotations

from src.main import (
    DEFAULT_CRYPTO_SYMBOLS_15,
    DEFAULT_CRYPTO_SYMBOLS_5,
    parse_symbols_arg,
    resolve_crypto_symbol_universe,
)


def test_symbols_parsing_and_default_universe() -> None:
    assert parse_symbols_arg("btcusdt, ETH/USDT , btc-usdt, SOL_USDT") == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]

    assert resolve_crypto_symbol_universe(symbols_arg=None, universe_size=5, live_data=True) == list(
        DEFAULT_CRYPTO_SYMBOLS_5
    )
    assert resolve_crypto_symbol_universe(symbols_arg=None, universe_size=15, live_data=True) == list(
        DEFAULT_CRYPTO_SYMBOLS_15
    )

    # Non-live mode keeps legacy single-symbol behavior unless explicit override provided.
    assert resolve_crypto_symbol_universe(symbols_arg=None, universe_size=15, live_data=False) == []

    explicit = resolve_crypto_symbol_universe(
        symbols_arg="XRPUSDT,DOGEUSDT",
        universe_size=5,
        live_data=False,
    )
    assert explicit == ["XRPUSDT", "DOGEUSDT"]
