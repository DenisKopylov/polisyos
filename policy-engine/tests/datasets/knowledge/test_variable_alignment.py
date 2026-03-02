from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.datasets.knowledge.variable_alignment import (
    AlignmentMethod,
    align_meta_analytic,
    align_semantic,
    load_seed_alignments,
)


def test_load_seed_alignments_contains_core_sources() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(path)
    assert len(alignments) > 0
    dataset_ids = {item.dataset_id for item in alignments}
    assert "WB_WGI" in dataset_ids
    assert "WB_WDI" in dataset_ids
    assert "WVS_W7" in dataset_ids


def test_seed_alignments_use_exact_method_only_for_phase_0b() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(path)
    assert all(item.method == AlignmentMethod.EXACT for item in alignments)


def test_semantic_alignment_not_implemented_in_phase_0b() -> None:
    with pytest.raises(NotImplementedError):
        align_semantic()


def test_meta_analytic_alignment_not_implemented_in_phase_0b() -> None:
    with pytest.raises(NotImplementedError):
        align_meta_analytic()
