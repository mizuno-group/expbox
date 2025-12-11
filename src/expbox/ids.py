from __future__ import annotations

"""
Experiment ID generation utilities.

The experiment ID is used as the directory name under `results_root/`:

    results/
      <exp_id>/
        meta.json
        artifacts/
        figures/
        logs/

This module is intentionally self-contained so that ID policies can be
changed or swapped out later without touching the rest of the codebase.

Typical usage
-------------
    from expbox.ids import generate_exp_id

    exp_id = generate_exp_id(
        style="datetime",
        prefix="baseline",
        suffix=None,
        link_style="kebab",
    )

Design notes
------------
- The default style is a compact datetime stamp with seconds: "YYMMDD-HHMMSS".
- An optional prefix/suffix can be attached.
- `link_style="kebab"` generates `"prefix-241125-132045-suffix"`.
- `link_style="snake"` generates `"prefix_241125-132045_suffix"`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Optional


IdStyle = Literal["datetime", "date", "seq", "rand"]
LinkStyle = Literal["kebab", "snake"]


@dataclass
class IdGenerator:
    """
    Lightweight pluggable ID generator.

    This is a small wrapper so that tests or advanced users can inject
    their own ID generation policy, while the default implementation
    remains simple and self-contained.
    """

    func: Callable[[], str]

    def __call__(self) -> str:  # pragma: no cover - trivial
        return self.func()


def _link(a: str, b: str, *, style: LinkStyle = "kebab") -> str:
    """
    Link two segments with either '-' (kebab) or '_' (snake).
    """
    if style == "kebab":
        sep = "-"
    elif style == "snake":
        sep = "_"
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported link style: {style!r}")
    return f"{a}{sep}{b}"


def generate_exp_id(
    *,
    style: IdStyle = "datetime",
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    datetime_fmt: str = "%y%m%d-%H%M%S",
    link_style: LinkStyle = "kebab",
    id_generator: Optional[IdGenerator] = None,
) -> str:
    """
    Generate a new experiment id.

    Parameters
    ----------
    style:
        ID style. The following styles are currently implemented:

        - "datetime": compact datetime stamp (default).
        - "date": date-only stamp.
        - "seq": reserved for future sequential IDs (currently same as datetime).
        - "rand": reserved for future random IDs (currently same as datetime).

    prefix:
        Optional prefix string.

    suffix:
        Optional suffix string.

    datetime_fmt:
        Datetime format string passed to :func:`datetime.strftime`. The
        default generates a compact "YYMMDD-HHMMSS" stamp.

    link_style:
        How to join prefix/base/suffix. "kebab" (`-`) or "snake" (`_`).

    id_generator:
        Optional custom :class:`IdGenerator` for advanced use cases. If
        provided, it overrides `style`/`datetime_fmt` and is used to generate
        the base ID.

    Returns
    -------
    str
        Generated experiment id.
    """
    # 1) Base ID
    if id_generator is not None:
        base_id = id_generator()
    else:
        now = datetime.utcnow()

        if style == "datetime":
            base_id = now.strftime(datetime_fmt)
        elif style == "date":
            base_id = now.strftime("%y%m%d")
        elif style in ("seq", "rand"):
            # For now, treat seq/rand as datetime-based as well.
            base_id = now.strftime(datetime_fmt)
        else:  # pragma: no cover - defensive, should not happen in normal use
            raise ValueError(f"Unsupported id style: {style!r}")

    # 2) Attach optional prefix / suffix
    full = base_id
    if prefix:
        full = _link(prefix, full, style=link_style)
    if suffix:
        full = _link(full, suffix, style=link_style)

    return full