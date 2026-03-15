from __future__ import annotations

from pathlib import Path

from src.main import ArgusPipeline


def test_liquidity_policy_loader_missing_file_defaults_disabled(tmp_path: Path) -> None:
    cfg = ArgusPipeline._load_liquidity_policy_config(path=tmp_path / "missing.yaml")
    assert cfg["enabled"] is False


def test_liquidity_policy_loader_reads_enabled_yaml(tmp_path: Path) -> None:
    path = tmp_path / "liquidity.yaml"
    path.write_text(
        "\n".join(
            [
                "high_liquidity_filters:",
                "  enabled: true",
                "  target_symbols: [BTCUSDT, ETHUSDT]",
                "  policies: {}",
            ]
        ),
        encoding="utf-8",
    )
    cfg = ArgusPipeline._load_liquidity_policy_config(path=path)
    assert cfg["enabled"] is True
    assert cfg["config_path"] == str(path)

