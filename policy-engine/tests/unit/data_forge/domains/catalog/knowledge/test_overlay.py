from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from pydantic import ValidationError

from polisyos.core import contracts
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.data_forge.domains.catalog.knowledge import overlay as overlay_module
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    BaselineMutationError,
    CatalogAcquisitionOverlay,
    OverlayAdmissionError,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import content_sha256
from polisyos.runtime.quality import semantic_epoch as semantic_epoch_runtime
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionStatus,
    ObservationProvenanceClass,
    build_admission_passport,
)
from tests._helpers import semantic_epoch_native as semantic_epoch_native_helper
from tests._helpers.semantic_epoch_native import (
    _emit_admitted_ref,
    _fixture,
    _real_epoch_scenario,
    _semantic_handshake_from_passport,
    _valid_passport,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
    _second_real_epoch_scenario,
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _admit(overlay, *, passport, store, authority):
    candidate, prepared = _semantic_handshake_from_passport(passport, store)
    return overlay.admit_epoch(
        passport=passport,
        prepared_epoch=prepared,
        boundary_candidate=candidate,
        artifact_store=store,
        authority=authority,
    )


def _scenario_with_raw_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]],
):
    """Build the normal served scenario around one explicit source-row set."""

    fixture = semantic_epoch_native_helper._fixture

    def selected_fixture(root: Path):
        return fixture(root, rows=rows, source_rows=rows)

    monkeypatch.setattr(semantic_epoch_native_helper, "_fixture", selected_fixture)
    return _real_epoch_scenario(tmp_path)


def _condition_rows() -> list[dict[str, object]]:
    return [
        {
            "country_code": "UA",
            "year": 2024,
            "distress_score": 0.42,
            "condition_json": {"cohort": "alpha"},
        },
        {
            "country_code": "UA",
            "year": 2025,
            "distress_score": 0.51,
            "condition_json": {"cohort": "beta"},
        },
    ]


def _downgrade_to_authentic_v1(scenario) -> str:
    """Rewrite one test row into the exact content-bound historical v1 shape."""

    payload = scenario.passport.model_dump(mode="json")
    for field in (
        "semantic_boundary_candidate_ref",
        "semantic_boundary_candidate_content_hash",
        "semantic_epoch_ref",
        "semantic_epoch_stamp_sha256",
        "semantic_epoch_stamp",
        "prepared_semantic_epoch_ref",
    ):
        payload.pop(field)
    payload["schema_version"] = "polisyos.runtime.acquisition_admission_passport.v1"
    identity = {
        key: value
        for key, value in payload.items()
        if key not in {"passport_id", "status", "rejection_codes"}
    }
    payload["passport_id"] = "passport:" + overlay_module.content_sha256(identity)
    legacy_id = str(payload["passport_id"])
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM acquisition_epoch_members WHERE epoch_id = ?", [scenario.passport.epoch_id]
        )
        con.execute(
            "DELETE FROM acquisition_passports WHERE epoch_id = ?", [scenario.passport.epoch_id]
        )
        con.execute(
            "INSERT INTO acquisition_passports VALUES (?, ?, ?, ?)",
            [
                legacy_id,
                scenario.passport.epoch_id,
                overlay_module.content_sha256(payload),
                json.dumps(payload),
            ],
        )
        con.execute(
            """
            UPDATE acquisition_epochs
            SET passport_id = ?, semantic_epoch_ref = NULL,
                semantic_epoch_stamp_sha256 = NULL, semantic_epoch_stamp_json = NULL,
                prepared_semantic_epoch_ref = NULL, pending_overlay_receipt_ref = NULL,
                admitted_boundary_evidence_ref = NULL,
                semantic_epoch_production_receipt_ref = NULL,
                activated_overlay_receipt_ref = NULL,
                epoch_activation_state = 'legacy_not_established'
            WHERE epoch_id = ?
            """,
            [legacy_id, scenario.passport.epoch_id],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return legacy_id


def test_overlay_owner_is_available_through_the_canonical_read_api() -> None:
    assert catalog_read_api.CatalogAcquisitionOverlay is CatalogAcquisitionOverlay
    assert callable(catalog_read_api.open_catalog_read_session)
    assert callable(catalog_read_api.project_catalog_acquisition_state)
    assert callable(catalog_read_api.validate_overlay_admission_receipt)
    assert catalog_read_api.CatalogAcquisitionEventProjection is not None
    assert catalog_read_api.CatalogAcquisitionPassportProjection is not None
    assert catalog_read_api.CatalogAcquisitionStateProjection is not None
    assert callable(catalog_read_api.verify_local_source_rights)
    assert callable(catalog_read_api.build_local_rights_trust_registry)
    assert callable(catalog_read_api.build_acquisition_authority_provision)
    assert catalog_read_api.AcquisitionAuthorityProvision is not None
    assert catalog_read_api.LocalRightsTrustRegistry is not None
    assert (
        Path("architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb")
        == catalog_read_api.DEFAULT_ACQUISITION_OVERLAY_PATH
    )
    assert catalog_read_api.default_acquisition_overlay_path(Path("/repo")) == Path(
        "/repo/architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"
    )


def test_overlay_owner_validates_the_active_receipt_identity(tmp_path: Path) -> None:
    """The read API, rather than a runtime copy, owns float-aware receipt identity."""

    scenario = _real_epoch_scenario(tmp_path / "active-receipt")
    _production, activated = _activate_real_epoch_scenario(scenario)

    metadata = catalog_read_api.validate_overlay_admission_receipt(activated)

    assert metadata.receipt_ref == str(activated.receipt_ref.artifact_id)
    assert metadata.receipt_kind == "epoch.activated_overlay_admission_receipt"
    assert metadata.receipt_content_hash == activated.receipt_content_hash

    with pytest.raises(
        OverlayAdmissionError,
        match=r"overlay_semantic_receipt_(ref|content_hash)_.*mismatch",
    ):
        catalog_read_api.validate_overlay_admission_receipt(
            activated.model_copy(update={"epoch_id": activated.epoch_id + 1})
        )


def test_catalog_acquisition_projection_is_read_only_and_content_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R02: projection reads owner state without opening its writer path."""

    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    _admit(overlay, passport=passport, store=store, authority=authority)
    overlay.close()
    before = _sha256(overlay_path)

    def fail_writer(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("read projection must not initialize an overlay")

    monkeypatch.setattr(CatalogAcquisitionOverlay, "initialize", fail_writer)
    projection = catalog_read_api.project_catalog_acquisition_state(
        authority.baseline_path,
        overlay_path=overlay_path,
    )

    assert projection.overlay_exists is True
    assert projection.epoch_count == 1
    assert projection.passport_count == 1
    assert projection.pending_epoch_count == 1
    assert projection.active_epoch_count == 0
    assert projection.admitted_observation_count == passport.measured_profile.sample_row_count
    assert projection.admitted_observation_count > 0
    assert projection.epochs[0].epoch_activation_state == "pending_epoch_activation"
    assert projection.passports[0].passport_id == passport.passport_id
    assert projection.passports[0].epoch_id == passport.epoch_id
    assert projection.passports[0].variable_id == passport.variable_id
    assert projection.passports[0].source_lane == passport.source_lane
    assert projection.passports[0].status == passport.status
    assert projection.passports[0].rejection_codes == passport.rejection_codes
    assert not hasattr(projection.passports[0], "raw_evidence_ref")
    assert projection.semantic_receipt_count == len(projection.events)
    assert projection.semantic_receipt_count > 0
    assert all(not hasattr(event, "receipt_json") for event in projection.events)
    assert _sha256(overlay_path) == before


def test_catalog_acquisition_projection_rejects_passport_property_drift(
    tmp_path: Path,
) -> None:
    """Remove the content-binding property while keeping passport markers."""

    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    _admit(overlay, passport=passport, store=store, authority=authority)
    overlay.close()
    con = duckdb.connect(str(overlay_path))
    try:
        con.execute(
            "UPDATE acquisition_passports SET passport_json = ? WHERE passport_id = ?",
            [json.dumps({"status": "admitted", "markers": ["passport_id"]}), passport.passport_id],
        )
    finally:
        con.close()

    with pytest.raises(OverlayAdmissionError, match="overlay_passport_content_hash_mismatch"):
        catalog_read_api.project_catalog_acquisition_state(
            authority.baseline_path,
            overlay_path=overlay_path,
        )


@pytest.mark.parametrize(
    "receipt_kind",
    [
        "epoch.acquisition_semantic_boundary_candidate",
        "epoch.pending_overlay_admission_receipt",
    ],
)
def test_catalog_acquisition_projection_rejects_event_property_drift(
    tmp_path: Path,
    receipt_kind: str,
) -> None:
    """Mutate decisive event bytes while retaining its identity and markers."""

    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    _admit(overlay, passport=passport, store=store, authority=authority)
    overlay.close()
    con = duckdb.connect(str(overlay_path))
    try:
        row = con.execute(
            "SELECT receipt_ref, receipt_json FROM acquisition_semantic_receipts "
            "WHERE receipt_kind = ?",
            [receipt_kind],
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row[1]))
        assert isinstance(payload, dict)
        if receipt_kind == "epoch.acquisition_semantic_boundary_candidate":
            payload["requested_query_context_ref"] = "sha256:" + "0" * 64
            statement = (
                contracts.epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
                    payload
                )
            )
            content_hash = contracts.epoch.acquisition_semantic_candidate_content_hash(statement)
        else:
            payload["admitted_observation_count"] = int(payload["admitted_observation_count"]) + 1
            content_hash = overlay_module._overlay_statement_content_hash(payload)
        con.execute(
            "UPDATE acquisition_semantic_receipts "
            "SET receipt_content_hash = ?, receipt_json = ? WHERE receipt_ref = ?",
            [content_hash, json.dumps(payload), str(row[0])],
        )
    finally:
        con.close()

    with pytest.raises(
        OverlayAdmissionError,
        match="overlay_semantic_receipt_ref_content_mismatch",
    ):
        catalog_read_api.project_catalog_acquisition_state(
            authority.baseline_path,
            overlay_path=overlay_path,
        )


def test_catalog_read_session_unifies_epoch_zero_and_overlay_audit_views(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(baseline, overlay_path)
    overlay.initialize()
    _admit(overlay, passport=passport, store=store, authority=authority)

    con = catalog_read_api.open_catalog_read_session(
        baseline,
        overlay_path=overlay_path,
    )
    catalog_store = catalog_read_api.DatasetCatalogStore(
        baseline,
        baseline.parent,
        overlay_path=overlay_path,
    )
    catalog_graph = catalog_read_api.DatasetCatalogGraph(
        baseline,
        baseline.parent,
        overlay_path=overlay_path,
    )
    try:
        # Admission first creates an auditable pending epoch.  No native row is
        # visible until the independently verified semantic activation receipt.
        assert con.execute("select count(*) from ds_observations").fetchone()[0] == 0
        assert con.execute("select count(*) from acquisition_epochs").fetchone()[0] == 1
        assert con.execute("select count(*) from acquisition_passports").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_metric_field_bindings").fetchone()[0] == 1
        with pytest.raises(duckdb.Error):
            con.execute("delete from baseline.ds_observations")
        with pytest.raises(duckdb.Error):
            con.execute("delete from acquisition_overlay.ds_observations")
        bindings = catalog_store.resolve_metric_bindings("cells.distress_score")
        assert bindings == []
        results = catalog_graph.search_datasets(
            "Owner validated local distress observations",
            top_k=5,
        )
        assert all(result.id != passport.registration.catalog_dataset_id for result in results)
    finally:
        catalog_graph.close()
        catalog_store.close()
        con.close()
        overlay.close()


def test_catalog_read_session_uses_baseline_when_overlay_is_absent(
    tmp_path: Path,
) -> None:
    _, _, authority, _ = _valid_passport(tmp_path / "evidence")
    missing = tmp_path / "not-created.duckdb"

    for overlay_path in (None, missing):
        con = catalog_read_api.open_catalog_read_session(
            authority.baseline_path,
            overlay_path=overlay_path,
        )
        try:
            assert con.execute("select count(*) from ds_datasets").fetchone()[0] > 0
            assert con.execute("select count(*) from ds_observations").fetchone()[0] == 0
            assert (
                con.execute(
                    "select count(*) from information_schema.tables "
                    "where table_name = 'acquisition_epochs'"
                ).fetchone()[0]
                == 0
            )
        finally:
            con.close()
    assert not missing.exists()


def test_catalog_read_session_rejects_overlay_bound_to_other_baseline(
    tmp_path: Path,
) -> None:
    _, _, first_authority, _ = _valid_passport(tmp_path / "first")
    _, _, second_authority, _ = _valid_passport(tmp_path / "second")
    overlay_path = tmp_path / "overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(first_authority.baseline_path, overlay_path)
    overlay.initialize()
    overlay.close()

    with pytest.raises(BaselineMutationError, match="overlay_baseline_identity_mismatch"):
        catalog_read_api.open_catalog_read_session(
            second_authority.baseline_path,
            overlay_path=overlay_path,
        )


def test_catalog_read_session_rejects_existing_non_overlay_database(
    tmp_path: Path,
) -> None:
    _, _, authority, _ = _valid_passport(tmp_path / "evidence")
    invalid_overlay = tmp_path / "invalid-overlay.duckdb"
    con = duckdb.connect(str(invalid_overlay))
    try:
        con.execute("create table unrelated(value integer)")
    finally:
        con.close()

    with pytest.raises(OverlayAdmissionError, match="overlay_catalog_contract_incomplete"):
        catalog_read_api.open_catalog_read_session(
            authority.baseline_path,
            overlay_path=invalid_overlay,
        )


def test_exact_alignment_cannot_be_self_minted_for_different_variables() -> None:
    with pytest.raises(
        ValueError,
        match="exact alignment requires identical variables and full confidence",
    ):
        catalog_read_api.build_metric_field_binding(
            dataset_id="dataset",
            distribution_id="distribution",
            raw_field="raw_value",
            canonical_variable="canonical.value",
            raw_unit="ratio",
            canonical_unit="ratio",
            unit_transform="identity",
            unit_transform_ref="owner://units/ratio-identity/v1",
            alignment_method="exact",
            alignment_confidence=0.0,
            is_proxy=False,
            proxy_penalty=0.0,
            evidence_refs=("self://invented",),
        )


def test_overlay_admits_passport_rows_at_new_epoch_without_mutating_baseline(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    before = _sha256(baseline)
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(baseline, overlay_path)
    identity = overlay.initialize()

    receipt = _admit(overlay, passport=passport, store=store, authority=authority)

    assert identity.epoch == 0
    assert receipt.epoch_id == 1
    assert receipt.admitted_observation_count == 2
    assert receipt.observation_class == ObservationProvenanceClass.OBSERVED.value
    assert receipt.effective_authority_score == 0.76
    assert receipt.baseline_before_sha256 == before
    assert receipt.baseline_after_sha256 == before
    assert _sha256(baseline) == before

    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        assert con.execute("select count(*) from ds_observations").fetchone()[0] == 2
        assert con.execute("select count(*) from acquisition_passports").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_metric_field_bindings").fetchone()[0] == 1
        confidence = con.execute("select confidence from ds_metric_bindings").fetchone()[0]
        assert confidence == pytest.approx(0.76)
        assert (
            con.execute(
                "select effective_authority_score from acquisition_observation_provenance limit 1"
            ).fetchone()[0]
            == 0.76
        )
        assert con.execute("select epoch_id from acquisition_epochs").fetchone()[0] == 1
    finally:
        con.close()

    overlay.close()


def test_overlay_reopens_license_authority_instead_of_trusting_passport(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()
    forged_license = passport.license_evidence.model_copy(
        update={"authority_content_sha256": "sha256:" + "0" * 64}
    )
    forged = passport.model_copy(update={"license_evidence": forged_license})

    with pytest.raises(OverlayAdmissionError, match="license_authority_drift"):
        _admit(overlay, passport=forged, store=store, authority=authority)
    overlay.close()


def test_overlay_refuses_quarantine_derived_model_and_epochless_rows(tmp_path: Path) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()

    for observation_class in (
        ObservationProvenanceClass.DERIVED,
        ObservationProvenanceClass.MODEL_OUTPUT,
    ):
        forged = passport.model_copy(update={"observation_class": observation_class})
        with pytest.raises(OverlayAdmissionError):
            _admit(overlay, passport=forged, store=store, authority=authority)

    with pytest.raises(ValidationError):
        type(passport)(**{**passport.model_dump(mode="python"), "epoch_id": 0})

    epochless = passport.model_copy(update={"epoch_id": 0})
    epochless = epochless.model_copy(update={"passport_id": epochless.recomputed_passport_id()})
    with pytest.raises(OverlayAdmissionError, match="epoch_stamp_required"):
        _admit(overlay, passport=epochless, store=store, authority=authority)

    overlay.close()


def test_overlay_revalidates_raw_and_cas_evidence_instead_of_trusting_passport_flags(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()
    fake_ref = passport.raw_evidence_ref.model_copy(update={"event_sha256": "sha256:" + "0" * 64})
    forged = passport.model_copy(
        update={"raw_evidence_ref": fake_ref, "raw_evidence_verified": True}
    )

    with pytest.raises(OverlayAdmissionError, match="raw_evidence_ref_unresolved"):
        _admit(overlay, passport=forged, store=store, authority=authority)

    con = duckdb.connect(str(overlay.overlay_path), read_only=True)
    try:
        assert con.execute("select count(*) from ds_observations").fetchone()[0] == 0
    finally:
        con.close()
    overlay.close()


def test_overlay_rejects_forged_source_watermark_after_passport_rebind(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()
    forged = passport.model_copy(update={"source_watermark": "sha256:" + "0" * 64})
    forged = forged.model_copy(update={"passport_id": forged.recomputed_passport_id()})

    with pytest.raises(OverlayAdmissionError, match="source_watermark_content_drift"):
        _admit(overlay, passport=forged, store=store, authority=authority)

    overlay.close()


def test_overlay_refuses_quarantined_status_with_complete_owner_evidence(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()
    quarantined = passport.model_copy(update={"status": AdmissionStatus.QUARANTINED})

    with pytest.raises(OverlayAdmissionError, match="passport_not_admitted"):
        _admit(overlay, passport=quarantined, store=store, authority=authority)

    overlay.close()


def test_overlay_refuses_canonical_values_not_derived_from_raw_evidence(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()
    candidate, prepared = _semantic_handshake_from_passport(passport, store)
    with pytest.raises(TypeError, match="observations"):
        overlay.admit_epoch(
            passport=passport,
            prepared_epoch=prepared,
            boundary_candidate=candidate,
            observations=({"value": 0.99},),  # type: ignore[call-arg]
            artifact_store=store,
            authority=authority,
        )

    receipt = _admit(overlay, passport=passport, store=store, authority=authority)
    assert receipt.admitted_observation_count == 2
    con = duckdb.connect(str(overlay.overlay_path), read_only=True)
    try:
        values = con.execute("SELECT value FROM ds_observations ORDER BY year").fetchall()
    finally:
        con.close()
    assert values == [(0.42,), (0.51,)]

    overlay.close()


def test_overlay_baseline_hash_fence_detects_any_epoch_zero_mutation(tmp_path: Path) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()

    con = duckdb.connect(str(baseline))
    try:
        con.execute("create table n13b_forbidden_baseline_mutation(value integer)")
    finally:
        con.close()

    with pytest.raises(BaselineMutationError, match="baseline_mutation_detected"):
        _admit(overlay, passport=passport, store=store, authority=authority)

    overlay.close()


def test_overlay_epoch_write_is_content_idempotent(tmp_path: Path) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()

    first = _admit(overlay, passport=passport, store=store, authority=authority)
    first_bytes = overlay.overlay_path.read_bytes()
    second = _admit(overlay, passport=passport, store=store, authority=authority)

    assert first.replayed is False
    assert second.replayed is True
    assert overlay.overlay_path.read_bytes() == first_bytes
    overlay.close()


def test_later_epoch_reuses_identical_registration_without_duplicate_catalog_rows(
    tmp_path: Path,
) -> None:
    passport, store, authority, _, raw_ref = _fixture(tmp_path / "evidence")
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()
    _admit(overlay, passport=passport, store=store, authority=authority)
    boundary_candidate, prepared_epoch = _semantic_handshake_from_passport(
        passport,
        store,
    )
    second_passport = build_admission_passport(
        epoch_id=2,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        raw_artifact_id=passport.raw_artifact_id,
        authority=authority,
        boundary_candidate=boundary_candidate,
        prepared_epoch=prepared_epoch,
    )

    second = _admit(
        overlay,
        passport=second_passport,
        store=store,
        authority=authority,
    )

    con = duckdb.connect(str(overlay.overlay_path), read_only=True)
    try:
        assert con.execute("select count(*) from acquisition_epochs").fetchone()[0] == 2
        assert con.execute("select count(*) from acquisition_registrations").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_datasets").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_distributions").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_metric_bindings").fetchone()[0] == 1
        assert con.execute("select count(*) from ds_observations").fetchone()[0] == 4
    finally:
        con.close()
    assert second.epoch_id == 2
    assert second.replayed is False
    overlay.close()


def test_overlay_reconciles_stamp_against_complete_owner_denominator(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "UPDATE acquisition_epochs SET semantic_epoch_stamp_sha256 = ? WHERE epoch_id = 1",
            ["sha256:" + "0" * 64],
        )
    finally:
        con.close()

    owner_query = scenario.service._owner_query(  # noqa: SLF001
        kind="catalog_acquisition",
        query=scenario.query,
    )
    receipt = scenario.overlay.resolve_native_membership(query=owner_query)

    assert receipt.declared_native_member_count == 1
    assert receipt.status == "unresolved"
    assert receipt.assessments[0].binding_status == "invalid"
    assert receipt.assessments[0].failure_code == "acquisition_candidate_binding_mismatch"


def test_active_owner_readback_refuses_value_drift_with_receipt_markers_retained(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _, activated = _activate_real_epoch_scenario(scenario)
    sibling = _second_real_epoch_scenario(scenario, epoch_id=2)
    baseline_identity = scenario.overlay._require_baseline_unchanged()
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        owner_markers = con.execute(
            "SELECT admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
            "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
            [scenario.passport.epoch_id, scenario.passport.passport_id],
        ).fetchone()
        member_markers = tuple(
            con.execute(
                "SELECT table_name, canonical_primary_key_bytes, canonical_primary_key_hash "
                "FROM acquisition_epoch_members WHERE epoch_id = ? AND passport_id = ? "
                "ORDER BY table_name, canonical_primary_key_hash",
                [scenario.passport.epoch_id, scenario.passport.passport_id],
            ).fetchall()
        )
        sibling_markers = tuple(
            con.execute(
                "SELECT table_name, canonical_primary_key_bytes, canonical_primary_key_hash "
                "FROM acquisition_epoch_members WHERE epoch_id = ? AND passport_id = ? "
                "ORDER BY table_name, canonical_primary_key_hash",
                [sibling.passport.epoch_id, sibling.passport.passport_id],
            ).fetchall()
        )
    finally:
        con.close()
    assert owner_markers is not None
    prefix = "ds_observations|observation_id="

    def observation_ids(members: tuple[tuple[object, ...], ...]) -> tuple[str, ...]:
        return tuple(
            bytes.fromhex(bytes(row[1]).decode("ascii").removeprefix(prefix)).decode("utf-8")
            for row in members
            if row[0] == "ds_observations"
        )

    selected_ids = observation_ids(member_markers)
    sibling_ids = observation_ids(sibling_markers)
    assert selected_ids
    assert sibling_ids
    assert set(selected_ids).isdisjoint(sibling_ids)
    observation_id = selected_ids[0]
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        original_row = con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone()
        sibling_rows = tuple(
            con.execute(
                "SELECT observation_id, value FROM ds_observations "
                "WHERE observation_id IN (?, ?) ORDER BY observation_id",
                sibling_ids[:2],
            ).fetchall()
        )
    finally:
        con.close()
    assert original_row is not None
    assert original_row[0] in selected_ids
    assert len(sibling_rows) == len(sibling_ids)

    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
            [float(original_row[1]) + 1.0, observation_id],
        )
    finally:
        con.close()

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        assert con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone() == (observation_id, float(original_row[1]) + 1.0)
        assert (
            con.execute(
                "SELECT admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
                "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
                [scenario.passport.epoch_id, scenario.passport.passport_id],
            ).fetchone()
            == owner_markers
        )
        assert (
            tuple(
                con.execute(
                    "SELECT table_name, canonical_primary_key_bytes, canonical_primary_key_hash "
                    "FROM acquisition_epoch_members WHERE epoch_id = ? AND passport_id = ? "
                    "ORDER BY table_name, canonical_primary_key_hash",
                    [scenario.passport.epoch_id, scenario.passport.passport_id],
                ).fetchall()
            )
            == member_markers
        )
        assert (
            tuple(
                con.execute(
                    "SELECT observation_id, value FROM ds_observations "
                    "WHERE observation_id IN (?, ?) ORDER BY observation_id",
                    sibling_ids[:2],
                ).fetchall()
            )
            == sibling_rows
        )
    finally:
        con.close()
    assert scenario.overlay._require_baseline_unchanged() == baseline_identity

    with pytest.raises(OverlayAdmissionError, match="active_epoch_observation_content_mismatch"):
        scenario.overlay.read_activated_semantic_epoch_admission(
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )


def test_active_observation_projection_binds_selected_rows_and_rejects_row_drift(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _, activated = _activate_real_epoch_scenario(scenario)

    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )

    assert projection.activation_state == "active"
    assert projection.epoch_id == scenario.passport.epoch_id
    assert projection.passport_id == scenario.passport.passport_id
    assert projection.admission_content_sha256 == activated.admission_content_sha256
    assert projection.source_time_status == "not_established"
    observations = tuple(row.observation for row in projection.observations)
    assert tuple(row.value for row in observations) == (0.42, 0.51)
    assert tuple(row.country_code for row in observations) == ("UA", "UA")
    assert tuple(row.year for row in observations) == (2024, 2025)
    assert len({row.observation_id for row in observations}) == 2
    assert all(
        row.row_content_sha256 == overlay_module.content_sha256(observation.model_dump(mode="json"))
        for row, observation in zip(projection.observations, observations, strict=True)
    )

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        owner_markers = con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
            "FROM acquisition_epochs WHERE epoch_id = ?",
            [scenario.passport.epoch_id],
        ).fetchone()
    finally:
        con.close()
    assert owner_markers is not None

    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
            [0.43, observations[0].observation_id],
        )
    finally:
        con.close()

    with pytest.raises(
        OverlayAdmissionError,
        match="active_epoch_observation_content_mismatch",
    ):
        scenario.overlay.read_activated_semantic_epoch_observations(
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        assert (
            con.execute(
                "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
                "FROM acquisition_epochs WHERE epoch_id = ?",
                [scenario.passport.epoch_id],
            ).fetchone()
            == owner_markers
        )
    finally:
        con.close()


def test_active_owner_readback_refuses_unrepresented_year_and_condition_with_markers_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, _condition_rows())
    _, activated = _activate_real_epoch_scenario(scenario)
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        owner_markers = con.execute(
            "SELECT admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
            "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
            [scenario.passport.epoch_id, scenario.passport.passport_id],
        ).fetchone()
        member_markers = tuple(
            con.execute(
                "SELECT table_name, canonical_primary_key_bytes, canonical_primary_key_hash "
                "FROM acquisition_epoch_members WHERE epoch_id = ? AND passport_id = ? "
                "ORDER BY table_name, canonical_primary_key_hash",
                [scenario.passport.epoch_id, scenario.passport.passport_id],
            ).fetchall()
        )
    finally:
        con.close()
    assert owner_markers is not None
    assert sum(str(member[0]) == "ds_observations" for member in member_markers) == 2

    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute("ALTER TABLE ds_observations DROP COLUMN year")
        con.execute("ALTER TABLE ds_observations DROP COLUMN condition_json")
    finally:
        con.close()

    with pytest.raises(
        OverlayAdmissionError,
        match="active_epoch_observation_projection_incomplete",
    ):
        scenario.overlay.read_activated_semantic_epoch_admission(
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        assert (
            con.execute(
                "SELECT admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
                "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
                [scenario.passport.epoch_id, scenario.passport.passport_id],
            ).fetchone()
            == owner_markers
        )
        assert (
            tuple(
                con.execute(
                    "SELECT table_name, canonical_primary_key_bytes, canonical_primary_key_hash "
                    "FROM acquisition_epoch_members WHERE epoch_id = ? AND passport_id = ? "
                    "ORDER BY table_name, canonical_primary_key_hash",
                    [scenario.passport.epoch_id, scenario.passport.passport_id],
                ).fetchall()
            )
            == member_markers
        )
    finally:
        con.close()


def test_admission_refuses_populated_year_and_condition_missing_from_owner_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, _condition_rows())
    reduced = CatalogAcquisitionOverlay(
        scenario.authority.baseline_path,
        tmp_path / "reduced-overlay.duckdb",
    )
    reduced.initialize()
    con = duckdb.connect(str(reduced.overlay_path))
    try:
        con.execute("ALTER TABLE ds_observations DROP COLUMN year")
        con.execute("ALTER TABLE ds_observations DROP COLUMN condition_json")
    finally:
        con.close()

    with pytest.raises(OverlayAdmissionError, match="overlay_observation_schema_incomplete"):
        _admit(
            reduced,
            passport=scenario.passport,
            store=scenario.store,
            authority=scenario.authority,
        )

    con = duckdb.connect(str(reduced.overlay_path), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM acquisition_epochs").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM acquisition_epoch_members").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM ds_observations").fetchone() == (0,)
    finally:
        con.close()


def test_admission_preserves_populated_year_and_condition_in_reduced_owner_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, _condition_rows())
    reduced = CatalogAcquisitionOverlay(
        scenario.authority.baseline_path,
        tmp_path / "reduced-preserving-overlay.duckdb",
    )
    reduced.initialize()
    con = duckdb.connect(str(reduced.overlay_path))
    try:
        # survey_year is null for every source row, so this reduced schema still
        # faithfully represents all populated temporal and condition values.
        con.execute("ALTER TABLE ds_observations DROP COLUMN survey_year")
    finally:
        con.close()

    receipt = _admit(
        reduced,
        passport=scenario.passport,
        store=scenario.store,
        authority=scenario.authority,
    )
    assert receipt.admitted_observation_count == 2
    con = duckdb.connect(str(reduced.overlay_path), read_only=True)
    try:
        assert tuple(
            con.execute(
                "SELECT year, condition_json, value FROM ds_observations ORDER BY condition_json"
            ).fetchall()
        ) == (
            (2024, '{"cohort":"alpha"}', 0.42),
            (2025, '{"cohort":"beta"}', 0.51),
        )
    finally:
        con.close()


def test_active_owner_readback_checks_observations_across_projection_chunk_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {
            "country_code": "UA",
            "year": 2024,
            "distress_score": 0.2 + (index % 60) / 100,
            "condition_json": {"case": f"{index:03d}"},
        }
        for index in range(129)
    ]
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, rows)
    _, activated = _activate_real_epoch_scenario(scenario)
    resolved = scenario.overlay.read_activated_semantic_epoch_admission(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    assert resolved.admitted_observation_count == 129

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        boundary_row = con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE condition_json = ?",
            ['{"case":"128"}'],
        ).fetchone()
    finally:
        con.close()
    assert boundary_row is not None
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
            [float(boundary_row[1]) + 0.01, boundary_row[0]],
        )
    finally:
        con.close()
    with pytest.raises(
        OverlayAdmissionError,
        match="active_epoch_observation_content_mismatch",
    ):
        scenario.overlay.read_activated_semantic_epoch_admission(
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )


def test_v1_table_migrates_transactionally_to_nullable_v2_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay_path = tmp_path / "overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    overlay.close()
    con = duckdb.connect(str(overlay_path))
    try:
        con.execute("DROP TABLE acquisition_epochs")
        con.execute(
            """
            CREATE TABLE acquisition_epochs (
                epoch_id BIGINT PRIMARY KEY,
                passport_id VARCHAR NOT NULL,
                admission_content_sha256 VARCHAR NOT NULL,
                baseline_content_sha256 VARCHAR NOT NULL,
                admitted_observation_count BIGINT NOT NULL,
                observation_class VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            "INSERT INTO acquisition_epochs VALUES (1, 'legacy', ?, ?, 1, 'observed')",
            ["sha256:" + "1" * 64, _sha256(authority.baseline_path)],
        )
    finally:
        con.close()

    original = overlay_module._ensure_epoch_state_constraint

    def fail_before_table_swap(_con) -> None:
        raise RuntimeError("migration-falsifier")

    monkeypatch.setattr(overlay_module, "_ensure_epoch_state_constraint", fail_before_table_swap)
    with pytest.raises(RuntimeError, match="migration-falsifier"):
        CatalogAcquisitionOverlay(authority.baseline_path, overlay_path).initialize()
    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        rolled_back = tuple(
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'acquisition_epochs' ORDER BY ordinal_position"
            ).fetchall()
        )
    finally:
        con.close()
    assert rolled_back == tuple(
        name for name, _, _ in overlay_module._ACQUISITION_EPOCH_COLUMNS[:6]
    )

    monkeypatch.setattr(overlay_module, "_ensure_epoch_state_constraint", original)
    migrated = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    migrated.initialize()
    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        columns = tuple(
            (str(name), str(data_type), str(nullable))
            for name, data_type, nullable in con.execute(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'acquisition_epochs' ORDER BY ordinal_position"
            ).fetchall()
        )
        state = con.execute(
            "SELECT epoch_activation_state, semantic_epoch_ref FROM acquisition_epochs"
        ).fetchone()
    finally:
        con.close()
    assert columns == overlay_module._ACQUISITION_EPOCH_COLUMNS
    assert state == ("legacy_not_established", None)


def test_partial_semantic_stamp_columns_fail_closed(tmp_path: Path) -> None:
    _, _, authority, _ = _valid_passport(tmp_path / "evidence")
    overlay_path = tmp_path / "overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(authority.baseline_path, overlay_path)
    overlay.initialize()
    overlay.close()
    con = duckdb.connect(str(overlay_path))
    try:
        con.execute("DROP TABLE acquisition_epochs")
        con.execute(
            """
            CREATE TABLE acquisition_epochs (
                epoch_id BIGINT PRIMARY KEY,
                passport_id VARCHAR NOT NULL,
                admission_content_sha256 VARCHAR NOT NULL,
                baseline_content_sha256 VARCHAR NOT NULL,
                admitted_observation_count BIGINT NOT NULL,
                observation_class VARCHAR NOT NULL,
                semantic_epoch_ref VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO acquisition_epochs VALUES (1, 'partial', ?, ?, 1, 'observed', ?)",
            ["sha256:" + "1" * 64, _sha256(authority.baseline_path), "sha256:" + "2" * 64],
        )
    finally:
        con.close()

    with pytest.raises(OverlayAdmissionError, match="partial_semantic_stamp_columns"):
        CatalogAcquisitionOverlay(authority.baseline_path, overlay_path).initialize()
    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        columns = tuple(
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'acquisition_epochs' ORDER BY ordinal_position"
            ).fetchall()
        )
    finally:
        con.close()
    assert columns[-1] == "semantic_epoch_ref"
    assert "semantic_epoch_stamp_json" not in columns


def test_every_baseline_union_table_has_generated_member_key_and_epoch_relation(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT table_name, count(*) FROM acquisition_epoch_members "
            "GROUP BY table_name ORDER BY table_name"
        ).fetchall()
    finally:
        con.close()
    observed = {str(table): int(count) for table, count in rows}
    assert set(observed) == set(overlay_module._BASELINE_UNION_TABLES)
    assert sum(observed.values()) == 7
    assert observed["ds_observations"] == 2
    assert all(count == 1 for table, count in observed.items() if table != "ds_observations")


def test_novel_union_table_without_native_key_relation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, authority, _ = _valid_passport(tmp_path / "evidence")
    con = duckdb.connect(str(authority.baseline_path))
    try:
        con.execute("CREATE TABLE novel_epoch_table(value INTEGER)")
    finally:
        con.close()
    monkeypatch.setattr(
        overlay_module,
        "_BASELINE_UNION_TABLES",
        (*overlay_module._BASELINE_UNION_TABLES, "novel_epoch_table"),
    )
    with pytest.raises(
        OverlayAdmissionError,
        match="baseline_native_key_denominator_unresolved",
    ):
        CatalogAcquisitionOverlay(
            authority.baseline_path,
            tmp_path / "overlay.duckdb",
        ).initialize()


def test_activation_retry_cannot_append_a_second_semantic_epoch(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    production, first = _activate_real_epoch_scenario(scenario)
    second = scenario.overlay.activate_semantic_epoch(
        pending_receipt=scenario.pending,
        production_receipt=production,
        artifact_store=scenario.store,
    )
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        epoch_count = con.execute("SELECT count(*) FROM acquisition_epochs").fetchone()[0]
    finally:
        con.close()
    assert first.replayed is False
    assert second.replayed is True
    assert first.receipt_ref == second.receipt_ref
    assert epoch_count == 1


def test_same_candidate_two_ordinals_change_native_not_semantic_denominator(
    tmp_path: Path,
) -> None:
    first = _real_epoch_scenario(tmp_path)
    second = _second_real_epoch_scenario(first)
    owner_query = first.service.acquisition_owner_query(query=first.query)
    native = first.overlay.resolve_native_membership(query=owner_query)
    semantic = first.overlay.resolve_semantic_candidate_denominator(
        query=owner_query,
        native_membership=native,
    )

    assert native.declared_native_member_count == 2
    assert {row.operational_epoch_id for row in native.assessments} == {1, 2}
    assert semantic.declared_unique_candidate_count == 1
    assert second.prepared.stamp.epoch_ref == first.prepared.stamp.epoch_ref


def test_overlay_ordinal_never_substitutes_for_semantic_epoch_ref(tmp_path: Path) -> None:
    first = _real_epoch_scenario(tmp_path, epoch_id=41)
    second = _second_real_epoch_scenario(first, epoch_id=97)

    assert first.passport.epoch_id == 41
    assert second.passport.epoch_id == 97
    assert first.passport.semantic_epoch_ref == second.passport.semantic_epoch_ref
    assert first.passport.semantic_epoch_ref == first.prepared.stamp.epoch_ref


def test_duplicate_ordinal_projection_binds_every_native_row(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    replay = scenario.overlay.admit_epoch(
        passport=scenario.passport,
        prepared_epoch=scenario.prepared,
        boundary_candidate=scenario.candidate,
        artifact_store=scenario.store,
        authority=scenario.authority,
    )
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        relation_count = con.execute(
            "SELECT count(*) FROM acquisition_epoch_members WHERE epoch_id = 1"
        ).fetchone()[0]
    finally:
        con.close()
    assert replay.replayed is True
    assert relation_count == 7


def test_deleting_reused_native_row_fails_complete_membership_receipt(
    tmp_path: Path,
) -> None:
    first = _real_epoch_scenario(tmp_path)
    second = _second_real_epoch_scenario(first)
    con = duckdb.connect(str(first.overlay.overlay_path))
    try:
        con.execute("DELETE FROM ds_datasets")
    finally:
        con.close()
    owner_query = first.service.acquisition_owner_query(query=first.query)
    with pytest.raises(
        OverlayAdmissionError,
        match="overlay_native_member_physical_row_mismatch",
    ):
        first.overlay.emit_admitted_boundary_evidence(
            query=owner_query,
            passport=second.passport,
            prepared_epoch=second.prepared,
            boundary_candidate=second.candidate,
            pending_receipt=second.pending,
            artifact_store=second.store,
        )


@pytest.mark.parametrize("deleted_table", ["acquisition_epochs", "acquisition_passports"])
def test_deleting_either_native_row_fails_membership_completeness(
    tmp_path: Path,
    deleted_table: str,
) -> None:
    first = _real_epoch_scenario(tmp_path)
    con = duckdb.connect(str(first.overlay.overlay_path))
    try:
        con.execute(
            f"DELETE FROM {deleted_table} WHERE epoch_id = ?",  # noqa: S608
            [first.passport.epoch_id],
        )
    finally:
        con.close()
    owner_query = first.service.acquisition_owner_query(query=first.query)
    receipt = first.overlay.resolve_native_membership(query=owner_query)
    assert receipt.status == "unresolved"
    assert receipt.declared_native_member_count == 1
    assert receipt.assessments[0].operational_epoch_id == first.passport.epoch_id
    assert receipt.assessments[0].failure_code == "acquisition_candidate_binding_mismatch"


def test_orphan_membership_rows_remain_in_native_denominator(tmp_path: Path) -> None:
    first = _real_epoch_scenario(tmp_path)
    con = duckdb.connect(str(first.overlay.overlay_path))
    try:
        con.execute(
            "DELETE FROM acquisition_epochs WHERE epoch_id = ?",
            [first.passport.epoch_id],
        )
        con.execute(
            "DELETE FROM acquisition_passports WHERE epoch_id = ?",
            [first.passport.epoch_id],
        )
    finally:
        con.close()
    owner_query = first.service.acquisition_owner_query(query=first.query)
    receipt = first.overlay.resolve_native_membership(query=owner_query)
    assert receipt.status == "unresolved"
    assert receipt.declared_native_member_count == 1
    assert receipt.assessments[0].operational_epoch_id == first.passport.epoch_id
    assert receipt.assessments[0].failure_code == "acquisition_candidate_binding_mismatch"


def test_distinct_invalid_passport_bytes_change_owner_snapshot(tmp_path: Path) -> None:
    first = _real_epoch_scenario(tmp_path)
    owner_query = first.service.acquisition_owner_query(query=first.query)

    def resolve_after_fabrication(serial: int):
        con = duckdb.connect(str(first.overlay.overlay_path))
        try:
            con.execute(
                "UPDATE acquisition_passports SET passport_json = ? "
                "WHERE epoch_id = ? AND passport_id = ?",
                [
                    json.dumps({"fabricated_passport": serial}, separators=(",", ":")),
                    first.passport.epoch_id,
                    first.passport.passport_id,
                ],
            )
        finally:
            con.close()
        return first.overlay.resolve_native_membership(query=owner_query)

    first_receipt = resolve_after_fabrication(1)
    second_receipt = resolve_after_fabrication(2)

    assert first_receipt.failure_codes == ("acquisition_candidate_binding_mismatch",)
    assert second_receipt.failure_codes == ("acquisition_candidate_binding_mismatch",)
    assert (
        first_receipt.owner_source_snapshot_content_hash
        != second_receipt.owner_source_snapshot_content_hash
    )
    assert first_receipt.native_membership_hash != second_receipt.native_membership_hash
    assert (
        first_receipt.assessments[0].native_member_content_hash
        != second_receipt.assessments[0].native_member_content_hash
    )


def test_deleting_bound_overlay_member_fails_physical_completeness(tmp_path: Path) -> None:
    first = _real_epoch_scenario(tmp_path)
    _second_real_epoch_scenario(first)
    con = duckdb.connect(str(first.overlay.overlay_path))
    try:
        con.execute(
            "DELETE FROM ds_observations WHERE observation_id = "
            "(SELECT observation_id FROM ds_observations ORDER BY observation_id LIMIT 1)"
        )
    finally:
        con.close()
    owner_query = first.service.acquisition_owner_query(query=first.query)
    with pytest.raises(
        OverlayAdmissionError,
        match="overlay_native_member_physical_row_mismatch",
    ):
        first.overlay.resolve_native_membership(query=owner_query)


def test_candidate_a_with_native_row_or_passport_b_refuses(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    other_ref = scenario.store.put_bytes(
        b"other-candidate",
        ArtifactWriteOptions(
            kind="epoch.acquisition_semantic_boundary_candidate",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    forged_passport = scenario.passport.model_copy(
        update={"semantic_boundary_candidate_ref": other_ref}
    )
    with pytest.raises(OverlayAdmissionError, match="prepared_epoch_candidate_binding_mismatch"):
        scenario.overlay.admit_epoch(
            passport=forged_passport,
            prepared_epoch=scenario.prepared,
            boundary_candidate=scenario.candidate,
            artifact_store=scenario.store,
            authority=scenario.authority,
        )


def test_same_semantic_candidate_under_two_ordinals_keeps_one_epoch_ref(
    tmp_path: Path,
) -> None:
    first = _real_epoch_scenario(tmp_path)
    second = _second_real_epoch_scenario(first)

    assert first.passport.semantic_epoch_ref == second.passport.semantic_epoch_ref
    assert first.passport.semantic_epoch_ref == first.prepared.stamp.epoch_ref


def test_legacy_native_row_is_recorded_and_blocks_positive_epoch(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _downgrade_to_authentic_v1(scenario)
    owner_query = scenario.service.acquisition_owner_query(query=scenario.query)
    native = scenario.overlay.resolve_native_membership(query=owner_query)
    owner_snapshot_bytes = scenario.overlay.load_acquisition_owner_snapshot(
        ref=native.owner_source_snapshot_ref
    )
    semantic_epoch_runtime._validate_owner_snapshot_reference_graph(
        json.loads(owner_snapshot_bytes[8:]),
        owner_kind="catalog_acquisition",
    )
    semantic = scenario.overlay.resolve_semantic_candidate_denominator(
        query=owner_query,
        native_membership=native,
    )

    assert native.declared_native_member_count == 1
    assert native.status == "unresolved"
    assert native.assessments[0].binding_status == "legacy_unresolved"
    assert native.assessments[0].failure_code == (
        "legacy_acquisition_candidate_identity_not_established"
    )
    assert semantic.status == "unresolved"


def test_legacy_row_has_not_established_semantic_epoch(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    legacy_id = _downgrade_to_authentic_v1(scenario)
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        row = con.execute(
            "SELECT passport_id, semantic_epoch_ref, epoch_activation_state "
            "FROM acquisition_epochs WHERE epoch_id = 1"
        ).fetchone()
    finally:
        con.close()
    assert row == (legacy_id, None, "legacy_not_established")


def test_epoch_statement_readback_recanonicalizes_typed_native_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real membership bytes survive Core readback, while changed decoded bytes refuse."""

    scenario = _real_epoch_scenario(tmp_path)
    query = scenario.service.acquisition_owner_query(query=scenario.query)
    membership = scenario.overlay.resolve_native_membership(query=query)
    kind = "epoch.r1721_typed_native_membership_fixture"
    domain = "polisyos.test.r1721-typed-native-membership"

    ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=scenario.store,
        value=membership,
        kind=kind,
        domain=domain,
    )
    assert ref.manifest_profile_sha256 is not None
    persisted = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=ref,
        expected_kind=kind,
    )
    persisted_query = persisted.get("query")
    assert isinstance(persisted_query, dict)
    assert isinstance(persisted_query.get("valid_effect_coordinate_bytes"), bytes)
    expected_canonical = contracts.epoch.canonical_epoch_bytes(membership)
    assert contracts.epoch.canonical_epoch_bytes(persisted) == expected_canonical
    assert (
        scenario.store.get_bytes(ref)
        == len(expected_canonical).to_bytes(8, "big") + expected_canonical
    )
    assert scenario.store.get_manifest(ref).canon == contracts.epoch.epoch_canon_info()

    real_reader = overlay_module._load_profiled_framed_statement

    def altered_readback(
        *,
        artifact_store: overlay_module._ArtifactStore,
        ref: overlay_module.ArtifactRef,
        expected_kind: str,
        raw_payload_bytes: bytes | None = None,
    ) -> dict[str, object]:
        mapping = real_reader(
            artifact_store=artifact_store,
            ref=ref,
            expected_kind=expected_kind,
            raw_payload_bytes=raw_payload_bytes,
        )
        if expected_kind != kind:
            return mapping
        query_mapping = mapping.get("query")
        if not isinstance(query_mapping, dict):
            raise AssertionError("native membership query did not decode as a mapping")
        altered_query = dict(query_mapping)
        altered_query["valid_effect_coordinate_bytes"] = b"changed-after-profile-read"
        return {**mapping, "query": altered_query}

    monkeypatch.setattr(overlay_module, "_load_profiled_framed_statement", altered_readback)
    with pytest.raises(OverlayAdmissionError) as refusal:
        overlay_module._persist_epoch_statement(
            artifact_store=scenario.store,
            value=membership,
            kind=kind,
            domain=domain,
        )
    assert refusal.value.code == "semantic_external_receipt_profile_readback_mismatch"
    assert (
        scenario.store.get_bytes(ref)
        == len(expected_canonical).to_bytes(8, "big") + expected_canonical
    )
    assert scenario.store.get_manifest(ref).canon == contracts.epoch.epoch_canon_info()
    assert ref.manifest_profile_sha256 is not None


def test_semantic_frame_producers_bind_their_actual_codec_and_refuse_profileless_history(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "profiled-overlay-cas")
    external_kind = "epoch.r6_external_statement_fixture"
    external_value = {"amount": 1.25, "optional": None}
    external_ref, _ = overlay_module._persist_external_statement(
        artifact_store=store,
        value=external_value,
        kind=external_kind,
    )
    external_profile = contracts.epoch.external_epoch_statement_canon_info()
    assert external_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(external_ref).canon == external_profile
    assert (
        overlay_module._load_external_statement(
            artifact_store=store,
            ref=external_ref,
            expected_kind=external_kind,
        )
        == external_value
    )

    legacy_body = overlay_module.fabric_data_plane.canonical_json_bytes(external_value)
    legacy_ref = store.put_bytes(
        len(legacy_body).to_bytes(8, "big") + legacy_body,
        ArtifactWriteOptions(
            kind=external_kind,
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    with pytest.raises(OverlayAdmissionError) as refusal:
        overlay_module._load_external_statement(
            artifact_store=store,
            ref=legacy_ref,
            expected_kind=external_kind,
        )
    assert refusal.value.code == "semantic_external_receipt_profile_missing"
    assert (
        store.get_bytes(legacy_ref.artifact_id) == len(legacy_body).to_bytes(8, "big") + legacy_body
    )

    epoch_kind = "epoch.r6_epoch_statement_fixture"
    epoch_ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=store,
        value={"ordinal": 4},
        kind=epoch_kind,
        domain="polisyos.test.r6-epoch-frame",
    )
    assert epoch_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(epoch_ref).canon == overlay_module.epoch_contract.epoch_canon_info()


def _alternate_profiled_provenance_ref(
    scenario: SimpleNamespace,
    owner_ref: overlay_module.ArtifactRef,
) -> overlay_module.ArtifactRef:
    """Persist the same owner bytes under a different, valid CAS canon profile."""
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        owner_mapping, _ = overlay_module._load_owner_record(
            con,
            ref=owner_ref,
            expected_kind="epoch.acquisition_projection_verifier_provenance",
        )
    finally:
        con.close()
    canonical = contracts.epoch.canonical_epoch_bytes(owner_mapping)
    payload = len(canonical).to_bytes(8, "big") + canonical
    alternate_canon = CanonInfo.from_spec(
        overlay_module.canon.CanonSpec(forbid_floats=False, exclude_none=False)
    )
    alternate_ref = scenario.store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=owner_ref.kind,
            media_type=owner_ref.media_type,
            canon=alternate_canon,
        ),
        return_selected_profile=True,
    )
    assert alternate_ref.artifact_id == owner_ref.artifact_id
    assert alternate_ref.kind == owner_ref.kind
    assert alternate_ref.media_type == owner_ref.media_type
    assert alternate_ref.manifest_profile_sha256 is not None
    assert scenario.store.get_bytes(alternate_ref) == payload
    assert scenario.store.get_manifest(alternate_ref).canon == alternate_canon
    return alternate_ref


def test_real_admission_finalizer_reconciles_owner_and_selected_provenance_views(
    tmp_path: Path,
) -> None:
    """The fresh finalizer resolves the actual selected CAS provenance before its gate."""
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    admitted_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    projection_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.semantic_projection_verification_receipt_ref,
        expected_kind="epoch.acquisition_semantic_projection_verification_receipt",
    )
    projection = contracts.epoch.AcquisitionSemanticProjectionVerificationReceipt.model_validate(
        projection_mapping
    )
    provenance_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.verifier_provenance_ref,
        expected_kind="epoch.acquisition_projection_verifier_provenance",
    )
    provenance = contracts.epoch.AcquisitionProjectionVerifierProvenance.model_validate(
        provenance_mapping
    )

    owner_ref = projection.verifier_provenance_ref
    selected_ref = admitted.verifier_provenance_ref
    assert owner_ref.manifest_profile_sha256 is None
    assert selected_ref.manifest_profile_sha256 is not None
    assert selected_ref.artifact_id == owner_ref.artifact_id
    assert selected_ref.kind == owner_ref.kind
    assert selected_ref.media_type == owner_ref.media_type
    assert scenario.store.get_manifest(selected_ref).canon == contracts.epoch.epoch_canon_info()
    assert projection.status == "verified"
    assert projection.verifier_provenance_content_hash == overlay_module._semantic_content_hash(
        domain="polisyos.epoch.acquisition-projection-verifier.v1",
        value=provenance,
    )

    selected_profiles = semantic_epoch_runtime._resolve_selected_reference_graph(
        scenario.store, admitted
    )
    assert selected_profiles is not None
    selected_kinds = {kind for _, kind, _ in selected_profiles}
    assert {
        "epoch.semantic_facet_source.v1",
        "epoch.coordinate.valid_effect.v1",
        "epoch.coordinate.visibility_knowledge_cutoff.v1",
        "epoch.coordinate.purpose_admission_cutoff.v1",
        "epoch.acquisition_owner_snapshot",
        "epoch.acquisition_native_membership",
        "epoch.acquisition_native_member",
        "epoch.acquisition_passport_snapshot",
        "epoch.acquisition_semantic_boundary_candidate",
        "epoch.acquisition_semantic_denominator_receipt",
        "epoch.acquisition_semantic_projection_verification_receipt",
        "epoch.acquisition_projection_verifier_provenance",
    } <= selected_kinds
    passport_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.passport_ref,
        expected_kind="epoch.acquisition_passport_snapshot",
    )
    native_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.native_member_ref,
        expected_kind="epoch.acquisition_native_member",
    )
    pending_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.pending_overlay_receipt_ref,
        expected_kind="epoch.pending_overlay_admission_receipt",
    )
    native_receipt_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.native_membership_receipt_ref,
        expected_kind="epoch.acquisition_native_membership",
    )
    semantic_receipt_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.semantic_denominator_receipt_ref,
        expected_kind="epoch.acquisition_semantic_denominator_receipt",
    )
    projection_owner = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.semantic_projection_verification_receipt_ref,
        expected_kind="epoch.acquisition_semantic_projection_verification_receipt",
    )
    for owner_projection in (
        passport_owner,
        native_owner,
        pending_owner,
        native_receipt_owner,
        semantic_receipt_owner,
        projection_owner,
        provenance,
    ):
        assert semantic_epoch_runtime._owner_reference_graph_matches_selected(
            selected_profiles, owner_projection, store=scenario.store
        )
    assert content_sha256(passport_owner) == admitted.passport_content_hash
    assert content_sha256(pending_owner) == admitted.pending_overlay_receipt_content_hash
    assert semantic_epoch_runtime._selected_ref_graph_matches_owner_projection(
        admitted.semantic_epoch_stamp, passport_owner["semantic_epoch_stamp"]
    )
    forged_stamp = dict(passport_owner["semantic_epoch_stamp"])
    forged_manifest_ref = dict(forged_stamp["semantic_manifest_ref"])
    forged_manifest_ref["manifest_profile_sha256"] = "sha256:" + "0" * 64
    forged_stamp["semantic_manifest_ref"] = forged_manifest_ref
    assert not semantic_epoch_runtime._selected_ref_graph_matches_owner_projection(
        admitted.semantic_epoch_stamp, forged_stamp
    )
    assert not semantic_epoch_runtime._owner_reference_graph_matches_selected(
        selected_profiles, {"semantic_epoch_stamp": forged_stamp}, store=scenario.store
    )

    production = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )

    # The actual provenance chain has passed; this fixture still lacks the separate
    # appointed policy authority, so no positive epoch production is claimed.
    assert production.status == "not_established"
    assert production.failure_codes == ("policy_admission_missing",)


def test_real_finalizer_refuses_passport_claim_drift_after_normal_owner_baseline(
    tmp_path: Path,
) -> None:
    """A changed admitted passport claim is refused by recursive owner binding."""
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    baseline = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )
    assert baseline.status == "not_established"
    assert baseline.failure_codes == ("policy_admission_missing",)

    admitted_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    original_passport_bytes = scenario.store.get_bytes(admitted.passport_ref)
    forged_hash = "sha256:" + "0" * 64
    if forged_hash == admitted.passport_content_hash:
        forged_hash = "sha256:" + "1" * 64
    forged = admitted.model_copy(update={"passport_content_hash": forged_hash})
    forged_ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=scenario.store,
        value=forged,
        kind="epoch.admitted_acquisition_boundary_evidence",
        domain="polisyos.epoch.admitted-acquisition-boundary-evidence.v1",
    )

    production = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=forged_ref,
    )

    # This field-only mutation is refused by the earlier recursive owner binding;
    # it is not claimed as an isolated test of the later mapping-hash comparison.
    assert production.status == "not_established"
    assert production.failure_codes == ("epoch_scope_unresolved",)
    assert scenario.store.get_bytes(admitted.passport_ref) == original_passport_bytes


def test_real_finalizer_rejects_pending_hash_drift_after_normal_owner_baseline(
    tmp_path: Path,
) -> None:
    """The selected pending statement hash is checked before policy refusal."""
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    baseline = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )
    assert baseline.status == "not_established"
    assert baseline.failure_codes == ("policy_admission_missing",)

    admitted_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    original_pending_bytes = scenario.store.get_bytes(admitted.pending_overlay_receipt_ref)
    forged_hash = "sha256:" + "0" * 64
    if forged_hash == admitted.pending_overlay_receipt_content_hash:
        forged_hash = "sha256:" + "1" * 64
    forged = admitted.model_copy(update={"pending_overlay_receipt_content_hash": forged_hash})
    forged_ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=scenario.store,
        value=forged,
        kind="epoch.admitted_acquisition_boundary_evidence",
        domain="polisyos.epoch.admitted-acquisition-boundary-evidence.v1",
    )

    production = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=forged_ref,
    )

    assert production.status == "not_established"
    assert production.failure_codes == ("epoch_scope_unresolved",)
    assert scenario.store.get_bytes(admitted.pending_overlay_receipt_ref) == original_pending_bytes


def test_fresh_admission_consumer_refuses_same_bytes_under_wrong_provenance_profile(
    tmp_path: Path,
) -> None:
    """A different resolvable profile cannot substitute for the epoch provenance profile."""
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    admitted_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    original_provenance_bytes = scenario.store.get_bytes(admitted.verifier_provenance_ref)
    wrong_profile_ref = _alternate_profiled_provenance_ref(
        scenario,
        admitted.verifier_provenance_ref,
    )
    assert wrong_profile_ref.manifest_profile_sha256 != (
        admitted.verifier_provenance_ref.manifest_profile_sha256
    )
    assert scenario.store.get_bytes(admitted.verifier_provenance_ref) == original_provenance_bytes

    forged_evidence = admitted.model_copy(update={"verifier_provenance_ref": wrong_profile_ref})
    forged_evidence_ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=scenario.store,
        value=forged_evidence,
        kind="epoch.admitted_acquisition_boundary_evidence",
        domain="polisyos.epoch.admitted-acquisition-boundary-evidence.v1",
    )
    production = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=forged_evidence_ref,
    )

    assert production.status == "not_established"
    assert production.failure_codes == ("epoch_scope_unresolved",)
    assert scenario.store.get_bytes(admitted.verifier_provenance_ref) == original_provenance_bytes
    assert scenario.store.get_manifest(wrong_profile_ref).canon != (
        contracts.epoch.epoch_canon_info()
    )

    # Keep the admitted artifact, IDs, and content intact while selecting the same
    # semantic-manifest bytes through a canon that its producer did not declare.
    selected_manifest_ref = admitted.semantic_epoch_stamp.semantic_manifest_ref
    manifest_bytes = scenario.store.get_bytes(selected_manifest_ref)
    alternate_manifest_ref = scenario.store.put_bytes(
        manifest_bytes,
        ArtifactWriteOptions(
            kind=selected_manifest_ref.kind,
            media_type=selected_manifest_ref.media_type,
            canon=contracts.epoch.external_epoch_statement_canon_info(),
        ),
        return_selected_profile=True,
    )
    assert alternate_manifest_ref.artifact_id == selected_manifest_ref.artifact_id
    assert alternate_manifest_ref.manifest_profile_sha256 != (
        selected_manifest_ref.manifest_profile_sha256
    )
    alternate_stamp = admitted.semantic_epoch_stamp.model_copy(
        update={"semantic_manifest_ref": alternate_manifest_ref}
    )
    alternate_evidence = admitted.model_copy(update={"semantic_epoch_stamp": alternate_stamp})
    alternate_evidence_ref, _ = overlay_module._persist_epoch_statement(
        artifact_store=scenario.store,
        value=alternate_evidence,
        kind="epoch.admitted_acquisition_boundary_evidence",
        domain="polisyos.epoch.admitted-acquisition-boundary-evidence.v1",
    )
    nested_profile_production = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=alternate_evidence_ref,
    )
    assert nested_profile_production.status == "not_established"
    assert nested_profile_production.failure_codes == ("epoch_scope_unresolved",)
    assert scenario.store.get_bytes(selected_manifest_ref) == manifest_bytes


def test_owner_to_cas_emission_rejects_forged_profile_while_markers_and_bytes_remain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The producer compares the actual selector, not just matching ref markers."""
    scenario = _real_epoch_scenario(tmp_path)
    actual_verify = scenario.overlay.verify_semantic_projection
    alternate_refs: list[overlay_module.ArtifactRef] = []

    def mismatched_profile(
        *,
        native_membership_ref: overlay_module.ArtifactRef,
        semantic_denominator_ref: overlay_module.ArtifactRef,
        prospective_candidate: contracts.epoch.AcquisitionSemanticBoundaryCandidate | None,
    ) -> contracts.epoch.AcquisitionSemanticProjectionVerificationReceipt:
        projection = actual_verify(
            native_membership_ref=native_membership_ref,
            semantic_denominator_ref=semantic_denominator_ref,
            prospective_candidate=prospective_candidate,
        )
        alternate_refs.append(
            _alternate_profiled_provenance_ref(scenario, projection.verifier_provenance_ref)
        )
        return projection.model_copy(update={"verifier_provenance_ref": alternate_refs[-1]})

    monkeypatch.setattr(scenario.overlay, "verify_semantic_projection", mismatched_profile)
    with pytest.raises(OverlayAdmissionError) as refusal:
        _emit_admitted_ref(scenario)

    assert refusal.value.code == "acquisition_projection_verifier_provenance_drift"
    assert len(alternate_refs) == 1
    owner_ref = alternate_refs[0]
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        owner_mapping, _ = overlay_module._load_owner_record(
            con,
            ref=owner_ref,
            expected_kind="epoch.acquisition_projection_verifier_provenance",
        )
    finally:
        con.close()
    owner_canonical = contracts.epoch.canonical_epoch_bytes(owner_mapping)
    owner_payload = len(owner_canonical).to_bytes(8, "big") + owner_canonical
    assert scenario.store.get_bytes(owner_ref) == owner_payload
    assert owner_ref.manifest_profile_sha256 is not None
    assert scenario.store.get_manifest(owner_ref).canon == CanonInfo.from_spec(
        overlay_module.canon.CanonSpec(forbid_floats=False, exclude_none=False)
    )


@pytest.mark.parametrize(
    ("field", "wrong_kind"),
    [
        ("passport_ref", "epoch.acquisition_native_member"),
        ("semantic_candidate_ref", "epoch.acquisition_passport_snapshot"),
    ],
)
def test_catalog_owner_reference_graph_rejects_retagged_receipt_refs_before_cas(
    tmp_path: Path, field: str, wrong_kind: str
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _second_real_epoch_scenario(scenario, epoch_id=2)
    owner_query = scenario.service.acquisition_owner_query(query=scenario.query)
    genuine = scenario.overlay.resolve_native_membership(query=owner_query)
    first = genuine.assessments[0]
    original_ref = getattr(first, field)
    assert original_ref is not None
    wrong_ref = original_ref.model_copy(update={"kind": wrong_kind})
    changed_assessments = list(genuine.assessments)
    changed_assessments[0] = first.model_copy(update={field: wrong_ref})
    receipt_values = genuine.model_dump(mode="python")
    receipt_values["assessments"] = tuple(changed_assessments)
    receipt_values["native_membership_hash"] = semantic_epoch_native_helper.epoch._model_hash(
        b"polisyos.epoch.acquisition-native-membership.v1\0",
        {
            "query": genuine.query.model_dump(mode="json"),
            "owner_source_snapshot_content_hash": genuine.owner_source_snapshot_content_hash,
            "assessments": [row.model_dump(mode="json") for row in changed_assessments],
        },
    )
    forged_receipt = contracts.epoch.AcquisitionNativeMembershipReceipt.model_validate(
        receipt_values
    )

    class RetaggedOwner:
        def __init__(self) -> None:
            self.semantic_calls = 0
            self.projection_calls = 0

        def resolve_native_membership(self, *, query, candidate=None):
            assert query == owner_query
            return forged_receipt

        def load_acquisition_owner_snapshot(self, *, ref):
            return scenario.overlay.load_acquisition_owner_snapshot(ref=ref)

        def resolve_semantic_candidate_denominator(
            self, *, query, native_membership, candidate=None
        ):
            self.semantic_calls += 1
            raise AssertionError("rejected owner graph reached semantic projection")

        def verify_semantic_projection(self, **kwargs):
            self.projection_calls += 1
            raise AssertionError("rejected owner graph reached projection verification")

    retagged = RetaggedOwner()
    empty_store = FileSystemCAS(tmp_path / "empty-cas")
    adapter = semantic_epoch_native_helper.epoch.CatalogAcquisitionEpochBoundaryOwnerAdapter(
        owner=retagged, artifacts=empty_store
    )
    registration = next(
        row
        for row in scenario.service._boundary_registry.registrations
        if row.owner_kind == "catalog_acquisition"
    )
    with pytest.raises(ValueError, match="owner artifact role mismatch"):
        adapter.resolve_complete_batch(registration=registration, owner_query=owner_query)

    assert wrong_ref.artifact_id == original_ref.artifact_id
    assert wrong_ref.media_type == original_ref.media_type
    assert wrong_ref.manifest_profile_sha256 == original_ref.manifest_profile_sha256
    assert wrong_ref.kind == wrong_kind
    assert forged_receipt.native_membership_hash != genuine.native_membership_hash
    assert retagged.semantic_calls == 0
    assert retagged.projection_calls == 0
    assert not empty_store.has(forged_receipt.owner_source_snapshot_ref.artifact_id)
    assert not empty_store.has(wrong_ref.artifact_id)


def _forge_catalog_owner_snapshot(
    scenario,
    *,
    mutate_row,
    passport_hash: str | None = None,
    mutate_assessment: Callable[[dict[str, object]], None] | None = None,
):
    """Recompute owner snapshot/member/receipt hashes around one controlled mutation."""
    owner_query = scenario.service.acquisition_owner_query(query=scenario.query)
    genuine = scenario.overlay.resolve_native_membership(query=owner_query)
    original_payload = scenario.overlay.load_acquisition_owner_snapshot(
        ref=genuine.owner_source_snapshot_ref
    )
    record = semantic_epoch_native_helper.epoch.chronology_contract._split_framed_records(
        original_payload
    )[0]
    snapshot = json.loads(record)
    rows = snapshot["rows"]
    assert rows
    mutate_row(rows[0])
    for source_row in rows:
        if passport_hash is not None:
            source_row["observed_passport_content_hash"] = passport_hash
            source_row["passport_content_hash"] = passport_hash

    epoch = semantic_epoch_native_helper.epoch
    canonical_snapshot = contracts.epoch.canonical_epoch_bytes(snapshot)
    forged_payload = len(canonical_snapshot).to_bytes(8, "big") + canonical_snapshot
    forged_snapshot_ref = overlay_module.ArtifactRef(
        artifact_id=overlay_module.ArtifactID(
            f"sha256:{hashlib.sha256(forged_payload).hexdigest()}"
        ),
        kind="epoch.acquisition_owner_snapshot",
        media_type="application/vnd.polisyos.epoch+json",
    )
    forged_assessments = []
    for source_row in rows:
        original_canonical = contracts.epoch.canonical_epoch_bytes(source_row)
        framed_member = epoch.chronology_contract._frame_record(original_canonical)
        member_id = epoch._raw_cas_hash(framed_member)
        # The mutation changes the member identity, so locate the original assessment by
        # row position when the new bytes no longer have their original id.
        original = next(
            (
                candidate
                for candidate in genuine.assessments
                if candidate.operational_epoch_id == source_row["epoch_id"]
            ),
            None,
        )
        if original is None:
            raise ValueError("native assessment does not match its original owner row")
        native_ref = overlay_module.ArtifactRef(
            artifact_id=overlay_module.ArtifactID(member_id),
            kind="epoch.acquisition_native_member",
            media_type="application/vnd.polisyos.epoch+json",
        )
        values = original.model_dump(mode="python")
        if mutate_assessment is not None:
            mutate_assessment(values)
        values["native_member_ref"] = native_ref
        values["native_member_content_hash"] = epoch._model_hash(
            b"polisyos.epoch.acquisition-native-member.v1\0", source_row
        )
        if passport_hash is not None:
            values["passport_content_hash"] = passport_hash
        forged_assessments.append(
            contracts.epoch.AcquisitionNativeMemberAssessment.model_validate(values)
        )
    snapshot_hash = epoch._model_hash(b"polisyos.epoch.acquisition-owner-snapshot.v1\0", snapshot)
    receipt_values = genuine.model_dump(mode="python")
    receipt_values["owner_source_snapshot_ref"] = forged_snapshot_ref
    receipt_values["owner_source_snapshot_content_hash"] = snapshot_hash
    receipt_values["assessments"] = tuple(forged_assessments)
    receipt_values["native_membership_hash"] = epoch._model_hash(
        b"polisyos.epoch.acquisition-native-membership.v1\0",
        {
            "query": genuine.query.model_dump(mode="json"),
            "owner_source_snapshot_content_hash": snapshot_hash,
            "assessments": [row.model_dump(mode="json") for row in forged_assessments],
        },
    )
    forged_receipt = contracts.epoch.AcquisitionNativeMembershipReceipt.model_validate(
        receipt_values
    )
    return owner_query, forged_receipt, forged_payload


def _assert_catalog_snapshot_preflight_refuses_without_cas_write(
    tmp_path: Path,
    scenario,
    *,
    mutate_row,
    passport_hash: str | None = None,
    mutate_assessment: Callable[[dict[str, object]], None] | None = None,
) -> None:
    owner_query, receipt, payload = _forge_catalog_owner_snapshot(
        scenario,
        mutate_row=mutate_row,
        passport_hash=passport_hash,
        mutate_assessment=mutate_assessment,
    )

    class ForgedCatalogOwner:
        def __init__(self) -> None:
            self.semantic_calls = 0
            self.projection_calls = 0

        def resolve_native_membership(self, *, query, candidate=None):
            assert query == owner_query
            return receipt

        def load_acquisition_owner_snapshot(self, *, ref):
            assert ref == receipt.owner_source_snapshot_ref
            return payload

        def resolve_semantic_candidate_denominator(
            self, *, query, native_membership, candidate=None
        ):
            self.semantic_calls += 1
            raise AssertionError("invalid owner snapshot reached semantic projection")

        def verify_semantic_projection(self, **kwargs):
            self.projection_calls += 1
            raise AssertionError("invalid owner snapshot reached projection verification")

    owner = ForgedCatalogOwner()
    empty_store = FileSystemCAS(tmp_path / "preflight-empty-cas")
    adapter = semantic_epoch_runtime.CatalogAcquisitionEpochBoundaryOwnerAdapter(
        owner=owner, artifacts=empty_store
    )
    registration = next(
        row
        for row in scenario.service._boundary_registry.registrations
        if row.owner_kind == "catalog_acquisition"
    )
    with pytest.raises(ValueError):
        adapter.resolve_complete_batch(registration=registration, owner_query=owner_query)

    assert owner.semantic_calls == 0
    assert owner.projection_calls == 0
    assert not empty_store.has(receipt.owner_source_snapshot_ref.artifact_id)
    for assessment in receipt.assessments:
        assert not empty_store.has(assessment.native_member_ref.artifact_id)


def test_catalog_snapshot_partial_registered_stamp_ref_refuses_before_cas(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)

    def remove_artifact_id(row: dict[str, object]) -> None:
        stamp = row["semantic_epoch_stamp"]
        assert isinstance(stamp, dict)
        ref = stamp["semantic_manifest_ref"]
        assert isinstance(ref, dict)
        ref.pop("artifact_id")

    _assert_catalog_snapshot_preflight_refuses_without_cas_write(
        tmp_path, scenario, mutate_row=remove_artifact_id
    )


def test_catalog_snapshot_row_stamp_must_match_embedded_passport_stamp(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)

    def change_duplicate_stamp(row: dict[str, object]) -> None:
        stamp = row["semantic_epoch_stamp"]
        assert isinstance(stamp, dict)
        # Keep row-local epoch identity and digest coherent; only the passport
        # comparison should distinguish this mutation.
        stamp["requested_query_context_ref"] = "sha256:" + "0" * 64
        row["semantic_epoch_stamp_sha256"] = contracts.epoch.semantic_epoch_stamp_content_hash(
            contracts.epoch.SemanticEpochStamp.model_validate(stamp)
        )

    _assert_catalog_snapshot_preflight_refuses_without_cas_write(
        tmp_path, scenario, mutate_row=change_duplicate_stamp
    )


def test_catalog_bound_v2_row_requires_duplicate_stamp_before_cas(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)

    def remove_bound_v2_stamp(row: dict[str, object]) -> None:
        passport_json = row["observed_passport_json"]
        assert isinstance(passport_json, str)
        passport = json.loads(passport_json)
        assert passport["schema_version"] == "polisyos.runtime.acquisition_admission_passport.v2"
        row["semantic_epoch_stamp"] = None

    _assert_catalog_snapshot_preflight_refuses_without_cas_write(
        tmp_path, scenario, mutate_row=remove_bound_v2_stamp
    )


@pytest.mark.parametrize(
    ("row_field", "row_value", "change_operational_epoch"),
    [
        ("epoch_row_present", False, False),
        ("passport_row_present", False, False),
        ("epoch_activation_state", "legacy_not_established", False),
        (None, None, True),
    ],
)
def test_catalog_bound_v2_decision_rejects_source_fact_drift_before_cas(
    tmp_path: Path,
    row_field: str | None,
    row_value: object,
    change_operational_epoch: bool,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)

    def mutate_row(row: dict[str, object]) -> None:
        if row_field is not None:
            row[row_field] = row_value

    def mutate_assessment(assessment: dict[str, object]) -> None:
        if change_operational_epoch:
            assessment["operational_epoch_id"] = int(assessment["operational_epoch_id"]) + 1

    _assert_catalog_snapshot_preflight_refuses_without_cas_write(
        tmp_path,
        scenario,
        mutate_row=mutate_row,
        mutate_assessment=mutate_assessment if change_operational_epoch else None,
    )


def test_catalog_snapshot_recomputes_passport_hash_when_owner_hashes_agree(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    forged_hash = "sha256:" + "f" * 64
    _assert_catalog_snapshot_preflight_refuses_without_cas_write(
        tmp_path,
        scenario,
        mutate_row=lambda _row: None,
        passport_hash=forged_hash,
    )


def test_finalizer_fails_closed_when_a_selected_owner_snapshot_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real finalizer refuses when one required owner graph node is absent."""
    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = _emit_admitted_ref(scenario)
    admitted_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    native_mapping = contracts.epoch.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.native_membership_receipt_ref,
        expected_kind="epoch.acquisition_native_membership",
    )
    native = contracts.epoch.AcquisitionNativeMembershipReceipt.model_validate(native_mapping)
    assert scenario.store.has(native.owner_source_snapshot_ref.artifact_id)
    assert (
        semantic_epoch_runtime._resolve_selected_reference_graph(scenario.store, admitted)
        is not None
    )
    original_load = semantic_epoch_runtime._load_selected_acquisition_mapping

    def hide_owner_snapshot(
        store: object, ref: ArtifactRef, *, expected_kind: str
    ) -> dict[str, object]:
        if ref.kind == "epoch.acquisition_owner_snapshot":
            raise FileNotFoundError("controlled missing owner snapshot")
        return original_load(store, ref, expected_kind=expected_kind)

    monkeypatch.setattr(
        semantic_epoch_runtime, "_load_selected_acquisition_mapping", hide_owner_snapshot
    )
    assert (
        semantic_epoch_runtime._resolve_selected_reference_graph(scenario.store, admitted) is None
    )
    receipt = scenario.service.finalize_admitted_epoch(
        prepared_epoch_ref=scenario.prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )

    assert receipt.status == "not_established"
    assert receipt.failure_codes == ("epoch_scope_unresolved",)
