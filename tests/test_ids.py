# tests/test_ids.py
from __future__ import annotations

from pathlib import Path

from expbox.ids import generate_exp_id, ensure_safe_exp_id


def test_generate_default_datetime(tmp_path: Path) -> None:
    exp_id = generate_exp_id(
        project="MyProj",
        results_root=tmp_path,
        id_style="datetime",
    )
    # e.g. "250124-1530"
    assert "-" in exp_id
    assert " " not in exp_id
    ensure_safe_exp_id(exp_id)  # should not raise


def test_generate_with_prefix_suffix_kebab(tmp_path: Path) -> None:
    exp_id = generate_exp_id(
        project="MyProj",
        results_root=tmp_path,
        id_style="datetime",
        prefix="rbc",
        suffix="v1",
        link_style="kebab",
    )
    # rbc-YYMMDD-HHMM-v1
    assert exp_id.startswith("rbc-")
    assert "-v1" in exp_id


def test_generate_with_prefix_suffix_snake(tmp_path: Path) -> None:
    exp_id = generate_exp_id(
        project="MyProj",
        results_root=tmp_path,
        id_style="datetime",
        prefix="rbc",
        suffix="v1",
        link_style="snake",
    )
    # rbc_YYMMDD-HHMM_v1
    assert exp_id.startswith("rbc_")
    assert exp_id.endswith("_v1")


def test_generate_seq(tmp_path: Path) -> None:
    # first call -> proj-01
    exp_id1 = generate_exp_id(
        project="SeqProj",
        results_root=tmp_path,
        id_style="seq",
    )
    (tmp_path / exp_id1).mkdir()

    # second call -> proj-02
    exp_id2 = generate_exp_id(
        project="SeqProj",
        results_root=tmp_path,
        id_style="seq",
    )

    assert exp_id1 != exp_id2
    assert exp_id1.endswith("-01")
    assert exp_id2.endswith("-02")


def test_ensure_safe_exp_id_rejects_invalid() -> None:
    bad_ids = ["a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', " ", ""]
    for bid in bad_ids:
        try:
            ensure_safe_exp_id(bid)
        except ValueError:
            pass
        else:
            assert False, f"expected ValueError for {bid!r}"
