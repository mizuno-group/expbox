# src/expbox/ids.py
from __future__ import annotations

"""
Utilities for generating experiment identifiers (exp_id).

Design goals:
- Safe on both POSIX and Windows (no forbidden characters).
- Lightweight, deterministic, and easy to reason about.
- Flexible enough to support:
    * datetime-based ids (default)
    * date-only ids
    * simple sequential ids
    * random ids
- Allow user-controlled `prefix` and `suffix`.
- If both prefix and suffix are omitted, default to `YYMMDD-HHMM`.

Link styles:
- "kebab": words joined by '-', e.g. "proj-250124-1530-suffix"
- "snake": words joined by '_', e.g. "proj_250124_1530_suffix"

TODO: In the future we may support user-defined templates like
      "{project}_{date}_exp{n}" instead of style enums.
"""

import random
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

IdStyle = Literal["datetime", "date", "seq", "rand"]
LinkStyle = Literal["kebab", "snake"]

INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*]')


def ensure_safe_exp_id(exp_id: str) -> str:
    """
    Ensure an experiment id is safe to be used as a directory name
    on Windows and POSIX systems.

    Raises
    ------
    ValueError
        If the id contains forbidden characters or becomes empty.
    """
    if INVALID_CHARS_PATTERN.search(exp_id):
        raise ValueError(
            f"exp_id '{exp_id}' contains invalid characters for file names. "
            r"Forbidden: <>:\"/\|?*"
        )
    exp_id = exp_id.strip().rstrip(". ")
    if not exp_id:
        raise ValueError("exp_id must not be empty")
    return exp_id


def slugify(text: str) -> str:
    """
    Simple slugify implementation.

    - Lowercases the input.
    - Keeps only [a-z0-9_-].
    - Replaces other characters with '-'.
    - Collapses multiple '-' into one.
    - Strips leading/trailing '-'.

    Note
    ----
    This is intentionally simple and deterministic. It is mainly used
    for prefix/suffix normalization and is not meant to be fully
    locale-aware.
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text or "id"


def _separator(link_style: LinkStyle) -> str:
    """
    Return the separator character for the given link style.

    - kebab -> "-"
    - snake -> "_"
    """
    if link_style == "snake":
        return "_"
    # default and "kebab"
    return "-"


def generate_exp_id(
    project: str,
    results_root: Path,
    *,
    id_style: IdStyle = "datetime",
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    datetime_fmt: str = "%y%m%d-%H%M",
    link_style: LinkStyle = "kebab",
) -> str:
    """
    Generate a new experiment id according to the given style and options.

    Parameters
    ----------
    project:
        Logical project name. Used only for `seq` style in the current
        implementation (and may be used in future templates).
    results_root:
        Root directory where experiment directories are stored. Used by
        `seq` style to scan existing ids.
    id_style:
        How to construct the core part of the id:
        - "datetime": datetime-based string (default).
        - "date":     date-only string.
        - "seq":      incremental integer (per project).
        - "rand":     random 10-character string.
    prefix:
        Optional prefix to prepend. If None, no prefix is added for
        "datetime", "date" and "rand". For "seq", the project name is
        used as prefix.
    suffix:
        Optional suffix to append. If None, no suffix is added.
    datetime_fmt:
        Datetime format string for "datetime" and "date" styles.
        By default "%y%m%d-%H%M" for "datetime".
    link_style:
        "kebab" for "-" join, "snake" for "_" join.

    Returns
    -------
    exp_id:
        A safe experiment id string.

    Notes
    -----
    - If both `prefix` and `suffix` are None and id_style="datetime",
      the default id is simply the datetime part, e.g. "250124-1530".
    - For "seq" style, the id is "{proj_slug}{sep}{NN}" where NN is a
      zero-padded integer. `prefix` is currently ignored for "seq".

    TODO: Improve "seq" style to better incorporate prefix/suffix and
          avoid scanning the whole directory for large result trees.
    """
    sep = _separator(link_style)

    if id_style == "seq":
        # Sequential ids: proj-01, proj-02, ...
        proj_slug = slugify(project)
        pattern = re.compile(rf"^{re.escape(proj_slug)}{re.escape(sep)}(\d+)$")
        max_n = 0
        if results_root.exists():
            for child in results_root.iterdir():
                if not child.is_dir():
                    continue
                m = pattern.match(child.name)
                if m:
                    n = int(m.group(1))
                    max_n = max(max_n, n)
        next_n = max_n + 1
        core = f"{proj_slug}{sep}{next_n:02d}"
        # We ignore prefix/suffix for seq for now.
        exp_id = core
        return ensure_safe_exp_id(exp_id)

    # Non-seq styles: build [prefix] + core + [suffix]
    if id_style == "datetime":
        core = datetime.now().strftime(datetime_fmt)
    elif id_style == "date":
        core = datetime.now().strftime(datetime_fmt)
    elif id_style == "rand":
        core = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    else:
        raise ValueError(f"Unknown id_style: {id_style}")

    parts = []

    if prefix is not None and prefix != "":
        parts.append(slugify(prefix))

    parts.append(core)

    if suffix is not None and suffix != "":
        parts.append(slugify(suffix))

    exp_id = sep.join(parts)
    return ensure_safe_exp_id(exp_id)
