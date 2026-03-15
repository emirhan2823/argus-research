from __future__ import annotations

from pathlib import Path

from src.main import ArgusPipeline


def test_strategy_profiles_loader_missing_file_defaults_disabled(tmp_path: Path) -> None:
    cfg = ArgusPipeline._load_strategy_profiles_config(path=tmp_path / "missing.yaml")
    assert cfg["enabled"] is False


def test_strategy_profiles_loader_missing_file_can_force_enable(tmp_path: Path) -> None:
    cfg = ArgusPipeline._load_strategy_profiles_config(
        path=tmp_path / "missing.yaml",
        enabled_override=True,
    )
    assert cfg["enabled"] is True


def test_strategy_profiles_loader_override_beats_yaml_flag(tmp_path: Path) -> None:
    path = tmp_path / "profiles.yaml"
    path.write_text(
        "\n".join(
            [
                "strategy_profiles:",
                "  enabled: false",
                "  defaults:",
                "    confidence_shift: 0.0",
                "  profiles: {}",
            ]
        ),
        encoding="utf-8",
    )
    cfg = ArgusPipeline._load_strategy_profiles_config(path=path, enabled_override=True)
    assert cfg["enabled"] is True
    assert cfg["config_path"] == str(path)

