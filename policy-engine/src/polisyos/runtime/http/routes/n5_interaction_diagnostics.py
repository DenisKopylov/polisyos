"""Authenticated, run-bound read projection for persisted N5 interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from polisyos.core.contracts.runtime import N5InteractionDiagnosticsResponse
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.container import resolve_control_service
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    build_meta,
    enforce_run_tenant_access,
    get_runtime_api_context,
    record_data_access_audit,
    require_access_scope,
    set_authz_resource,
)
from polisyos.runtime.http.errors import (
    forbidden,
    not_found,
    service_unavailable,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.adapters.core_run import load_terminal_core_run_source
from polisyos.runtime.http.services.control.generation_cycle import (
    load_compiled_recursive_generation_cycle_run,
    project_compiled_n5_interaction_diagnostics,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, Depends, Request
else:
    try:  # pragma: no cover - optional runtime dependency
        from fastapi import APIRouter, Depends, Request
    except ModuleNotFoundError:  # pragma: no cover
        APIRouter = cast("Any", None)
        Depends = cast("Any", None)
        Request = cast("Any", object)


def _build_router() -> APIRouter:
    if APIRouter is None:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("runtime HTTP routes require FastAPI to be installed")
    return APIRouter(prefix="/api/v1/runs", tags=["runtime-runs"])


router = _build_router()
_GET_N5_INTERACTION_DIAGNOSTICS_AUTHZ = require_action_permission(
    RuntimePermission.RUNS_VIEW,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.n5_interaction_diagnostics",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)


if router is not None:

    @router.get(
        "/{run_id}/n5-interaction-diagnostics",
        response_model=N5InteractionDiagnosticsResponse,
        dependencies=[Depends(_GET_N5_INTERACTION_DIAGNOSTICS_AUTHZ)],
        operation_id="get_run_n5_interaction_diagnostics",
    )
    def get_run_n5_interaction_diagnostics(
        run_id: str,
        request: Request,
        ctx: RuntimeApiContext = Depends(get_runtime_api_context),  # noqa: B008
    ) -> N5InteractionDiagnosticsResponse:
        """Expose verified K_sim coverage after run, tenant, and cell preflight."""

        try:
            run = ctx.run_index.get_run(run_id)
        except KeyError as exc:
            raise not_found("Run was not found", code="run_not_found") from exc
        enforce_run_tenant_access(request, ctx=ctx, run=run)
        scope = require_access_scope(request)
        routed_cell_id = getattr(request.state, "cell_id", None)
        if (
            not isinstance(scope.cell_id, str)
            or not scope.cell_id
            or not isinstance(routed_cell_id, str)
            or not routed_cell_id
        ):
            raise service_unavailable(
                "The authenticated run cell is not established",
                code="n5_diagnostics_cell_scope_not_established",
            )
        if (
            scope.cell_id != routed_cell_id
            or run.details.cell_id != routed_cell_id
        ):
            raise forbidden(
                "Run belongs to a different cell",
                code="run_cell_mismatch",
            )
        if run.details.tenant_id != scope.tenant_id:
            raise forbidden(
                "Run belongs to a different tenant",
                code="run_tenant_mismatch",
            )
        set_authz_resource(
            request,
            tenant_id=scope.tenant_id,
            kind="runtime.run.n5_interaction_diagnostics",
            artifact_id=run_id,
        )

        try:
            terminal = load_terminal_core_run_source(
                store=ctx.store,
                core_runs_root=ctx.core_runs_root,
                run_id=run_id,
            )
        except Exception as exc:
            raise service_unavailable(
                "The terminal Core run source cannot be established",
                code="n5_diagnostics_terminal_source_not_established",
            ) from exc
        if (
            terminal.run_id != run_id
            or terminal.tenant_id != scope.tenant_id
            or terminal.cell_id != routed_cell_id
            or run.details.manifest_ref is None
            or terminal.manifest_ref.model_dump(mode="json")
            != run.details.manifest_ref.model_dump(mode="json")
        ):
            raise service_unavailable(
                "The terminal Core source does not match the indexed run",
                code="n5_diagnostics_terminal_run_binding_mismatch",
            )

        manifest = terminal.manifest
        compiled_refs = [
            ref
            for ref in manifest.outputs
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        ]
        if (
            manifest.status not in {"completed", "ok"}
            or len(compiled_refs) != 1
            or manifest.control_job_id is None
            or (
                run.details.control_job_id is not None
                and manifest.control_job_id != run.details.control_job_id
            )
        ):
            raise service_unavailable(
                "The terminal manifest does not identify one compiled generation job",
                code="n5_diagnostics_compiled_source_not_established",
            )
        compiled_ref = compiled_refs[0]
        if (
            compiled_ref.media_type != "application/json"
            or str(compiled_ref.artifact_id) == ""
        ):
            raise service_unavailable(
                "The terminal manifest compiled output contract is invalid",
                code="n5_diagnostics_compiled_ref_contract_mismatch",
            )
        try:
            compiled_manifest = ctx.store.get_manifest(compiled_ref)
            compiled_schema = compiled_manifest.artifact_schema
            compiled_owner = compiled_manifest.tenant_context
        except Exception as exc:
            raise service_unavailable(
                "The compiled generation manifest is unavailable",
                code="n5_diagnostics_compiled_manifest_unavailable",
            ) from exc
        if (
            compiled_manifest.kind != compiled_ref.kind
            or compiled_manifest.media_type != compiled_ref.media_type
            or compiled_schema is None
            or compiled_schema.name
            != "polisyos.runtime.CompiledRecursiveGenerationCycleRun"
            or compiled_schema.version != "1.0"
            or compiled_owner is None
            or compiled_owner.tenant_id != scope.tenant_id
            or compiled_owner.cell_id != routed_cell_id
        ):
            raise service_unavailable(
                "The compiled generation manifest contract is invalid",
                code="n5_diagnostics_compiled_manifest_contract_mismatch",
            )

        control_service = resolve_control_service(request)
        if control_service is None:
            raise service_unavailable(
                "The control job reader is not installed",
                code="n5_diagnostics_job_reader_missing",
            )
        try:
            record = control_service.get_latest_job_for_run(run_id)
        except Exception as exc:
            raise service_unavailable(
                "The run control job could not be resolved",
                code="n5_diagnostics_job_read_failed",
            ) from exc
        if (
            record is None
            or record.kind != "natural_language_run"
            or record.state != "completed"
            or record.run_id != run_id
            or record.job_id != manifest.control_job_id
            or record.progress.get("compiled_recursive_generation_cycle_ref")
            != str(compiled_ref.artifact_id)
        ):
            raise service_unavailable(
                "The durable job does not match the terminal compiled source",
                code="n5_diagnostics_job_source_binding_mismatch",
            )
        try:
            compiled = load_compiled_recursive_generation_cycle_run(
                ctx.store,
                compiled_ref,
                tenant_id=scope.tenant_id,
                cell_id=routed_cell_id,
            )
            diagnostics, status, limitations = (
                project_compiled_n5_interaction_diagnostics(
                    compiled,
                    store=ctx.store,
                    tenant_id=scope.tenant_id,
                    cell_id=routed_cell_id,
                )
            )
        except Exception as exc:
            raise service_unavailable(
                "The compiled N5 diagnostic evidence cannot be established",
                code="n5_diagnostics_projection_not_established",
            ) from exc

        record_data_access_audit(
            request,
            resource_id=run_id,
            resource_kind="runtime.run.n5_interaction_diagnostics",
            tenant_id=scope.tenant_id,
            metadata={
                "job_id": record.job_id,
                "diagnostic_count": len(diagnostics),
                "interaction_evidence_status": status,
            },
        )
        return N5InteractionDiagnosticsResponse(
            meta=build_meta(request, source_kinds=[run.source_kind]),
            run_id=run_id,
            job_id=record.job_id,
            compiled_run_ref=str(compiled_ref.artifact_id),
            interaction_evidence_status=status,
            diagnostics=diagnostics,
            limitations=limitations,
        )
