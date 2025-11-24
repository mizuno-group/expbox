# src/expbox/api.py
from __future__ import annotations

"""
Public-facing experiment lifecycle API.

Core functions:
- init_exp(...) -> ExpContext
- load_exp(...) -> ExpContext
- save_exp(ctx) -> None

At the top level, these are exposed as `expbox.init`, `expbox.load`,
`expbox.save` for ease of use.

Design principles:
- Local-first: everything lives under `results/<exp_id>/`.
- Minimal surface: one context object (`ExpContext`) passed to user code.
- No hard dependency on specific loggers or tracking services.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Union

from .config import ConfigLike, load_config, snapshot_config
from .context import ExpContext, ExpPaths, ExperimentMeta
from .ids import IdStyle, LinkStyle, ensure_safe_exp_id, generate_exp_id
from .logger import BaseLogger, FileLogger, LoggerKind, NullLogger, WandbLogger
from .meta_io import load_meta, save_meta

IdGenerator = Callable[[str, Path], str]


def _make_logger(
    kind: LoggerKind,
    project: str,
    exp_id: str,
    cfg: Mapping[str, Any],
    log_dir: Path,
) -> BaseLogger:
    """
    Internal helper to construct a logger backend.

    TODO: Add support for mlflow or multi-backend logging here.
    """
    if kind == "none":
        return NullLogger()
    if kind == "file":
        return FileLogger(log_dir)
    if kind == "wandb":
        return WandbLogger(project=project, exp_id=exp_id, config=cfg)
    raise ValueError(f"Unknown logger kind: {kind}")


def init_exp(
    project: str,
    title: Optional[str] = None,
    purpose: Optional[str] = None,
    config: ConfigLike = None,
    logger: LoggerKind = "none",
    results_root: Union[str, Path] = "results",

    # exp_id settings
    exp_id: Optional[str] = None,
    id_style: IdStyle = "datetime",
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    datetime_fmt: str = "%y%m%d-%H%M",
    link_style: LinkStyle = "kebab",
    id_generator: Optional[IdGenerator] = None,
) -> ExpContext:
    """
    Initialize a new experiment context.

    This function:
        - Decides an exp_id (using the provided options or an id generator).
        - Creates `results/<exp_id>/` and its subdirectories.
        - Loads the configuration and saves a snapshot under artifacts/.
        - Initializes a logger backend.
        - Writes an initial meta.json.

    Parameters
    ----------
    project:
        Logical project name (free-form string).
    title:
        Short experiment title.
    purpose:
        Short description of the experiment purpose.
    config:
        Configuration source:
        - None
        - Mapping
        - path to JSON/YAML file
    logger:
        Logger backend: "none", "file", or "wandb".
    results_root:
        Root directory under which experiments are stored, usually "results".

    exp_id:
        Explicit exp_id to use. If provided, no automatic generation is done.
    id_style:
        Style used when generating exp_id ("datetime", "date", "seq", "rand").
    prefix:
        Optional prefix for exp_id (used for non-"seq" styles).
    suffix:
        Optional suffix for exp_id (used for non-"seq" styles).
    datetime_fmt:
        Datetime format string for datetime-based styles.
    link_style:
        How to join parts: "kebab" -> "-", "snake" -> "_".
    id_generator:
        Optional custom function `(project, results_root) -> exp_id`.
        If provided, this takes precedence over id_style.

    Returns
    -------
    ExpContext
        The initialized experiment context.
    """
    results_root = Path(results_root)

    # Decide exp_id
    if exp_id is not None:
        exp_id = ensure_safe_exp_id(exp_id)
    elif id_generator is not None:
        exp_id = ensure_safe_exp_id(id_generator(project, results_root))
    else:
        exp_id = generate_exp_id(
            project=project,
            results_root=results_root,
            id_style=id_style,
            prefix=prefix,
            suffix=suffix,
            datetime_fmt=datetime_fmt,
            link_style=link_style,
        )

    # Paths
    paths = ExpPaths.create(results_root, exp_id)

    # Config
    cfg = load_config(config)
    cfg_snapshot_path = paths.artifacts / "config.yaml"
    snapshot_config(cfg, cfg_snapshot_path)
    rel_cfg_path = cfg_snapshot_path.relative_to(paths.root).as_posix()

    # Meta
    meta = ExperimentMeta(
        exp_id=exp_id,
        project=project,
        title=title,
        purpose=purpose,
        config_path=rel_cfg_path,
        logger_backend=logger,
    )

    # Logger
    lg = _make_logger(logger, project=project, exp_id=exp_id, cfg=cfg, log_dir=paths.logs)

    ctx = ExpContext(
        exp_id=exp_id,
        project=project,
        paths=paths,
        config=cfg,
        meta=meta,
        logger=lg,
    )

    save_meta(meta, paths.root / "meta.json")
    return ctx


def load_exp(
    exp_id: str,
    project: Optional[str] = None,
    results_root: Union[str, Path] = "results",
) -> ExpContext:
    """
    Load an existing experiment context from `results/<exp_id>`.

    Parameters
    ----------
    exp_id:
        Experiment id (directory name under `results_root`).
    project:
        Optional override for `meta.project`.
        If None, the value stored in meta.json is used.
    results_root:
        Root directory under which experiments are stored.

    Returns
    -------
    ExpContext
        The reconstructed experiment context.

    Notes
    -----
    - For now, W&B runs are not re-attached automatically. If meta.json
      indicates `logger_backend="wandb"`, a NullLogger is used instead.
      You can open the previous run manually using the stored info if needed.

    TODO:
        - Optionally re-attach W&B runs if desired.
        - Add hooks for custom logger re-attachment logic.
    """
    results_root = Path(results_root)
    root = results_root / exp_id
    meta_path = root / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"meta.json not found for exp_id={exp_id}")

    meta = load_meta(meta_path)
    paths = ExpPaths.create(results_root, exp_id)

    cfg_rel = meta.config_path or "artifacts/config.yaml"
    cfg_path = root / Path(cfg_rel)
    cfg = load_config(cfg_path)

    # Re-attach logger: file logger is safe to recreate; W&B becomes NullLogger for now.
    if meta.logger_backend == "file":
        lg = FileLogger(paths.logs)
    else:
        lg = NullLogger()

    ctx = ExpContext(
        exp_id=meta.exp_id,
        project=meta.project if project is None else project,
        paths=paths,
        config=cfg,
        meta=meta,
        logger=lg,
    )
    return ctx


def save_exp(ctx: ExpContext) -> None:
    """
    Finalize an experiment.

    This function:
        - Sets `meta.finished_at` if it is not already set.
        - Closes the logger.
        - Writes meta.json to disk.

    Parameters
    ----------
    ctx:
        The experiment context to finalize.

    TODO:
        - Allow registering user-defined "on_save" hooks for custom cleanup.
    """
    if ctx.meta.finished_at is None:
        ctx.meta.finished_at = datetime.utcnow().isoformat()

    try:
        ctx.logger.close()
    except Exception:
        # Logging errors on close are non-fatal.
        pass

    save_meta(ctx.meta, ctx.paths.root / "meta.json")
