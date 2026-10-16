from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes
from polisyos.runtime.http.services.artifact_inspector import ArtifactInspectorService
from polisyos.runtime.http.services.lineage import LineageService


def test_content_refuses_payload_that_violates_declared_profile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    raw = to_canonical_bytes(
        {
            "authority_boundary": {
                "boundary_id": "boundary-canon-test",
                "authoritative_for": ["runtime_closeout_authority"],
                "may_not_use_for": ["publication"],
                "source_authority": "canon_test_fixture",
                "posture": "governed",
                "rule_version_refs": ["policyos.test.authority.v1"],
                "evidence_kind": "measurement",
                "decision_grade": "decision_admissible",
            },
            "fraction": 1.5,
        },
        CanonSpec(forbid_floats=False),
    )
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.profiled-json",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=True),
        ),
    )
    service = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_payload_nonconformant",
    ):
        service.get_content_preview(ref.artifact_id)


def test_schema_and_bureaucratic_render_refuse_the_same_selected_mismatch(
    tmp_path: Path,
) -> None:
    from polisyos.core.contracts.runtime import BureaucraticRenderRequest
    from polisyos.runtime.http.services.bureaucratic_rendering import (
        BureaucraticRenderingService,
    )

    store = FileSystemCAS(tmp_path / "cas")
    raw = to_canonical_bytes({"fraction": 1.5}, CanonSpec(forbid_floats=False))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.profiled-json",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=True),
        ),
    )
    inspector = ArtifactInspectorService(
        store=store,
        lineage_service=LineageService(store=store),
    )

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        inspector.get_schema_view(ref.artifact_id)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        BureaucraticRenderingService(store=store).render_document(
            ref.artifact_id,
            BureaucraticRenderRequest(genre="postanova_kmu"),
            manifest=store.get_manifest(ref),
        )


def test_run_quantity_and_fabric_source_contract_refuse_selected_mismatch(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    store = FileSystemCAS(tmp_path / "cas")
    raw = to_canonical_bytes({"simulation_results": {"gdp": 1.5}}, CanonSpec(forbid_floats=False))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=True),
        ),
    )
    run = SimpleNamespace(
        run_id="run-profile-mismatch",
        decision_packet_ref=ref,
        details=SimpleNamespace(started_at=None, finished_at=None, duration_ms=None),
        summary=SimpleNamespace(root_artifact_count=0),
    )
    lineage = LineageService(store=store)

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        lineage.build_quantity_inventory_for_run(run)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        lineage.source_contract_ref_for_run(run)


def test_source_contract_reader_preserves_valid_selected_packet_and_absence_default(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    from polisyos.fabric.evidence.decision_data import SourceContractRef
    from polisyos.runtime.http.services.lineage import DEFAULT_DECISION_SOURCE_CONTRACT

    store = FileSystemCAS(tmp_path / "cas")
    lineage = LineageService(store=store)
    packet = store.put_json(
        {"source_contract_ref": {"id": "worldbank.wdi.generic", "version": "1.1.0"}},
        PutOptions(
            kind="scientist.decision_packet", media_type="application/json", canon=CanonInfo()
        ),
        return_selected_profile=True,
    )
    if packet.manifest_profile_sha256 is None:
        pytest.fail("selected-profile producer did not return the written packet view")
    selected = lineage.source_contract_ref_for_run(SimpleNamespace(decision_packet_ref=packet))
    expected = SourceContractRef(id="worldbank.wdi.generic", version="1.1.0")
    if selected != expected:
        pytest.fail(f"valid selected source-contract field was not preserved: {selected!r}")

    # A conformant selected packet with no source-contract field keeps the
    # established field-absence default; malformed bytes are not this case.
    packet_without_contract = store.put_json(
        {"simulation_results": {"gdp": 2}},
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    if packet_without_contract.manifest_profile_sha256 is None:
        pytest.fail("selected-profile producer did not return the written packet view")
    absent_field = lineage.source_contract_ref_for_run(
        SimpleNamespace(decision_packet_ref=packet_without_contract)
    )
    if absent_field != DEFAULT_DECISION_SOURCE_CONTRACT:
        pytest.fail(f"absent source-contract field did not retain the default: {absent_field!r}")

    # A genuinely absent decision packet keeps the established default behavior.
    missing_packet = lineage.source_contract_ref_for_run(SimpleNamespace(decision_packet_ref=None))
    if missing_packet != DEFAULT_DECISION_SOURCE_CONTRACT:
        pytest.fail(f"absent decision packet did not retain the default: {missing_packet!r}")


def test_debug_and_run_paper_consumers_refuse_selected_profile_mismatch(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.debug import DebugService
    from polisyos.runtime.http.services.run_paper_case_record import (
        RunBoundDesignRecordResolver,
    )

    store = FileSystemCAS(tmp_path / "cas")
    raw = to_canonical_bytes({"fraction": 1.5}, CanonSpec(forbid_floats=False))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.profiled-json",
            media_type="application/json",
            canon=CanonInfo(forbid_floats=True),
        ),
    )
    debug = DebugService(store=store, timeline_service=object())
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        debug._load_json_artifact(ref)

    paper = RunBoundDesignRecordResolver(store=store, core_runs_root=tmp_path)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        paper._load_payload(ref, role="fixture")


def test_raw_sidecar_reader_refuses_profileless_current_sidecar_by_default(
    tmp_path: Path,
) -> None:
    import json

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import FileSystemCAS, PutOptions
    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        to_canonical_bytes({"ok": True}),
        PutOptions(
            kind="test.raw-profile-sidecar",
            media_type="application/json",
            canon=CanonInfo(),
        ),
    )
    selected_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    selected = json.loads(selected_path.read_bytes())
    selected["canon"].pop("separators")
    selected_path.write_text(json.dumps(selected, sort_keys=True), encoding="utf-8")

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_incomplete"):
        read_core_json_artifact(store, ref)

    # This selected artifact uses the current canonical manifest schema.
    # That label and its creation time do not prove historical eligibility.
    created_manifest = store.get_manifest(ref.artifact_id)
    if created_manifest.manifest_schema_version != "v3":
        pytest.fail("selected manifest did not retain the current schema")
    if created_manifest.canon != CanonInfo():
        pytest.fail("selected manifest canon info changed")
    legacy_path = store._manifest_path_for_ref(ref.artifact_id, None)
    legacy = json.loads(legacy_path.read_bytes())
    legacy.pop("canon")
    legacy_path.write_text(json.dumps(legacy, sort_keys=True), encoding="utf-8")
    if store.get_raw_manifest_bytes(ref.artifact_id) != legacy_path.read_bytes():
        pytest.fail("raw manifest read did not return the selected legacy bytes")
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        read_core_json_artifact(store, ref.artifact_id)

    candidate_read = read_core_json_artifact(store, ref.artifact_id, allow_profile_absent=True)
    if candidate_read.status != "profile_absent_unqualified_candidate":
        pytest.fail(f"unexpected candidate status: {candidate_read.status!r}")
    if candidate_read.unqualified_candidate_value != {"ok": True}:
        pytest.fail("unqualified candidate payload changed")
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = candidate_read.value


def test_n5_source_resolver_refuses_malformed_selected_profile_before_verify(
    tmp_path: Path,
) -> None:
    import json

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import CanonInfo, FileSystemCAS, PutOptions
    from polisyos.core.canon.canon_json import to_canonical_bytes
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        to_canonical_bytes({"candidate": "untrusted"}),
        PutOptions(
            kind="runtime.quality.candidate_simulation_n5_input",
            media_type="application/json",
            canon=CanonInfo(),
        ),
    )
    selected_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    selected = json.loads(selected_path.read_bytes())
    selected["canon"].pop("separators")
    selected_path.write_text(json.dumps(selected, sort_keys=True), encoding="utf-8")

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_incomplete"):
        GenerationSourceRepository(store).resolve_candidate_simulation_v5(
            ref=ref,
            expected_run_id="untrusted-run",
        )


def test_feedback_packet_keeps_full_selected_ref_and_refuses_truncated_ref() -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.services.feedback import FeedbackService

    artifact_id = "sha256:" + "a" * 64
    profile = "sha256:" + "b" * 64
    ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="runtime.feedback_report",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )
    packet = {"feedback_loop": {"feedback_report_ref": ref.model_dump(mode="json")}}

    selected = FeedbackService._feedback_ref_from_packet(packet, "feedback_report_ref")
    if selected != ref:
        pytest.fail("complete selected feedback ref was not preserved")
    legacy_candidate = FeedbackService._feedback_ref_from_packet(
        {"feedback_loop": {"feedback_report_ref": {"artifact_id": artifact_id}}},
        "feedback_report_ref",
    )
    if legacy_candidate != artifact_id:
        pytest.fail("profileless feedback ref did not remain an unqualified candidate")

    truncated = {
        "feedback_loop": {
            "feedback_report_ref": {
                "artifact_id": artifact_id,
                "kind": "runtime.feedback_report",
                "manifest_profile_sha256": profile,
            }
        }
    }
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_feedback_ref_invalid"):
        FeedbackService._feedback_ref_from_packet(truncated, "feedback_report_ref")
