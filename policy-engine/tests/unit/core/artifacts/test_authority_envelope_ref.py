from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactRef,
    CanonInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.protocol import resolve_authority_envelope_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.runtime.quality.authority import (
    _surface_authority_payload,
    authority_surface_decision,
)

_ENVELOPE_KIND = "runtime_quality.evidence_authority_envelope"
_ENVELOPE_SCHEMA = "runtime_quality.evidence_authority_envelope"
_CORE_CANON_SPEC = CanonSpec()
_CORE_CANON_INFO = CanonInfo.from_spec(_CORE_CANON_SPEC)


def _canonical_json_bytes(value: object) -> bytes:
    """Encode a fixture through the Core canonical JSON profile."""
    if isinstance(value, bytes):
        value = json.loads(value)
    return to_canonical_bytes(value, _CORE_CANON_SPEC)


def _envelope_options(
    *,
    kind: str = _ENVELOPE_KIND,
    media_type: str = "application/json",
    schema_name: str = _ENVELOPE_SCHEMA,
    schema_version: str = "1.0.0",
    producer_version: str,
) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
        canon=_CORE_CANON_INFO,
        producer=ProducerInfo(
            component="polisyos.tests.authority-envelope",
            version=producer_version,
        ),
    )


def _authority_link(ref: ArtifactRef) -> ArtifactAuthorityInfo:
    return ArtifactAuthorityInfo(
        authority_envelope_ref=str(ref.artifact_id),
        authority_envelope_manifest_profile_sha256=ref.manifest_profile_sha256,
        diagnostic_event_ref="sha256:" + "2" * 64,
        manifest_ref=f"cas-manifest://{ref.artifact_id}",
        payload_sha256=ref.artifact_id.hex,
    )


def test_authority_envelope_ref_resolves_exact_profile_and_legacy_default(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "authority-envelope-views")
    payload = _canonical_json_bytes({"authority": "same bytes, selected metadata"})
    default_ref = store.put_bytes(
        payload,
        _envelope_options(producer_version="default-view"),
    )
    selected_ref = store.put_bytes(
        payload,
        _envelope_options(producer_version="selected-view"),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    resolved = resolve_authority_envelope_ref(store, _authority_link(selected_ref))

    assert resolved == selected_ref
    assert (
        store.get_manifest(resolved).producer
        == _envelope_options(producer_version="selected-view").producer
    )
    assert store.get_bytes(resolved) == payload
    assert store.verify(resolved).ok

    legacy_default = resolve_authority_envelope_ref(store, _authority_link(default_ref))

    assert legacy_default == default_ref
    assert legacy_default.manifest_profile_sha256 is None
    assert (
        store.get_manifest(legacy_default).producer
        == _envelope_options(producer_version="default-view").producer
    )

    invalid_contracts = (
        {"kind": "runtime_quality.not_authority_envelope"},
        {"media_type": "application/octet-stream"},
        {"schema_name": "runtime_quality.not_authority_envelope"},
        {"schema_version": "2.0.0"},
    )
    for index, contract in enumerate(invalid_contracts):
        wrong_ref = store.put_bytes(
            payload,
            _envelope_options(producer_version=f"wrong-{index}", **contract),
        )
        assert wrong_ref.manifest_profile_sha256 is not None
        with pytest.raises(ValueError, match="authority_envelope_manifest_contract_mismatch"):
            resolve_authority_envelope_ref(store, _authority_link(wrong_ref))

    mismatched_profile = _authority_link(selected_ref).model_copy(
        update={"authority_envelope_manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(ValueError, match="authority_envelope_manifest_resolution_failed"):
        resolve_authority_envelope_ref(store, mismatched_profile)


def test_authority_surface_reads_the_producer_selected_envelope_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "authority-envelope-surface")
    envelope_bytes = _canonical_json_bytes({"authority_boundary": {"posture": "limited"}})
    store.put_bytes(envelope_bytes, _envelope_options(producer_version="default-view"))
    selected_ref = store.put_bytes(
        envelope_bytes,
        _envelope_options(producer_version="selected-view"),
    )
    assert selected_ref.manifest_profile_sha256 is not None
    payload_ref = store.put_bytes(
        _canonical_json_bytes({"ordinary_payload": "no authority carrier"}),
        ArtifactWriteOptions(
            kind="runtime.test_payload",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
            canon=_CORE_CANON_INFO,
            authority=_authority_link(selected_ref),
        ),
    )

    class RecordingStore:
        def __init__(self) -> None:
            self.profiled_reads: list[object] = []

        def __getattr__(self, name: str) -> object:
            return getattr(store, name)

        def get_bytes(self, artifact_id: object) -> bytes:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id: object) -> object:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.get_manifest(artifact_id)

        def verify(self, artifact_id: object) -> object:
            if getattr(artifact_id, "artifact_id", None) == selected_ref.artifact_id:
                self.profiled_reads.append(artifact_id)
            return store.verify(artifact_id)

    recording_store = RecordingStore()
    projected = _surface_authority_payload(
        None,
        artifact_store=recording_store,
        artifact_id=payload_ref,
    )

    assert projected == {"authority_boundary": {"posture": "limited"}}
    assert selected_ref in recording_store.profiled_reads


def test_surface_authority_uses_selected_payload_manifest_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "selected-payload-authority-view")
    default_envelope = store.put_bytes(
        _canonical_json_bytes(
            b'{"authority_result":"authority","legacy_path_disposition":"authority_path","authority_boundary":{"boundary_id":"boundary://default","source_authority":"runtime_quality","posture":"authority","authoritative_for":["dashboard_display"],"may_not_use_for":["evaluation_execution"],"rule_version_refs":["rule://selected-profile-test"]}}'
        ),
        _envelope_options(producer_version="default-envelope"),
    )
    selected_envelope = store.put_bytes(
        _canonical_json_bytes(
            b'{"authority_result":"authority","legacy_path_disposition":"authority_path","authority_boundary":{"boundary_id":"boundary://selected","source_authority":"runtime_quality","posture":"authority","authoritative_for":["dashboard_display"],"may_not_use_for":["dashboard_display"],"rule_version_refs":["rule://selected-profile-test"]}}'
        ),
        _envelope_options(producer_version="selected-envelope"),
    )
    payload = b'{"ordinary_payload":"identical bytes"}'
    payload_default = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="runtime.test_payload",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
            canon=_CORE_CANON_INFO,
            authority=_authority_link(default_envelope),
        ),
    )
    payload_selected = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="runtime.test_payload",
            media_type="application/json",
            schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
            canon=_CORE_CANON_INFO,
            authority=_authority_link(selected_envelope),
        ),
    )
    assert payload_default.artifact_id == payload_selected.artifact_id
    assert payload_default.manifest_profile_sha256 != payload_selected.manifest_profile_sha256

    common = {
        "surface": "dashboard",
        "purpose": "dashboard_display",
        "artifact_store": store,
        "require_cas_integrity": True,
        "enforce_s12": False,
        "enforce_time_source": False,
        "enforce_candidate_firewall": False,
    }
    default_decision = authority_surface_decision(
        None,
        artifact_id=payload_default.artifact_id,
        artifact_ref=payload_default,
        **common,
    )
    selected_decision = authority_surface_decision(
        None,
        artifact_id=payload_selected.artifact_id,
        artifact_ref=payload_selected,
        **common,
    )

    assert default_decision.status == "allowed"
    assert selected_decision.status == "downgraded"
    assert selected_decision.reason == "authority_purpose_forbidden"


def test_inline_and_selected_manifest_authority_are_both_constraints(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "inline-and-selected-authority")
    inline_permit = {
        "authority_result": "authority",
        "legacy_path_disposition": "authority_path",
        "authority_boundary": {
            "boundary_id": "boundary://inline-permit",
            "source_authority": "runtime_quality",
            "posture": "authority",
            "authoritative_for": ["dashboard_display"],
            "may_not_use_for": ["evaluation_execution"],
            "rule_version_refs": ["rule://selected-profile-test"],
        },
    }
    inline_deny = {
        **inline_permit,
        "authority_boundary": {
            **inline_permit["authority_boundary"],
            "boundary_id": "boundary://inline-deny",
            "may_not_use_for": ["dashboard_display"],
        },
    }
    envelope_allow = store.put_bytes(
        _canonical_json_bytes(
            b'{"authority_result":"authority","legacy_path_disposition":"authority_path","authority_boundary":{"boundary_id":"boundary://linked-allow","source_authority":"runtime_quality","posture":"authority","authoritative_for":["dashboard_display"],"may_not_use_for":["evaluation_execution"],"rule_version_refs":["rule://selected-profile-test"]}}'
        ),
        _envelope_options(producer_version="linked-allow"),
    )
    envelope_deny = store.put_bytes(
        _canonical_json_bytes(
            b'{"authority_result":"authority","legacy_path_disposition":"authority_path","authority_boundary":{"boundary_id":"boundary://linked-deny","source_authority":"runtime_quality","posture":"authority","authoritative_for":["dashboard_display"],"may_not_use_for":["dashboard_display"],"rule_version_refs":["rule://selected-profile-test"]}}'
        ),
        _envelope_options(producer_version="linked-deny"),
    )

    def payload_ref(payload: dict[str, object], linked_envelope: ArtifactRef) -> ArtifactRef:
        return store.put_bytes(
            _canonical_json_bytes(payload),
            ArtifactWriteOptions(
                kind="runtime.test_payload",
                media_type="application/json",
                schema=SchemaInfo(name="runtime.test_payload", version="1.0.0"),
                canon=_CORE_CANON_INFO,
                authority=_authority_link(linked_envelope),
            ),
        )

    inline_permit_ref = payload_ref(inline_permit, envelope_deny)
    inline_deny_ref = payload_ref(inline_deny, envelope_allow)
    assert inline_permit_ref.artifact_id != inline_deny_ref.artifact_id

    decisions = (
        authority_surface_decision(
            inline_permit,
            surface="dashboard",
            purpose="dashboard_display",
            artifact_store=store,
            artifact_id=inline_permit_ref,
            require_cas_integrity=True,
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        ),
        authority_surface_decision(
            inline_deny,
            surface="dashboard",
            purpose="dashboard_display",
            artifact_store=store,
            artifact_id=inline_deny_ref,
            require_cas_integrity=True,
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        ),
    )

    assert all(decision.visible_downgrade for decision in decisions)
    assert all(decision.reason == "authority_purpose_forbidden" for decision in decisions)
    assert all(
        "selected_manifest_authority" in decision.composed_gate_inputs for decision in decisions
    )

    inline_permit_decision, inline_deny_decision = decisions
    assert inline_permit_decision.authority_boundary_ref == "boundary://linked-deny"
    assert "dashboard_display" in inline_permit_decision.may_not_use_for
    permit_contributors = {row.basis: row for row in inline_permit_decision.authority_contributors}
    assert permit_contributors["base_surface"].authority_boundary_ref == (
        "boundary://inline-permit"
    )
    assert permit_contributors["selected_manifest"].authority_boundary_ref == (
        "boundary://linked-deny"
    )
    assert permit_contributors["selected_manifest"].reason == "authority_purpose_forbidden"
    assert inline_deny_decision.authority_boundary_ref == "boundary://inline-deny"
    assert "dashboard_display" in inline_deny_decision.may_not_use_for
    deny_contributors = {row.basis: row for row in inline_deny_decision.authority_contributors}
    assert deny_contributors["base_surface"].authority_boundary_ref == ("boundary://inline-deny")
    assert deny_contributors["selected_manifest"].authority_boundary_ref == (
        "boundary://linked-allow"
    )

    both_deny_ref = payload_ref(inline_deny, envelope_deny)
    both_permit_ref = payload_ref(inline_permit, envelope_allow)
    both_deny = authority_surface_decision(
        inline_deny,
        surface="dashboard",
        purpose="dashboard_display",
        artifact_store=store,
        artifact_id=both_deny_ref,
        require_cas_integrity=True,
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    both_permit = authority_surface_decision(
        inline_permit,
        surface="dashboard",
        purpose="dashboard_display",
        artifact_store=store,
        artifact_id=both_permit_ref,
        require_cas_integrity=True,
        enforce_time_source=False,
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )
    assert both_deny.status == "downgraded"
    assert both_deny.reason == "authority_purpose_forbidden"
    assert [row.basis for row in both_deny.authority_contributors] == [
        "base_surface",
        "selected_manifest",
    ]
    assert both_deny.authority_boundary_ref == "boundary://linked-deny"
    assert both_permit.status == "allowed"
    assert all(row.status == "allowed" for row in both_permit.authority_contributors)
