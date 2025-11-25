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

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Union

from .config import ConfigLike, load_config, snapshot_config
from .context import ExpContext, ExpPaths, ExperimentMeta
from .ids import IdStyle, LinkStyle, ensure_safe_exp_id, generate_exp_id
from .logger import BaseLogger, FileLogger, LoggerKind, NullLogger, WandbLogger
from .meta_io import load_meta, save_meta

IdGenerator = Callable[[str, Path], str]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _find_git_root(start: Path) -> Optional[Path]:
    """
    Walk up from `start` to find a `.git` directory.

    Returns
    -------
    Path or None
        Repository root if found, else None.
    """
    cur = start.resolve()
    for p in (cur, *cur.parents):
        if (p / ".git").exists():
            return p
    return None


def _run_git(args: list[str], cwd: Path) -> Optional[str]:
    """
    Run a git command and return stdout (stripped), or None on failure.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception:
        return None

    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _get_git_status(repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    Collect basic git status information for the repository.

    Returns
    -------
    dict or None
        {
          "commit": str,
          "branch": str or None,
          "dirty": bool,
          "dirty_files": [str, ...],
          "remote": {
            "name": "origin",
            "url": "...",
            "github_commit_url": "https://github.com/.../commit/<hash>"  # optional
          } or None,
        }
    """
    commit = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
    if not commit:
        return None

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    status_out = _run_git(["status", "--porcelain"], cwd=repo_root) or ""
    dirty = bool(status_out.strip())

    dirty_files = []
    for line in status_out.splitlines():
        if not line.strip():
            continue
        # format: "XY path"
        if len(line) > 3:
            dirty_files.append(line[3:])
        else:
            dirty_files.append(line.strip())

    remote_url = _run_git(["config", "--get", "remote.origin.url"], cwd=repo_root)
    remote: Dict[str, Any] = {}
    if remote_url:
        remote["name"] = "origin"
        remote["url"] = remote_url

        commit_url: Optional[str] = None
        if "github.com" in remote_url:
            base: Optional[str] = None
            if remote_url.startswith("git@github.com:"):
                path = remote_url[len("git@github.com:") :]
                if path.endswith(".git"):
                    path = path[:-4]
                base = f"https://github.com/{path}"
            elif remote_url.startswith("https://github.com/") or remote_url.startswith(
                "http://github.com/"
            ):
                base = remote_url
                if base.endswith(".git"):
                    base = base[:-4]
            if base:
                commit_url = f"{base}/commit/{commit}"

        if commit_url:
            remote["github_commit_url"] = commit_url

    return {
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
        "dirty_files": dirty_files,
        "remote": remote or None,
    }


def _init_git_section() -> Dict[str, Any]:
    """
    Initialize the `git` section for ExperimentMeta at init_exp time.

    - Uses current working directory to locate the repo.
    - Records both `start` and initial `last` (same values).
    """
    start_path = Path.cwd()
    repo_root = _find_git_root(start_path)
    if repo_root is None:
        return {}

    status = _get_git_status(repo_root)
    if status is None:
        return {}

    try:
        project_relpath = str(start_path.relative_to(repo_root))
    except ValueError:
        project_relpath = None

    now_iso = datetime.utcnow().isoformat()

    git_section: Dict[str, Any] = {
        "repo_root": str(repo_root),
        "project_relpath": project_relpath,
        "start": {
            "commit": status["commit"],
            "branch": status["branch"],
            "dirty": status["dirty"],
            "captured_at": now_iso,
        },
        "last": {
            "commit": status["commit"],
            "branch": status["branch"],
            "dirty": status["dirty"],
            "saved_at": None,
        },
        "dirty_files": status["dirty_files"],
        "remote": status["remote"],
    }
    return git_section


def _update_git_on_save(meta: ExperimentMeta) -> None:
    """
    Update the `git.last` section on each save_exp call.

    - If repo_root is known, use it; otherwise try to rediscover.
    - Does NOT create or push any commits.
    """
    try:
        git_section: Dict[str, Any] = dict(meta.git) if meta.git else {}
        repo_root_str = git_section.get("repo_root")
        if repo_root_str:
            repo_root = Path(repo_root_str)
        else:
            repo_root = _find_git_root(Path.cwd())
            if repo_root is None:
                return
            git_section["repo_root"] = str(repo_root)

        status = _get_git_status(repo_root)
        if status is None:
            return

        last = dict(git_section.get("last") or {})
        last.update(
            {
                "commit": status["commit"],
                "branch": status["branch"],
                "dirty": status["dirty"],
                "saved_at": datetime.utcnow().isoformat(),
            }
        )
        git_section["last"] = last
        git_section["dirty_files"] = status["dirty_files"]
        git_section["remote"] = status["remote"]

        # If project_relpath is missing, try to fill it from current cwd.
        if git_section.get("project_relpath") is None:
            try:
                git_section["project_relpath"] = str(Path.cwd().relative_to(repo_root))
            except ValueError:
                pass

        meta.git = git_section
        # Backward compatibility: keep git_commit in sync with last.commit
        meta.git_commit = status["commit"]
    except Exception:
        # Git metadata should never break save_exp
        return


# ---------------------------------------------------------------------------
# Logger helper
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
        - Writes an initial meta.json (including Git metadata, if available).

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

    # Git metadata at init
    git_section = _init_git_section()
    if git_section:
        meta.git = git_section
        # For compatibility / convenience, also set git_commit = start.commit
        start_info = git_section.get("start") or {}
        commit = start_info.get("commit")
        if isinstance(commit, str):
            meta.git_commit = commit

    # Logger
    lg = _make_logger(
        logger,
        project=project,
        exp_id=exp_id,
        cfg=cfg,
        log_dir=paths.logs,
    )

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
    Save (and optionally finalize) an experiment.

    This function:
        - Updates Git metadata (`meta.git.last`) if a Git repo is found.
        - Sets `meta.finished_at` if it is not already set.
        - Closes the logger.
        - Writes meta.json to disk.

    Parameters
    ----------
    ctx:
        The experiment context to save.

    TODO:
        - Allow registering user-defined "on_save" hooks for custom cleanup.
    """
    # Update Git metadata first (best-effort, never raises)
    _update_git_on_save(ctx.meta)

    if ctx.meta.finished_at is None:
        ctx.meta.finished_at = datetime.utcnow().isoformat()

    try:
        ctx.logger.close()
    except Exception:
        # Logging errors on close are non-fatal.
        pass

    save_meta(ctx.meta, ctx.paths.root / "meta.json")
