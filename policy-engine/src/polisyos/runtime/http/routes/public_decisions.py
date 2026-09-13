"""Public verification and tenant-bound report or governed-record issuance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts  # noqa: TC001 - Pydantic resolves the public DTO at runtime.
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
    PublicDecisionJsonValue,
    PublicDecisionVerificationResponse,
)
from polisyos.runtime.quality import (
    PublicExportRedactionError,
    assert_public_export_official_use_limits,
    build_public_export_bundle,
)
from polisyos.scientist.governance.continuous import (
    GovernedPublicRecordError,
    GovernedPublicRecordProjection,
    GovernedPublicRecordVerificationResponse,
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


class GovernedPublicRecordIssued(BaseModel):
    """Public locator for an independently admitted, retained owner snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: str
    public_path: str
    publication_class: Literal["governed_public_record"] = "governed_public_record"
    promoted_record: GovernedPublicRecordProjection


class GovernedPublicRecordPrepared(BaseModel):
    """Private review material for a future external institutional signature."""

    model_config = ConfigDict(extra="forbid", strict=True)

    publication_class: Literal["governed_public_record_candidate"] = (
        "governed_public_record_candidate"
    )
    candidate_ref: artifacts.ArtifactRef
    public_document: dict[str, PublicDecisionJsonValue]
    public_document_digest: str


def _service(request: Request) -> PublicDecisionVerificationService:
    return request.app.state.runtime_container.public_decision_verification_service


@router.get(
    "/api/v1/public-decisions/verification",
    response_model=PublicDecisionVerificationResponse | GovernedPublicRecordVerificationResponse,
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
) -> PublicDecisionVerificationResponse | GovernedPublicRecordVerificationResponse:
    """Verify an issued locator without admitting any browser-provided document."""
    response.headers["Cache-Control"] = "no-store"
    return _service(request).verify(record_id)


@router.post(
    "/api/v1/runs/{run_id}/public-verification-record",
    response_model=(
        PublicDecisionVerificationIssued | GovernedPublicRecordIssued | GovernedPublicRecordPrepared
    ),
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
    response: Response,
    ctx: Annotated[RuntimeApiContext, Depends(get_runtime_api_context)],
    publication_class: Literal[
        "verification_report_only", "governed_public_record", "governed_public_record_candidate"
    ] = "verification_report_only",
) -> PublicDecisionVerificationIssued | GovernedPublicRecordIssued | GovernedPublicRecordPrepared:
    """Resolve an owned run and invoke its explicitly selected publication owner.

    The caller selects an owned run, never supplies a document, key or authority
    verdict. The selected report or governed-record producer owns disclosure and
    admission limits; its refusal precedes every public link.
    """
    response.headers["Cache-Control"] = "no-store"
    if request.headers.get("content-length", "0") != "0":
        raise HTTPException(status_code=422, detail="verification_issuance_body_not_allowed")
    try:
        run = ctx.run_index.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="run_not_found") from exc
    enforce_run_tenant_access(request, ctx=ctx, run=run)
    if run.decision_packet_ref is None:
        raise HTTPException(status_code=409, detail="decision_packet_not_established")
    if publication_class != "verification_report_only":
        owner = _service(request).governed_owner
        if owner is None:
            raise HTTPException(status_code=503, detail="governed_public_record_owner_unconfigured")
        try:
            issued_at = datetime.now(UTC)
            if publication_class == "governed_public_record_candidate":
                draft = owner.prepare(
                    decision_id=run_id,
                    decision_packet_ref=run.decision_packet_ref,
                    issued_at=issued_at,
                )
                return GovernedPublicRecordPrepared(
                    candidate_ref=draft.candidate_ref,
                    public_document=draft.public_document,
                    public_document_digest=draft.public_document_digest,
                )
            record_id = owner.issue(
                decision_id=run_id,
                decision_packet_ref=run.decision_packet_ref,
                issued_at=issued_at,
            )
            readback = owner.verify(record_id)
            if readback.promoted_record is None:
                raise HTTPException(
                    status_code=503, detail="governed_public_record_readback_failed"
                )
            return GovernedPublicRecordIssued(
                record_id=record_id,
                public_path=f"/public/decisions/{record_id}",
                promoted_record=readback.promoted_record,
            )
        except GovernedPublicRecordError as exc:
            raise HTTPException(status_code=409, detail=exc.code) from exc
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
