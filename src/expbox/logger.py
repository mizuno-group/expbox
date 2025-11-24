# src/expbox/logger.py
from __future__ import annotations

"""
Logging backends for expbox.

The interface is intentionally similar to other experiment-tracking tools:

- `log_metrics`  : log a dict of metrics (similar to mlflow.log_metrics)
- `log_figure`   : log a matplotlib figure-like object
- `log_artifact` : log a file artifact

This makes it easy to later add MLflow or other loggers without changing
user code.

TODO:
    - Add MLflowLogger backend.
    - Allow multi-backend logging (e.g. file + wandb).
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Optional, Literal

from .exceptions import WandbNotAvailableError

LoggerKind = Literal["none", "file", "wandb"]


class BaseLogger(ABC):
    """
    Abstract base class for all logging backends.

    Implementations should be lightweight and avoid importing heavy
    packages at module import time.
    """

    @abstractmethod
    def log_metrics(self, metrics: Mapping[str, float], step: Optional[int] = None) -> None:
        """Log a dictionary of metrics for a given step."""

    @abstractmethod
    def log_figure(self, fig: Any, name: str, step: Optional[int] = None) -> None:
        """Log a figure object (e.g. matplotlib Figure) with a given name."""

    @abstractmethod
    def log_artifact(self, path: Path, name: Optional[str] = None) -> None:
        """Log a file artifact located at `path`."""

    @abstractmethod
    def close(self) -> None:
        """Clean up resources (e.g. flush files, finish remote sessions)."""


class NullLogger(BaseLogger):
    """
    No-op logger implementation.

    Useful when logging is disabled but the code expects a logger object.
    """

    def log_metrics(self, metrics, step=None) -> None:
        return

    def log_figure(self, fig, name, step=None) -> None:
        return

    def log_artifact(self, path: Path, name: Optional[str] = None) -> None:
        return

    def close(self) -> None:
        return


class FileLogger(BaseLogger):
    """
    Simple file-based logger.

    - Metrics are appended as JSONL records to `logs/metrics.jsonl`.
    - Figures are saved as PNG files into the `logs/` directory by default.

    This backend is completely local and does not require any external services.
    """

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.log_dir / "metrics.jsonl"
        self._metrics_file = self.metrics_path.open("a", encoding="utf-8")

    def log_metrics(self, metrics: Mapping[str, float], step: Optional[int] = None) -> None:
        record = {"step": step, "metrics": dict(metrics)}
        self._metrics_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._metrics_file.flush()

    def log_figure(self, fig: Any, name: str, step: Optional[int] = None) -> None:
        fname = f"{name}.png" if not name.endswith(".png") else name
        out_path = self.log_dir / fname
        fig.savefig(out_path)

    def log_artifact(self, path: Path, name: Optional[str] = None) -> None:
        # v0.1: no-op or future implementation for copying/recording artifacts.
        # TODO: Optionally copy artifacts into a dedicated subdirectory.
        return

    def close(self) -> None:
        try:
            self._metrics_file.close()
        except Exception:
            pass


class WandbLogger(BaseLogger):
    """
    W&B-based logger backend.

    This logger imports `wandb` lazily in the constructor, so that users
    who do not use W&B do not need the dependency installed.
    """

    def __init__(self, project: str, exp_id: str, config: Mapping[str, Any]):
        try:
            import wandb  # type: ignore
        except ImportError as e:  # pragma: no cover - env dependent
            raise WandbNotAvailableError(
                "wandb logger requested, but wandb is not installed. "
                "Install with: pip install 'expbox[wandb]'"
            ) from e

        self._wandb = wandb
        # TODO: allow passing additional wandb.init kwargs if needed.
        self.run = wandb.init(project=project, name=exp_id, config=dict(config))

    def log_metrics(self, metrics: Mapping[str, float], step: Optional[int] = None) -> None:
        self.run.log(dict(metrics), step=step)

    def log_figure(self, fig: Any, name: str, step: Optional[int] = None) -> None:
        self.run.log({name: self._wandb.Image(fig)}, step=step)

    def log_artifact(self, path: Path, name: Optional[str] = None) -> None:
        artifact_name = name or path.name
        art = self._wandb.Artifact(artifact_name, type="file")
        art.add_file(str(path))
        self.run.log_artifact(art)

    def close(self) -> None:
        self.run.finish()
