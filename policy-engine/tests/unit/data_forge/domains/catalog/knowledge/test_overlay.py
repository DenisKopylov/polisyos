from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from polisyos.core import contracts
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.data_forge.domains.catalog.knowledge import overlay as overlay_module
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    BaselineMutationError,
    CatalogAcquisitionOverlay,
    OverlayAdmissionError,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionStatus,
    ObservationProvenanceClass,
    build_admission_passport,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
    _fixture,
    _real_epoch_scenario,
    _second_real_epoch_scenario,
    _semantic_handshake_from_passport,
    _valid_passport,
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
