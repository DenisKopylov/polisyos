from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from string import ascii_lowercase, digits
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from starlette.requests import Request

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.run.context import RunContext
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.dependencies import (
    enforce_artifact_tenant_access,
    enforce_run_tenant_access,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services.run_index import RunIndexService

_TENANT_IDS = st.text(alphabet=ascii_lowercase + digits, min_size=1, max_size=24)
_CELL_ID = "cell-a"


def _request_for_tenant(tenant_id: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/property-access",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace()),
            "state": {
                "access_scope": AccessScope(
                    tenant_id=tenant_id,
                    cell_id="cell-a",
                    principal_type="user",
                    user_sub="property-user",
                    roles=frozenset({PolicyOSRole.VIEWER}),
                    max_pii_tier=PIIAccessLevel.LOW,
                    mfa_verified=True,
                )
            },
        }
    )


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
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
    registry_ref: ArtifactRef,
    root_ref: ArtifactRef,
    tenant_id: str,
    run_index: int,
) -> None:
    run_id = f"R_property_artifact_owner_{run_index}"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=_CELL_ID):
        run = RunContext.start(
            store,
            registry_ref,
            producer=ProducerInfo(component="tests.property_access", version="1.0"),
            run_dir=run_root / run_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=_CELL_ID,
        )
        run.add_output(root_ref)
        manifest_ref = run.finalize(status="completed")
        store.record_artifact_owner(
            manifest_ref.artifact_id,
            tenant_id=tenant_id,
            cell_id=_CELL_ID,
            writer="test_access_invariants_properties",
        )


@contextmanager
def _artifact_tenant_index(
    tenant_ids: tuple[str, ...],
) -> Iterator[tuple[ArtifactID, RunIndexService]]:
    """Build real CAS/run-index ownership for one property example."""
    with TemporaryDirectory(prefix="polisyos-property-artifact-access-") as directory:
        root = Path(directory)
        cas_root = root / "cas"
        run_root = root / "runs"
        run_root.mkdir()
        shared_store = FileSystemCAS(cas_root)
        artifact_payload = {"artifact": "property-access"}

        if tenant_ids:
            artifact_ref: ArtifactRef | None = None
            for run_index, tenant_id in enumerate(tenant_ids):
                tenant_store = shared_store.for_tenant(tenant_id, _CELL_ID)
                with tenant_scope(None, tenant_id=tenant_id, cell_id=_CELL_ID):
                    registry_ref = _put_json(
                        tenant_store,
                        {"registry": "property-access"},
                        kind="core.registry_bundle",
                    )
                    owner_ref = _put_json(
                        tenant_store,
                        artifact_payload,
                        kind="test.property_access_artifact",
                    )
                    _create_owned_run(
                        tenant_store,
                        run_root=run_root,
                        registry_ref=registry_ref,
                        root_ref=owner_ref,
                        tenant_id=tenant_id,
                        run_index=run_index,
                    )
                if artifact_ref is None:
                    artifact_ref = owner_ref
                else:
                    assert owner_ref.artifact_id == artifact_ref.artifact_id
            assert artifact_ref is not None
        else:
            artifact_ref = _put_json(
                shared_store,
                artifact_payload,
                kind="test.property_access_artifact",
            )

        run_index = RunIndexService(
            store=shared_store,
            core_runs_root=run_root,
        )
        run_index.refresh(force=True)
        yield artifact_ref.artifact_id, run_index


@pytest.fixture(scope="module", autouse=True)
def _runtime_telemetry_dependencies() -> None:
    """Load telemetry dependencies before Hypothesis times individual examples."""
    from polisyos.runtime.http.container import (
        resolve_runtime_access_audit,
        resolve_runtime_metrics,
    )

    request = _request_for_tenant("setup")
    assert resolve_runtime_access_audit(request) is None
    assert resolve_runtime_metrics(request) is None


@dataclass(frozen=True)
class _RunDetails:
    tenant_id: str | None


@dataclass(frozen=True)
class _RunRecord:
    run_id: str
    details: _RunDetails


@pytest.mark.property
@given(
    scope_tenant=_TENANT_IDS,
    artifact_tenant=st.one_of(_TENANT_IDS, st.none()),
    allow_unscoped=st.booleans(),
)
def test_enforce_artifact_tenant_access_respects_tenant_invariants(
    scope_tenant: str,
    artifact_tenant: str | None,
    allow_unscoped: bool,
) -> None:
    request = _request_for_tenant(scope_tenant)
    tenant_ids = (artifact_tenant,) if artifact_tenant is not None else ()
    with _artifact_tenant_index(tenant_ids) as (artifact_id, run_index):
        ctx = SimpleNamespace(
            allow_unscoped_artifacts=allow_unscoped,
            run_index=run_index,
        )

        if artifact_tenant is None and allow_unscoped:
            assert enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=artifact_id) is None
            return

        if artifact_tenant == scope_tenant:
            assert (
                enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=artifact_id)
                == artifact_tenant
            )
            return

        with pytest.raises(RuntimeHTTPError) as exc_info:
            enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=artifact_id)

        assert exc_info.value.status_code == 403


@pytest.mark.property
def test_enforce_artifact_tenant_access_allows_one_of_multiple_indexed_tenants() -> None:
    tenant_a = "tenant-property-a"
    tenant_b = "tenant-property-b"
    with _artifact_tenant_index((tenant_a, tenant_b)) as (artifact_id, run_index):
        ctx = SimpleNamespace(allow_unscoped_artifacts=False, run_index=run_index)
        assert run_index.get_artifact_tenants(str(artifact_id)) == frozenset({tenant_a, tenant_b})

        for tenant_id in (tenant_a, tenant_b):
            assert (
                enforce_artifact_tenant_access(
                    _request_for_tenant(tenant_id),
                    ctx=ctx,
                    artifact_id=artifact_id,
                )
                == tenant_id
            )

        with pytest.raises(RuntimeHTTPError) as exc_info:
            enforce_artifact_tenant_access(
                _request_for_tenant("tenant-property-foreign"),
                ctx=ctx,
                artifact_id=artifact_id,
            )
        assert exc_info.value.status_code == 403


@pytest.mark.property
@given(scope_tenant=_TENANT_IDS, run_tenant=st.one_of(_TENANT_IDS, st.none()))
def test_enforce_run_tenant_access_is_fail_closed_when_scope_or_tenant_mismatch(
    scope_tenant: str,
    run_tenant: str | None,
) -> None:
    request = _request_for_tenant(scope_tenant)
    run = _RunRecord(run_id="R_property", details=_RunDetails(tenant_id=run_tenant))

    if run_tenant == scope_tenant:
        enforce_run_tenant_access(request, ctx=SimpleNamespace(), run=run)
        return

    with pytest.raises(RuntimeHTTPError) as exc_info:
        enforce_run_tenant_access(request, ctx=SimpleNamespace(), run=run)

    assert exc_info.value.status_code == 403
