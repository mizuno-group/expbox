# tests/test_config.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from expbox.config import load_config, snapshot_config
from expbox.exceptions import ConfigLoadError


def test_load_config_from_mapping() -> None:
    cfg = load_config({"lr": 1e-3, "epochs": 10})
    assert cfg["lr"] == 1e-3
    assert cfg["epochs"] == 10


def test_load_config_from_json_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    data = {"lr": 1e-3, "epochs": 5}
    path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(path)
    assert cfg == data


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError):
        load_config(tmp_path / "missing.yaml")


def test_snapshot_config_to_yaml_or_json(tmp_path: Path, monkeypatch) -> None:
    # We don't care if it's YAML or JSON; we just check that it is valid and round-trips.
    dest = tmp_path / "snapshot.yaml"
    cfg = {"lr": 1e-3, "epochs": 10}

    snapshot_config(cfg, dest)
    text = dest.read_text(encoding="utf-8")

    # try JSON first
    try:
        loaded = json.loads(text)
    except Exception:
        # if not JSON, try YAML (optional)
        try:
            import yaml  # type: ignore
        except ImportError:
            pytest.skip("PyYAML not installed; cannot fully check snapshot format")
        loaded = yaml.safe_load(text)

    assert loaded == cfg


@pytest.mark.skipif("yaml" not in globals(), reason="optional: only if PyYAML is installed")
def test_load_config_from_yaml_file(tmp_path: Path) -> None:  # type: ignore[func-returns-value]
    try:
        import yaml  # type: ignore
    except ImportError:
        pytest.skip("PyYAML not installed")

    path = tmp_path / "config.yaml"
    data = {"lr": 1e-3, "epochs": 5}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    cfg = load_config(path)
    assert cfg == data
