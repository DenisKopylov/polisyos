"""Governance pass for proof-carrying IC claims on typed mechanisms."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.canon.hashing import fingerprint
from polisyos.core.contracts.ic_verification import (
    ICVerificationReport,
    ICVerificationRequest,
)
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.governance.game_design import MechanismConstraintType
from polisyos.scientist.validation.verification.ic import (
    evaluate_incentive_compatibility,
    load_ic_certificate,
    load_ic_negative_certificate,
    load_ic_report,
    verify_incentive_compatibility,
)

_IC_PROPERTIES = (
    MechanismConstraintType.DOMINANT_STRATEGY_IC.value,
    MechanismConstraintType.BAYESIAN_IC.value,
    MechanismConstraintType.EX_POST_IR.value,
    MechanismConstraintType.EX_INTERIM_IR.value,
)
_PASS_ID = "incentive_compatibility"


class IncentiveCompatibilityPass(ValidatorPass):
    """Enforce machine-checkable DSIC/BIC claims when a policy declares them."""

    @property
    def pass_id(self) -> str:
        return _PASS_ID

    @property
    def estimated_cost_ms(self) -> int:
        return 40

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        policy = ctx.ir.policy_spec if ctx.ir is not None else None
        design = None if policy is None else policy.mechanism_design
        if design is None:
            return []

        claims = [
            property_name
            for property_name in _IC_PROPERTIES
            if any(
                constraint.constraint_type.value == property_name
                for constraint in design.constraints
            )
        ]
        if not claims:
            return []

        issues: list[ComplianceIssue] = []
        store = _resolve_store(ctx.state)
        artifacts_index = ctx.state.setdefault("artifacts_index", {})
        verification_state = ctx.state.setdefault("ic_verification", {})
        input_ref = _resolve_or_persist_trinity_ref(ctx, store, artifacts_index)

        for property_name in claims:
            report = _resolve_or_compute_report(
                ctx=ctx,
                store=store,
                property_name=property_name,
                artifacts_index=artifacts_index,
                input_ref=input_ref,
            )
            verification_state[property_name] = report.model_dump(mode="json")
            issues.extend(_issues_for_report(ctx, property_name, report))
        return issues


def _resolve_store(state: dict[str, Any]) -> FileSystemCAS | None:
    store = state.get("_store")
    if store is None or not hasattr(store, "get_bytes") or not hasattr(store, "put_json"):
        return None
    return store


def _artifact_key(property_name: str, suffix: str) -> str:
    return f"{property_name}_{suffix}"


def _resolve_or_persist_trinity_ref(
    ctx: PassContext,
    store: FileSystemCAS | None,
    artifacts_index: dict[str, Any],
) -> TrinityBundleRef | None:
    for _key, value in artifacts_index.items():
        if hasattr(value, "kind") and getattr(value, "kind", None) == "ir.trinity_bundle":
            try:
                return TrinityBundleRef.model_validate(value.model_dump(mode="json"))
            except (AttributeError, TypeError, ValidationError, ValueError):
                continue

    if ctx.ir is None or store is None:
        return None

    artifact = store.put_json(
        ctx.ir.model_dump(mode="json"),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle",
                version=str(ctx.ir.schema_version),
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = TrinityBundleRef.model_validate(artifact.model_dump(mode="json"))
    artifacts_index.setdefault("trinity_bundle_ref", ref)
    return ref


def _resolve_or_compute_report(
    *,
    ctx: PassContext,
    store: FileSystemCAS | None,
    property_name: str,
    artifacts_index: dict[str, Any],
    input_ref: TrinityBundleRef | None,
) -> ICVerificationReport:
    report_key = _artifact_key(property_name, "report_ref")
    existing = artifacts_index.get(report_key)
    if existing is not None and store is not None:
        try:
            return load_ic_report(store, existing)
        except (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError):
            existing = None

    request = ICVerificationRequest(
        property=property_name,
        mode="strict_proof",
        backend_hint="auto",
        input_ref=input_ref or _ephemeral_input_ref(ctx),
    )

    if store is not None and input_ref is not None:
        result = verify_incentive_compatibility(store, request)
        if result.report_ref is not None:
            artifacts_index[report_key] = result.report_ref
            report = load_ic_report(store, result.report_ref)
            if result.certificate_ref is not None:
                suffix = (
                    "certificate_ref"
                    if result.verdict == "positive"
                    else "negative_certificate_ref"
                )
                artifacts_index[_artifact_key(property_name, suffix)] = result.certificate_ref
                _index_mechanism_family_sidecars(
                    store=store,
                    property_name=property_name,
                    certificate_ref=result.certificate_ref,
                    positive=result.verdict == "positive",
                    artifacts_index=artifacts_index,
                )
            return report

    try:
        report, _ = evaluate_incentive_compatibility(
            ctx.ir.policy_spec,
            request,
            input_digest=str(request.input_ref.artifact_id),
        )
        return report
    except (TypeError, ValidationError, ValueError) as exc:
        return ICVerificationReport(
            property=property_name,
            mode="strict_proof",
            backend=request.backend_hint if request.backend_hint != "auto" else "auto",
            verdict="semantic_validation_failure",
            input_digest=str(request.input_ref.artifact_id),
            notes=(str(exc),),
        )


def _index_mechanism_family_sidecars(
    *,
    store: FileSystemCAS,
    property_name: str,
    certificate_ref: ArtifactRef,
    positive: bool,
    artifacts_index: dict[str, Any],
) -> None:
    try:
        certificate = (
            load_ic_certificate(store, certificate_ref)
            if positive
            else load_ic_negative_certificate(store, certificate_ref)
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError):
        return

    for witness_key in (
        "mechanism_family_spec_ref",
        "mechanism_ic_certificate_ref",
        "mechanism_welfare_loss_bound_ref",
    ):
        value = certificate.witness.get(witness_key)
        if value is None:
            continue
        try:
            artifacts_index[_artifact_key(property_name, witness_key)] = ArtifactRef.model_validate(
                value
            )
        except (TypeError, ValidationError, ValueError):
            artifacts_index[_artifact_key(property_name, witness_key)] = value

    for witness_key in (
        "mechanism_family_spec_refs",
        "mechanism_ic_certificate_refs",
        "mechanism_welfare_loss_bound_refs",
    ):
        value = certificate.witness.get(witness_key)
        if not isinstance(value, dict):
            continue
        singular_key = witness_key.removesuffix("s")
        for mechanism_id, ref_payload in value.items():
            artifact_key = _artifact_key(property_name, f"{mechanism_id}_{singular_key}")
            try:
                artifacts_index[artifact_key] = ArtifactRef.model_validate(ref_payload)
            except (TypeError, ValidationError, ValueError):
                artifacts_index[artifact_key] = ref_payload


def _ephemeral_input_ref(ctx: PassContext) -> ArtifactRef:
    if ctx.ir is None:
        raise ValueError("IC verification requires TrinityBundle input")
    return ArtifactRef(
        artifact_id=fingerprint(
            ctx.ir.model_dump(mode="json"),
            prefix=True,
            canon_spec=CanonSpec(forbid_floats=False),
        ),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _issues_for_report(
    ctx: PassContext,
    property_name: str,
    report: ICVerificationReport,
) -> list[ComplianceIssue]:
    if report.verdict == "positive":
        return []

    strict = ctx.profile.level is ProfileLevel.STRICT
    severity = IssueSeverity.BLOCKER if strict else IssueSeverity.WARNING

    if report.verdict == "negative":
        return [
            ComplianceIssue(
                pass_id=_PASS_ID,
                path=["policy_spec", "mechanism_design", "constraints"],
                message=(
                    f"Declared claim '{property_name}' is false on the provided typed "
                    "mechanism semantics."
                ),
                severity=severity,
                code="INCENTIVE_COMPATIBILITY_VIOLATED",
                suggestion=(
                    "Revise the claim or mechanism semantics, then rerun the exact "
                    "verification route for this fragment."
                ),
            )
        ]

    return [
        ComplianceIssue(
            pass_id=_PASS_ID,
            path=["policy_spec", "mechanism_design", "semantics"],
            message=(
                f"Declared claim '{property_name}' could not be certified in strict proof mode."
            ),
            severity=severity,
            code="INCENTIVE_COMPATIBILITY_UNCERTIFIED",
            suggestion=(
                "Provide complete exact semantics for a supported fragment or attach a "
                "constructive witness-producing backend route."
            ),
            input_value=f"{report.verdict}: {'; '.join(report.notes)}",
        )
    ]


__all__ = ["IncentiveCompatibilityPass"]
