"""Public verification reads and tenant-bound server report issuance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.dependencies import (
    RuntimeApiContext,
    enforce_run_tenant_access,
    get_runtime_api_context,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.public_decision_verification import (
    PublicDecisionVerificationError,
    PublicDecisionVerificationService,
)
from polisyos.runtime.http.services.public_decision_verification_contracts import (
    PublicDecisionVerificationResponse,
)
from polisyos.runtime.quality import (
    PublicExportRedactionError,
    assert_public_export_official_use_limits,
    build_public_export_bundle,
)

router = APIRouter(tags=["public-decisions"])
_ISSUE_AUTHZ = require_action_permission(
    RuntimePermission.PLATFORM_ADMIN,
    ResourceBindingSpec(
        source=ResourceBindingSource.OWNED_EXISTING_PATH,
        resource_kind="runtime.run.public_verification_record",
        path_parameter="run_id",
        allow_empty_body=True,
    ),
)


class PublicDecisionVerificationIssued(BaseModel):
    """Opaque locator returned only after durable issuance and verifier readback."""

    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: str
    public_path: str
    publication_class: Literal["verification_report_only"] = "verification_report_only"
    promoted_record: Literal[None] = None


def _service(request: Request) -> PublicDecisionVerificationService:
    return request.app.state.runtime_container.public_decision_verification_service


@router.get(
    "/api/v1/public-decisions/verification",
    response_model=PublicDecisionVerificationResponse,
    operation_id="verify_public_decision_record",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": PublicDecisionVerificationResponse(
                        record_id="pvr_" + "a" * 32,
                        report_authentication="not_established",
                        reason_codes=(
                            "record_not_issued",
                            "promoted_public_record_not_established",
                        ),
                    ).model_dump(mode="json")
                }
            }
        }
    },
)
def verify_public_decision_record(
    request: Request,
    response: Response,
    record_id: Annotated[str, Query(min_length=1, max_length=16384)],
) -> PublicDecisionVerificationResponse:
    """Verify an issued locator without admitting any browser-provided document."""
    response.headers["Cache-Control"] = "no-store"
    return _service(request).verify(record_id)


@router.post(
    "/api/v1/runs/{run_id}/public-verification-record",
    response_model=PublicDecisionVerificationIssued,
    status_code=201,
    operation_id="issue_public_decision_record",
    responses={
        201: {
            "content": {
                "application/json": {
                    "example": PublicDecisionVerificationIssued(
                        record_id="pvr_" + "a" * 32,
                        public_path="/public/decisions/pvr_" + "a" * 32,
                    ).model_dump(mode="json")
                }
            }
        }
    },
    dependencies=[Depends(_ISSUE_AUTHZ)],
)
def issue_public_decision_record(
    run_id: str,
    request: Request,
    ctx: Annotated[RuntimeApiContext, Depends(get_runtime_api_context)],
) -> PublicDecisionVerificationIssued:
    """Redact the persisted run packet, then issue a report about those exact bytes.

    The caller selects an owned run, never supplies a document, key or authority
    verdict. The existing public-export producer owns disclosure and projection
    limits; its refusal is propagated before any record or public link is issued.
    """
    if request.headers.get("content-length", "0") != "0":
        raise HTTPException(status_code=422, detail="verification_issuance_body_not_allowed")
    try:
        run = ctx.run_index.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="run_not_found") from exc
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    if run.decision_packet_ref is None:
        raise HTTPException(status_code=409, detail="decision_packet_not_established")
    try:
        packet = json.loads(ctx.store.get_bytes(run.decision_packet_ref.artifact_id))
        if not isinstance(packet, dict):
            raise ValueError("decision packet must be an object")
        issued_at = datetime.now(UTC)
        document = build_public_export_bundle(
            run_id=run_id,
            artifacts={"decision_packet": packet},
            generated_at=issued_at,
        )
        assert_public_export_official_use_limits(document)
    except PublicExportRedactionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail="public_document_source_unavailable") from exc
    try:
        record_id = _service(request).issue(
            decision_id=run_id, public_document=document, issued_at=issued_at
        )
    except PublicDecisionVerificationError as exc:
        raise HTTPException(status_code=503, detail=exc.code) from exc
    return PublicDecisionVerificationIssued(
        record_id=record_id, public_path=f"/public/decisions/{record_id}"
    )
