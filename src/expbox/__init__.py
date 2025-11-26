from __future__ import annotations

"""
Top-level package for expbox.

This module provides a notebook-friendly, stateful API around the
stateless lifecycle functions in :mod:`expbox.api`.

Typical usage
-------------

    import expbox as xb

    xb.init(project="demo", logger="file")
    for step in range(100):
        loss = ...
        xb.logger.log_metrics(step=step, loss=float(loss))

    xb.meta.final_note = "seed sweep finished"
    xb.save()

The currently active "box" (experiment) is:

- stored in-memory as a module-level `_active_ctx`
- shared across processes via `.expbox/active` in the project root.

Advanced users can still access the lower-level API:

- :func:`expbox.api.init_exp`
- :func:`expbox.api.load_exp`
- :func:`expbox.api.save_exp`
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from .api import init_exp, load_exp, save_exp
from .core import ExpContext, ExpMeta, ExpPaths
from .io import set_active_exp_id, get_active_exp_id

# ---------------------------------------------------------------------------
# Package version
# ---------------------------------------------------------------------------

try:
    __version__ = version("expbox")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Active experiment context (in-memory)
# ---------------------------------------------------------------------------

_active_ctx: Optional[ExpContext] = None


def _require_active() -> ExpContext:
    """
    Return the currently active experiment context, or raise a helpful error.
    """
    if _active_ctx is None:
        raise RuntimeError(
            "No active experiment box. "
            "Call expbox.init(...) or expbox.load(...) first."
        )
    return _active_ctx


def get_active() -> ExpContext:
    """
    Return the currently active experiment context.

    This is a thin wrapper around the internal `_require_active()` and is
    mainly provided for advanced users.
    """
    return _require_active()


# ---------------------------------------------------------------------------
# Public high-level API
# ---------------------------------------------------------------------------


def init(*, set_active: bool = True, **kwargs) -> ExpContext:
    """
    Initialize a new experiment box and (optionally) make it active.

    Parameters
    ----------
    set_active:
        If True (default), the created experiment becomes the active box:
        - stored in-memory as `_active_ctx`
        - persisted to `.expbox/active` in the current project.
    **kwargs:
        Passed through to :func:`expbox.api.init_exp`.

    Returns
    -------
    ExpContext
        The newly created experiment context.
    """
    global _active_ctx

    ctx = init_exp(**kwargs)
    if set_active:
        _active_ctx = ctx
        set_active_exp_id(ctx.exp_id)
    return ctx


def load(
    exp_id: Optional[str] = None,
    *,
    set_active: bool = True,
    **kwargs,
) -> ExpContext:
    """
    Load an existing experiment and (optionally) make it active.

    Parameters
    ----------
    exp_id:
        Experiment id to load. If omitted, tries to read from
        `.expbox/active`. If that also fails, raises RuntimeError.
    set_active:
        If True (default), the loaded experiment becomes the active box.
    **kwargs:
        Passed through to :func:`expbox.api.load_exp` (e.g., results_root, logger).

    Returns
    -------
    ExpContext
    """
    global _active_ctx

    if exp_id is None:
        exp_id = get_active_exp_id()
        if not exp_id:
            raise RuntimeError(
                "No exp_id was given and no active experiment was found "
                "under .expbox/active. Call expbox.init(...) first."
            )

    ctx = load_exp(exp_id=exp_id, **kwargs)
    if set_active:
        _active_ctx = ctx
        set_active_exp_id(ctx.exp_id)
    return ctx


def save(
    ctx: Optional[ExpContext] = None,
    **kwargs,
) -> None:
    """
    Save a snapshot of an experiment box.

    Parameters
    ----------
    ctx:
        Experiment context to save. If omitted, uses the currently active
        context (see :func:`get_active`).
    **kwargs:
        Passed through to :func:`expbox.api.save_exp`, e.g.:

        - status: Optional[str]
        - final_note: Optional[str]
        - update_git: bool = True
    """
    if ctx is None:
        ctx = _require_active()
    save_exp(ctx, **kwargs)


# ---------------------------------------------------------------------------
# Dynamic attribute forwarding to the active context
# ---------------------------------------------------------------------------


def __getattr__(name: str):
    """
    Provide convenient accessors for the active box:

    - expbox.paths   -> active_ctx.paths
    - expbox.config  -> active_ctx.config
    - expbox.meta    -> active_ctx.meta
    - expbox.logger  -> active_ctx.logger
    - expbox.exp_id  -> active_ctx.exp_id
    - expbox.project -> active_ctx.project
    """
    if name in {"paths", "config", "meta", "logger", "exp_id", "project"}:
        ctx = _require_active()
        return getattr(ctx, name)
    raise AttributeError(f"module 'expbox' has no attribute {name!r}")


__all__ = [
    "init",
    "load",
    "save",
    "get_active",
    "ExpContext",
    "ExpMeta",
    "ExpPaths",
    "__version__",
]
