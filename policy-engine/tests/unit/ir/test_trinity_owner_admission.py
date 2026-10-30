from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactStore,
    ArtifactTenantContextInfo,
    CanonInfo,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    with_ambient_ownership_enforcement_if_supported,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.ir.trinity.loaders import (
    TrinityLoadError,
    load_trinity_bundle,
    load_trinity_bundle_artifact,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    _persist_trinity_bundle,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

ZERO_REF = "sha256:" + "0" * 64
TRINITY_OWNER_SPEC = CanonSpec(forbid_floats=False)


def test_trinity_facade_exports_the_actual_owned_persistence_function() -> None:
    from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact as owner_persist

    assert persist_trinity_bundle_artifact is owner_persist


def _bundle(*, schema_version: str = "1.0") -> TrinityBundle:
    return TrinityBundle.model_validate(
        {
            "schema_version": schema_version,
            "problem_frame": {
                "schema_version": "1.0",
                "problem_id": "pf_owner",
                "domain": "custom",
                "objectives": [],
                "kpis": [],
                "success_criteria": [],
                "hard_constraints": [],
                "soft_constraints": [],
                "stakeholders": [],
                "labels": [],
                "notes": [],
            },
            "policy_spec": {
                "schema_version": "1.0",
                "policy_id": "ps_owner",
                "interventions": [],
                "mechanism_bindings": [],
                "parameters": [],
                "labels": [],
                "notes": [],
            },
            "model_spec": {
                "schema_version": "1.0",
                "model_id": "ms_owner",
                "data_snapshot_ref": ZERO_REF,
                "registry_bundle_ref": None,
                "assumptions": [],
                "labels": [],
                "notes": [],
            },
        }
    )


def _execution_context(
    store: ArtifactStore,
    *,
    run_dir: Path,
    run_id: str,
    tenant_id: str | None = None,
    cell_id: str | None = None,
    access_scope: AccessScope | None = None,
) -> ExecutionContext:
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_dir=run_dir,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        access_scope=access_scope,
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def _unowned_write(store: FileSystemCAS, payload: object, *, spec: CanonSpec):
    return store.put_json(
        payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version="1.0",
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def test_shared_trinity_writer_binds_selected_owner_profile_and_lineage_for_fresh_readers(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    ir_store = ensure_ir_artifact_store(store)
    bundle = _bundle()

    default_view = persist_trinity_bundle_artifact(ir_store, bundle)
    assert default_view.manifest_profile_sha256 is not None
    default_manifest = store.get_manifest(default_view)
    assert default_manifest.canon == CanonInfo.from_spec(TRINITY_OWNER_SPEC)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    assert load_trinity_bundle_artifact(fresh_store, default_view) == bundle

    # Profileless historical selectors remain usable for inspection when unambiguous.
    history_selector = ArtifactRefModel.model_validate(
        default_view.model_dump(exclude={"manifest_profile_sha256"})
    )
    assert load_trinity_bundle_artifact(fresh_store, history_selector) == bundle

    anchor = store.put_json(
        {"source": "lineage-anchor"},
        PutOptions(
            kind="ir.test_source_anchor",
            media_type="application/json",
            schema=SchemaInfo(name="ir.test_source_anchor", version="1.0"),
        ),
        return_selected_profile=True,
    )
    source_a = InputRef(
        artifact_id=anchor.artifact_id,
        role="source-view-a",
        manifest_profile_sha256=anchor.manifest_profile_sha256,
    )
    source_b = InputRef(
        artifact_id=anchor.artifact_id,
        role="source-view-b",
        manifest_profile_sha256=anchor.manifest_profile_sha256,
    )
    view_a = persist_trinity_bundle_artifact(ir_store, bundle, inputs=[source_a])
    view_b = persist_trinity_bundle_artifact(ir_store, bundle, inputs=[source_b])
    assert view_a.artifact_id == view_b.artifact_id == default_view.artifact_id
    assert view_a.manifest_profile_sha256 != view_b.manifest_profile_sha256
    assert store.get_manifest(view_a).inputs[0].role == "source-view-a"
    assert store.get_manifest(view_b).inputs[0].role == "source-view-b"
    assert load_trinity_bundle_artifact(fresh_store, view_a) == bundle
    assert load_trinity_bundle_artifact(fresh_store, view_b) == bundle

    profileless_payload = dict(view_a)
    profileless_payload.pop("manifest_profile_sha256")
    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        ArtifactRefModel.from_selected_write(profileless_payload)


def test_trinity_writer_persists_typed_tenant_context_for_fresh_owner_reader(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "tenant-owned-cas"
    owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(owner_store),
            _bundle(),
            tenant_context=context,
        )
        manifest = owner_store.get_manifest(ref)
        assert manifest.tenant_context == context
        assert manifest.canon == CanonInfo.from_spec(TRINITY_OWNER_SPEC)
        assert owner_store.verify(ref).ok

    fresh_owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
    fresh_reader = ensure_ir_artifact_store(fresh_owner_store)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert load_trinity_bundle_artifact(fresh_reader, ref) == _bundle()


def test_trinity_writer_rejects_malformed_context_without_fallback_or_publication(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "malformed-context-cas"
    owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")

    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(CanonViolation, match="ir_owned_artifact_write_options_invalid"),
    ):
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(owner_store),
            _bundle(),
            tenant_context={"tenant_id": "tenant-a", "cell_id": "cell-a", "extra": "bad"},
        )

    assert list(owner_store.iter_artifact_ids()) == []


def test_trinity_writer_refuses_context_foreign_to_the_active_store_owner(
    tmp_path: Path,
) -> None:
    owner_store = FileSystemCAS(tmp_path / "foreign-context-cas").for_tenant("tenant-a", "cell-a")
    foreign_context = ArtifactTenantContextInfo(tenant_id="tenant-b", cell_id="cell-b")

    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(CanonViolation, match="ir_owned_artifact_write_refused") as raised,
    ):
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(owner_store),
            _bundle(),
            tenant_context=foreign_context,
        )

    assert isinstance(raised.value.__cause__, ArtifactOwnershipError)
    assert list(owner_store.iter_artifact_ids()) == []


def test_trinity_writer_keeps_none_unscoped_under_an_ambient_tenant_scope(
    tmp_path: Path,
) -> None:
    owner_store = FileSystemCAS(tmp_path / "explicitly-unscoped-cas").for_tenant(
        "tenant-a", "cell-a"
    )

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(owner_store),
            _bundle(),
            tenant_context=None,
        )
        manifest = owner_store.get_manifest(ref)
        assert manifest.tenant_context is None
        assert manifest.canon == CanonInfo.from_spec(TRINITY_OWNER_SPEC)
        assert owner_store.verify(ref).ok


def test_foreign_trinity_context_cannot_be_admitted_from_another_tenant_scope(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "foreign-owner-cas"
    foreign_store = FileSystemCAS(cas_root).for_tenant("tenant-b", "cell-b")
    foreign_context = ArtifactTenantContextInfo(tenant_id="tenant-b", cell_id="cell-b")

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        foreign_ref = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(foreign_store),
            _bundle(),
            tenant_context=foreign_context,
        )
        assert foreign_store.get_manifest(foreign_ref).tenant_context == foreign_context

    requesting_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(TrinityLoadError, match="failed IR owner admission"),
    ):
        load_trinity_bundle_artifact(
            ensure_ir_artifact_store(requesting_store),
            foreign_ref,
        )


def test_shared_trinity_writer_refuses_profile_dropped_at_selected_write_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.ir.trinity.loaders as loaders

    profileless = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": TrinityBundle.ARTIFACT_KIND,
        "media_type": TrinityBundle.ARTIFACT_MEDIA_TYPE,
    }
    monkeypatch.setattr(loaders, "_put_owned_json_artifact", lambda *_args, **_kwargs: profileless)
    with pytest.raises(ValueError, match="selected_write_ref_requires_profile"):
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")),
            _bundle(),
        )


def test_hierarchical_trinity_producer_preserves_profile_lineage_and_uses_run_owner_context(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = with_ambient_ownership_enforcement_if_supported(FileSystemCAS(cas_root))
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        lineage_anchor = store.put_json(
            {"source": "lineage-anchor"},
            PutOptions(
                kind="ir.test_source_anchor",
                media_type="application/json",
                schema=SchemaInfo(name="ir.test_source_anchor", version="1.0"),
            ),
            return_selected_profile=True,
        )
        source_payload = {"source": "experiment-input"}
        first_source_view = store.put_json(
            source_payload,
            PutOptions(
                kind="ir.test_source",
                media_type="application/json",
                schema=SchemaInfo(name="ir.test_source", version="1.0"),
                inputs=[InputRef(artifact_id=lineage_anchor.artifact_id, role="source-lineage-a")],
            ),
            return_selected_profile=True,
        )
        source_ref = store.put_json(
            source_payload,
            PutOptions(
                kind="ir.test_source",
                media_type="application/json",
                schema=SchemaInfo(name="ir.test_source", version="1.0"),
                inputs=[InputRef(artifact_id=lineage_anchor.artifact_id, role="source-lineage-b")],
            ),
            return_selected_profile=True,
        )
        assert source_ref.artifact_id == first_source_view.artifact_id
        assert source_ref.manifest_profile_sha256 != first_source_view.manifest_profile_sha256
        state = ExperimentState(
            run_id="trinity-owner-run",
            inputs={
                "source_case_a": first_source_view,
                "source_case_b": source_ref,
            },
        )

        execution = _execution_context(
            store,
            run_dir=tmp_path / "run",
            run_id="trinity-owner-run",
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
        ref = _persist_trinity_bundle(execution, _bundle(), state=state)
        assert isinstance(ref, TrinityBundleRef)
        assert ref.manifest_profile_sha256 is not None
        manifest = store.get_manifest(ref)
    assert manifest.canon.forbid_floats is False
    assert manifest.tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    assert [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in manifest.inputs
    ] == [
        (
            str(first_source_view.artifact_id),
            "source_case_a",
            first_source_view.manifest_profile_sha256,
        ),
        (
            str(source_ref.artifact_id),
            "source_case_b",
            source_ref.manifest_profile_sha256,
        ),
    ]

    fresh_owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
    fresh_reader = ensure_ir_artifact_store(fresh_owner_store)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert load_trinity_bundle_artifact(fresh_reader, ref) == _bundle()


def test_hierarchical_trinity_producer_carries_scope_through_subworkflow_child_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polisyos.scientist.orchestration.engine.executor as executor_module
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.sub_workflow import (
        SubWorkflowConfig,
        SubWorkflowNode,
    )
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    cas_root = tmp_path / "tenant-owned-cas"
    owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
    scope = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id="cell-a",
        spiffe_id="spiffe://tests/trinity-owner",
    )
    parent_run_id = "trinity-tenant-owner-run"
    captured: dict[str, object] = {}

    class _CapturingChildExecutor:
        def __init__(self, ctx: ExecutionContext, _registry: object) -> None:
            self._ctx = ctx

        def execute(self, _workflow: WorkflowSpec, state: ExperimentState) -> SimpleNamespace:
            captured["child_run_id"] = state.run_id
            captured["child_run_context"] = self._ctx.run
            captured["ref"] = _persist_trinity_bundle(self._ctx, _bundle(), state=state)
            return SimpleNamespace(
                report=SimpleNamespace(nodes=[], status="ok"),
                state=state,
            )

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        execution = _execution_context(
            owner_store,
            run_dir=tmp_path / "tenant-run",
            run_id=parent_run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            access_scope=scope,
        )
        monkeypatch.setattr(executor_module, "WorkflowExecutor", _CapturingChildExecutor)
        subworkflow = SubWorkflowNode(
            SubWorkflowConfig(workflow=WorkflowSpec(workflow_id="child_scope", nodes=[])),
            NodeRegistry(),
            alias="tenant_child",
        )
        outcome = subworkflow.execute(execution, ExperimentState(run_id=parent_run_id))

        assert outcome.status == "ok"
        assert captured["child_run_id"] == f"{parent_run_id}__sub_tenant_child"
        assert captured["child_run_context"] is execution.run
        ref = captured["ref"]
        assert isinstance(ref, TrinityBundleRef)
        manifest = owner_store.get_manifest(ref)
        assert manifest.tenant_context == ArtifactTenantContextInfo(
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
        assert manifest.canon == CanonInfo.from_spec(TRINITY_OWNER_SPEC)

        fresh_owner_store = FileSystemCAS(cas_root).for_tenant("tenant-a", "cell-a")
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            assert (
                load_trinity_bundle_artifact(
                    ensure_ir_artifact_store(fresh_owner_store),
                    ref,
                )
                == _bundle()
            )


@pytest.mark.parametrize(
    ("scope_case", "error_code"),
    [
        ("wrong_type", "timeout_worker_owner_snapshot_invalid"),
        ("empty_tenant", "timeout_worker_owner_inputs_mismatch"),
        ("foreign_scope", "timeout_worker_owner_inputs_mismatch"),
    ],
)
def test_hierarchical_trinity_producer_refuses_scope_detached_from_run_owner_before_publication(
    scope_case: str,
    error_code: str,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    execution = _execution_context(
        store,
        run_dir=tmp_path / "run",
        run_id="trinity-owner-run",
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    if scope_case == "wrong_type":
        execution.run.access_scope = {"tenant_id": "tenant-a", "cell_id": "cell-a"}  # type: ignore[assignment]
    elif scope_case == "empty_tenant":
        execution.run.access_scope = AccessScope.for_service(
            tenant_id="",
            cell_id="cell-a",
            spiffe_id="spiffe://tests/trinity-owner",
        )
    elif scope_case == "foreign_scope":
        execution.run.access_scope = AccessScope.for_service(
            tenant_id="tenant-b",
            cell_id="cell-b",
            spiffe_id="spiffe://tests/trinity-owner",
        )
    state = ExperimentState(run_id="trinity-owner-run")

    with pytest.raises(ValueError, match=error_code):
        _persist_trinity_bundle(execution, _bundle(), state=state)

    assert not [
        ref
        for ref in store.iter_artifact_ids()
        if store.get_manifest(ref).kind == TrinityBundle.ARTIFACT_KIND
    ]


def test_trinity_owner_refuses_same_kind_wrong_manifest_and_payload_versions(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    wrong_manifest_payload = _bundle().model_dump(mode="json")
    wrong_manifest = FileSystemCAS(tmp_path / "wrong-manifest")
    wrong_manifest_ref = wrong_manifest.put_json(
        wrong_manifest_payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version="9.0",
            ),
            canon=CanonInfo.from_spec(TRINITY_OWNER_SPEC),
        ),
        canon_spec=TRINITY_OWNER_SPEC,
        return_selected_profile=True,
    )
    with pytest.raises(TrinityLoadError, match="manifest"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(wrong_manifest), wrong_manifest_ref)

    wrong_payload = _bundle().model_dump(mode="json")
    wrong_payload["schema_version"] = "9.0"
    payload_store = FileSystemCAS(tmp_path / "wrong-payload")
    wrong_payload_ref = _unowned_write(payload_store, wrong_payload, spec=TRINITY_OWNER_SPEC)
    with pytest.raises(TrinityLoadError, match="Unsupported schema_version"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(payload_store), wrong_payload_ref)


def test_trinity_owner_refuses_wrong_profile_even_when_markers_and_payload_validate(
    tmp_path: Path,
) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    wrong_profile = CanonSpec(forbid_floats=True)
    ref = _unowned_write(
        store,
        _bundle().model_dump(mode="json"),
        spec=wrong_profile,
    )

    # Generic byte decoding plus the public DTO parser still succeeds. The CAS
    # consumer must separately enforce the registered owner profile.
    generic_payload = get_json_artifact(ensure_ir_artifact_store(store), ref)
    assert load_trinity_bundle(generic_payload) == _bundle()

    with pytest.raises(TrinityLoadError, match="profile"):
        load_trinity_bundle_artifact(ensure_ir_artifact_store(FileSystemCAS(cas_root)), ref)
