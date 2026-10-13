from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine.builders.contracts import StageBuildResult
from polisyos.data_forge.domains.ukraine.demography import (
    load_demography_artifacts as load_domain_demography_artifacts,
)
from polisyos.data_forge.domains.ukraine.demography import (
    load_donor_pool as load_domain_donor_pool,
)
from polisyos.data_forge.domains.ukraine.demography import (
    load_reconciled_targets as load_domain_reconciled_targets,
)
from polisyos.data_forge.domains.ukraine.demography import (
    load_transition_priors as load_domain_transition_priors,
)
from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
    InventoryBuildRequest,
    SourceFact,
    SourceSemanticClaims,
)
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import (
    StageId,
    build_default_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator
from polisyos.data_forge.read_api.ukraine import (
    DemographyRoleProjection,
    DemographySourceRequest,
    InventorySourceRequest,
    SourceResolutionRefusalError,
    VerifiedUkraineStageArtifacts,
    build_static_aging_state,
    load_demography_artifacts,
    load_demography_candidate_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
    load_verified_stage_artifacts,
)
from polisyos.foundry.methods.catalog.simulation.demography import (
    StaticAgingSimulationEstimator,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


_FACT_KEYS = (
    "source_owner_id",
    "source_object_id",
    "source_version",
    "source_profile",
    "observed_at",
    "state_domain",
    "state_mapping",
    "state_refinement",
    "ordered_state_ids",
    "target_measure",
    "target_unit",
    "target_period",
    "target_mapping",
    "entrant_measure",
    "entrant_unit",
    "entrant_period",
    "entrant_mapping",
    "prior_origin_axis",
    "prior_destination_axis",
    "prior_derivation",
    "prior_unit",
    "prior_period",
    "prior_mapping",
    "donor_absence_reason",
)


def _claims(
    state_ids: list[str],
    *,
    donor_disposition: Literal["present", "intentionally_absent", "not_established"] = "present",
) -> SourceSemanticClaims:
    facts = {
        name: SourceFact(value=f"fixture:{name}", provenance="consumer_asserted")
        for name in _FACT_KEYS
    }
    facts["ordered_state_ids"] = SourceFact(
        value=state_ids,
        provenance="consumer_asserted",
    )
    facts["prior_origin_axis"] = SourceFact(
        value=state_ids,
        provenance="consumer_asserted",
    )
    facts["prior_destination_axis"] = SourceFact(
        value=state_ids,
        provenance="consumer_asserted",
    )
    facts["donor_absence_reason"] = SourceFact(
        value=(
            "fixture:donor-not-applicable"
            if donor_disposition == "intentionally_absent"
            else None
        ),
        provenance=(
            "consumer_asserted"
            if donor_disposition == "intentionally_absent"
            else "not_established"
        ),
    )
    return SourceSemanticClaims(
        facts=facts,
        donor_disposition=donor_disposition,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _make_candidate(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    materialized_state_ids: list[str] | None = None,
    donor_disposition: Literal["present", "intentionally_absent", "not_established"] = "present",
    member_overrides: dict[str, dict[str, object]] | None = None,
    include_entrant_totals: bool = True,
) -> tuple[Path, Path, FileSystemCAS]:
    state_ids = ["state:a", "state:b"]
    materialized_state_ids = materialized_state_ids or state_ids
    member_overrides = member_overrides or {}
    if set(member_overrides).difference({"targets", "priors", "donor"}):
        raise ValueError("member_overrides contains an unknown demographic role")
    if "donor" in member_overrides and donor_disposition != "present":
        raise ValueError("donor member overrides require a present donor role")
    build_root = tmp_path / "build"
    upstream_root = tmp_path / "upstream"
    source_dir = upstream_root / "d1-output"
    targets_path = source_dir / "target_materialized.json"
    priors_path = source_dir / "prior_materialized.json"
    donor_path = source_dir / "donor_materialized.json"
    targets_payload = {
        "state_ids": materialized_state_ids,
        "target_state_totals": [10.0, 20.0],
        "metadata": {"fixture_profile": "candidate-only"},
    }
    if include_entrant_totals:
        targets_payload["entrant_state_totals"] = [0.0, 0.0]
    targets_payload.update(member_overrides.get("targets", {}))
    _write_json(targets_path, targets_payload)
    priors_payload: dict[str, object] = {
        "transition_prior_matrix": [[0.8, 0.2], [0.1, 0.9]],
        "allowed_transition_mask": [[True, True], [False, True]],
    }
    priors_payload.update(member_overrides.get("priors", {}))
    _write_json(priors_path, priors_payload)
    if donor_disposition == "present":
        donor_payload: dict[str, object] = {
            "donor_weights": [0.25, 0.75],
            "donor_state_index": [0, 1],
            "donor_record_index": [101, 102],
        }
        donor_payload.update(member_overrides.get("donor", {}))
        _write_json(donor_path, donor_payload)
    upstream_manifest_path = upstream_root / "build_run_d1.json"
    source_outputs = [
        ArtifactRecord.from_path(targets_path),
        ArtifactRecord.from_path(priors_path),
    ]
    if donor_disposition == "present":
        source_outputs.append(ArtifactRecord.from_path(donor_path))
    write_manifest(
        upstream_manifest_path,
        BuildRunManifest(
            run_id="fixture-d1-run",
            stage_id=StageId.D1,
            status="completed",
            started_at="2026-10-12T00:00:00+00:00",
            finished_at="2026-10-12T00:01:00+00:00",
            outputs=source_outputs,
        ),
    )
    recipe = InventoryBuildRequest(
        upstream_manifest_path=upstream_manifest_path,
        upstream_allowed_root=upstream_root,
        upstream_expected_stage=StageId.D1.value,
        role_outputs={
            "targets": targets_path.name,
            "priors": priors_path.name,
            **(
                {"donor": donor_path.name}
                if donor_disposition == "present"
                else {}
            ),
        },
        source_claims=_claims(
            state_ids,
            donor_disposition=donor_disposition,
        ),
    )
    request_path = tmp_path / "inventory-request.json"
    request_path.write_text(recipe.model_dump_json(indent=2), encoding="utf-8")
    config = build_default_pipeline_config(root=build_root)
    config.demography_inventory_request_path = request_path
    monkeypatch.setattr(
        "polisyos.data_forge.domains.ukraine.orchestrator.assert_server_execution_allowed",
        lambda _server: None,
    )
    orchestrator = UkraineDataOrchestrator(config=config, workspace_root=tmp_path)
    monkeypatch.setattr(orchestrator, "_ensure_part_a_gate", lambda: None)
    monkeypatch.setattr(
        orchestrator,
        "_ensure_previous_stage_manifests",
        lambda _stage_id: None,
    )
    summary = orchestrator.build_stage(StageId.DEMOGRAPHY_SOURCE_INVENTORY)
    assert summary.status == "completed"
    store = FileSystemCAS(config.build_root.resolved_cas_root)
    return orchestrator.stage_manifest_path(StageId.DEMOGRAPHY_SOURCE_INVENTORY), build_root, store


@pytest.mark.parametrize(
    "donor_disposition",
    ["present", "intentionally_absent"],
)
def test_inventory_stage_inputs_equal_every_selected_producer_output(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    donor_disposition: Literal["present", "intentionally_absent"],
) -> None:
    """The stage manifest records the dynamically selected output set, with full metadata."""
    manifest_path, _build_root, _store = _make_candidate(
        tmp_path,
        monkeypatch,
        donor_disposition=donor_disposition,
    )
    stage_manifest = BuildRunManifest.model_validate_json(manifest_path.read_bytes())
    inventory_path = Path(stage_manifest.outputs[0].path)
    envelope = json.loads(inventory_path.read_text(encoding="utf-8"))
    source_outputs = envelope["source_stage_receipt"]["outputs"]

    expected = {
        (
            output["source_path"],
            output["sha256"],
            output["size_bytes"],
            output["row_count"],
            output["nnz"],
            output["producer_artifact_id"],
        )
        for output in source_outputs.values()
    }
    actual = {
        (
            record.path,
            record.sha256,
            record.size_bytes,
            record.row_count,
            record.nnz,
            record.artifact_id,
        )
        for record in stage_manifest.inputs
    }
    assert len(stage_manifest.inputs) == len(envelope["role_outputs"])
    assert actual == expected


def test_stage_build_result_inputs_are_strict_and_positional_api_stays_compatible(
    tmp_path: Path,
) -> None:
    """The optional input field preserves old constructors and rejects unbound/colliding rows."""
    legacy_result = StageBuildResult({}, [], [], {}, [])
    assert legacy_result.inputs == []

    input_path = tmp_path / "shared.json"
    unbound = ArtifactRecord(path=str(input_path), sha256="", size_bytes=0)
    with pytest.raises(ValueError, match="verified SHA-256"):
        StageBuildResult(inputs=[unbound])

    bound = ArtifactRecord(path=str(input_path), sha256="a" * 64, size_bytes=1)
    with pytest.raises(ValueError, match="disjoint paths"):
        StageBuildResult(inputs=[bound], outputs={"same-path": bound})


def test_inventory_candidate_reaches_all_real_readers_and_foundry(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The explicit candidate stage feeds four readers and the actual Foundry consumer."""
    manifest_path, build_root, store = _make_candidate(tmp_path, monkeypatch)
    allowed_root = build_root
    receipt: VerifiedUkraineStageArtifacts = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=allowed_root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
        required_outputs=("inventory.json",),
    )
    source: DemographySourceRequest = InventorySourceRequest(
        kind="inventory", stage_receipt=receipt, store=store
    )
    artifacts = load_demography_candidate_artifacts(
        manifest_path,
        store=store,
        allowed_root=allowed_root,
    )
    targets = load_reconciled_targets(source=source)
    priors = load_transition_priors(source=source)
    donors = load_donor_pool(source=source)
    aggregate = load_demography_artifacts(source=source)

    assert isinstance(source, InventorySourceRequest)
    assert isinstance(targets, DemographyRoleProjection)
    assert {
        targets.evidence.source_status,
        priors.evidence.source_status,
        donors.evidence.source_status,
    } == {"candidate_only"}
    assert targets["state_ids"] == ["state:a", "state:b"]
    assert priors["transition_prior_matrix"] == [[0.8, 0.2], [0.1, 0.9]]
    assert donors["donor_record_index"] == [101, 102]
    assert len(
        {
            targets.evidence.source_identity,
            priors.evidence.source_identity,
            donors.evidence.source_identity,
            aggregate.source_evidence.source_identity,
            artifacts.source_evidence.source_identity,
        }
    ) == 1
    assert aggregate.source_evidence.source_status == "candidate_only"
    assert aggregate.source_evidence.source_fact_provenance == "consumer_asserted"
    assert aggregate.source_evidence.source_authority_provenance == "not_established"
    assert aggregate.source_evidence.source_currentness_provenance == "not_established"
    assert aggregate.source_evidence.semantic_completeness_provenance == "not_established"
    assert aggregate.source_evidence.member_content_binding_provenance == "recomputed"
    assert aggregate.source_evidence.declared_basis_binding_provenance == "recomputed"

    state = build_static_aging_state(
        base_weights=np.array([1.0, 2.0]),
        origin_state_index=np.array([0, 1]),
        artifacts=aggregate,
        microsim_calibration_report={
            "decision": "pass",
            "can_run_microsim": True,
            "compatibility_status": "compatible",
        },
    )
    result = StaticAgingSimulationEstimator.pure_step(state, {})["result"]
    assert result.diagnostics["demography_source_evidence"]["source_status"] == "candidate_only"
    assert (
        result.diagnostics["demography_source_evidence"]["source_currentness_provenance"]
        == "not_established"
    )


@pytest.mark.parametrize(
    ("member_overrides", "expected_code"),
    [
        pytest.param(
            {"targets": {"target_state_totals": [10.0]}},
            "demography_bundle_invalid",
            id="target-state-axis",
        ),
        pytest.param(
            {"targets": {"entrant_state_totals": [0.0]}},
            "demography_bundle_invalid",
            id="entrant-state-axis",
        ),
        pytest.param(
            {"priors": {"transition_prior_matrix": [[1.0]]}},
            "declared_prior_axis_shape_mismatch",
            id="prior-destination-axis",
        ),
        pytest.param(
            {"priors": {"allowed_transition_mask": [[True, True]]}},
            "demography_bundle_invalid",
            id="prior-mask-shape",
        ),
        pytest.param(
            {"donor": {"donor_state_index": [0]}},
            "demography_bundle_invalid",
            id="donor-state-index-length",
        ),
        pytest.param(
            {"donor": {"donor_record_index": [101]}},
            "demography_bundle_invalid",
            id="donor-record-index-length",
        ),
        pytest.param(
            {"donor": {"donor_state_index": [0, 2]}},
            "demography_bundle_invalid",
            id="donor-state-index-range",
        ),
        pytest.param(
            {"donor": {"donor_weights": [-0.25, 1.25]}},
            "demography_bundle_invalid",
            id="donor-weight-domain",
        ),
    ],
)
def test_candidate_readers_refuse_malformed_present_members(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    member_overrides: dict[str, dict[str, object]],
    expected_code: str,
) -> None:
    """Every canonical reader validates all present roles against the bundle contract."""
    manifest_path, build_root, store = _make_candidate(
        tmp_path,
        monkeypatch,
        member_overrides=member_overrides,
    )
    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
        required_outputs=("inventory.json",),
    )
    source = InventorySourceRequest(
        kind="inventory",
        stage_receipt=receipt,
        store=store,
    )
    readers: tuple[Callable[..., object], ...] = (
        load_domain_reconciled_targets,
        load_domain_transition_priors,
        load_domain_donor_pool,
        load_domain_demography_artifacts,
    )

    for reader in readers:
        with pytest.raises(SourceResolutionRefusalError) as exc_info:
            reader(source=source)

        assert exc_info.value.code == expected_code


def test_missing_entrant_materialization_is_refused_without_zero_default(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A missing required producer field is not synthesized as an empty measurement."""
    manifest_path, build_root, store = _make_candidate(
        tmp_path,
        monkeypatch,
        include_entrant_totals=False,
    )

    with pytest.raises(SourceResolutionRefusalError) as exc_info:
        load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )

    assert exc_info.value.code == "entrant_measure_not_materialized"
    assert "candidate inventory requires entrant_state_totals" in str(exc_info.value)


def test_same_shape_state_order_drift_is_rejected_by_the_real_resolver(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A reordered state list with unchanged claims fails despite identical dimensions."""
    manifest_path, build_root, store = _make_candidate(
        tmp_path,
        monkeypatch,
        materialized_state_ids=["state:b", "state:a"],
    )
    with pytest.raises(SourceResolutionRefusalError) as exc_info:
        load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )

    assert exc_info.value.code == "declared_state_order_mismatch"
    assert "target state order differs from the explicit claim" in str(exc_info.value)


@pytest.mark.parametrize("fact_name", ["source_profile", "observed_at"])
def test_inventory_claim_tamper_without_basis_rewrite_is_rejected(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    fact_name: str,
) -> None:
    """Changed profile and time claims cannot pass on the old declared basis."""
    manifest_path, build_root, store = _make_candidate(tmp_path, monkeypatch)
    manifest = BuildRunManifest.model_validate_json(manifest_path.read_bytes())
    inventory_path = Path(manifest.outputs[0].path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["source_claims"]["facts"][fact_name]["value"] = "fixture:changed"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    rewritten_manifest = manifest.model_copy(
        update={"outputs": [ArtifactRecord.from_path(inventory_path)]}
    )
    write_manifest(manifest_path, rewritten_manifest)

    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
        required_outputs=("inventory.json",),
    )
    source = InventorySourceRequest(
        kind="inventory",
        stage_receipt=receipt,
        store=store,
    )
    readers: tuple[Callable[..., object], ...] = (
        load_domain_reconciled_targets,
        load_domain_transition_priors,
        load_domain_donor_pool,
        load_domain_demography_artifacts,
    )
    for reader in readers:
        with pytest.raises(SourceResolutionRefusalError) as exc_info:
            reader(source=source)

        assert exc_info.value.code == "semantic_basis_mismatch"
        assert "declared basis is" in str(exc_info.value)

    with pytest.raises(SourceResolutionRefusalError) as facade_exc_info:
        load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )

    assert facade_exc_info.value.code == "semantic_basis_mismatch"


@pytest.mark.parametrize("add_extra", [False, True])
def test_inventory_stage_manifest_rejects_inexact_selected_input_membership(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    add_extra: bool,
) -> None:
    """The resolver rejects missing or extra stage inputs after producer materialization."""
    manifest_path, build_root, store = _make_candidate(tmp_path, monkeypatch)
    manifest = BuildRunManifest.model_validate_json(manifest_path.read_bytes())
    records = list(manifest.inputs)
    if add_extra:
        records.append(manifest.outputs[0])
    else:
        records.pop()
    write_manifest(manifest_path, manifest.model_copy(update={"inputs": records}))

    with pytest.raises(SourceResolutionRefusalError) as exc_info:
        load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )

    assert exc_info.value.code == "inventory_stage_input_membership_mismatch"
    assert "candidate stage inputs differ from all selected producer outputs" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("producer_identity", "foreign.producer"),
        ("source_currentness_provenance", "institutionally_supplied"),
    ],
)
def test_inventory_rejects_foreign_producer_or_currentness_self_label(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    field: str,
    value: str,
) -> None:
    """Neither producer identity nor currentness can be promoted by editing the envelope."""
    manifest_path, build_root, store = _make_candidate(tmp_path, monkeypatch)
    manifest = BuildRunManifest.model_validate_json(manifest_path.read_bytes())
    inventory_path = Path(manifest.outputs[0].path)
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    payload[field] = value
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    rewritten = manifest.model_copy(
        update={"outputs": [ArtifactRecord.from_path(inventory_path)]}
    )
    write_manifest(manifest_path, rewritten)

    with pytest.raises(SourceResolutionRefusalError) as exc_info:
        load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )

    assert exc_info.value.code == "inventory_malformed"
    assert field in str(exc_info.value)


def test_inventory_route_never_falls_back_to_historical_filesystem(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Supplying an inventory source and a path is an error, never alternate selection."""
    manifest_path, build_root, store = _make_candidate(tmp_path, monkeypatch)
    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
    )
    source = InventorySourceRequest(kind="inventory", stage_receipt=receipt, store=store)
    with pytest.raises(ValueError, match="either an inventory source"):
        load_demography_artifacts(tmp_path / "unrelated-history", source=source)


@pytest.mark.parametrize(
    ("donor_disposition", "should_read"),
    [("intentionally_absent", True), ("not_established", False)],
)
def test_candidate_donor_absence_requires_an_explicit_disposition(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    donor_disposition: str,
    should_read: bool,
) -> None:
    """Only explicit absence yields an empty donor projection; unknown refuses."""
    manifest_path, build_root, store = _make_candidate(
        tmp_path,
        monkeypatch,
        donor_disposition=donor_disposition,
    )
    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
    )
    source = InventorySourceRequest(
        kind="inventory",
        stage_receipt=receipt,
        store=store,
    )
    targets = load_domain_reconciled_targets(source=source)
    priors = load_domain_transition_priors(source=source)
    assert targets.evidence.source_status == "candidate_only"
    assert priors.evidence.source_status == "candidate_only"

    if should_read:
        artifacts = load_demography_candidate_artifacts(
            manifest_path,
            store=store,
            allowed_root=build_root,
        )
        donor = load_domain_donor_pool(source=source)
        aggregate = load_domain_demography_artifacts(source=source)

        assert dict(donor) == {}
        assert donor.evidence.source_status == "candidate_only"
        assert donor.evidence.donor_disposition == "intentionally_absent"
        assert artifacts.donor_weights is None
        assert aggregate.donor_weights is None
        assert aggregate.source_evidence.donor_disposition == "intentionally_absent"
    else:
        assert targets.evidence.donor_disposition == "not_established"
        assert priors.evidence.donor_disposition == "not_established"
        with pytest.raises(SourceResolutionRefusalError) as exc_info:
            load_domain_donor_pool(source=source)

        assert exc_info.value.code == "member_not_established"
        assert str(exc_info.value) == "donor"
        with pytest.raises(SourceResolutionRefusalError) as direct_aggregate_exc_info:
            load_domain_demography_artifacts(source=source)

        assert direct_aggregate_exc_info.value.code == "member_not_established"
        assert str(direct_aggregate_exc_info.value) == "donor"
        with pytest.raises(SourceResolutionRefusalError) as aggregate_exc_info:
            load_demography_candidate_artifacts(
                manifest_path,
                store=store,
                allowed_root=build_root,
            )

        assert aggregate_exc_info.value.code == "member_not_established"
        assert str(aggregate_exc_info.value) == "donor"


def test_inventory_facts_cannot_claim_independent_provenance() -> None:
    """The input DTO has no caller-controlled authority or currentness upgrade."""
    with pytest.raises(ValidationError):
        SourceFact(value="fixture:profile", provenance="independently_reconciled")
