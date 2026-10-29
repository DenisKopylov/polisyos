"""Exercise persisted mechanical facts against real source and enforcing CAS owners."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, ProducerInfo, PutOptions
from polisyos.core.artifacts.ownership import ArtifactOwnershipError, ArtifactOwnershipIndex
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.execute import read_method_artifact_output_bounded
from polisyos.runtime.http.resilience import GuardedDependencyProxy, build_runtime_cas_guard
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.technical_inspection_evidence import (
    TECHNICAL_INSPECTION_PURPOSE,
    TechnicalInspectionOwnerNotEstablishedError,
    create_technical_inspection_evidence,
    verify_technical_inspection_evidence,
)
from tests._helpers.method_artifact_writer import (
    capture_fixture,
    cas_content,
    local_store,
    produce,
    selected_ref,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from polisyos.runtime.quality.authority import AuthoritySurfaceDecision


@contextmanager
def _fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, value: object = 1
) -> Iterator[tuple[GuardedDependencyProxy, ArtifactRef]]:
    """Establish synthetic software access; this does not attest method execution."""
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "30")
    local = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(local)
    produced = selected_ref(produce(local, capture, occurrence, {"sidecar": {"value": value}}))
    ref = ArtifactRef.model_validate(produced.model_dump(mode="python"))
    target = local_store(tmp_path / "owned-cas").for_tenant("tenant-a", "cell-a")
    refs = [
        *(
            ArtifactRef.model_validate(item.model_dump(mode="python"))
            for item in (
                capture.program_graph_ref,
                capture.exec_plan_ref,
                capture.method_metric_binding_set_ref,
            )
        ),
        ref,
    ]
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        for selected in refs:
            # The real exact-view importer recomputes bytes/profile and records
            # blob AND selected-view software access under its transaction owner.
            actual = target.import_exact_view(
                local.get_bytes(selected),
                local.get_raw_manifest_bytes(selected),
                artifact_id=selected,
            )
            assert actual == selected
            assert target.get_bytes(actual) == local.get_bytes(selected)
            assert target.get_raw_manifest_bytes(actual) == local.get_raw_manifest_bytes(selected)
    guarded = GuardedDependencyProxy(target=target, guard=build_runtime_cas_guard())
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            yield guarded, ref
    finally:
        guarded.close()


def _decide(
    store: GuardedDependencyProxy | FileSystemCAS,
    ref: ArtifactRef,
    evidence: ArtifactRef | None,
    *,
    surface: str = "artifact",
    purpose: str = TECHNICAL_INSPECTION_PURPOSE,
) -> AuthoritySurfaceDecision:
    scan_scope = "raw artifact content/download routes"
    return authority_surface_decision(
        {},
        surface=surface,
        purpose=purpose,
        artifact_store=store,
        artifact_ref=ref,
        technical_inspection_evidence_ref=evidence,
        require_cas_integrity=True,
        secret_pii_scope=scan_scope,
    )


def _rewritten_evidence(
    store: GuardedDependencyProxy,
    evidence: ArtifactRef,
    mutate: Callable[[dict[str, Any]], None],
) -> ArtifactRef:
    manifest = store.get_manifest(evidence)
    payload = from_canonical_bytes(store.get_bytes(evidence))
    mutate(payload)
    return store.put_bytes(
        to_canonical_bytes(payload),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        return_selected_profile=True,
    )


@pytest.mark.parametrize("surface", ["artifact", "dashboard"])
def test_actual_producer_persisted_evidence_fresh_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        before = store.get_manifest_bytes(ref)
        missing = _decide(store, ref, None, surface=surface)
        assert missing.blocking
        assert missing.reason == "technical_inspection_evidence_missing"
        evidence = create_technical_inspection_evidence(store, ref)
        # A new guarded enforcing handle must independently resolve both artifacts.
        fresh = GuardedDependencyProxy(
            target=FileSystemCAS(tmp_path / "owned-cas").for_tenant("tenant-a", "cell-a"),
            guard=build_runtime_cas_guard(),
        )
        try:
            verified = verify_technical_inspection_evidence(fresh, ref, evidence)
            assert verified.selected_ref == ref
            assert verified.observed_source_bytes <= 122880
            result = _decide(fresh, ref, evidence, surface=surface)
            assert result.status == "allowed"
            assert not result.blocking
            assert not result.visible_downgrade
            assert result.integrity_status == "verified"
            assert not result.consumed_authority_boundary
            assert "publication" in result.may_not_use_for
            assert "technical_inspection_evidence" in result.composed_gate_inputs
            assert fresh.get_manifest_bytes(ref) == before
        finally:
            fresh.close()


@pytest.mark.parametrize("purpose", ["runtime_closeout_authority", "publication", "claim_evidence"])
def test_mechanical_evidence_never_admits_protected_purposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, purpose: str
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        result = _decide(store, ref, evidence, purpose=purpose)
        assert result.blocking
        assert result.reason == "technical_inspection_purpose_not_permitted"


def test_same_payload_other_selected_profile_cannot_borrow_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        manifest = store.get_manifest(ref)
        other = store.put_bytes(
            store.get_bytes(ref),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                producer=ProducerInfo(component="different-owner", version="1"),
                inputs=manifest.inputs,
            ),
            return_selected_profile=True,
        )
        assert other.artifact_id == ref.artifact_id
        assert other.manifest_profile_sha256 != ref.manifest_profile_sha256
        assert _decide(store, other, evidence).blocking


def test_borrowed_evidence_ref_missing_profile_and_corrupt_bytes_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        absent = evidence.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
        assert _decide(store, ref, absent).blocking
        profileless = evidence.model_copy(update={"manifest_profile_sha256": None})
        assert _decide(store, ref, profileless).blocking
        # Deliberately alter actual stored bytes while preserving receipt markers.
        raw_path = store._target._paths(evidence.artifact_id)[0]
        original = raw_path.read_bytes()
        try:
            raw_path.write_bytes(original.replace(b"tenant-a", b"tenant-b"))
            assert _decide(store, ref, evidence).blocking
        finally:
            raw_path.write_bytes(original)


@pytest.mark.parametrize("field", ["selected_ref", "payload_sha256", "read_limits", "tenant_id"])
def test_present_receipt_markers_cannot_replace_recomputed_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)

        def corrupt(payload: dict[str, Any]) -> None:
            payload["fact"][field] = "present-but-fake"

        corrupt_ref = _rewritten_evidence(store, evidence, corrupt)
        assert _decide(store, ref, corrupt_ref).blocking


def test_stale_scope_and_non_enforcing_resolver_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
            assert _decide(store, ref, evidence).blocking
        local = local_store(tmp_path / "cas")
        assert _decide(local, ref, evidence).blocking


def test_evidence_for_another_subject_and_removed_fact_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        manifest = store.get_manifest(ref)

        # Actual selected A stays conformant but E's declared subject is removed.
        def remove_fact(payload: dict[str, Any]) -> None:
            payload["fact"] = {"predicate_provenance": "recomputed"}

        removed = _rewritten_evidence(store, evidence, remove_fact)
        assert _decide(store, ref, removed).blocking
        other_ref = store.put_json(
            {"unrelated": True},
            PutOptions(kind=manifest.kind, media_type=manifest.media_type),
            return_selected_profile=True,
        )
        assert _decide(store, other_ref, evidence).blocking


def test_projection_cannot_hide_subject_secret_or_existing_boundary_blocker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch, value={"api_key": "sk-live-" + "a" * 32}) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        result = _decide(store, ref, evidence, surface="dashboard")
        assert result.blocking
        assert result.secret_pii_finding_kinds
    with _fixture(tmp_path / "blocked", monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        result = authority_surface_decision(
            {"authority_result": "blocked", "legacy_path_disposition": "blocked"},
            surface="artifact",
            purpose=TECHNICAL_INSPECTION_PURPOSE,
            artifact_store=store,
            artifact_ref=ref,
            technical_inspection_evidence_ref=evidence,
        )
        assert result.blocking
        assert result.reason != "technical_inspection_fact_recomputed"


def test_oversized_proof_refuses_without_unbounded_reader_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)

        def enlarge(payload: dict[str, Any]) -> None:
            payload["fact"]["extra"] = "x" * 32768

        oversized = _rewritten_evidence(store, evidence, enlarge)

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("technical inspection used an unbounded read")

        monkeypatch.setattr(store._target, "get_bytes", forbidden)
        monkeypatch.setattr(store._target, "get_manifest", forbidden)
        monkeypatch.setattr(store._target, "verify", forbidden)
        assert _decide(store, ref, oversized).blocking
        assert not _decide(store, ref, evidence).blocking


@pytest.mark.parametrize("root_field", ["purpose", "rule_version"])
def test_wrong_purpose_or_rule_with_preserved_fact_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_field: str
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)

        def corrupt(payload: dict[str, Any]) -> None:
            payload[root_field] = "publication"

        corrupt_ref = _rewritten_evidence(store, evidence, corrupt)
        assert _decide(store, ref, corrupt_ref).blocking


def test_same_evidence_payload_other_actual_profile_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        manifest = store.get_manifest(evidence)
        other = store.put_bytes(
            store.get_bytes(evidence),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                producer=ProducerInfo(component="borrowed-inspection-owner", version="1"),
                inputs=manifest.inputs,
            ),
            return_selected_profile=True,
        )
        assert evidence.artifact_id == other.artifact_id
        assert evidence.manifest_profile_sha256 != other.manifest_profile_sha256
        assert _decide(store, ref, other).blocking


def test_transferred_current_access_does_not_make_stale_scope_fact_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        records = []
        seen = set()

        def collect(selected: ArtifactRef) -> None:
            key = (str(selected.artifact_id), selected.manifest_profile_sha256)
            if key in seen:
                return
            seen.add(key)
            manifest = store.get_manifest(selected)
            for edge in manifest.inputs:
                child_manifest = store.get_manifest_by_profile(
                    edge.artifact_id, edge.manifest_profile_sha256
                )
                collect(
                    ArtifactRef(
                        artifact_id=edge.artifact_id,
                        kind=child_manifest.kind,
                        media_type=child_manifest.media_type,
                        manifest_profile_sha256=edge.manifest_profile_sha256,
                    )
                )
            records.append(
                (selected, store.get_bytes(selected), store.get_raw_manifest_bytes(selected))
            )

        collect(evidence)
        target = local_store(tmp_path / "other-owner").for_tenant("tenant-b", "cell-b")
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            for selected, raw, manifest_raw in records:
                assert target.import_exact_view(raw, manifest_raw, artifact_id=selected) == selected
            guarded = GuardedDependencyProxy(target=target, guard=build_runtime_cas_guard())
            try:
                # Both artifacts are now genuinely accessible under B. Their
                # old scope declaration still cannot become a current fact.
                with pytest.raises(ValueError, match="technical_inspection_evidence_fact_mismatch"):
                    verify_technical_inspection_evidence(guarded, ref, evidence)
                new_evidence = create_technical_inspection_evidence(guarded, ref)
                assert new_evidence.artifact_id != evidence.artifact_id
                assert not _decide(guarded, ref, new_evidence).blocking
            finally:
                guarded.close()


@pytest.mark.parametrize(
    ("value", "reason", "blocking"),
    [
        ({"candidate_ref": "hypothesis-candidate:unadmitted"}, "candidate_firewall_blocked", True),
        ({"reference": "s12://unresolved"}, "s12_reference_candidate_only", False),
        (
            {"projection_kind": "time_source_consistency_audit_projection"},
            "time_source_envelope_obligation",
            False,
        ),
    ],
)
def test_inspection_evidence_preserves_subject_gate_contributors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: dict[str, str],
    reason: str,
    blocking: bool,
) -> None:
    with _fixture(tmp_path, monkeypatch, value=value) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        result = _decide(store, ref, evidence, surface="dashboard")
        assert result.reason == reason
        assert result.blocking is blocking
        assert result.visible_downgrade


def test_equal_python_values_with_different_canon_flag_types_are_not_same_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)

        def corrupt(payload: dict[str, Any]) -> None:
            assert payload["fact"]["manifest"]["canon"]["forbid_floats"] is False
            payload["fact"]["manifest"]["canon"]["forbid_floats"] = 0

        corrupt_ref = _rewritten_evidence(store, evidence, corrupt)
        assert _decide(store, ref, corrupt_ref).blocking


class _PermissiveOwnershipIndex(ArtifactOwnershipIndex):
    """A public-constructor provider substitution, without private-state edits."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.admission_calls = 0

    def require_blob_reader(self, *args: object, **kwargs: object) -> None:
        self.admission_calls += 1

    def require_view_owner(self, *args: object, **kwargs: object) -> None:
        self.admission_calls += 1

    def require_owner(self, *args: object, **kwargs: object) -> None:
        self.admission_calls += 1


def test_constructor_injected_permissive_provider_is_not_current_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        root = store._target.root
        stock = FileSystemCAS(root, tenant_id="tenant-b", cell_id="cell-b", ownership_enforced=True)
        injected = _PermissiveOwnershipIndex(root)
        substituted = FileSystemCAS(
            root,
            tenant_id="tenant-b",
            cell_id="cell-b",
            ownership_enforced=True,
            ownership_index=injected,
        )
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            # Establish the actual distinguishing context: native ledger has no
            # B claim, while the publicly supplied permissive provider reads A.
            with pytest.raises(ArtifactOwnershipError):
                read_method_artifact_output_bounded(stock, ref, max_bytes=65536)
            assert (
                read_method_artifact_output_bounded(substituted, ref, max_bytes=65536).effective_ref
                == ref
            )
            assert injected.admission_calls > 0
            injected.admission_calls = 0
            before = cas_content(root)
            guarded = GuardedDependencyProxy(target=substituted, guard=build_runtime_cas_guard())
            try:
                with pytest.raises(
                    TechnicalInspectionOwnerNotEstablishedError,
                    match="enforcement_provider_not_stock",
                ):
                    create_technical_inspection_evidence(guarded, ref)
                assert injected.admission_calls == 0
                assert cas_content(root) == before
            finally:
                guarded.close()


def test_stock_provider_requires_the_actual_root_and_configuration_relation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _fixture(tmp_path, monkeypatch) as (store, ref):
        root = store._target.root
        # The CAS constructor itself refuses a stock provider at another root.
        with pytest.raises(ValueError, match="filesystem_cas_ownership_root_mismatch"):
            FileSystemCAS(root, ownership_index=ArtifactOwnershipIndex(tmp_path / "other-root"))
        # A stock class with a public-constructor read-only configuration mismatch
        # is still not the stock enforcement plane of this writable CAS.
        mismatched = FileSystemCAS(
            root,
            tenant_id="tenant-a",
            cell_id="cell-a",
            ownership_enforced=True,
            ownership_index=ArtifactOwnershipIndex(root, read_only=True),
        )
        with pytest.raises(
            TechnicalInspectionOwnerNotEstablishedError,
            match="enforcement_provider_root_or_config_mismatch",
        ):
            create_technical_inspection_evidence(mismatched, ref)
        # The intact stock enforcing provider remains in the supported domain.
        evidence = create_technical_inspection_evidence(store, ref)
        assert not _decide(store, ref, evidence).blocking


def _base_authority_payload(blocked: bool) -> dict[str, Any]:
    return {
        "authority_result": "blocked" if blocked else "authority",
        "legacy_path_disposition": "blocked" if blocked else "authority_path",
        "authority_boundary": {
            "boundary_id": "boundary://mixed-outcome-ownership-test",
            "source_authority": "runtime_quality",
            "posture": "authority",
            "authoritative_for": ["runtime_closeout_authority", TECHNICAL_INSPECTION_PURPOSE],
            "may_not_use_for": ["publication"],
            "rule_version_refs": ["rule://mixed-outcome-ownership-test"],
        },
    }


@pytest.mark.parametrize("blocked", [True, False])
@pytest.mark.parametrize("signal", ["none", "s12", "time"])
def test_actual_inspection_gate_keeps_the_strongest_contributor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocked: bool, signal: str
) -> None:
    value = {
        "none": {"value": "plain"},
        "s12": {"reference": "s12://unresolved"},
        "time": {"projection_kind": "time_source_consistency_audit_projection"},
    }[signal]
    with _fixture(tmp_path, monkeypatch, value=value) as (store, ref):
        evidence = create_technical_inspection_evidence(store, ref)
        result = authority_surface_decision(
            _base_authority_payload(True) if blocked else {},
            surface="artifact",
            purpose=TECHNICAL_INSPECTION_PURPOSE,
            artifact_store=store,
            artifact_ref=ref,
            technical_inspection_evidence_ref=evidence,
            require_cas_integrity=True,
        )
        if blocked:
            assert result.status == "blocked"
            assert result.blocking
            assert result.reason == "workflow_failure_or_blocked_disposition"
            assert result.authority_contributors[0].blocking
        elif signal == "none":
            assert result.status == "allowed"
            assert not result.blocking
            assert not result.visible_downgrade
        else:
            assert result.status == "downgraded"
            assert not result.blocking
            assert result.visible_downgrade
        if signal == "s12":
            assert result.s12_issue_codes
        elif signal == "time":
            assert result.time_source_dispositions


@pytest.mark.parametrize("blocked", [True, False])
@pytest.mark.parametrize("signal", ["none", "s12", "time"])
def test_shared_gate_outcome_meet_also_preserves_noninspection_contributors(
    blocked: bool, signal: str
) -> None:
    payload = _base_authority_payload(blocked)
    payload["subject_signal"] = {
        "none": {"value": "plain"},
        "s12": {"reference": "s12://unresolved"},
        "time": {"projection_kind": "time_source_consistency_audit_projection"},
    }[signal]
    result = authority_surface_decision(
        payload, surface="artifact", purpose="runtime_closeout_authority"
    )
    if blocked:
        assert result.status == "blocked"
        assert result.blocking
        assert result.reason == "workflow_failure_or_blocked_disposition"
    elif signal == "none":
        assert result.status == "allowed"
        assert not result.blocking
    else:
        assert result.status == "downgraded"
        assert not result.blocking
        assert result.visible_downgrade
