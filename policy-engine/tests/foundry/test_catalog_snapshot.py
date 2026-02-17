from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot


def test_method_catalog_snapshot_contains_stable_entries() -> None:
    ensure_causal_methods_registered()
    first = build_method_catalog_snapshot(run_id="R_catalog")
    second = build_method_catalog_snapshot(run_id="R_catalog")

    first_fqns = [entry.fqn for entry in first.entries]
    second_fqns = [entry.fqn for entry in second.entries]

    assert first_fqns
    assert first_fqns == second_fqns
    assert first.snapshot_id == second.snapshot_id
