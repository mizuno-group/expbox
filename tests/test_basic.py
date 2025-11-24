# tests/test_basic.py
from __future__ import annotations

from pathlib import Path

from expbox import init, load


def test_init_and_load(tmp_path: Path) -> None:
    ctx = init(
        project="testproj",
        config={"lr": 1e-3},
        results_root=tmp_path,
        logger="none",
    )
    assert ctx.paths.root.exists()
    assert (ctx.paths.root / "meta.json").exists()

    ctx2 = load(ctx.exp_id, results_root=tmp_path)
    assert ctx2.exp_id == ctx.exp_id
    assert ctx2.config["lr"] == 1e-3
