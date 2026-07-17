from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import QuarantineRecord, persist_quarantine_record
from polisyos.runtime.quality import data_state_substrate, substrate_registry
from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
from polisyos.runtime.quality.generation_cycle import (
    RealValueOwnerGateway,
    ValueDataProfile,
    _load_value_data_profile_from_l1_dcat,
)
from tests.unit.runtime.quality.test_acquisition_executor import _fixture


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_quarantine_is_invisible_until_admitted_epoch_reaches_existing_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"country_code": "UA-01", "year": 2024, "distress_score": 0.42},
        {"country_code": "UA-02", "year": 2024, "distress_score": 0.51},
        {"country_code": "UA-03", "year": 2025, "distress_score": 0.47},
        {"country_code": "UA-04", "year": 2025, "distress_score": 0.56},
    ]
    passport, store, authority, _, _ = _fixture(tmp_path / "evidence", rows=rows)
    baseline_before = _sha256(authority.baseline_path)
    paths = SimpleNamespace(l1_dcat_path=authority.baseline_path)
    monkeypatch.setattr(
        data_state_substrate,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    overlay_path = catalog_read_api.default_acquisition_overlay_path(
        authority.repo_root
    )

    persist_quarantine_record(
        store,
        record=QuarantineRecord.new(
            reason="pre_admission_shadow_characterization",
            severity="info",
            source="test.acquisition_overlay_visibility",
            downstream_impacts=("L1_admission_blocked",),
        ),
        raw_payload=rows,
    )
    before = l1_dcat_variable_availability(
        authority.repo_root,
        passport.variable_id,
        overlay_path=overlay_path,
    )
    before_profile = _load_value_data_profile_from_l1_dcat(
        repo_root=authority.repo_root,
        outcome=passport.variable_id,
        owner_access_ref=before.coverage_ref,
        overlay_path=overlay_path,
    )

    assert before.status == "unavailable"
    assert before.observation_count == 0
    assert before_profile is None

    overlay = catalog_read_api.CatalogAcquisitionOverlay(
        authority.baseline_path,
        overlay_path,
    )
    overlay.initialize()
    receipt = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=authority,
    )

    after = l1_dcat_variable_availability(
        authority.repo_root,
        passport.variable_id,
        overlay_path=overlay_path,
    )
    profile = _load_value_data_profile_from_l1_dcat(
        repo_root=authority.repo_root,
        outcome=passport.variable_id,
        owner_access_ref=after.coverage_ref,
        overlay_path=overlay_path,
    )
    gateway_profile = RealValueOwnerGateway(
        repo_root=authority.repo_root,
        catalog_overlay_path=overlay_path,
    ).load_value_data_profile(
        candidate=SimpleNamespace(
            atom=SimpleNamespace(target_world_slots=(passport.variable_id,)),
        ),
        problem=SimpleNamespace(
            outcome_of_interest=SimpleNamespace(
                target_variable=passport.variable_id,
            ),
        ),
        world_record=object(),
    )

    assert receipt.epoch_id == 1
    assert receipt.admitted_observation_count == 4
    assert after.status == "available"
    assert after.dataset_count == 1
    assert after.metric_binding_count == 1
    assert after.observation_count == 4
    assert isinstance(profile, ValueDataProfile)
    assert profile.owner_row_count == 4
    assert profile.unit_count == 4
    assert profile.period_count == 2
    assert gateway_profile == profile
    assert _sha256(authority.baseline_path) == baseline_before
    overlay.close()
