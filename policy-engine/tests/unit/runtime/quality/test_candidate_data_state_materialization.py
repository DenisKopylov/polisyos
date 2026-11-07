"""Test-owned WDI model output reaches Foundry without observed-data authority.

The controlled response, catalog, and source provision come from the shared
LANE-01 fixture. They exercise the real owners and transport but establish no
production source authority, external observations, release rights, or freshness.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, load_core_json_artifact
from polisyos.core.contracts.fabric import (
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import build_input_bindings, load_input_bindings
from polisyos.foundry.execute import load_state_snapshot
from polisyos.runtime.quality.data_snapshot_lineage import (
    DataSnapshotSourceRowNotEstablishedError,
    validate_data_snapshot_owner_lineage,
)
from polisyos.runtime.quality.data_state_substrate import (
    CandidateAcquisitionSourceSlotBinding,
    DataStateSubstrateError,
    materialize_candidate_acquisition_snapshot,
)
from tests._helpers.lane01_candidate_source import build_lane01_candidate_source
from tests._helpers.world_model_record import _data_snapshot_ref

TRANSACTION_TIME = datetime(2026, 11, 3, 12, tzinfo=UTC)
TENANT_ID = "c1a61b9c-3e0c-4496-a4b7-4d1bd025733b"
CELL_ID = "9cb4caf0-573b-4a0c-a014-cba26f9d6058"
# This test-owned selection is carried here; the live bridge verifies scenario context.
SCENARIO_PROFILE_SELECTION_REF = (
    "sha256:" + hashlib.sha256(b"lane01-test-scenario-profile:v1").hexdigest()
)


def test_modeled_wdi_percent_reaches_selected_candidate_snapshot_and_foundry_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Consume the owner-normalized ratio through actual persisted input bindings."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = build_lane01_candidate_source(
            tmp_path / "source", monkeypatch, tenant_id=TENANT_ID, cell_id=CELL_ID
        )
        assert isinstance(case.store, FileSystemCAS)
        source = case.source
        raw_response = json.loads(case.store.get_bytes(source.raw_source_ref))
        assert raw_response[1][0]["indicator"]["id"] == "SL.UEM.TOTL.ZS"
        assert raw_response[1][0]["value"] == 17.5
        assert case.entry.raw_unit == "percent"
        assert case.entry.canonical_unit == source.canonical_unit == "ratio"
        assert (
            case.entry.source_measure_scope.quantity_kind
            == source.quantity_kind
            == "share_of_denominator"
        )
        assert source.observation == pytest.approx(0.175)
        assert source.observation_class == "model_output"
        assert source.status == "candidate_only"

        base_ref = _data_snapshot_ref(case.store)
        mapping = CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref=SCENARIO_PROFILE_SELECTION_REF,
            candidate_digest=case.candidate_digest,
            canonical_variable_id=case.entry.target_variable,
            target_slot_id=source.target_slot_id,
        )
        assert mapping.profile_selection_ref != mapping.candidate_digest
        issued = materialize_candidate_acquisition_snapshot(
            case.store,
            workspace_dir=tmp_path / "candidate-data",
            base_data_snapshot_ref=base_ref,
            candidate_source_ref=case.source_ref,
            slot_binding=mapping,
            transaction_time=TRANSACTION_TIME,
            authority=case.authority,
        )

        fresh = FileSystemCAS(case.store.root)
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(fresh, issued.data_snapshot_ref)
        )
        assert isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        assert snapshot.source_lineage.base_data_snapshot_ref == base_ref
        assert snapshot.source_lineage.candidate_source_ref == case.source_ref
        payload = load_core_json_artifact(fresh, snapshot.data_ref)
        assert isinstance(payload, dict)
        selected = payload["acquisition"]["selected"]
        assert selected["value"] == pytest.approx(0.175)
        assert selected["canonical_unit"] == "ratio"
        assert selected["canonical_variable_id"] == case.entry.target_variable
        assert selected["candidate_source_ref"] == case.source_ref.model_dump(mode="json")
        assert selected["candidate_digest"] == case.candidate_digest
        assert (selected["country_code"], selected["year"]) == ("USA", 2024)
        assert selected["population"] == source.population == "total_labor_force"
        assert selected["denominator"] == source.denominator == "total_labor_force"
        assert selected["quantity_kind"] == source.quantity_kind == "share_of_denominator"
        assert selected["provenance_class"] == "model_output"
        assert selected["source_time_status"] == "not_established"
        assert "_policyos_acquisition" not in payload
        marker = payload["_policyos_candidate_acquisition"]
        assert marker["purpose"] == "candidate_simulation"
        assert marker["source_provenance_class"] == "model_output"
        assert marker["slot_binding"] == mapping.model_dump(mode="json")
        assert marker["limitation_codes"] == list(source.limitations)
        assert {
            "candidate_only",
            "source_currentness_not_established",
            "current_run_job_route_ownership_not_established",
            "population_is_declared_source_scope_not_sample_denominator_evidence",
            "measurement_validity_not_established",
            "causal_validity_not_established",
            "claim_evidence_not_established",
        }.issubset(marker["limitation_codes"])
        assert issued.data_forge_snapshot_binding_path.is_file()

        registry_ref = build_default_registry_bundle(fresh, return_selected_profile=True).bundle_ref
        slot = load_registry_bundle_content(fresh, registry_ref).slot_registry.slots[
            "global.unemployment_rate"
        ]
        assert slot.state_path == "market.unemployment_rate"
        assert slot.unit.unit_id == "ratio"
        rule = issued.foundry_binding_rule
        assert rule.source_path == "acquisition.selected.value"
        assert rule.target_slot_id == source.target_slot_id == "global.unemployment_rate"
        assert rule.required
        assert "candidate_only_controlled_mapping" in rule.notes
        assert "source_to_target_measurement_contract_not_established" in rule.notes
        assert f"profile_selection_ref:{SCENARIO_PROFILE_SELECTION_REF}" in rule.notes
        assert f"candidate_digest:{case.candidate_digest}" in rule.notes

        built = build_input_bindings(
            fresh,
            data_snapshot_ref=issued.data_snapshot_ref,
            registry_bundle_ref=registry_ref,
            rules=[rule],
            return_selected_profile=True,
        )
        reader = FileSystemCAS(case.store.root)
        bindings = load_input_bindings(reader, built.input_bindings_ref)
        assert bindings.data_snapshot_ref == issued.data_snapshot_ref
        assert bindings.rules == [rule]
        assert bindings.bound_state_snapshot_ref == built.bound_state_snapshot_ref
        assert built.applied_binding_ids == (rule.binding_id,)
        state = load_state_snapshot(reader, snapshot_ref=built.bound_state_snapshot_ref)
        assert float(state.market.unemployment_rate) == pytest.approx(0.175)
        assert float(state.gdp) == 0.0
        assert float(state.tax_rate) == 0.0
        assert all(
            ref.manifest_profile_sha256
            for ref in (
                case.source_ref,
                snapshot.data_ref,
                issued.data_snapshot_ref,
                registry_ref,
                built.input_bindings_ref,
                built.bound_state_snapshot_ref,
            )
        )

        verdict = validate_data_snapshot_owner_lineage(
            reader, issued.data_snapshot_ref, snapshot, candidate_only=True
        )
        assert verdict.acquisition_source_row_status == "not_established"
        assert "claim_evidence_not_established" in verdict.required_admissibility_blockers
        with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
            validate_data_snapshot_owner_lineage(reader, issued.data_snapshot_ref, snapshot)


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        (
            "candidate_digest",
            "sha256:" + hashlib.sha256(b"unselected-lane01-candidate:v1").hexdigest(),
        ),
        ("canonical_variable_id", "global.gdp"),
        ("target_slot_id", "global.gdp"),
    ],
)
def test_materializer_rejects_wrong_selected_source_mapping_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, wrong_value: str
) -> None:
    """Well-formed selectors cannot redirect the real source to another binding."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = build_lane01_candidate_source(
            tmp_path / "source", monkeypatch, tenant_id=TENANT_ID, cell_id=CELL_ID
        )
        assert isinstance(case.store, FileSystemCAS)
        base_ref = _data_snapshot_ref(case.store)
        mapping = CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref=SCENARIO_PROFILE_SELECTION_REF,
            candidate_digest=case.candidate_digest,
            canonical_variable_id=case.entry.target_variable,
            target_slot_id=case.source.target_slot_id,
        ).model_copy(update={field: wrong_value})
        workspace = tmp_path / "refused-candidate-data"
        with pytest.raises(DataStateSubstrateError, match="candidate_source_slot_binding_mismatch"):
            materialize_candidate_acquisition_snapshot(
                case.store,
                workspace_dir=workspace,
                base_data_snapshot_ref=base_ref,
                candidate_source_ref=case.source_ref,
                slot_binding=mapping,
                transaction_time=TRANSACTION_TIME,
                authority=case.authority,
            )
        assert not workspace.exists()


def test_materializer_requires_live_authority_before_using_historical_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A replayable candidate source does not replace the live issuance owner."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = build_lane01_candidate_source(
            tmp_path / "source", monkeypatch, tenant_id=TENANT_ID, cell_id=CELL_ID
        )
        assert isinstance(case.store, FileSystemCAS)
        base_ref = _data_snapshot_ref(case.store)
        workspace = tmp_path / "refused-without-authority"
        with pytest.raises(
            DataStateSubstrateError, match="candidate_source_live_authority_required"
        ):
            materialize_candidate_acquisition_snapshot(
                case.store,
                workspace_dir=workspace,
                base_data_snapshot_ref=base_ref,
                candidate_source_ref=case.source_ref,
                slot_binding=CandidateAcquisitionSourceSlotBinding(
                    profile_selection_ref=SCENARIO_PROFILE_SELECTION_REF,
                    candidate_digest=case.candidate_digest,
                    canonical_variable_id=case.entry.target_variable,
                    target_slot_id=case.source.target_slot_id,
                ),
                transaction_time=TRANSACTION_TIME,
                authority=None,  # type: ignore[arg-type]
            )
        assert not workspace.exists()
