from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.contracts import ParetoBasisScope
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoRegistrySnapshot,
    ParetoView,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
    resolve_transfer_context,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema(
        candidate_id="candidate_policy",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_policy",
                domain=ProblemDomain.FISCAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="welfare",
                        metric_id="welfare_metric",
                        direction=OptimizationDirection.MAXIMIZE,
                    )
                ],
            ),
            policy_spec=PolicySpec(
                policy_id="policy_policy",
                interventions=[
                    InterventionSpec(
                        intervention_id="tax_cut",
                        kind="tax_policy",
                        target={
                            "kind": "predicate",
                            "field": "id",
                            "operator": SelectorOperator.EQUALS,
                            "value": "all",
                        },
                        schedule={"start_step": 0, "duration_steps": 2},
                        params={"rate": Decimal("0.1")},
                    )
                ],
                parameters=[
                    ParameterSpec(
                        param_id="tax_rate",
                        intervention_id="tax_cut",
                        param_path="rate",
                        default_value=Decimal("0.1"),
                    )
                ],
            ),
            model_spec=ModelSpec(
                model_id="model_policy",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        target_population=TargetPopulationSpec(
            population_id="population_policy",
            description="General population",
            geography="national",
        ),
        metadata={"policy_family": "core_family"},
    )


def _candidate_ref(label: str) -> ArtifactRef:
    """Build a typed ref with a selected manifest profile for catalog controls."""
    artifact_digest = hashlib.sha256(label.encode()).hexdigest()
    profile_digest = hashlib.sha256(f"profile:{label}".encode()).hexdigest()
    return ArtifactRef(
        artifact_id=ArtifactID(f"sha256:{artifact_digest}"),
        kind="scientist.policy_candidate",
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{profile_digest}",
    )


def _evaluation_vector(
    candidate: PolicyCandidateSchema, *, employment: float | None = None
) -> PolicyEvaluationVector:
    primary = {
        "policy_value": ObjectiveChannelValue(
            name="policy_value",
            kind=ObjectiveKind.PRIMARY,
            value=1.2,
            direction=ObjectiveDirection.MAXIMIZE,
        )
    }
    if employment is not None:
        primary["employment"] = ObjectiveChannelValue(
            name="employment",
            kind=ObjectiveKind.PRIMARY,
            value=employment,
            direction=ObjectiveDirection.MAXIMIZE,
            source="controlled-test-evaluation",
        )
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary=primary,
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        secondary={},
        penalties={},
        feasible=True,
        blocking_reasons=[],
        metadata={"policy_family": "core_family", "candidate_hash": candidate.candidate_hash()},
    )


def test_publish_transfer_surface_produces_seed_only_bundle(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )

    registry.update(
        "loop-source",
        candidate_hash=candidate.candidate_hash(),
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )

    bundle = registry.get_seed_bundle(target, max_seeds=3)
    warm_start = registry.build_warm_start_evaluations(target, max_seeds=3)

    assert bundle.entries
    assert all(entry.seed_only for entry in bundle.entries)
    assert bundle.cross_domain_seed_count == 1
    assert warm_start
    assert warm_start[0]["metadata"]["seed_only"] is True
    assert registry.get_snapshot("loop-target").entries == {}


def test_same_domain_seed_sorting_precedes_cross_domain(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    registry.update(
        "loop-fiscal",
        candidate_hash=f"{candidate.candidate_hash()}::fiscal",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_fiscal"}),
        candidate_id="candidate_fiscal",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop-fiscal",
            tenant_hash="tenant-a",
        ),
    )
    registry.update(
        "loop-labor",
        candidate_hash=f"{candidate.candidate_hash()}::labor",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_labor"}),
        candidate_id="candidate_labor",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-labor",
            tenant_hash="tenant-a",
        ),
    )

    bundle = registry.get_seed_bundle(
        TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-target",
            tenant_hash="tenant-a",
        ),
        max_seeds=5,
    )

    assert len(bundle.entries) >= 2
    assert bundle.entries[0].domain == "labor"


def test_partial_registry_persists_status_withholds_rank_and_keeps_candidate_seed(
    tmp_path: Path,
) -> None:
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-partial",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )
    declared_basis = ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:partial-pareto-basis.v1",
    )
    measured_candidate = _candidate()
    measured_hash = measured_candidate.candidate_hash()
    registry.update(
        source.run_id,
        candidate_hash=measured_hash,
        evaluation=_evaluation_vector(measured_candidate, employment=0.7),
        seed_payload=measured_candidate.model_dump(mode="json"),
        transfer_context=source,
        objective_basis_by_view={ParetoView.GLOBAL_FEASIBLE.value: declared_basis},
    )
    complete_snapshot = registry.get_snapshot(source.run_id, transfer_context=source)
    assert complete_snapshot.view_assessments[ParetoView.GLOBAL_FEASIBLE.value].status == "complete"
    assert ParetoView.GLOBAL_FEASIBLE.value in complete_snapshot.hypervolume_by_view

    missing_candidate = _candidate().model_copy(
        update={"candidate_id": "candidate_missing_employment"}
    )
    missing_hash = missing_candidate.candidate_hash()
    registry.update(
        source.run_id,
        candidate_hash=missing_hash,
        evaluation=_evaluation_vector(missing_candidate),
        seed_payload=missing_candidate.model_dump(mode="json"),
        transfer_context=source,
        objective_basis_by_view={ParetoView.GLOBAL_FEASIBLE.value: declared_basis},
    )

    fresh_reader = ParetoRegistry(registry_root)
    snapshot = fresh_reader.get_snapshot(source.run_id, transfer_context=source)
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    assessment = projection.assessment
    assert assessment.status == "partial"
    assert assessment.input_count == 2
    assert assessment.assessed_count == 1
    assert assessment.unassessed_candidate_hashes == [missing_hash]
    assert set(assessment.missing_coordinate_ids_by_candidate_hash) == {missing_hash}
    assert projection.candidate_frontier_hashes == (measured_hash,)
    assert projection.ranked_frontier_hashes == ()
    assert projection.unassessed_candidate_hashes == (missing_hash,)
    assert ParetoView.GLOBAL_FEASIBLE.value not in snapshot.hypervolume_by_view

    catalog = fresh_reader._load_snapshot(fresh_reader._catalog_path(source))
    catalog_projection = catalog.project_view(ParetoView.GLOBAL_FEASIBLE)
    catalog_entry_ids = tuple(sorted(catalog.entries))
    assert len(catalog_entry_ids) == 1
    catalog_entry_id = catalog_entry_ids[0]
    assert catalog.schema_version == "3.0"
    assert catalog.entries[catalog_entry_id].candidate_hash == measured_hash
    assert catalog.entries[catalog_entry_id].source_loop_id == source.run_id
    assert catalog_projection.assessment.status == "basis_limited"
    assert catalog_projection.assessment.basis_scope.scope == "not_established"
    assert catalog_projection.assessment.input_count == 1
    assert catalog_projection.eligible_candidate_hashes == (measured_hash,)
    assert catalog_projection.assessment.unassessed_candidate_hashes == [measured_hash]
    assert catalog_projection.candidate_frontier_hashes == (measured_hash,)
    assert catalog_projection.ranked_frontier_hashes == ()
    assert catalog_projection.unassessed_candidate_hashes == (measured_hash,)
    assert not catalog.hypervolume_by_view

    seed_bundle = fresh_reader.get_seed_bundle(target, max_seeds=3)
    assert [entry.candidate_hash for entry in seed_bundle.entries] == [measured_hash]
    assert all(entry.seed_only for entry in seed_bundle.entries)


@pytest.mark.parametrize("unknown_version", ["0.9", "3.1", "4.0", "9.9"])
def test_pareto_fresh_reader_refuses_unknown_persisted_schema(
    tmp_path: Path, unknown_version: str
) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    path = registry._snapshot_path("unknown-schema")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": unknown_version,
                "loop_id": "unknown-schema",
                "task_family": "policy",
                "domain": "fiscal",
                "entries": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.get_snapshot("unknown-schema")

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY


def test_pareto_writer_refuses_malformed_context_before_persist(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.update(
            "loop-invalid",
            candidate_hash=candidate.candidate_hash(),
            evaluation=_evaluation_vector(candidate),
            transfer_context=[],  # type: ignore[arg-type]
        )

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    assert list((tmp_path / "registry").rglob("*.json")) == []


def test_pareto_consumer_refuses_malformed_context_before_catalog_scan(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.get_seed_bundle({"tenant_hash": []})  # type: ignore[arg-type]

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE


def _publish_source_for_legacy_reader_test(
    registry: ParetoRegistry, source: TransferContext
) -> None:
    candidate = _candidate()
    registry.update(
        source.run_id,
        candidate_hash=candidate.candidate_hash(),
        evaluation=_evaluation_vector(candidate),
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )


@pytest.mark.parametrize("legacy_version", ["1.0", "2.0", "2.1"])
def test_pareto_parser_recognizes_but_fresh_reader_refuses_unbound_history(
    tmp_path: Path, legacy_version: str
) -> None:
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="legacy-run",
        tenant_hash="tenant-a",
    )
    _publish_source_for_legacy_reader_test(registry, source)
    snapshot_path = registry._snapshot_path(source.run_id)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["source_scope"]["tenant_hash"] == "tenant-a"
    payload.pop("source_scope")
    payload["schema_version"] = legacy_version
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    parsed = registry._load_snapshot(snapshot_path)
    assert parsed.schema_version == legacy_version
    assert parsed.source_scope is None

    fresh_reader = ParetoRegistry(registry_root)
    with pytest.raises(TransferScopeRefusedError) as refused:
        fresh_reader.get_snapshot(source.run_id, transfer_context=source)
    assert refused.value.refusals[0].reason is TransferScopeRefusalReason.SOURCE_BINDING_MISSING


def test_pareto_fresh_seed_reader_withholds_unbound_historical_catalog(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="catalog-source",
        tenant_hash="tenant-a",
    )
    _publish_source_for_legacy_reader_test(registry, source)
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="fresh-target",
        tenant_hash="tenant-a",
    )
    valid_control = ParetoRegistry(registry_root).get_seed_bundle(target)
    assert valid_control.entries

    catalog_path = registry._catalog_path(source)
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert payload["entries"]
    assert payload["source_scope"]["tenant_hash"] == "tenant-a"
    payload.pop("source_scope")
    payload["schema_version"] = "2.1"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    bundle = ParetoRegistry(registry_root).get_seed_bundle(target)
    assert not bundle.entries
    assert any(
        refusal.reason is TransferScopeRefusalReason.SOURCE_BINDING_MISSING
        for refusal in bundle.scope_refusals
    )


def test_catalog_projection_and_seed_preserve_source_occurrence_identity(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root)
    candidate = _candidate()
    candidate_hash = candidate.candidate_hash()
    base_evaluation = _evaluation_vector(candidate)
    source_contexts = [
        TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id=run_id,
            tenant_hash="tenant-a",
        )
        for run_id in ("loop-one", "loop-two", "a", "a:b")
    ]
    candidate_hashes = (candidate_hash, candidate_hash, "b:c", "c")
    candidate_refs = tuple(_candidate_ref(f"source-{index}") for index in range(4))
    seed_payload = candidate.model_dump(mode="json")

    for source, source_candidate_hash, candidate_ref in zip(
        source_contexts, candidate_hashes, candidate_refs, strict=True
    ):
        evaluation = base_evaluation.model_copy(
            update={
                "metadata": {**base_evaluation.metadata, "candidate_hash": source_candidate_hash}
            }
        )
        registry.update(
            source.run_id,
            candidate_hash=source_candidate_hash,
            evaluation=evaluation,
            candidate_id=candidate.candidate_id,
            candidate_ref=candidate_ref,
            seed_payload=seed_payload,
            transfer_context=source,
        )

    fresh_reader = ParetoRegistry(registry_root)
    first_source = source_contexts[0]
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )
    catalog = fresh_reader._load_snapshot(fresh_reader._catalog_path(first_source))
    assert len(catalog.entries) == 4
    # The old delimiter join aliases these two distinct source/hash pairs.
    assert f"{source_contexts[2].run_id}:{candidate_hashes[2]}" == (
        f"{source_contexts[3].run_id}:{candidate_hashes[3]}"
    )
    assert len(set(catalog.entries)) == 4

    projection = catalog.project_view(ParetoView.GLOBAL_FEASIBLE)
    logical_candidate_hashes = tuple(sorted(set(candidate_hashes)))
    assert projection.assessment.status == "basis_limited"
    assert projection.assessment.input_count == len(logical_candidate_hashes) == 3
    assert projection.assessment.assessed_count == 0
    assert projection.eligible_candidate_hashes == logical_candidate_hashes
    assert projection.candidate_frontier_hashes == logical_candidate_hashes
    assert projection.ranked_frontier_hashes == ()
    assert projection.unassessed_candidate_hashes == logical_candidate_hashes
    assert not catalog.hypervolume_by_view

    catalog_occurrences = {
        (
            entry.source_loop_id,
            entry.candidate_hash,
            entry.candidate_id,
            entry.candidate_ref.model_dump_json() if entry.candidate_ref else None,
        )
        for entry in catalog.entries.values()
    }
    expected_occurrences = {
        (source.run_id, source_hash, candidate.candidate_id, ref.model_dump_json())
        for source, source_hash, ref in zip(
            source_contexts, candidate_hashes, candidate_refs, strict=True
        )
    }
    assert catalog_occurrences == expected_occurrences

    seed_bundle = fresh_reader.get_seed_bundle(target, max_seeds=10)
    seed_occurrences = {
        (
            entry.source_loop_id,
            entry.candidate_hash,
            entry.candidate_id,
            entry.candidate_ref.model_dump_json() if entry.candidate_ref else None,
            entry.seed_only,
        )
        for entry in seed_bundle.entries
    }
    expected_seed_occurrences = {
        (source.run_id, source_hash, candidate.candidate_id, ref.model_dump_json(), True)
        for source, source_hash, ref in zip(
            source_contexts, candidate_hashes, candidate_refs, strict=True
        )
    }
    assert seed_occurrences == expected_seed_occurrences

    # Historical delimiter keys remain readable only when their stored source/hash agree.
    legacy_sources = source_contexts[:2]
    legacy_entries = {
        f"{entry.source_loop_id}:{entry.candidate_hash}": entry
        for entry in catalog.entries.values()
        if entry.source_loop_id in {source.run_id for source in legacy_sources}
    }
    legacy_ids = sorted(legacy_entries)
    legacy_assessment = catalog.view_assessments[ParetoView.GLOBAL_FEASIBLE.value].model_copy(
        update={"unassessed_candidate_hashes": legacy_ids, "input_count": 2}
    )
    legacy_catalog = catalog.model_copy(
        update={
            "schema_version": "2.0",
            "entries": legacy_entries,
            "frontiers": {ParetoView.GLOBAL_FEASIBLE.value: legacy_ids},
            "view_assessments": {ParetoView.GLOBAL_FEASIBLE.value: legacy_assessment},
        }
    )
    legacy_projection = legacy_catalog.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert legacy_projection.assessment.status == "basis_limited"
    assert legacy_projection.eligible_candidate_hashes == (candidate_hashes[0],)
    assert legacy_projection.assessment.input_count == 1
    assert legacy_projection.assessment.unassessed_candidate_hashes == [candidate_hashes[0]]
    assert legacy_projection.candidate_frontier_hashes == (candidate_hashes[0],)

    # Keep every status/frontier marker while replacing only the selected source key.
    bad_source = source_contexts[0]
    bad_entry_id = next(
        key for key, entry in catalog.entries.items() if entry.source_loop_id == bad_source.run_id
    )
    bad_key = f"{bad_entry_id}:wrong"
    bad_entries = dict(catalog.entries)
    bad_entry = bad_entries.pop(bad_entry_id)
    assert bad_entry.source_loop_id == bad_source.run_id
    bad_entries[bad_key] = bad_entry
    bad_catalog = catalog.model_copy(update={"entries": bad_entries})
    fresh_reader._write_catalog_snapshot(first_source, bad_catalog)
    bad_reader = ParetoRegistry(registry_root)
    bad_snapshot = bad_reader._load_snapshot(bad_reader._catalog_path(first_source))
    bad_projection = bad_snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert bad_projection.assessment.status == "legacy_limited"
    assert bad_projection.candidate_frontier_hashes == ()
    bad_seeds = bad_reader.get_seed_bundle(target, max_seeds=10)
    expected_bad_seed_sources = {
        source.run_id for source in source_contexts if source.run_id != bad_source.run_id
    }
    assert {entry.source_loop_id for entry in bad_seeds.entries} == expected_bad_seed_sources

    # A correct key with a foreign unit scope also withholds projection and seed use.
    scope_source = source_contexts[1]
    scope_key = next(
        key for key, entry in catalog.entries.items() if entry.source_loop_id == scope_source.run_id
    )
    scoped_entries = dict(catalog.entries)
    scoped_entries[scope_key] = scoped_entries[scope_key].model_copy(update={"domain": "other"})
    wrong_scope_catalog = catalog.model_copy(update={"entries": scoped_entries})
    fresh_reader._write_catalog_snapshot(first_source, wrong_scope_catalog)
    scope_reader = ParetoRegistry(registry_root)
    scope_snapshot = scope_reader._load_snapshot(scope_reader._catalog_path(first_source))
    scope_projection = scope_snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert scope_projection.assessment.status == "legacy_limited"
    assert scope_projection.candidate_frontier_hashes == ()
    scope_seeds = scope_reader.get_seed_bundle(target, max_seeds=10)
    assert scope_seeds.entries == []
    assert any(
        refusal.reason is TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH
        for refusal in scope_seeds.scope_refusals
    )


def test_versioned_pareto_scope_keeps_none_global_and_foreign_distinct(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    registry = ParetoRegistry(root)
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    sources = [
        TransferContext(task_family="policy", domain="fiscal", run_id=f"run-{i}", tenant_hash=value)
        for i, value in enumerate((None, "", "global", "tenant-b", "x" * 300))
    ]
    for source in sources:
        registry.update(
            source.run_id,
            candidate_hash=f"{candidate.candidate_hash()}-{source.run_id}",
            evaluation=evaluation.model_copy(update={"candidate_id": source.run_id}),
            seed_payload=candidate.model_dump(mode="json"),
            transfer_context=source,
        )
    fresh = ParetoRegistry(root)
    partitions = {source.tenant_hash: fresh._catalog_path(source) for source in sources}
    assert len(set(partitions.values())) == 5
    for index, source in enumerate(sources):
        isolated = ParetoRegistry(tmp_path / f"isolated-{index}")
        isolated.update(
            source.run_id,
            candidate_hash=f"{candidate.candidate_hash()}-{source.run_id}",
            evaluation=evaluation.model_copy(update={"candidate_id": source.run_id}),
            seed_payload=candidate.model_dump(mode="json"),
            transfer_context=source,
        )
        bundle = ParetoRegistry(tmp_path / f"isolated-{index}").get_seed_bundle(
            TransferContext(
                task_family="policy",
                domain="labor",
                run_id="target",
                tenant_hash=source.tenant_hash,
            )
        )
        assert not bundle.scope_refusals
        assert bundle.entries
        assert all(entry.source_loop_id == source.run_id for entry in bundle.entries)
    mixed = fresh.get_seed_bundle(
        TransferContext(
            task_family="policy", domain="labor", run_id="target-none", tenant_hash=None
        )
    )
    assert mixed.entries
    assert {entry.source_loop_id for entry in mixed.entries} == {"run-0"}
    assert any(
        item.reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        for item in mixed.scope_refusals
    )
    refused = fresh.get_seed_bundle(
        TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="target-unknown",
            tenant_hash="not-present",
        )
    )
    assert refused.entries == []
    assert any(
        item.reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        for item in refused.scope_refusals
    )


def test_pareto_writer_and_fresh_reader_reconcile_access_scope(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    expected = anonymize_tenant_id("tenant-a")
    access = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    token = set_current_access_scope(access)
    try:
        source = resolve_transfer_context(
            transfer_context=TransferContext(
                task_family="policy",
                domain="fiscal",
                run_id="authenticated-source",
                tenant_hash=expected,
            )
        )
        registry.update(
            source.run_id,
            candidate_hash=candidate.candidate_hash(),
            evaluation=_evaluation_vector(candidate),
            seed_payload=candidate.model_dump(mode="json"),
            transfer_context=source,
        )
        snapshot = registry.get_snapshot(source.run_id, transfer_context=source)
        assert snapshot.source_scope is not None
        assert snapshot.source_scope.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        assert (
            next(iter(snapshot.entries.values())).source_scope_status
            is TransferTenantScopeStatus.AUTHENTICATED
        )
        tampered = snapshot.model_copy(deep=True)
        next(
            iter(tampered.entries.values())
        ).source_scope_status = TransferTenantScopeStatus.UNKNOWN
        with pytest.raises(TransferScopeRefusedError) as row_mismatch:
            registry.publish_transfer_surface(
                source.run_id,
                transfer_context=source,
                snapshot=tampered,
            )
        assert (
            row_mismatch.value.refusals[0].reason is TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH
        )
    finally:
        reset_current_access_scope(token)

    wrong_access = AccessScope.for_service(
        tenant_id="tenant-b",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    wrong_token = set_current_access_scope(wrong_access)
    try:
        with pytest.raises(TransferScopeRefusedError) as mismatch:
            registry.get_seed_bundle(
                TransferContext(
                    task_family="policy",
                    domain="fiscal",
                    run_id="foreign-reader",
                    tenant_hash=expected,
                )
            )
        assert (
            mismatch.value.refusals[0].reason
            is TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
        )
    finally:
        reset_current_access_scope(wrong_token)


def test_pareto_local_loop_id_reads_require_the_matching_tenant(tmp_path: Path) -> None:
    registry = ParetoRegistry(tmp_path / "local")
    candidate = _candidate()
    source = TransferContext(
        task_family="policy", domain="fiscal", run_id="loop-1", tenant_hash="tenant-a"
    )
    registry.update(
        source.run_id,
        candidate_hash=candidate.candidate_hash(),
        evaluation=_evaluation_vector(candidate),
        transfer_context=source,
    )
    fresh = ParetoRegistry(tmp_path / "local")
    assert fresh.get_frontier("loop-1", transfer_context=source)
    with pytest.raises(TransferScopeRefusedError):
        fresh.get_frontier(
            "loop-1",
            transfer_context=TransferContext(
                task_family="policy", domain="fiscal", run_id="reader", tenant_hash="tenant-b"
            ),
        )


def test_pareto_fresh_reader_refuses_path_body_mismatch_and_legacy_namespace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "registry"
    registry = ParetoRegistry(root)
    candidate = _candidate()
    source = TransferContext(
        task_family="policy", domain="fiscal", run_id="source", tenant_hash="global"
    )
    registry.update(
        source.run_id,
        candidate_hash=candidate.candidate_hash(),
        evaluation=_evaluation_vector(candidate),
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )
    catalog_path = registry._catalog_path(source)
    payload = json.loads(catalog_path.read_text())
    payload["source_scope"]["tenant_hash"] = None
    catalog_path.write_text(json.dumps(payload))
    fresh = ParetoRegistry(root).get_seed_bundle(source.model_copy(update={"run_id": "target"}))
    assert fresh.entries == []
    assert fresh.scope_refusals[0].reason is TransferScopeRefusalReason.PATH_BODY_MISMATCH

    legacy_root = tmp_path / "legacy"
    legacy_registry = ParetoRegistry(legacy_root)
    legacy_path = legacy_root / "catalog" / "global" / "policy" / "fiscal" / "pareto_registry.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps(
            {
                "schema_version": "2.1",
                "loop_id": "catalog::policy:fiscal",
                "task_family": "policy",
                "domain": "fiscal",
                "entries": {},
            }
        )
    )
    malformed_path = legacy_root / "catalog" / "v2" / "not-a-digest" / "pareto_registry.json"
    malformed_path.parent.mkdir(parents=True)
    malformed_path.write_text("{}")
    legacy = ParetoRegistry(legacy_root).get_seed_bundle(
        TransferContext(task_family="policy", domain="fiscal", run_id="target", tenant_hash=None)
    )
    assert legacy.entries == []
    assert any(
        item.reason is TransferScopeRefusalReason.LEGACY_PATH_UNBOUND
        for item in legacy.scope_refusals
    )
    assert any(
        item.reason is TransferScopeRefusalReason.MALFORMED_PATH for item in legacy.scope_refusals
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(math.nan, id="nan"),
        pytest.param(math.inf, id="positive-infinity"),
        pytest.param(-math.inf, id="negative-infinity"),
    ],
)
def test_registry_refuses_non_finite_metrics_before_persisted_json(
    tmp_path: Path, invalid_value: float
) -> None:
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root)
    candidate = _candidate()
    candidate_hash = candidate.candidate_hash()
    evaluation = _evaluation_vector(candidate)
    registry.update(
        "loop-finite",
        candidate_hash=candidate_hash,
        evaluation=evaluation,
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop-finite",
            tenant_hash="tenant-a",
        ),
    )
    snapshot_path = registry._snapshot_path("loop-finite")
    prior_bytes = snapshot_path.read_bytes()
    invalid_primary = dict(evaluation.primary)
    invalid_primary["policy_value"] = invalid_primary["policy_value"].model_copy(
        update={"value": invalid_value}
    )
    invalid_evaluation = evaluation.model_copy(update={"primary": invalid_primary})

    with pytest.raises(
        ValueError,
        match=r"non-finite Pareto metric .*primary\.policy_value\.value",
    ):
        registry.update(
            "loop-finite",
            candidate_hash=f"{candidate_hash}-invalid",
            evaluation=invalid_evaluation,
            seed_payload=candidate.model_dump(mode="json"),
        )

    assert snapshot_path.read_bytes() == prior_bytes
    persisted = ParetoRegistry(registry_root).get_snapshot(
        "loop-finite",
        transfer_context=TransferContext(
            task_family="policy", domain="fiscal", run_id="loop-finite", tenant_hash="tenant-a"
        ),
    )
    assert set(persisted.entries) == {candidate_hash}


def test_registry_refuses_non_finite_hypervolume_before_file_creation(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    snapshot = ParetoRegistrySnapshot(
        loop_id="invalid-hypervolume",
        hypervolume_by_view={ParetoView.GLOBAL_FEASIBLE.value: math.inf},
    )

    with pytest.raises(ValueError, match="non-finite Pareto hypervolume"):
        ParetoRegistry._write_json(path, snapshot)

    assert not path.exists()


def test_update_uses_typed_task_scope_and_rejects_empty_declaration(tmp_path) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    declared = TransferContext(task_family="discovery", domain="fiscal", run_id="loop-discovery")

    registry.update(
        "loop-discovery",
        candidate_hash=candidate.candidate_hash(),
        evaluation=_evaluation_vector(candidate),
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=declared,
    )
    assert registry.get_snapshot("loop-discovery").task_family == "discovery"

    with pytest.raises(TransferScopeRefusedError):
        registry.update(
            "loop-invalid",
            candidate_hash=candidate.candidate_hash(),
            evaluation=_evaluation_vector(candidate),
            seed_payload=candidate.model_dump(mode="json"),
            task_family="",
            transfer_context=TransferContext(
                task_family="policy", domain="fiscal", run_id="loop-invalid"
            ),
        )
