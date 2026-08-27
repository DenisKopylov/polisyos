from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from polisyos.data_forge.domains.catalog.knowledge import overlay as overlay_module
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import QuarantineRecord, persist_quarantine_record
from polisyos.runtime.quality import data_state_substrate, substrate_registry
from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
from polisyos.runtime.quality.generation_cycle import (
    RealValueOwnerGateway,
    ValueOwnerAccessError,
    _load_value_data_profile_from_l1_dcat,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_overlay import (
    _downgrade_to_authentic_v1,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
    _fixture,
    _real_epoch_scenario,
    _second_real_epoch_scenario,
    _semantic_handshake_from_passport,
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_pending_semantic_epoch_is_invisible_across_existing_reads(
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
    overlay_path = catalog_read_api.default_acquisition_overlay_path(authority.repo_root)

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
    boundary_candidate, prepared_epoch = _semantic_handshake_from_passport(
        passport,
        store,
    )
    receipt = overlay.admit_epoch(
        passport=passport,
        prepared_epoch=prepared_epoch,
        boundary_candidate=boundary_candidate,
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
    with pytest.raises(ValueOwnerAccessError) as raised:
        RealValueOwnerGateway(
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
    assert raised.value.code == "acquire_data:value_panel_data_missing"

    assert receipt.epoch_id == 1
    assert receipt.activation_state == "pending_epoch_activation"
    assert receipt.admitted_observation_count == 4
    assert after.status == "unavailable"
    assert after.dataset_count == 0
    assert after.metric_binding_count == 0
    assert after.observation_count == 0
    assert profile is None
    assert _sha256(authority.baseline_path) == baseline_before
    overlay.close()


def _table_counts(baseline: Path, *, overlay: Path | None = None) -> dict[str, int]:
    con = catalog_read_api.open_catalog_read_session(baseline, overlay_path=overlay)
    try:
        return {
            table: int(con.execute("SELECT count(*) FROM query_table(?)", [table]).fetchone()[0])
            for table in overlay_module._BASELINE_UNION_TABLES
        }
    finally:
        con.close()


def test_pending_epoch_is_hidden_from_all_six_baseline_union_views(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    before = _table_counts(scenario.authority.baseline_path)
    after = _table_counts(
        scenario.authority.baseline_path,
        overlay=scenario.overlay.overlay_path,
    )

    assert after == before
    assert len(after) == 6


def test_pending_epoch_activation_is_hidden_after_crash(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    before = _table_counts(scenario.authority.baseline_path)
    after = _table_counts(
        scenario.authority.baseline_path,
        overlay=scenario.overlay.overlay_path,
    )
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        audit = con.execute(
            "SELECT epoch_activation_state, count(*) OVER () FROM acquisition_epochs"
        ).fetchone()
    finally:
        con.close()

    assert audit == ("pending_epoch_activation", 1)
    assert after == before


def test_overlay_visibility_never_promotes_a_legacy_null_stamp(tmp_path: Path) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _downgrade_to_authentic_v1(scenario)
    before = _table_counts(scenario.authority.baseline_path)
    after = _table_counts(
        scenario.authority.baseline_path,
        overlay=scenario.overlay.overlay_path,
    )

    assert after == before


def test_active_reuser_exposes_complete_metadata_when_creator_is_pending(
    tmp_path: Path,
) -> None:
    first = _real_epoch_scenario(tmp_path)
    second = _second_real_epoch_scenario(first)
    _activate_real_epoch_scenario(second)
    before = _table_counts(first.authority.baseline_path)
    after = _table_counts(
        first.authority.baseline_path,
        overlay=first.overlay.overlay_path,
    )

    assert after["ds_observations"] - before["ds_observations"] == 2
    for table in overlay_module._BASELINE_UNION_TABLES:
        if table != "ds_observations":
            assert after[table] - before[table] == 1


def test_two_active_epochs_reusing_registration_emit_each_row_once(tmp_path: Path) -> None:
    first = _real_epoch_scenario(tmp_path)
    second = _second_real_epoch_scenario(first)
    _activate_real_epoch_scenario(first)
    _activate_real_epoch_scenario(second)
    before = _table_counts(first.authority.baseline_path)
    after = _table_counts(
        first.authority.baseline_path,
        overlay=first.overlay.overlay_path,
    )

    assert after["ds_observations"] - before["ds_observations"] == 4
    for table in overlay_module._BASELINE_UNION_TABLES:
        if table != "ds_observations":
            assert after[table] - before[table] == 1
