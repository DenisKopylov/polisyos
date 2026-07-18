from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

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
from tests.unit.runtime.quality.test_acquisition_executor import _fixture, _valid_passport


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_overlay_owner_is_available_through_the_canonical_read_api() -> None:
    assert catalog_read_api.CatalogAcquisitionOverlay is CatalogAcquisitionOverlay
    assert callable(catalog_read_api.open_catalog_read_session)
    assert callable(catalog_read_api.verify_local_source_rights)
    assert callable(catalog_read_api.build_local_rights_trust_registry)
    assert callable(catalog_read_api.build_acquisition_authority_provision)
    assert catalog_read_api.AcquisitionAuthorityProvision is not None
    assert catalog_read_api.LocalRightsTrustRegistry is not None
    assert Path(
        "architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"
    ) == catalog_read_api.DEFAULT_ACQUISITION_OVERLAY_PATH
    assert catalog_read_api.default_acquisition_overlay_path(Path("/repo")) == Path(
        "/repo/architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"
    )


def test_catalog_read_session_unifies_epoch_zero_and_overlay_audit_views(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay_path = tmp_path / "acquisition-overlay.duckdb"
    overlay = CatalogAcquisitionOverlay(baseline, overlay_path)
    overlay.initialize()
    overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )

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
        assert con.execute("select count(*) from ds_observations").fetchone()[0] == 2
        assert con.execute("select count(*) from acquisition_epochs").fetchone()[0] == 1
        assert con.execute("select count(*) from acquisition_passports").fetchone()[0] == 1
        assert (
            con.execute("select count(*) from ds_metric_field_bindings").fetchone()[0]
            == 1
        )
        with pytest.raises(duckdb.Error):
            con.execute("delete from baseline.ds_observations")
        with pytest.raises(duckdb.Error):
            con.execute("delete from acquisition_overlay.ds_observations")
        bindings = catalog_store.resolve_metric_bindings("cells.distress_score")
        assert bindings
        assert bindings[0].catalog_dataset_id == (
            "acquisition.local.corrected_firm_panels"
        )
        results = catalog_graph.search_datasets(
            "Owner validated local distress observations",
            top_k=5,
        )
        assert results
        assert results[0].id == "acquisition.local.corrected_firm_panels"
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

    receipt = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )

    assert identity.epoch == 0
    assert receipt.epoch_id == 1
    assert receipt.admitted_observation_count == 2
    assert receipt.observation_class is ObservationProvenanceClass.OBSERVED
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
                "select effective_authority_score "
                "from acquisition_observation_provenance limit 1"
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
        overlay.admit_epoch(
            passport=forged,
            artifact_store=store,
            authority=authority,
        )
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
        forged = passport.model_copy(
            update={"observation_class": observation_class}
        )
        with pytest.raises(OverlayAdmissionError):
            overlay.admit_epoch(
                passport=forged,
                artifact_store=store,
                authority=authority,
            )

    with pytest.raises(ValidationError):
        type(passport)(**{**passport.model_dump(mode="python"), "epoch_id": 0})

    epochless = passport.model_copy(update={"epoch_id": 0})
    epochless = epochless.model_copy(update={"passport_id": epochless.recomputed_passport_id()})
    with pytest.raises(OverlayAdmissionError, match="epoch_stamp_required"):
        overlay.admit_epoch(
            passport=epochless,
            artifact_store=store,
            authority=authority,
        )

    overlay.close()


def test_overlay_revalidates_raw_and_cas_evidence_instead_of_trusting_passport_flags(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()
    fake_ref = passport.raw_evidence_ref.model_copy(
        update={"event_sha256": "sha256:" + "0" * 64}
    )
    forged = passport.model_copy(
        update={"raw_evidence_ref": fake_ref, "raw_evidence_verified": True}
    )

    with pytest.raises(OverlayAdmissionError, match="raw_evidence_ref_unresolved"):
        overlay.admit_epoch(
            passport=forged,
            artifact_store=store,
            authority=authority,
        )

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
        overlay.admit_epoch(
            passport=forged,
            artifact_store=store,
            authority=authority,
        )

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
        overlay.admit_epoch(
            passport=quarantined,
            artifact_store=store,
            authority=authority,
        )

    overlay.close()


def test_overlay_refuses_canonical_values_not_derived_from_raw_evidence(
    tmp_path: Path,
) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()
    with pytest.raises(TypeError, match="observations"):
        overlay.admit_epoch(
            passport=passport,
            observations=({"value": 0.99},),  # type: ignore[call-arg]
            artifact_store=store,
            authority=authority,
        )

    receipt = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )
    assert receipt.admitted_observation_count == 2
    con = duckdb.connect(str(overlay.overlay_path), read_only=True)
    try:
        values = con.execute(
            "SELECT value FROM ds_observations ORDER BY year"
        ).fetchall()
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
        overlay.admit_epoch(
            passport=passport,
            artifact_store=store,
            authority=authority,
        )

    overlay.close()


def test_overlay_epoch_write_is_content_idempotent(tmp_path: Path) -> None:
    passport, store, authority, _ = _valid_passport(tmp_path / "evidence")
    baseline = authority.baseline_path
    overlay = CatalogAcquisitionOverlay(baseline, tmp_path / "overlay.duckdb")
    overlay.initialize()

    first = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )
    first_bytes = overlay.overlay_path.read_bytes()
    second = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )

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
    overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )
    second_passport = build_admission_passport(
        epoch_id=2,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        raw_artifact_id=passport.raw_artifact_id,
        authority=authority,
    )

    second = overlay.admit_epoch(
        passport=second_passport,
        artifact_store=store,
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
