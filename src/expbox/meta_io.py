# src/expbox/meta_io.py
from __future__ import annotations

"""
Serialization helpers for ExperimentMeta.

Currently JSON-only to keep dependencies minimal.

TODO:
    - Support optional additional formats if needed (e.g. YAML).
"""

import json
from pathlib import Path

from .context import ExperimentMeta


def save_meta(meta: ExperimentMeta, path: Path) -> None:
    """
    Serialize an ExperimentMeta instance to a JSON file.
    """
    data = meta.__dict__
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_meta(path: Path) -> ExperimentMeta:
    """
    Load an ExperimentMeta instance from a JSON file.
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return ExperimentMeta(**data)
