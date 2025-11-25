# tests/test_logger.py
from __future__ import annotations

import json
from pathlib import Path

from expbox.logger import NullLogger, FileLogger


def test_null_logger_does_nothing(tmp_path: Path) -> None:
    logger = NullLogger()
    logger.log_metrics({"loss": 1.0}, step=0)
    logger.log_figure(fig=None, name="dummy")
    logger.log_artifact(tmp_path / "dummy.txt")
    logger.close()  # should not raise


def test_file_logger_writes_metrics(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    logger = FileLogger(log_dir)

    logger.log_metrics({"loss": 0.5}, step=1)
    logger.log_metrics({"loss": 0.3, "acc": 0.8}, step=2)
    logger.close()

    metrics_path = log_dir / "metrics.jsonl"
    assert metrics_path.exists()

    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])

    assert rec1["step"] == 1
    assert rec1["metrics"]["loss"] == 0.5
    assert rec2["step"] == 2
    assert rec2["metrics"]["acc"] == 0.8
