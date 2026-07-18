"""Resolve immutable production-approval scorecards before policy evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.runtime.http.errors import bad_request, forbidden

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


_CONTEXT_KIND = "runtime.production_approval.scorecard.v1"
_CANON_SPEC = CanonSpec(forbid_floats=False)
_SCORECARD_ARTIFACT_KIND = "runtime.quality_scorecard"
_SCORECARD_SCHEMA_VERSION = "policyos.quality_scorecard.v1"


@dataclass(frozen=True, slots=True)
class ResolvedProductionApprovalScorecard:
    """Frozen scorecard snapshot bound into one authorization resource."""

    reference: str
    run_id: str
    payload: dict[str, Any]
    payload_sha256: str
    context_bytes: bytes


def resolve_production_approval_scorecard(
    *,
    body: Mapping[str, Any],
    control_service: object | None,
    run_id: str,
    store: ArtifactStore,
) -> ResolvedProductionApprovalScorecard:
    """Resolve one persisted scorecard and reject cross-run attribution."""
    explicit_ref = _string_or_none(body.get("quality_scorecard_ref"))
    if explicit_ref is not None:
        payload = _load_scorecard_artifact(store, explicit_ref)
        if payload is None:
            raise bad_request(
                "quality_scorecard_ref does not point to an available persisted scorecard",
                code="quality_scorecard_ref_unavailable",
            )
        return _freeze_scorecard(payload=payload, ref=explicit_ref, run_id=run_id)

    inline_value = body.get("quality_scorecard")
    inline_scorecard = dict(inline_value) if isinstance(inline_value, Mapping) else None
    inline_ref = _scorecard_ref_from_payload(inline_scorecard)
    if inline_ref is not None:
        payload = _load_scorecard_artifact(store, inline_ref)
        if payload is not None:
            return _freeze_scorecard(
                payload=payload,
                ref=inline_ref,
                run_id=run_id,
            )

    progress_scorecard = _latest_control_progress_scorecard(control_service, run_id)
    progress_ref = _scorecard_ref_from_payload(progress_scorecard)
    if progress_ref is not None:
        payload = _load_scorecard_artifact(store, progress_ref)
        if payload is None:
            raise bad_request(
                "control progress points to an unavailable persisted quality scorecard",
                code="quality_scorecard_ref_unavailable",
            )
        return _freeze_scorecard(
            payload=payload,
            ref=progress_ref,
            run_id=run_id,
        )

    if inline_scorecard is not None:
        raise bad_request(
            "quality_scorecard must reference a persisted scorecard artifact",
            code="quality_scorecard_not_persisted",
        )
    raise bad_request(
        "quality_scorecard_ref or persisted control progress is required",
        code="quality_scorecard_required",
    )


def production_approval_context_kind() -> str:
    """Return the stable resolved-context discriminator used by the binder."""
    return _CONTEXT_KIND


def _scorecard_ref_from_payload(scorecard: Mapping[str, Any] | None) -> str | None:
    if scorecard is None:
        return None
    evidence_refs = scorecard.get("evidence_refs")
    if not isinstance(evidence_refs, Mapping):
        evidence_refs = {}
    return _string_or_none(
        scorecard.get("quality_scorecard_ref")
        or scorecard.get("scorecard_ref")
        or evidence_refs.get("quality_scorecard")
    )


def _load_scorecard_artifact(
    store: ArtifactStore,
    ref: str,
) -> dict[str, Any] | None:
    try:
        artifact_id = ArtifactID.model_validate(ref)
        manifest = store.get_manifest(artifact_id)
        payload = from_canonical_bytes(store.get_bytes(artifact_id))
    except ArtifactOwnershipError as exc:
        raise forbidden(
            "The quality scorecard belongs to a different tenant",
            code="authorization_binding_scorecard_tenant_mismatch",
        ) from exc
    except Exception:
        return None
    if manifest.kind != _SCORECARD_ARTIFACT_KIND:
        raise forbidden(
            "The referenced artifact is not a runtime quality scorecard",
            code="authorization_binding_scorecard_kind_invalid",
        )
    if not isinstance(payload, Mapping):
        return None
    return dict(payload)


def _freeze_scorecard(
    *,
    payload: Mapping[str, Any],
    ref: str,
    run_id: str,
) -> ResolvedProductionApprovalScorecard:
    scorecard = dict(payload)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA_VERSION:
        raise forbidden(
            "The persisted quality scorecard schema is not admitted",
            code="authorization_binding_scorecard_schema_invalid",
        )
    payload_run_id = _string_or_none(scorecard.get("run_id"))
    if payload_run_id is None:
        raise forbidden(
            "The persisted quality scorecard has no durable run binding",
            code="authorization_binding_scorecard_run_unbound",
        )
    if payload_run_id != run_id:
        raise forbidden(
            "The persisted quality scorecard belongs to a different run",
            code="authorization_binding_scorecard_run_mismatch",
        )
    evidence_refs = scorecard.get("evidence_refs")
    normalized_refs = dict(evidence_refs) if isinstance(evidence_refs, Mapping) else {}
    normalized_refs["quality_scorecard"] = ref
    scorecard["evidence_refs"] = normalized_refs
    scorecard["quality_scorecard_ref"] = ref
    scorecard["authoritative_scorecard_ref"] = ref
    scorecard["scorecard_identity_ref"] = ref
    scorecard["scorecard_identity_verified"] = True
    scorecard["scorecard_ref_source"] = "runtime_cas"
    scorecard["run_id"] = run_id
    payload_bytes = to_canonical_bytes(scorecard, spec=_CANON_SPEC)
    payload_sha256 = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
    context_bytes = to_canonical_bytes(
        {
            "context_version": _CONTEXT_KIND,
            "run_id": run_id,
            "scorecard_ref": ref,
            "scorecard_sha256": payload_sha256,
            "scorecard": scorecard,
        },
        spec=_CANON_SPEC,
    )
    return ResolvedProductionApprovalScorecard(
        reference=ref,
        run_id=run_id,
        payload=scorecard,
        payload_sha256=payload_sha256,
        context_bytes=context_bytes,
    )


def _latest_control_progress_scorecard(
    control_service: object | None,
    run_id: str,
) -> dict[str, Any] | None:
    if control_service is None:
        return None
    get_latest = getattr(control_service, "get_latest_job_for_run", None)
    record = None
    if callable(get_latest):
        try:
            record = get_latest(run_id)
        except Exception:
            record = None
    if record is None:
        control_store = getattr(control_service, "_control_store", None)
        get_latest_from_store = getattr(control_store, "get_latest_job_by_run", None)
        if callable(get_latest_from_store):
            try:
                record = get_latest_from_store(run_id)
            except Exception:
                record = None
    progress = getattr(record, "progress", None)
    if not isinstance(progress, Mapping):
        return None
    scorecard = progress.get("quality_scorecard") or progress.get("quality")
    if isinstance(scorecard, Mapping):
        return dict(scorecard)
    if any(
        key in progress
        for key in ("quality_status", "quality_gates", "blocking_quality_failures")
    ):
        return dict(progress)
    return None


def _string_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


__all__ = [
    "ResolvedProductionApprovalScorecard",
    "production_approval_context_kind",
    "resolve_production_approval_scorecard",
]
