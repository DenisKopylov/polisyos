from __future__ import annotations

from pathlib import Path

from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.datasets.knowledge.variable_alignment import load_seed_alignments


def _canonical_namespace() -> set[str]:
    namespace: set[str] = set()
    for root, children in CANONICAL_VARIABLES.items():
        namespace.add(root)
        for child in children:
            if child == "_root":
                continue
            namespace.add(f"{root}.{child}")
    return namespace


def test_seed_alignment_canonical_vars_are_in_canonical_namespace() -> None:
    alignments_path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )
    alignments = load_seed_alignments(alignments_path)
    namespace = _canonical_namespace()

    missing = sorted(
        {
            item.canonical_var
            for item in alignments
            if item.canonical_var and item.canonical_var not in namespace
        }
    )
    assert missing == []
