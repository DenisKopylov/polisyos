from __future__ import annotations

import hashlib
import json
import os
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.data_forge.read_api import catalog as catalog_read_api
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    RecurringCarrierAttemptEvidence,
    RecurringCarrierLivenessUpdate,
    derive_recurring_carrier_liveness_update,
    read_census_manifest,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    DEFAULT_ACCEPTANCE_CASE,
    AcceptanceCaseReceipt,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
CENSUS_PATH = (
    POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
)
PROVISION_PATH = (
    POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
JOURNAL_PATH = (
    POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)
CAS_ROOT = POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_acquisition_cas"


def _carrier_receipt_with_source_lever(source_id: str) -> RecurringCarrierLivenessUpdate:
    request_dataset_id = f"metric.example.{source_id}"
    data_body = b'[{"page":0,"pages":0,"per_page":0,"total":0},null]'
    source_name = f"Example Source {source_id}"
    metadata_body = json.dumps(
        [
            {"page": 1, "pages": 1, "per_page": "1", "total": 1},
            [
                {
                    "id": request_dataset_id,
                    "source": {"id": source_id, "value": source_name},
                }
            ],
        ],
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    def digest(value: bytes) -> str:
        return f"sha256:{hashlib.sha256(value).hexdigest()}"

    data_attempt = RecurringCarrierAttemptEvidence(
        attempt_id=f"data-{source_id}",
        call_class="data_fetch",
        request_dataset_id=request_dataset_id,
        request_event_sha256=digest(f"data-request-{source_id}".encode()),
        raw_evidence_event_sha256=digest(f"data-event-{source_id}".encode()),
        terminal_sha256=digest(f"data-terminal-{source_id}".encode()),
        terminal_outcome="quarantined_shape_drift",
        raw_body_sha256=digest(data_body),
        http_status_code=200,
        max_elapsed_seconds=1.0,
    )
    metadata_attempt = RecurringCarrierAttemptEvidence(
        attempt_id=f"metadata-{source_id}",
        call_class="indicator_metadata",
        request_dataset_id=request_dataset_id,
        request_event_sha256=digest(f"metadata-request-{source_id}".encode()),
        raw_evidence_event_sha256=digest(f"metadata-event-{source_id}".encode()),
        terminal_sha256=digest(f"metadata-terminal-{source_id}".encode()),
        terminal_outcome="quarantined_metadata_characterization_complete",
        raw_body_sha256=digest(metadata_body),
        http_status_code=200,
        max_elapsed_seconds=1.0,
    )
    return derive_recurring_carrier_liveness_update(
        connector_id=f"example.connector.{source_id}",
        request_dataset_id=request_dataset_id,
        execution_tier="transport_ready",
        data_attempts=(data_attempt,),
        decisive_data_body=data_body,
        metadata_attempt=metadata_attempt,
        metadata_body=metadata_body,
        catalog_source_names=(source_name,),
        profile_source_descriptors=("Different declared profile",),
        source_selector_declared=False,
    )


def test_local_lift_refusal_covers_every_census_residual_and_uses_rights_owner() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        derive_local_lift_refusal,
    )

    census = read_census_manifest(CENSUS_PATH)
    provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate_json(
        PROVISION_PATH.read_bytes()
    )

    refusal = derive_local_lift_refusal(census=census, provision=provision)

    assert refusal.residual_denominator_count == 15
    assert refusal.admissible_count == 0
    assert refusal.disposition == "no_admissible_local_binding"
    assert refusal.local_rights_trust_anchor_sha256 is None
    assert tuple(row.variable_id for row in refusal.rows) == tuple(
        row.variable_id for row in census.growth_backlog
    )
    assert all(
        row.rejection_codes == ("local_rights_authority_unavailable",) for row in refusal.rows
    )


def test_d2_source_growth_routes_every_carrier_lever_through_n7_without_fake_voi() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        derive_d2_source_growth_backlog,
        derive_local_lift_refusal,
    )

    receipts = (
        _carrier_receipt_with_source_lever("23"),
        _carrier_receipt_with_source_lever("17"),
    )
    backlog = derive_d2_source_growth_backlog(receipts)

    assert backlog.carrier_receipt_denominator_count == 2
    assert backlog.missing_request_lever_denominator_count == 2
    assert backlog.connector_gap_count == 2
    assert tuple(row.missing_request_lever for row in backlog.rows) == (
        "source_selector:17",
        "source_selector:23",
    )
    assert all(row.gap_kind == "connector_gap" for row in backlog.rows)
    assert all(
        row.requirement_gap.gap_type.value == "scenario_source_family" for row in backlog.rows
    )
    assert all(row.planner_route.terminal_disposition == "acquire" for row in backlog.rows)
    assert all(row.planner_route.voi_ranking_ref is None for row in backlog.rows)
    assert all(row.planner_route.voi_numeric_support is False for row in backlog.rows)

    census = read_census_manifest(CENSUS_PATH)
    provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate_json(
        PROVISION_PATH.read_bytes()
    )
    local_lift = derive_local_lift_refusal(census=census, provision=provision)
    assert local_lift.residual_denominator_count == 15
    assert all(row.gap_kind == "binding_gap" for row in local_lift.rows)
    assert not (
        {row.variable_id for row in local_lift.rows}
        & {row.missing_request_lever for row in backlog.rows}
    )


@pytest.mark.parametrize("mutation", ["tamper", "drop", "duplicate", "reorder"])
def test_d2_source_growth_rejects_decisive_denominator_mutations(mutation: str) -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        D2SourceGrowthBacklog,
        derive_d2_source_growth_backlog,
    )

    backlog = derive_d2_source_growth_backlog(
        (
            _carrier_receipt_with_source_lever("23"),
            _carrier_receipt_with_source_lever("17"),
        )
    )
    payload = backlog.model_dump(mode="json")
    if mutation == "tamper":
        payload["rows"][0]["missing_request_lever"] = "request_header:novel"
    elif mutation == "drop":
        payload["rows"] = payload["rows"][:-1]
    elif mutation == "duplicate":
        payload["rows"][1] = payload["rows"][0]
    else:
        payload["rows"] = list(reversed(payload["rows"]))

    with pytest.raises(ValidationError):
        D2SourceGrowthBacklog.model_validate(payload)


def test_journal_projection_reopens_full_attempt_denominator_and_cas_bytes() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        derive_journal_evidence_projection,
    )

    projection = derive_journal_evidence_projection(
        journal_path=JOURNAL_PATH,
        cas_root=CAS_ROOT,
    )

    assert projection.request_count == 5
    assert projection.terminal_count == 5
    assert projection.raw_response_count == 2
    assert projection.response_admitted_count == 0
    assert projection.quarantine_count == 5
    assert projection.persisted_raw_response_count == 2
    assert projection.journal_raw_evidence_persistence_missing_closed is True
    assert tuple(row.request_sequence for row in projection.attempts) == (1, 10, 19, 27, 36)


def test_derivation_projection_binds_one_recipe_two_consumers_and_cache_hit() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        derive_derivation_projection,
    )

    acceptance = AcceptanceCaseReceipt.model_validate_json(
        (POLICY_ENGINE_ROOT / DEFAULT_ACCEPTANCE_CASE).read_bytes()
    )

    projection = derive_derivation_projection(acceptance=acceptance, cas_root=CAS_ROOT)

    assert projection.recipe_id.startswith("derivation-recipe:sha256:")
    assert projection.first_materialization_cache_hit is False
    assert projection.second_materialization_cache_hit is True
    assert projection.consumer_count == 2
    assert projection.distinct_consumer_count == 2
    assert projection.observation_class == "derived"
    assert projection.basis_mismatch_refusal_code == "basis_mismatch"
    assert projection.model_output_observation_rejection_codes == ("model_output_not_observation",)


def test_capstone_route_projection_rejects_label_laundering() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        CapstoneRoutePreservation,
        derive_capstone_route_preservation,
    )

    projection = derive_capstone_route_preservation(read_census_manifest(CENSUS_PATH))
    assert projection.route_count == 3
    assert {row.route_class for row in projection.routes} == {"not_a_data_gap"}

    payload = projection.model_dump(mode="json")
    payload["routes"][0]["route_class"] = "live_fetchable"
    with pytest.raises(ValidationError):
        CapstoneRoutePreservation.model_validate(payload)


def test_lifecycle_manifest_derives_registered_outputs_and_no_phantom_snapshot() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        DEFAULT_N13B_CONTRACT,
        DEFAULT_N13B_LIFECYCLE_MANIFEST,
        derive_lifecycle_manifest,
    )

    manifest = derive_lifecycle_manifest(POLICY_ENGINE_ROOT)

    paths = {row.path for row in manifest.registrations}
    assert DEFAULT_N13B_CONTRACT.as_posix() in paths
    assert DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix() in paths
    assert manifest.materialized_acquired_snapshot_count == 0
    assert manifest.registered_acquired_snapshot_count == 0
    assert manifest.phantom_output_count == 0
    assert manifest.owner_registration_derivation_missing_closed is True
    assert manifest.canonical_provision_registered is True
    assert manifest.derived_artifact_registered is True
    assert manifest.derivation_certificate_registered is True
    assert manifest.universality_receipt_registered is True


def test_generated_registry_update_derives_full_cas_graph_and_preserves_other_families() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13B_FAMILY_ID,
        derive_n13b_generated_registry_update,
    )

    update = derive_n13b_generated_registry_update(POLICY_ENGINE_ROOT)
    current = (POLICY_ENGINE_ROOT / "architecture/generated_artifacts.toml").read_bytes()
    before = tomllib.loads(current.decode("utf-8"))
    after = tomllib.loads(update.registry_bytes.decode("utf-8"))
    before_by_id = {row["id"]: row for row in before["family"]}
    after_by_id = {row["id"]: row for row in after["family"]}

    assert before_by_id.keys() == after_by_id.keys()
    assert {
        family_id: family
        for family_id, family in before_by_id.items()
        if family_id != N13B_FAMILY_ID
    } == {
        family_id: family
        for family_id, family in after_by_id.items()
        if family_id != N13B_FAMILY_ID
    }
    n13b_outputs = tuple(after_by_id[N13B_FAMILY_ID]["outputs"])
    assert tuple(sorted(n13b_outputs)) == n13b_outputs
    assert (
        tuple(path for path in n13b_outputs if "layer3_gy_acquisition_cas/artifacts/sha256" in path)
        == update.required_cas_output_paths
    )
    assert "sha256:244e629ceec4b53324246967388d17b706efe2207744b8148d60ea52dbccd264" in (
        update.required_cas_artifact_ids
    )
    assert "sha256:2c03b35d4f4421e3e3033882e689b2c8a9c3ee813257425c3984828534c88841" in (
        update.required_cas_artifact_ids
    )
    assert "sha256:9630b0d0f0cdca75b123b1d5701a1d0fb77f53efde5d257cc5683eb91e8db875" in (
        update.required_cas_artifact_ids
    )
    assert "sha256:13621fe4601a42e3b1713c43a23b1f5c4f8a37b8cba9294845b136a31184b1f0" in (
        update.required_cas_artifact_ids
    )


def test_cas_graph_closure_rejects_missing_transitive_input(tmp_path: Path) -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bContractError,
        derive_cas_artifact_closure,
    )

    root_id = "sha256:" + "1" * 64
    missing_id = "sha256:" + "2" * 64
    digest = root_id.removeprefix("sha256:")
    artifact_dir = tmp_path / "artifacts/sha256" / digest[:2] / digest[2:4]
    artifact_dir.mkdir(parents=True)
    blob = b"root"
    actual_root_id = f"sha256:{hashlib.sha256(blob).hexdigest()}"
    actual_digest = actual_root_id.removeprefix("sha256:")
    actual_dir = tmp_path / "artifacts/sha256" / actual_digest[:2] / actual_digest[2:4]
    actual_dir.mkdir(parents=True)
    (actual_dir / f"{actual_digest}.blob").write_bytes(blob)
    (actual_dir / f"{actual_digest}.manifest.json").write_text(
        json.dumps(
            {
                "artifact_id": actual_root_id,
                "byte_size": len(blob),
                "inputs": [{"artifact_id": missing_id, "role": "missing"}],
                "integrity": {"sha256": actual_digest},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(N13bContractError, match="n13b_cas_artifact_missing"):
        derive_cas_artifact_closure(tmp_path, (actual_root_id,))


def test_lifecycle_missing_universality_cannot_be_forged_closed(tmp_path: Path) -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        DEFAULT_GENERATED_ARTIFACTS,
        DEFAULT_N13B_CONTRACT,
        DEFAULT_N13B_LIFECYCLE_MANIFEST,
        DEFAULT_N13B_PROVISION,
        N13B_FAMILY_ID,
        _cas_blob_relative,
        derive_lifecycle_manifest,
    )

    derived_id = "sha256:" + "1" * 64
    certificate_id = "sha256:" + "2" * 64
    outputs = (
        DEFAULT_N13B_CONTRACT.as_posix(),
        DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix(),
        DEFAULT_N13B_PROVISION.as_posix(),
        _cas_blob_relative(derived_id),
        _cas_blob_relative(certificate_id),
    )
    registry_path = tmp_path / DEFAULT_GENERATED_ARTIFACTS
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        "\n".join(
            (
                "[[family]]",
                f'id = "{N13B_FAMILY_ID}"',
                "outputs = [",
                *(f'  "{path}",' for path in outputs),
                "]",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    for relative in outputs:
        if relative in {
            DEFAULT_N13B_CONTRACT.as_posix(),
            DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix(),
        }:
            continue
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))

    manifest = derive_lifecycle_manifest(
        tmp_path,
        derived_artifact_id=derived_id,
        certificate_artifact_id=certificate_id,
    )

    assert manifest.phantom_output_count == 0
    assert manifest.canonical_provision_registered is True
    assert manifest.derived_artifact_registered is True
    assert manifest.derivation_certificate_registered is True
    assert manifest.universality_receipt_registered is False
    assert manifest.owner_registration_derivation_missing_closed is False


def test_checker_rejects_split_brain_derivation_owner_paths(tmp_path: Path) -> None:
    from tools.quality.validation.check_layer3_gy_n13b_acquisition_contract import (
        POLICY_ENGINE_ROOT,
        _canonical_derivation_paths,
    )
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bContractError,
    )
    from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
        DEFAULT_DERIVATION_FAMILY_REGISTRY,
        DEFAULT_UNIVERSALITY_RECEIPT,
    )

    registry, receipt = _canonical_derivation_paths(
        registry_path=DEFAULT_DERIVATION_FAMILY_REGISTRY,
        universality_output=POLICY_ENGINE_ROOT / DEFAULT_UNIVERSALITY_RECEIPT,
    )
    assert registry == (POLICY_ENGINE_ROOT / DEFAULT_DERIVATION_FAMILY_REGISTRY).resolve()
    assert receipt == (POLICY_ENGINE_ROOT / DEFAULT_UNIVERSALITY_RECEIPT).resolve()

    with pytest.raises(
        N13bContractError,
        match="n13b_noncanonical_derivation_owner_paths",
    ):
        _canonical_derivation_paths(
            registry_path=tmp_path / "other.toml",
            universality_output=receipt,
        )


def test_contract_output_write_is_transactional(tmp_path: Path) -> None:
    from tools.quality.validation.check_layer3_gy_n13b_acquisition_contract import (
        _write_transaction,
    )
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bContractError,
    )

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    third = tmp_path / "third.json"
    for path, payload in ((first, b"old-1"), (second, b"old-2"), (third, b"old-3")):
        path.write_bytes(payload)

    calls = 0

    def fail_on_second_replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replacement failure")
        os.replace(source, target)

    with pytest.raises(N13bContractError, match="n13b_write_transaction_failed"):
        _write_transaction(
            ((first, b"new-1"), (second, b"new-2"), (third, b"new-3")),
            _replace=fail_on_second_replace,
        )

    assert first.read_bytes() == b"old-1"
    assert second.read_bytes() == b"old-2"
    assert third.read_bytes() == b"old-3"
    assert not tuple(tmp_path.glob(".*.transaction.tmp"))


def test_contract_output_write_rolls_back_removed_stale_outputs(tmp_path: Path) -> None:
    from tools.quality.validation.check_layer3_gy_n13b_acquisition_contract import (
        _write_transaction,
    )
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bContractError,
    )

    output = tmp_path / "output.json"
    stale = tmp_path / "stale.blob"
    output.write_bytes(b"old-output")
    stale.write_bytes(b"old-stale")

    def fail_removal(_path: Path) -> None:
        raise OSError("injected removal failure")

    with pytest.raises(N13bContractError, match="n13b_write_transaction_failed"):
        _write_transaction(
            ((output, b"new-output"),),
            remove_paths=(stale,),
            _unlink=fail_removal,
        )

    assert output.read_bytes() == b"old-output"
    assert stale.read_bytes() == b"old-stale"


def test_decisive_projection_fields_are_content_bound() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        JournalEvidenceProjection,
        LocalLiftRefusal,
        derive_journal_evidence_projection,
        derive_local_lift_refusal,
    )

    census = read_census_manifest(CENSUS_PATH)
    provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate_json(
        PROVISION_PATH.read_bytes()
    )
    refusal = derive_local_lift_refusal(census=census, provision=provision)
    refusal_payload = refusal.model_dump(mode="json")
    refusal_payload["disposition"] = "local_lift_admissible"
    with pytest.raises(ValidationError):
        LocalLiftRefusal.model_validate(refusal_payload)

    journal = derive_journal_evidence_projection(journal_path=JOURNAL_PATH, cas_root=CAS_ROOT)
    journal_payload = journal.model_dump(mode="json")
    journal_payload["attempts"][0]["failure_code"] = "alive_conformant"
    with pytest.raises(ValidationError):
        JournalEvidenceProjection.model_validate(journal_payload)


def test_contract_recomputes_honest_terminal_and_closes_lifecycle_residuals() -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        N13bAcquisitionExecutorContract,
        derive_n13b_acquisition_executor_contract,
    )

    provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate_json(
        PROVISION_PATH.read_bytes()
    )
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        (
            POLICY_ENGINE_ROOT
            / "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
        ).read_bytes()
    )

    contract = derive_n13b_acquisition_executor_contract(
        repo_root=POLICY_ENGINE_ROOT,
        baseline_sha256=provision.baseline_content_sha256,
        l5_sha256=registry.l5_measurement_registry_sha256,
    )

    assert isinstance(contract, N13bAcquisitionExecutorContract)
    assert contract.demonstration_status == "typed_deeper_terminal"
    assert contract.world_growth.status == "no_growth"
    assert contract.world_growth.event_count == 0
    assert contract.world_growth.overlay_epoch_count == 0
    assert contract.world_growth.availability_count_delta == 0
    assert contract.resumption_budget.spent_call_count == 3
    assert contract.resumption_budget.remaining_call_count == 3
    assert contract.d2_source_growth.carrier_receipt_denominator_count == 1
    assert contract.d2_source_growth.connector_gap_count == 1
    assert contract.d2_source_growth.rows[0].missing_request_lever == "source_selector:11"
    assert contract.local_lift.residual_denominator_count == 15
    assert contract.residual_closure.owner_registration_derivation_missing_closed is True
    assert contract.residual_closure.journal_raw_evidence_persistence_missing_closed is True
    assert contract.capstone_routes.laundered_route_count == 0
    assert contract.quarantine.response_admitted_count == 0

    payload = contract.model_dump(mode="json")
    payload["world_growth"]["status"] = "grew"
    with pytest.raises(ValidationError):
        N13bAcquisitionExecutorContract.model_validate(payload)
