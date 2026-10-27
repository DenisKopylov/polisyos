"""Genuine source-authority controls for the reusable native epoch fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections


def test_conditioned_fixture_carriers_are_admitted_and_fresh_read_rejects_source_drift(
    tmp_path: Path,
) -> None:
    """Actual signed rights/epoch owners admit the carrier, then refuse changed bytes."""
    source_rows: list[dict[str, object]] = [
        {
            "country_code": "UA",
            "year": 2000 + index,
            "distance": float(index + 1),
            "treated": float(index % 2),
        }
        for index in range(4)
    ]
    assert all("condition_json" not in row for row in source_rows)
    fixture = make_native_multivariable_active_projections(
        tmp_path / "source-owner",
        source_rows=source_rows,
        variable_specs=(
            {
                "target_variable": "distance",
                "raw_field": "distance",
                "raw_unit": "m",
                "canonical_unit": "m",
                "valid_min": 0.0,
                "valid_max": 10.0,
            },
            {
                "target_variable": "treated",
                "raw_field": "treated",
                "raw_unit": "binary",
                "canonical_unit": "binary",
                "valid_min": 0.0,
                "valid_max": 1.0,
            },
        ),
        condition_units_by_raw_field={"distance": "m", "treated": "binary"},
    )
    passports: dict[str, AdmissionPassport] = {}
    try:
        for entry in fixture.entries:
            carrier_path = fixture.repo_root / entry.local_source_path
            carrier = carrier_path.read_bytes()
            carrier_rows = json.loads(carrier)
            declared = {column.name: column for column in entry.schema_columns}
            assert set(declared) == {name for row in carrier_rows for name in row}
            assert declared["condition_json"].logical_types == ("string",)
            resolved = fixture.authority.resolve(entry.entry_id)
            assert resolved.entry == entry
            assert fixture.authority.verify_source_body(entry.entry_id, carrier) is True
            projection = fixture.projections[entry.target_variable]
            passport = AdmissionPassport.model_validate(
                epoch_contract.load_verified_epoch_statement(
                    store=fixture.artifact_store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            passports[entry.target_variable] = passport
            assert passport.source_authority_verified is True
            assert passport.schema_validation.conformant is True
            assert passport.schema_validation.drift_codes == ()
            assert passport.raw_evidence_verified is True
            assert passport.cas_evidence_verified is True
            assert passport.rejection_codes == ()
            assert (
                fixture.overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=projection.receipt_ref,
                    artifact_store=fixture.artifact_store,
                    passport=passport,
                    authority=fixture.authority,
                )
                == projection
            )

        # Preserve all valid CAS receipts, passport flags and registry markers.
        # A real source-byte change still has to fail the fresh authority intake.
        entry = fixture.entries[0]
        projection = fixture.projections[entry.target_variable]
        passport = passports[entry.target_variable]
        path = fixture.repo_root / entry.local_source_path
        original = path.read_bytes()
        path.write_bytes(original + b"\n")
        assert passport.source_authority_verified is True
        with pytest.raises(catalog_read_api.AcquisitionAuthorityError) as authority_failure:
            fixture.authority.resolve(entry.entry_id)
        assert authority_failure.value.code == "local_source_content_drift"
        with pytest.raises(OverlayAdmissionError) as fresh_failure:
            fixture.overlay.read_activated_semantic_epoch_observations(
                receipt_ref=projection.receipt_ref,
                artifact_store=fixture.artifact_store,
                passport=passport,
                authority=fixture.authority,
            )
        assert fresh_failure.value.code == "acquisition_authority_unresolved"
    finally:
        fixture.overlay.close()
