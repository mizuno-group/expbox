# src/expbox/config.py
from __future__ import annotations

"""
Configuration loading and snapshot utilities.

The design is intentionally minimal:

- Accepts:
    * None          -> {}
    * Mapping       -> shallow-copied dict
    * Path / str    -> JSON or YAML file
- YAML support is optional and requires PyYAML.
- Snapshot is written as YAML if possible, otherwise JSON.

TODO:
    - Support TOML configuration (e.g. using tomllib or toml) if needed.
"""

import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Union

from .exceptions import ConfigLoadError

ConfigLike = Union[str, Path, Mapping[str, Any], None]


def load_config(config: ConfigLike) -> MutableMapping[str, Any]:
    """
    Load configuration from various possible inputs.

    Parameters
    ----------
    config:
        - None -> empty dict.
        - Mapping -> shallow copy.
        - str / Path -> JSON or YAML file; extension is inspected.

    Returns
    -------
    dict
        A mutable dictionary containing the configuration.

    Raises
    ------
    ConfigLoadError
        If the file cannot be found or parsed.
    """
    if config is None:
        return {}

    if isinstance(config, Mapping):
        return dict(config)

    path = Path(config)
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except ImportError as e:  # pragma: no cover - env dependent
                raise ConfigLoadError(
                    "YAML config requested, but PyYAML is not installed. "
                    "Install with: pip install 'expbox[yaml]'"
                ) from e
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, Mapping):
                raise ConfigLoadError(f"YAML config must map to an object: {path}")
            return dict(data)

        if suffix == ".json":
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, Mapping):
                raise ConfigLoadError(f"JSON config must map to an object: {path}")
            return dict(data)

        # Fallback: try JSON first, then YAML.
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, Mapping):
                return dict(data)
        except Exception:
            pass

        try:
            import yaml  # type: ignore
        except ImportError as e:
            raise ConfigLoadError(
                "Could not interpret config as JSON, and PyYAML is not installed."
            ) from e

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, Mapping):
            raise ConfigLoadError(f"Config file must map to an object: {path}")
        return dict(data)

    except ConfigLoadError:
        raise
    except Exception as e:
        raise ConfigLoadError(f"Failed to load config: {path}") from e


def snapshot_config(config: Mapping[str, Any], dest: Path) -> None:
    """
    Save a snapshot of the configuration.

    Parameters
    ----------
    config:
        Configuration mapping to be saved.
    dest:
        Destination file path.

    Notes
    -----
    - Tries to use YAML if PyYAML is installed.
    - Falls back to JSON otherwise.
    """
    data = dict(config)
    try:
        import yaml  # type: ignore

        with dest.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    except ImportError:  # pragma: no cover - env dependent
        # Fallback to JSON
        with dest.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
