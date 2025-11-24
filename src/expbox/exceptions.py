# src/expbox/exceptions.py
from __future__ import annotations


class ExpboxError(Exception):
    """Base exception for expbox."""


class ConfigLoadError(ExpboxError):
    """Raised when configuration file cannot be loaded."""


class WandbNotAvailableError(ExpboxError):
    """Raised when wandb logger is requested but wandb is not installed."""
