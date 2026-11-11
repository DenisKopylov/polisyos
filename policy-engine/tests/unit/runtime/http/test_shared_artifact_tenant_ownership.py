from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http import dependencies, resource_binding
from polisyos.runtime.http.dependencies import RuntimeAccessScope
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services.run_index import RunIndexService

TENANT_A = "tenant-shared-a"
TENANT_B = "tenant-shared-b"
TENANT_C = "tenant-shared-c"
CELL_A = "cell-shared-a"
CELL_B = "cell-shared-b"


def _request_for(tenant_id: str, cell_id: str) -> Request:
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/artifacts",
            "raw_path": b"/artifacts",
            "query_string": b"",
            "headers": [],
            "client": ("test", 1234),
            "server": ("test", 80),
        }
    )
    request.state.access_scope = RuntimeAccessScope.for_service(
        tenant_id=tenant_id,
        cell_id=cell_id,
        spiffe_id=f"spiffe://tests/{tenant_id}",
    )
    return request


def _put_json(store: FileSystemCAS, payload: object, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
        ),
        return_selected_profile=True,
    )


def _create_owned_run(
    store: FileSystemCAS,
    *,
    run_root: Path,
    registry_ref,
    root_ref,
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> None:
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        run = RunContext.start(
            store,
            registry_ref,
            producer=ProducerInfo(component="tests.shared_artifact", version="1.0"),
            run_dir=run_root / run_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        run.add_output(root_ref)
        manifest_ref = run.finalize(status="completed")
        store.record_artifact_owner(
            manifest_ref.artifact_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            writer="test_shared_artifact_tenant_ownership",
        )


def test_shared_cas_artifact_is_accessible_to_each_owner_and_denied_to_others(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cas_root = tmp_path / "cas"
    run_root = tmp_path / "runs"
    run_root.mkdir()
    store_a = FileSystemCAS(cas_root, tenant_id=TENANT_A, cell_id=CELL_A)
    store_b = FileSystemCAS(cas_root, tenant_id=TENANT_B, cell_id=CELL_B)
    store_c = FileSystemCAS(cas_root, tenant_id=TENANT_C, cell_id="cell-shared-c")

    with tenant_scope(None, tenant_id=TENANT_A, cell_id=CELL_A):
        registry_a = _put_json(store_a, {"registry": "shared"}, kind="core.registry_bundle")
        root_a = _put_json(store_a, {"shared": "same-bytes"}, kind="test.shared_root")
    with tenant_scope(None, tenant_id=TENANT_B, cell_id=CELL_B):
        registry_b = _put_json(store_b, {"registry": "shared"}, kind="core.registry_bundle")
        root_b = _put_json(store_b, {"shared": "same-bytes"}, kind="test.shared_root")
    assert root_a.artifact_id == root_b.artifact_id

    _create_owned_run(
        store_a,
        run_root=run_root,
        registry_ref=registry_a,
        root_ref=root_a,
        tenant_id=TENANT_A,
        cell_id=CELL_A,
        run_id="R_shared_a",
    )
    _create_owned_run(
        store_b,
        run_root=run_root,
        registry_ref=registry_b,
        root_ref=root_b,
        tenant_id=TENANT_B,
        cell_id=CELL_B,
        run_id="R_shared_b",
    )
    # The catalog reader is the runtime's unscoped read view: it must inspect
    # manifests from each tenant to assemble membership. Request-side access
    # still uses each tenant/cell-bound store below.
    index_store = FileSystemCAS(cas_root)
    run_index = RunIndexService(store=index_store, core_runs_root=run_root, max_cached_runs=1)
    shared_id = str(root_a.artifact_id)
    assert run_index.get_artifact_tenants(shared_id) == frozenset({TENANT_A, TENANT_B})
    assert run_index.get_artifact_tenant(shared_id) is None

    monkeypatch.setattr(dependencies, "_record_tenant_ownership_denial", lambda *_a, **_k: None)
    context = SimpleNamespace(run_index=run_index, allow_unscoped_artifacts=True)
    for tenant_id, cell_id, store in (
        (TENANT_A, CELL_A, store_a),
        (TENANT_B, CELL_B, store_b),
    ):
        request = _request_for(tenant_id, cell_id)
        assert (
            dependencies.enforce_artifact_tenant_access(
                request,
                ctx=context,
                artifact_id=root_a.artifact_id,
            )
            == tenant_id
        )
        scope = request.state.access_scope
        assert resource_binding._resolve_owned_artifact(
            SimpleNamespace(run_index=run_index, store=store),
            scope,
            shared_id,
        ) == (shared_id, tenant_id)

    third_party_scope = RuntimeAccessScope.for_service(
        tenant_id=TENANT_C,
        cell_id="cell-shared-c",
        spiffe_id=f"spiffe://tests/{TENANT_C}",
    )
    third_party_request = _request_for(TENANT_C, "cell-shared-c")
    with pytest.raises(RuntimeHTTPError) as rejected:
        dependencies.enforce_artifact_tenant_access(
            third_party_request,
            ctx=context,
            artifact_id=root_a.artifact_id,
        )
    assert rejected.value.status_code == 403
    assert rejected.value.code == "artifact_tenant_mismatch"

    with pytest.raises(RuntimeHTTPError) as binding_rejected:
        resource_binding._resolve_owned_artifact(
            SimpleNamespace(run_index=run_index, store=store_c),
            third_party_scope,
            shared_id,
        )
    assert binding_rejected.value.status_code == 403
    assert binding_rejected.value.code == "authorization_binding_artifact_tenant_mismatch"

    wrong_cell_store = FileSystemCAS(cas_root, tenant_id=TENANT_B, cell_id="cell-wrong")
    with pytest.raises(RuntimeHTTPError) as cell_rejected:
        resource_binding._resolve_owned_artifact(
            SimpleNamespace(run_index=run_index, store=wrong_cell_store),
            RuntimeAccessScope.for_service(
                tenant_id=TENANT_B,
                cell_id="cell-wrong",
                spiffe_id=f"spiffe://tests/{TENANT_B}/wrong-cell",
            ),
            shared_id,
        )
    assert cell_rejected.value.status_code == 403
