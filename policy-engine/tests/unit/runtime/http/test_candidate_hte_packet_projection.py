from __future__ import annotations

import importlib
import importlib.util
import runpy
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef

try:
    _projection_module = importlib.import_module(
        "polisyos.runtime.http.services.candidate_hte_packet_projection"
    )
except ModuleNotFoundError as exc:
    if "candidate_hte_packet_projection" not in str(exc):
        raise
    _AUTHOR_ROOT = Path(__file__).resolve().parents[1]
    _MODULE_PATH = (
        _AUTHOR_ROOT
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "candidate_hte_packet_projection.py"
    )
    _SPEC = importlib.util.spec_from_file_location(
        "_r24_candidate_hte_packet_projection",
        _MODULE_PATH,
    )
    assert _SPEC is not None and _SPEC.loader is not None
    _projection_module = importlib.util.module_from_spec(_SPEC)
    sys.modules[_SPEC.name] = _projection_module
    _SPEC.loader.exec_module(_projection_module)

_REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (
        parent
        / "policy-engine"
        / "tests"
        / "unit"
        / "scientist"
        / "nodes"
        / "builtins"
        / "decide"
        / "test_completed_hte_source_projection.py"
    ).is_file()
)
_FIXTURES = runpy.run_path(
    str(
        _REPO_ROOT
        / "policy-engine"
        / "tests"
        / "unit"
        / "scientist"
        / "nodes"
        / "builtins"
        / "decide"
        / "test_completed_hte_source_projection.py"
    )
)
_selected_source = _FIXTURES["_selected_source"]


def _ref(index: int, kind: str = "scientist.decision_packet") -> ArtifactRef:
    digit = str(index)
    return ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + digit * 64,
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + str((index + 1) % 10) * 64,
        },
        strict=True,
    )


def _association_wire(source: Any, *, verified_at: datetime | None = None) -> dict[str, Any]:
    association = source.association
    if verified_at is not None:
        association = association.model_copy(update={"verified_at": verified_at})
    return association.model_dump(mode="json", exclude_none=True)


def _packet_payload(
    source: Any,
    *,
    status: str = "selected",
    summary_wire: dict[str, Any] | None = None,
    association_wire: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = status == "selected"
    source_summary = summary_wire or source.summary.model_dump(mode="json")
    basis: dict[str, Any] = {
        "completed_hte_source_status": status,
        "completed_hte_request_status": "requested",
        "completed_hte_requested_source_run_id": source.source_run_id,
        "completed_hte_authority_purpose": "candidate_method_evidence",
        "completed_hte_publication_authorization": "not_established",
        "completed_hte_currentness_status": (
            "reconciled_at_completed_event" if selected else "not_established"
        ),
        "completed_hte_limitations": list(source.summary.limitations),
    }
    if selected:
        basis.update(
            {
                "completed_hte_source_run_id": source.source_run_id,
                "completed_hte_source_job_id": source.source_job_id,
                "completed_hte_source_attempt": source.source_attempt,
                "completed_hte_completion_event_id": source.completed_event_id,
                "completed_hte_completion_event_payload_sha256": (
                    source.completed_event_payload_sha256
                ),
                "completed_hte_outcome_kind": source.summary.kind,
                "completed_hte_method_profile_id": source.summary.method_profile_id,
                "completed_hte_owner_association": (
                    association_wire if association_wire is not None else _association_wire(source)
                ),
            }
        )
    return {
        "schema_version": "3.4",
        "hte": source_summary if selected else None,
        "decision_validity_envelope": {
            "data_basis": {"summary": basis},
        },
    }


def _fresh_source(source: Any) -> Any:
    fresh_verified_at = source.association.verified_at + timedelta(seconds=1)
    return replace(
        source,
        association=source.association.model_copy(update={"verified_at": fresh_verified_at}),
    )


def _project(
    packet_payload: object,
    *,
    source: Any | None,
    packet_ref: ArtifactRef | None = None,
    source_run_id: str | None = None,
    packet_run_id: str | None = None,
) -> Any:
    return _projection_module.project_candidate_hte_packet(
        packet_payload=packet_payload,
        packet_run_id=packet_run_id
        or _projection_module.candidate_packet_source_selector(packet_payload)[1],
        packet_ref=packet_ref or _ref(8),
        source_run_id_selector=source_run_id or "source-run-controlled",
        fresh_source=source,
        reader_at=datetime(2026, 10, 23, 0, 2, tzinfo=UTC),
    )


def test_selected_projection_requires_exact_persisted_summary_and_full_association() -> None:
    source = _selected_source()
    projection = _project(_packet_payload(source), source=_fresh_source(source))

    assert projection.candidate_status == "selected"
    assert projection.candidate_only is True
    assert projection.packet_run_id == source.source_run_id
    assert projection.source.summary == source.summary
    assert projection.source.association.model_dump(
        mode="python", exclude={"verified_at"}
    ) == source.association.model_dump(mode="python", exclude={"verified_at"})
    assert projection.source.association.verified_at > source.association.verified_at
    assert projection.publication_authorization == "not_established"
    assert projection.live_source_currentness == "not_established"
    assert projection.reader_at.tzinfo is not None


def test_absent_packet_stays_absent_without_resolving_fresh_owner() -> None:
    source = _selected_source()
    projection = _project(
        _packet_payload(source, status="verification_missing"),
        source=None,
    )

    assert projection.candidate_status == "absent"
    assert projection.source is None
    assert projection.limitations == tuple(source.summary.limitations)
    assert projection.live_source_currentness == "not_established"


def test_packet_summary_mismatch_refuses_while_selected_markers_remain() -> None:
    source = _selected_source()
    summary = source.summary.model_dump(mode="json")
    summary["point_estimate"] = summary["point_estimate"] + 0.01

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(
            _packet_payload(source, summary_wire=summary),
            source=_fresh_source(source),
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("run_id", "another-source-run"),
        ("job_id", "another-source-job"),
        ("attempt", 2),
        ("selected_summary_sha256", "0" * 64),
        ("outcome_kind", "interval_estimate"),
    ],
)
def test_stable_association_field_mismatch_refuses(
    field: str,
    replacement: object,
) -> None:
    source = _selected_source()
    association = _association_wire(source)
    association[field] = replacement

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(
            _packet_payload(source, association_wire=association),
            source=_fresh_source(source),
        )


@pytest.mark.parametrize("field", ["summary", "association"])
def test_extra_json_keys_refuse_even_with_selected_status(field: str) -> None:
    source = _selected_source()
    packet = _packet_payload(source)
    if field == "summary":
        packet["hte"]["unrecognized_candidate_field"] = "present"
    else:
        packet["decision_validity_envelope"]["data_basis"]["summary"][
            "completed_hte_owner_association"
        ]["unrecognized_association_field"] = "present"

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(packet, source=_fresh_source(source))


def test_remove_association_control_fails_with_candidate_markers_intact() -> None:
    source = _selected_source()
    packet = _packet_payload(source)
    basis = packet["decision_validity_envelope"]["data_basis"]["summary"]
    basis.pop("completed_hte_owner_association")

    assert packet["hte"] is not None
    assert basis["completed_hte_source_status"] == "selected"
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(packet, source=_fresh_source(source))


def test_verified_at_must_be_aware_and_packet_time_must_precede_fresh_owner() -> None:
    source = _selected_source()
    naive = datetime(2026, 10, 23, 0, 0)
    packet = _packet_payload(
        source,
        association_wire=_association_wire(source, verified_at=naive),
    )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(packet, source=_fresh_source(source))

    future = source.association.verified_at + timedelta(seconds=5)
    packet = _packet_payload(
        source,
        association_wire=_association_wire(source, verified_at=future),
    )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(packet, source=_fresh_source(source))


def test_source_run_selector_is_derived_from_packet_before_owner_read() -> None:
    source = _selected_source()
    packet = _packet_payload(source)
    assert _projection_module.candidate_packet_source_selector(packet) == (
        "selected",
        source.source_run_id,
    )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _project(
            packet,
            source=_fresh_source(source),
            source_run_id="different-source-run",
        )


@pytest.mark.parametrize(
    ("packet_tenant", "packet_cell", "source_tenant", "source_cell"),
    [
        ("other-tenant", "controlled-cell", "controlled-tenant", "controlled-cell"),
        ("controlled-tenant", "other-cell", "controlled-tenant", "controlled-cell"),
        ("controlled-tenant", "controlled-cell", "other-tenant", "controlled-cell"),
        ("controlled-tenant", "controlled-cell", "controlled-tenant", "other-cell"),
        (None, "controlled-cell", "controlled-tenant", "controlled-cell"),
        ("controlled-tenant", None, "controlled-tenant", "controlled-cell"),
    ],
)
def test_packet_and_source_runs_must_share_verified_tenant_cell_scope(
    packet_tenant: str | None,
    packet_cell: str | None,
    source_tenant: str | None,
    source_cell: str | None,
) -> None:
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _projection_module.require_candidate_projection_scope(
            scope_tenant_id="controlled-tenant",
            scope_cell_id="controlled-cell",
            packet_tenant_id=packet_tenant,
            packet_cell_id=packet_cell,
            source_tenant_id=source_tenant,
            source_cell_id=source_cell,
        )


def test_packet_id_and_profile_are_equality_selectors_against_index_ref() -> None:
    ref = _ref(8)
    assert (
        _projection_module.require_exact_candidate_packet_ref(
            indexed_packet_ref=ref,
            requested_packet_id=str(ref.artifact_id),
            requested_manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        == ref
    )

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _projection_module.require_exact_candidate_packet_ref(
            indexed_packet_ref=ref,
            requested_packet_id=str(_ref(9).artifact_id),
            requested_manifest_profile_sha256=ref.manifest_profile_sha256,
        )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _projection_module.require_exact_candidate_packet_ref(
            indexed_packet_ref=ref,
            requested_packet_id=str(ref.artifact_id),
            requested_manifest_profile_sha256=_ref(7).manifest_profile_sha256,
        )


def test_bounded_read_requires_exact_packet_ref_and_decision_packet_schema() -> None:
    ref = _ref(8)
    payload = {"schema_version": "3.4", "hte": None}
    manifest = SimpleNamespace(
        artifact_id=ref.artifact_id,
        kind="scientist.decision_packet",
        media_type="application/json",
        artifact_schema=SimpleNamespace(name="polisyos.scientist.DecisionPacket", version="3.4"),
    )
    bounded = SimpleNamespace(effective_ref=ref, manifest=manifest, value=payload)

    assert (
        _projection_module.validate_bounded_candidate_packet(
            bounded_read=bounded,
            selected_ref=ref,
        )
        == payload
    )

    wrong_profile = ref.model_copy(
        update={"manifest_profile_sha256": _ref(7).manifest_profile_sha256}
    )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _projection_module.validate_bounded_candidate_packet(
            bounded_read=bounded,
            selected_ref=wrong_profile,
        )

    wrong_schema = SimpleNamespace(
        effective_ref=ref,
        manifest=SimpleNamespace(
            artifact_id=ref.artifact_id,
            kind="scientist.decision_packet",
            media_type="application/json",
            artifact_schema=SimpleNamespace(
                name="polisyos.scientist.DecisionPacket",
                version="3.3",
            ),
        ),
        value=payload,
    )
    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError):
        _projection_module.validate_bounded_candidate_packet(
            bounded_read=wrong_schema,
            selected_ref=ref,
        )


@pytest.mark.parametrize("status", ["selected", "verification_missing"])
def test_cross_run_candidate_refuses_for_selected_and_absent_packet(status: str) -> None:
    source = _selected_source()
    packet = _packet_payload(source, status=status)
    fresh = _fresh_source(source) if status == "selected" else None

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError) as exc_info:
        _project(packet, source=fresh, packet_run_id="packet-run-other")

    assert exc_info.value.code == "cross_run_authorization_not_established"


def test_same_run_projection_requires_exact_packet_source_identity() -> None:
    source = _selected_source()
    packet = _packet_payload(source)
    assert _project(packet, source=_fresh_source(source)).packet_run_id == source.source_run_id

    with pytest.raises(_projection_module.CandidatePacketProjectionRefusalError) as exc_info:
        _project(packet, source=_fresh_source(source), source_run_id="other-source-run")
    assert exc_info.value.code == "candidate_packet_source_selector_mismatch"
