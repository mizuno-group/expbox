# src/expbox/__init__.py
from __future__ import annotations

"""
Top-level package for expbox.

Public API is intentionally minimal:

    import expbox as xb

    ctx = xb.init(...)
    ctx = xb.load(...)
    xb.save(ctx)

Internally, these are backed by `init_exp`, `load_exp`, `save_exp` in `api.py`,
so that we can later add more explicit functions if needed without breaking
the top-level namespace.
"""

from importlib.metadata import PackageNotFoundError, version

from .api import init_exp as init, load_exp as load, save_exp as save
from .context import ExpContext, ExperimentMeta, ExpPaths

try:
    __version__ = version("expbox")
except PackageNotFoundError:  # pragma: no cover - dev / editable install etc.
    __version__ = "0.0.0"

__all__ = [
    "init",
    "load",
    "save",
    "ExpContext",
    "ExperimentMeta",
    "ExpPaths",
    "__version__",
]
