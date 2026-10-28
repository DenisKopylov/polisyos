"""Bind candidate source reads to Runtime's expected owner and Core's effective owner.

This is an in-process read precondition, not a persisted grant or purpose-complete
source-authority receipt. Core still checks current blob and exact-view claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.runtime.http.execution_policy import RuntimePrincipal

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
    )


@dataclass(frozen=True, slots=True)
class _ObservationalSourceReadScope:
    """Capture an expected byte-read owner without claiming external authority."""

    tenant_id: str | None
    cell_id: str | None
    tenant_source_supported: bool

    @property
    def writer_tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Return the actual admitted writer, independently of source provenance."""
        if self.tenant_id is None:
            return None
        return ArtifactTenantContextInfo(tenant_id=self.tenant_id, cell_id=self.cell_id)


def _current_source_read_scope() -> _ObservationalSourceReadScope:
    """Select verified request scope, retaining limited legacy unscoped reads."""
    access = get_current_access_scope_or_none()
    if type(access) is AccessScope and (access.user_sub or access.spiffe_id) and access.tenant_id:
        return _ObservationalSourceReadScope(access.tenant_id, access.cell_id, True)
    return _ObservationalSourceReadScope(
        get_current_tenant_id_or_none(), get_current_cell_id(), False
    )


def _request_source_read_scope(
    principal: RuntimePrincipal | None,
    execution_scope: ControlJobExecutionScope,
) -> _ObservationalSourceReadScope:
    """Reconcile the typed route principal with the effective job admission policy."""
    if type(principal) is RuntimePrincipal and principal.authenticated:
        if (
            execution_scope.status != "established"
            or not execution_scope.actor_authenticated
            or not principal.tenant_id
            or execution_scope.tenant_id != principal.tenant_id
            or execution_scope.cell_id != principal.cell_id
            or execution_scope.actor_subject != principal.subject
        ):
            raise ValueError("observational_source_request_scope_not_established")
        active = get_current_access_scope_or_none()
        if active is not None and (
            type(active) is not AccessScope
            or active.tenant_id != principal.tenant_id
            or active.cell_id != principal.cell_id
            or (active.user_sub or active.spiffe_id) != principal.subject
        ):
            raise ValueError("observational_source_request_scope_mismatch")
        return _ObservationalSourceReadScope(principal.tenant_id, principal.cell_id, True)
    if execution_scope.status == "established":
        raise ValueError("observational_source_request_principal_not_established")
    # Legacy in-process callers retain their existing public/unscoped candidate
    # path. Ambient tenant context never authorizes tenant-bound source metadata.
    scope = _current_source_read_scope()
    return _ObservationalSourceReadScope(scope.tenant_id, scope.cell_id, False)


def _job_source_read_scope(
    admission: ControlJobExecutionAdmission,
) -> _ObservationalSourceReadScope:
    """Use only the store-reconciled job admission, never payload or ambient scope."""
    scope = admission.scope
    if scope.status != "established":
        return _ObservationalSourceReadScope(None, None, False)
    if (
        not scope.actor_authenticated
        or not scope.tenant_id
        or not scope.cell_id
        or scope.actor_subject != admission.job.submitted_by
    ):
        raise ValueError("observational_source_job_scope_not_established")
    return _ObservationalSourceReadScope(scope.tenant_id, scope.cell_id, True)


def _require_source_read_owner(store: object, scope: _ObservationalSourceReadScope) -> None:
    """Compare the concrete Core resolver's owner before any protected artifact read.

    Known adapters are inspected only. Reads retain their original configured
    handle, including dependency guards. Unsupported owner carriers fail closed;
    a caller callback or owner-shaped mapping cannot establish the predicate.
    """
    from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
    from polisyos.runtime.http.resilience import GuardedDependencyProxy

    if type(scope) is not _ObservationalSourceReadScope:
        raise ValueError("observational_source_expected_scope_invalid")
    active = _current_source_read_scope()
    if active.tenant_id is not None and (active.tenant_id, active.cell_id) != (
        scope.tenant_id,
        scope.cell_id,
    ):
        raise ValueError("observational_source_active_scope_mismatch")
    owner = store
    seen: set[int] = set()
    while type(owner) in {CoreToIRArtifactStoreAdapter, GuardedDependencyProxy}:
        if id(owner) in seen:
            raise ValueError("observational_source_owner_adapter_cycle")
        seen.add(id(owner))
        # Inspect the known guard only; all reads retain the guarded handle.
        owner = (
            cast("CoreToIRArtifactStoreAdapter", owner).store
            if type(owner) is CoreToIRArtifactStoreAdapter
            else cast("GuardedDependencyProxy", owner)._target
        )
    if type(owner) is not FileSystemCAS:
        raise ValueError("observational_source_owner_resolution_not_established")
    owner = cast("FileSystemCAS", owner)
    effective_owner = FileSystemCAS._resolve_owner(owner, required=False)
    if effective_owner != (scope.tenant_id, scope.cell_id):
        raise ValueError("observational_source_effective_owner_scope_mismatch")
    if not owner._ownership_enforced:
        raise ValueError("observational_source_owner_enforcement_not_established")


def _require_supported_candidate_source(
    store: object,
    scope: _ObservationalSourceReadScope,
    governance: ArtifactGovernanceInfo,
    tenant_context: ArtifactTenantContextInfo | None,
) -> None:
    """Re-enter effective owner scope and the independently supported source policy."""
    _require_source_read_owner(store, scope)
    # Tenant metadata is provenance, never an access grant. Core may genuinely
    # grant this exact view to another current owner; do not override that law
    # with creator-metadata equality.
    if governance.classification != "public" or (
        tenant_context is not None and not scope.tenant_source_supported
    ):
        raise ValueError("observational_source_current_access_not_established")


def _reader_source_read_scope(tenant_id: str, cell_id: str | None) -> _ObservationalSourceReadScope:
    """Match an already-authorized reader port to its current active read owner."""
    current = _current_source_read_scope()
    if not tenant_id or (current.tenant_id, current.cell_id) != (tenant_id, cell_id):
        raise ValueError("observational_source_reader_scope_mismatch")
    return _ObservationalSourceReadScope(tenant_id, cell_id, True)


def _require_derived_tenant_context(
    actual: ArtifactTenantContextInfo | None,
    scope: _ObservationalSourceReadScope,
    source_origin: ArtifactTenantContextInfo | None,
) -> None:
    """Validate producer custody, retaining limited old unscoped header reads.

    Old unscoped producers omitted this header. Their source-origin field is
    still unbound and their existing authority limitations remain unchanged.
    Neither that historical omission nor source-origin metadata grants access;
    the current enforcing Core owner is checked independently before the read.
    """
    if actual == scope.writer_tenant_context:
        return
    if actual is None and source_origin is None:
        return
    raise ValueError("observational_derived_artifact_writer_scope_mismatch")
