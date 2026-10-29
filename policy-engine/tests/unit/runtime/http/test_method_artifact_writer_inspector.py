"""Fresh public Inspector must consume full source policy, never a kind hint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import ArtifactRef, CanonInfo, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile_bounded
from polisyos.core.artifacts.signing import SigningConfig
from polisyos.core.contracts.foundry import MethodArtifactOutputPayload
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.resilience import GuardedDependencyProxy, build_runtime_cas_guard
from polisyos.runtime.http.services import artifact_inspector as inspector_module
from polisyos.runtime.http.services.artifact_inspector import (
    ArtifactInspectorService,
    ArtifactSurfaceAdmissionError,
)
from polisyos.runtime.http.services.lineage import LineageService
from polisyos.runtime.quality.technical_inspection_evidence import (
    create_technical_inspection_evidence,
)
from tests._helpers.method_artifact_writer import (
    capture_fixture,
    local_store,
    produce,
    selected_ref,
)


def _import_selected_closure(source: FileSystemCAS, target: Any, ref: ArtifactRef) -> None:
    """Transfer exact source views; the target transaction grants its actual owner."""
    manifest = source.get_manifest(ref)
    for edge in manifest.inputs:
        child = source.get_manifest_by_profile(edge.artifact_id, edge.manifest_profile_sha256)
        child_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=child.kind,
            media_type=child.media_type,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        _import_selected_closure(source, target, child_ref)
    imported = target.import_exact_view(
        source.get_bytes(ref), source.get_raw_manifest_bytes(ref), artifact_id=ref
    )
    assert imported == ref
    assert target.get_raw_manifest_bytes(ref) == source.get_raw_manifest_bytes(ref)
    assert target.get_bytes(ref) == source.get_bytes(ref)


def test_fresh_public_inspector_consumes_literal_collision_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    root = tmp_path / "cas"
    tenant, cell = "inspection-tenant", "inspection-cell"
    scope = AccessScope.for_service(
        tenant_id=tenant, cell_id=cell, spiffe_id="spiffe://test/inspection"
    )
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        token = set_current_access_scope(scope)
        try:
            # The .3 producer requires the unsigned, ownership-disabled local
            # writer. Exact CAS import, not reissue, transfers A and its input
            # views into the enforcing consumer owner under this tenant scope.
            source = local_store(tmp_path / "producer")
            capture, occurrence = capture_fixture(source)
            raw = {"ordinary": {"_type": "decimal", "value": "9"}, "null": None}
            produced = selected_ref(produce(source, capture, occurrence, {"sidecar": raw}))
            ref = ArtifactRef.model_validate(produced.model_dump(mode="python"))
            store = FileSystemCAS(
                root, ownership_enforced=True, signing_config=SigningConfig(enabled=False)
            )
            _import_selected_closure(source, store, ref)
            assert store.get_manifest(ref) == source.get_manifest(ref)
            guard = build_runtime_cas_guard()
            guarded = GuardedDependencyProxy(target=store, guard=guard)
            try:
                evidence = create_technical_inspection_evidence(guarded, ref)
            finally:
                guard.close()
            # Reopen the ownership-enforcing backend and preserve the guarded
            # handle for the actual consumer; read-only opening disables owner checks.
            fresh = FileSystemCAS(
                root, ownership_enforced=True, signing_config=SigningConfig(enabled=False)
            )
            fresh_guard = build_runtime_cas_guard()
            guarded_fresh = GuardedDependencyProxy(target=fresh, guard=fresh_guard)
            try:
                inspector = ArtifactInspectorService(
                    store=guarded_fresh, lineage_service=LineageService(store=guarded_fresh)
                )
                header = read_core_manifest_profile_bounded(
                    guarded_fresh,
                    ref,
                    max_manifest_bytes=inspector_module.INSPECTOR_MANIFEST_MAX_BYTES,
                )
                with pytest.raises(ArtifactSurfaceAdmissionError) as missing:
                    inspector.get_content_preview(ref.artifact_id, manifest_read=header)
                assert missing.value.decision.reason == "authority_surface_signal_missing"
                preview = inspector.get_content_preview(
                    ref.artifact_id,
                    manifest_read=header,
                    technical_inspection_evidence_ref=evidence,
                )
                assert preview.mode == "json"
                assert preview.preview["payload"] == raw
                assert preview.canon_read_status == "declared_bytes_conformant"
                schema = inspector.get_schema_view(
                    ref.artifact_id,
                    manifest_read=header,
                    technical_inspection_evidence_ref=evidence,
                )
                assert schema.top_level_keys == sorted(MethodArtifactOutputPayload.model_fields)
                assert schema.canon_read_status == "declared_bytes_conformant"
            finally:
                fresh_guard.close()
        finally:
            reset_current_access_scope(token)


@pytest.mark.parametrize("surface", ["get_content_preview", "get_schema_view"])
@pytest.mark.parametrize(
    "changed",
    [
        "kind",
        "media_type",
        "schema",
        "canon",
        "producer",
        "inputs",
        "kind_and_media",
        "kind_media_schema_version",
        "kind_media_producer",
    ],
)
def test_same_id_selected_adversarial_context_is_not_inspected_as_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
    surface: str,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    ref = selected_ref(
        produce(store, capture, occurrence, {"sidecar": {"_type": "decimal", "value": "9"}})
    )
    manifest = store.get_manifest(ref)
    kwargs = {
        "kind": manifest.kind,
        "media_type": manifest.media_type,
        "schema": manifest.artifact_schema,
        "canon": manifest.canon,
        "producer": manifest.producer,
        "inputs": manifest.inputs,
    }
    changes: dict[str, Any] = {
        "kind": "other.owner",
        "media_type": "application/octet-stream",
        "schema": SchemaInfo(name="other.schema", version="1.0"),
        "canon": CanonInfo(version="0.3.0", max_depth=17, forbid_floats=False),
        "producer": None,
        "inputs": [],
    }
    if changed.startswith("kind_"):
        kwargs.update(kind="other.owner", media_type="application/octet-stream")
        if changed == "kind_media_schema_version":
            kwargs["schema"] = SchemaInfo(name=manifest.artifact_schema.name, version="unqualified")
        elif changed == "kind_media_producer":
            kwargs["producer"] = None
    else:
        kwargs[changed] = changes[changed]
    bad = store.put_bytes(store.get_bytes(ref), PutOptions(**kwargs), return_selected_profile=True)
    assert bad.artifact_id == ref.artifact_id
    opened = type(store).open_existing_read_only(tmp_path / "cas")
    header = read_core_manifest_profile_bounded(opened, bad, max_manifest_bytes=4096)
    inspector = ArtifactInspectorService(store=opened, lineage_service=LineageService(store=opened))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("payload opened before complete selected cohort refusal")

    monkeypatch.setattr(type(opened), "get_bytes", forbidden)
    monkeypatch.setattr(type(opened), "open_member_bounded", forbidden)
    # Both public methods use the actual selected same-ID view, including its
    # source-owned schema while kind and media are jointly substituted.
    with pytest.raises(CanonicalProfileRefusalError):
        getattr(inspector, surface)(bad.artifact_id, manifest_read=header)


def test_producer_failure_retains_unavailable_without_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    from polisyos.foundry.execute._internal import graph

    def removed(*args: Any, **kwargs: Any) -> Any:
        raise CanonicalProfileRefusalError("removed_real_producer")

    monkeypatch.setattr(graph, "put_core_json_artifact_bounded", removed)
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    rows = produce(store, capture, occurrence, {"sidecar": {"answer": 1}})
    assert rows[0][0].status == "unavailable"
    assert rows[0][0].artifact_ref is None
    assert capture.sidecar_refs_used == 0


@pytest.mark.parametrize("surface", ["get_content_preview", "get_schema_view"])
def test_fresh_header_overcap_refuses_before_unbounded_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.runtime.http.services import artifact_inspector as module

    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    ref = selected_ref(produce(store, capture, occurrence, {"sidecar": {"answer": 1}}))
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, None)
    manifest_path.write_bytes(
        manifest_path.read_bytes() + b" " * module.INSPECTOR_MANIFEST_MAX_BYTES
    )
    opened = type(store).open_existing_read_only(tmp_path / "cas")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("unbounded manifest or payload loader invoked")

    monkeypatch.setattr(module, "read_core_manifest_profile", forbidden)
    for owner in (type(opened), type(store)):
        for operation in (
            "get_bytes",
            "get_manifest",
            "get_manifest_by_profile",
            "get_raw_manifest_bytes",
        ):
            monkeypatch.setattr(owner, operation, forbidden)
    monkeypatch.setattr(type(store), "get_manifest_bytes", forbidden)
    inspector = ArtifactInspectorService(store=opened, lineage_service=LineageService(store=opened))
    with pytest.raises(CoreJsonReadBoundsRefusalError):
        getattr(inspector, surface)(ref.artifact_id)


def test_qualified_legacy_reader_succeeds_but_public_inspection_remains_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store, "legacy")
    produced = selected_ref(produce(store, capture, occurrence, {"sidecar": {"answer": 2}}))
    ref = ArtifactRef.model_validate(produced.model_dump(mode="python"))
    # The existing .2 reader still interprets the actual produced payload.
    read = inspector_module._read_inspector_semantic_json(store, ref, max_payload_bytes=65536)
    assert read.value["payload"] == {"answer": 2}
    inspector = ArtifactInspectorService(store=store, lineage_service=LineageService(store=store))
    # The .2 cohort is outside the new proof producer. Its public-positive
    # authority remains HOLD; codec conformance does not supply that authority.
    with pytest.raises(ArtifactSurfaceAdmissionError) as blocked:
        inspector.get_content_preview(ref.artifact_id)
    assert blocked.value.decision.reason == "authority_surface_signal_missing"


def test_backend_without_bounded_owner_ports_cannot_load_header(tmp_path: Path) -> None:
    from polisyos.core.artifacts import ArtifactID
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError

    class UnboundedBackend:
        def get_manifest(self, *args: Any, **kwargs: Any) -> Any:
            pytest.fail("unbounded manifest fallback")

        def get_raw_manifest_bytes(self, *args: Any, **kwargs: Any) -> Any:
            pytest.fail("unbounded raw manifest fallback")

        def get_bytes(self, *args: Any, **kwargs: Any) -> Any:
            pytest.fail("unbounded payload fallback")

    store = UnboundedBackend()
    inspector = ArtifactInspectorService(store=store, lineage_service=LineageService(store=store))
    with pytest.raises(CoreJsonReadBoundsRefusalError):
        inspector.get_content_preview(ArtifactID.from_sha256_hex("f" * 64))


def test_unknown_non_json_projection_is_uninterpreted_but_public_read_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    ref = selected_ref(
        produce(store, capture, occurrence, {"sidecar": {"_type": "decimal", "value": "9"}})
    )
    manifest = store.get_manifest(ref)
    raw = store.get_bytes(ref)
    unrelated = store.put_bytes(
        raw,
        PutOptions(
            kind="other.raw_owner",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="other.raw_schema", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert unrelated.artifact_id == ref.artifact_id
    opened = type(store).open_existing_read_only(tmp_path / "cas")
    header = read_core_manifest_profile_bounded(opened, unrelated, max_manifest_bytes=4096)
    inspector = ArtifactInspectorService(store=opened, lineage_service=LineageService(store=opened))
    seen: list[object] = []
    original = inspector_module.authority_surface_decision

    def observe(payload: object, **kwargs: Any) -> Any:
        seen.append(payload)
        return original(payload, **kwargs)

    monkeypatch.setattr(inspector_module, "authority_surface_decision", observe)
    # No replacement grant: preserve the real authority gate, recording the
    # actual pre-gate projection to prove the unknown view is not interpreted.
    with pytest.raises(ArtifactSurfaceAdmissionError) as content_blocked:
        inspector.get_content_preview(unrelated.artifact_id, manifest_read=header)
    assert content_blocked.value.decision.reason == "authority_surface_signal_missing"
    assert seen[-1] == raw
    with pytest.raises(ArtifactSurfaceAdmissionError) as schema_blocked:
        inspector.get_schema_view(unrelated.artifact_id, manifest_read=header)
    assert schema_blocked.value.decision.reason == "authority_surface_signal_missing"
    assert isinstance(seen[-1], dict)
    assert seen[-1]["canon_read_status"] == "not_evaluated"
    assert seen[-1]["top_level_keys"] == []
    # This cohort is not eligible for the bounded .3 Method evidence. Its
    # public-positive raw preview remains HOLD pending independently admitted
    # authority; the negative above does not claim to repair it.
