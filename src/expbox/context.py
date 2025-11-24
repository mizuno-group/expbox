# src/expbox/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


@dataclass
class ExpPaths:
    """
    Collection of paths for an experiment under results_root/exp_id/.

    Attributes
    ----------
    root:
        Root directory for the experiment, e.g. `results/<exp_id>/`.
    artifacts:
        Directory for configuration snapshots, model weights, tables, etc.
    figures:
        Directory for generated figures.
    logs:
        Directory for log files and metrics.
    notebooks:
        Directory intended for experiment-specific notebooks (optional use).
    """

    root: Path
    artifacts: Path
    figures: Path
    logs: Path
    notebooks: Path

    @classmethod
    def create(cls, results_root: Path, exp_id: str) -> "ExpPaths":
        """
        Create (or reuse) the directory tree for a given exp_id
        under `results_root`.

        This method is idempotent: existing directories will not be removed.

        TODO: In the future we could allow a configurable subdirectory layout.
        """
        root = results_root / exp_id
        artifacts = root / "artifacts"
        figures = root / "figures"
        logs = root / "logs"
        notebooks = root / "notebooks"

        for p in (root, artifacts, figures, logs, notebooks):
            p.mkdir(parents=True, exist_ok=True)

        return cls(
            root=root,
            artifacts=artifacts,
            figures=figures,
            logs=logs,
            notebooks=notebooks,
        )


@dataclass
class ExperimentMeta:
    """
    Metadata for a single experiment.

    Stored as `meta.json` in the experiment root. This is the primary
    machine-readable source of truth for Notion/W&B/other integrations.

    Attributes
    ----------
    exp_id:
        Experiment identifier, used as directory name under results_root.
    project:
        Logical project name (free-form string).
    title:
        Short title for the experiment (optional).
    purpose:
        Short description of the purpose (optional).
    created_at:
        UTC timestamp when the experiment was initialized (ISO 8601).
    finished_at:
        UTC timestamp when the experiment was finalized, if any.
    git_commit:
        Git commit hash at the time of initialization (optional, not set by expbox).
        TODO: In the future we might auto-populate this by calling `git`.
    config_path:
        Relative path (POSIX style) from the experiment root to the
        configuration snapshot file.
    logger_backend:
        Selected logger backend: "none", "file", or "wandb".
    wandb_run_id:
        W&B run id, if any (expbox does not currently auto-populate this).
    env_note:
        Free-form note about the execution environment.
    final_note:
        Free-form final comment about the result.
    extra:
        Free-form dictionary for user extensions.
    """

    exp_id: str
    project: str

    title: Optional[str] = None
    purpose: Optional[str] = None

    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: Optional[str] = None

    git_commit: Optional[str] = None
    config_path: Optional[str] = None
    logger_backend: str = "none"
    wandb_run_id: Optional[str] = None

    env_note: Optional[str] = None
    final_note: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpContext:
    """
    Central context object passed to training / analysis code.

    This is the only object most user code should need to know about.

    Attributes
    ----------
    exp_id:
        Experiment id (directory name under results_root).
    project:
        Logical project name.
    paths:
        `ExpPaths` holding the directory structure for this experiment.
    config:
        Loaded configuration as a mapping.
    meta:
        `ExperimentMeta` describing this experiment.
    logger:
        A `BaseLogger` implementation used for metrics/figures/artifacts.
    """

    exp_id: str
    project: str
    paths: ExpPaths
    config: Mapping[str, Any]
    meta: ExperimentMeta
    logger: "BaseLogger"  # defined in logger.py
