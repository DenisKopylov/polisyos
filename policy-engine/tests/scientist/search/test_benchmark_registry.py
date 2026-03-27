from __future__ import annotations

import hashlib

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
        ),
        kind="scientist.test",
        media_type="application/json",
    )


def test_benchmark_registry_records_and_resolves_latest_by_split(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    first = _ref("1")
    second = _ref("2")

    registry.record("hidden_holdout", first, run_id="run-a", suite_id="suite-1")
    registry.record("hidden_holdout", second, run_id="run-a", suite_id="suite-1")

    refs = registry.get("hidden_holdout", run_id="run-a", suite_id="suite-1")

    assert refs == [second, first]
    assert registry.latest("hidden_holdout", run_id="run-a", suite_id="suite-1") == second


def test_benchmark_registry_normalizes_visible_alias_to_selection(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    selection = _ref("a")

    registry.record("visible", selection, run_id="run-a")

    assert registry.latest("selection", run_id="run-a") == selection


def test_benchmark_registry_resolves_family_bundle_by_scope(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    selection = _ref("a")
    hidden = _ref("b")

    registry.record(
        "selection",
        selection,
        run_id="run-a",
        loop_id="loop-a",
        family="causal_core",
        query_type="policy",
        estimator_name="cf",
        readiness_target="deployment_ready",
    )
    registry.record(
        "hidden_holdout",
        hidden,
        run_id="run-a",
        loop_id="loop-a",
        family="causal_core",
        query_type="policy",
        estimator_name="cf",
        readiness_target="deployment_ready",
    )

    bundle = registry.resolve_family_bundle(
        family="causal_core",
        claim_mode="estimation",
        run_id="run-a",
        loop_id="loop-a",
        query_type="policy",
        estimator_name="cf",
        readiness_target="deployment_ready",
    )

    assert bundle.selection_evaluation_ref == selection
    assert bundle.hidden_holdout_evaluation_ref == hidden
    assert registry.require_promotion_evidence(
        family="causal_core",
        claim_mode="estimation",
        run_id="run-a",
        loop_id="loop-a",
        query_type="policy",
        estimator_name="cf",
        readiness_target="deployment_ready",
    ) == []


def test_benchmark_registry_requires_rotating_challenge_for_non_core_family(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    selection = _ref("c")
    hidden = _ref("d")

    registry.record(
        "selection",
        selection,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
    )
    registry.record(
        "hidden_holdout",
        hidden,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
    )

    missing = registry.require_promotion_evidence(
        family="frontier_family",
        claim_mode="estimation",
        run_id="run-a",
        loop_id="loop-a",
    )

    assert missing == ["rotating_challenge_evaluation_refs"]


def test_benchmark_registry_requires_full_bounds_evidence_for_non_core_family(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    selection = _ref("e")
    sentinel = _ref("f")

    registry.record(
        "selection",
        selection,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
    )
    registry.record(
        "sentinel",
        sentinel,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
    )

    missing = registry.require_promotion_evidence(
        family="frontier_family",
        claim_mode="bounds",
        run_id="run-a",
        loop_id="loop-a",
    )

    assert missing == [
        "hidden_holdout_evaluation_ref",
        "rotating_challenge_evaluation_refs",
    ]


def test_benchmark_registry_resolve_family_bundle_dedupes_phase_d4_suites(tmp_path) -> None:
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    strategic_old = _ref("g")
    multiplicity = _ref("h")
    strategic_new = _ref("i")

    registry.record(
        "rotating_challenge",
        strategic_old,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
        suite_id="strategic_gaming_v1",
        rotation_group="phase_d4_v1",
        metadata={"challenge_suite_id": "strategic_gaming_v1", "rotation_group": "phase_d4_v1"},
    )
    registry.record(
        "rotating_challenge",
        multiplicity,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
        suite_id="multiplicity_disclosure_v1",
        rotation_group="phase_d4_v1",
        metadata={
            "challenge_suite_id": "multiplicity_disclosure_v1",
            "rotation_group": "phase_d4_v1",
        },
    )
    registry.record(
        "rotating_challenge",
        strategic_new,
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
        suite_id="strategic_gaming_v1",
        rotation_group="phase_d4_v1",
        metadata={"challenge_suite_id": "strategic_gaming_v1", "rotation_group": "phase_d4_v1"},
    )

    raw_refs = registry.get(
        "rotating_challenge",
        run_id="run-a",
        loop_id="loop-a",
        family="frontier_family",
    )
    bundle = registry.resolve_family_bundle(
        family="frontier_family",
        claim_mode="estimation",
        run_id="run-a",
        loop_id="loop-a",
    )

    assert raw_refs == [strategic_new, multiplicity, strategic_old]
    assert bundle.rotating_challenge_evaluation_refs == [strategic_new, multiplicity]
