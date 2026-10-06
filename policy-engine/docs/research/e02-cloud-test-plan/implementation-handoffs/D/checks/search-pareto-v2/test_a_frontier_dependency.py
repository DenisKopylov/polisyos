"""Explicit red native recipes for the unapplied A supplier/export boundary."""

# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.methods.search.contracts import ParetoBasisScope
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyFrontierReport,
    PolicyFrontierReportRef,
    _persist_model,
    load_policy_frontier_report,
)
from tests.unit.remediation.test_opt_01_hypervolume_consumers import vector
from tests.unit.scientist.policy_design.test_phase_b_output import _candidate


def produced_report(tmp_path: Path, values: Sequence[float]) -> PolicyFrontierReport:
    registry = ParetoRegistry(tmp_path / "registry")
    basis = ParetoBasisScope(
        scope="declared", coordinate_ids=["policy_value", "employment"], basis_ref="fixture:axes.v1"
    )
    for i, value in enumerate(values, start=1):
        registry.update(
            "fixture",
            candidate_hash=f"sha256:{i:064x}",
            evaluation=vector(str(i), value),
            objective_basis_by_view={"global_feasible": basis},
        )
    candidate = _candidate()
    source = PolicyArtifactBuildInput(
        loop_id="fixture",
        run_id="fixture",
        candidate=candidate,
        candidate_hash=candidate.candidate_hash(),
        pareto_snapshot=registry.get_snapshot("fixture"),
    )
    return PolicyArtifactBuilder()._build_frontier_report(source)


def test_actual_builder_cas_reader_retains_unavailable_indicator_reason(tmp_path: Path) -> None:
    report = produced_report(tmp_path, (-1e308, 1e308))
    store = FileSystemCAS(tmp_path / "CAS")
    ref = _persist_model(
        store,
        report,
        kind="fixture.policy.frontier_report",
        schema_name="PolicyFrontierReport",
        ref_cls=PolicyFrontierReportRef,
        inputs=[],
    )
    reopened = load_policy_frontier_report(store, ref)
    assert reopened.metadata["hypervolume_by_view"]["global_feasible"] is None
    assert (
        reopened.metadata["hypervolume_assessments"]["global_feasible"]["reason"]
        == "non_finite_derived_hypervolume"
    )


def test_registry_declaration_does_not_supply_independent_source_denominator(
    tmp_path: Path,
) -> None:
    report = produced_report(tmp_path, (1, 2))
    # The producer supplied no independently reconciled run/tenant/cell universe.
    assert report.global_frontier == [], (
        "registry-derived source_feasible is the same denominator, not independent input"
    )
