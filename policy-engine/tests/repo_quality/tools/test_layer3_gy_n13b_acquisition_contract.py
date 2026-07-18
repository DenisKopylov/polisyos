from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.data_forge.read_api import catalog as catalog_read_api
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
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
    assert contract.residual_closure.owner_registration_derivation_missing_closed is True
    assert contract.residual_closure.journal_raw_evidence_persistence_missing_closed is True
    assert contract.capstone_routes.laundered_route_count == 0
    assert contract.quarantine.response_admitted_count == 0

    payload = contract.model_dump(mode="json")
    payload["world_growth"]["status"] = "grew"
    with pytest.raises(ValidationError):
        N13bAcquisitionExecutorContract.model_validate(payload)
