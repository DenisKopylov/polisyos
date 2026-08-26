"""Public export redaction and authority-boundary helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.core import PromptSanitizer, scan_secret_and_pii
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeInput,
    AuthoritySurfaceDecision,
    authority_surface_decision,
    deserialize_authority_envelope,
)
from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.case_lifecycle import (
    LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION,
    PUBLIC_REVISION_STATE_SCHEMA_VERSION,
    PolicyDesignLifecycleError,
    validate_lifecycle_reissue_report,
)
from polisyos.runtime.quality.contestability import (
    PolicyDesignContestabilityError,
    verified_recourse_pointer_for_publication,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleRun,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.open_world_risk import (
    OpenWorldRiskArtifactResolver,
    OpenWorldRiskGenerationProjectionResolver,
    OpenWorldRiskPromotionGate,
    OpenWorldRiskPublicLimitation,
    OpenWorldRiskResolutionNonReceipt,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
    verify_policy_design_case_projection_consumer_contract,
    verify_s9_projection_faithfulness_for_pdc_consumer_contract,
    verify_s10_forecast_projection_consumer_contract,
    verify_s11_predictive_projection_consumer_contract,
    verify_s12_resource_projection_consumer_contract,
    verify_s13_post_deploy_accountability_projection_consumer_contract,
    verify_s14_universality_projection_consumer_contract,
)
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionReceipt,
    validate_canonical_promotion_receipt,
)
from polisyos.runtime.quality.rule_evolution import (
    RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.runtime.quality.design_problem import DesignProblem

PUBLIC_EXPORT_SCHEMA_VERSION = "policyos.runtime.public_export_bundle.v1"
PUBLIC_EXPORT_REDACTION_POLICY_REF = "redaction-policy/public-export-v1"

_TENANT_PRIVATE_REF_PATTERNS = (
    re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE),
    re.compile(r"^cas://sha256/[0-9a-f]{64}$", re.IGNORECASE),
)

_SCALAR_WELFARE_KEYS = frozenset(
    {
        "aggregate_welfare",
        "bcr",
        "net_benefit",
        "npv",
        "scalar_aggregate",
        "scalar_welfare",
        "welfare_aggregate",
        "welfare_delta",
        "welfare_score",
    }
)
_PUBLIC_EXPORT_EVIDENCE_CLASSES = {
    "diagnostic_supporting",
    "public_exported",
    "redacted_derived",
}
_PUBLIC_EXPORT_AUTHORITY_ROLES = {
    "diagnostic_only",
    "not_authoritative",
    "packaging_only",
    "projection_only",
}
_AUTHORITY_ROLES = {
    "approval_input",
    "producer_authority",
    "readiness_input",
    "runtime_blocker",
    "scorecard_input",
}
_AUTHORITY_PROVENANCE_KINDS = {
    "runtime_blocker",
    "runtime_emitted",
    "runtime_fallback",
}
_OFFICIAL_USE_LIMITS = {
    "official_use": "public_audit_only",
    "may_be_used_for": [
        "public_audit",
        "operator_triage",
        "external_explanation",
    ],
    "may_not_be_used_for": [
        "scorecard_authority",
        "approval_authority",
        "runtime_closeout_authority",
        "provider_credential_validation",
        "tenant_identity_resolution",
    ],
    "authority_limitation": (
        "This bundle is a redacted projection. Use the referenced runtime "
        "authority graph for scorecard, readiness, approval, or closeout."
    ),
}


class PublicExportRedactionError(ValueError):
    """Typed public-export redaction or authority-boundary violation."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        authority_surface_decisions: Sequence[Mapping[str, object]] = (),
    ) -> None:
        self.code = code
        self.authority_surface_decisions = [dict(item) for item in authority_surface_decisions]
        super().__init__(f"{code}: {message or code}")


def project_promotion_open_world_limitation(
    *,
    run: GenerationCycleRun,
    design_problem: DesignProblem,
    receipt: CanonicalPromotionReceipt | Mapping[str, object],
    resolver: OpenWorldRiskArtifactResolver,
    repo_root: Path | None = None,
) -> OpenWorldRiskPublicLimitation | None:
    """Project OWR only from one current receipt bound to its exact N6 run."""

    run_issues = validate_generation_cycle_run(run)
    if run_issues:
        raise PublicExportRedactionError(
            str(run_issues[0].get("code") or "generation_cycle_run_invalid")
        )
    if run.design_problem_ref != gy_content_hash(design_problem.model_dump(mode="json")):
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    try:
        parsed = (
            receipt
            if type(receipt) is CanonicalPromotionReceipt
            else CanonicalPromotionReceipt.model_validate(receipt)
        )
    except ValueError as exc:
        raise PublicExportRedactionError("promotion_receipt_invalid", str(exc)) from exc
    if type(parsed) is not CanonicalPromotionReceipt:
        raise PublicExportRedactionError("legacy_open_world_gate_authority_not_admitted")
    payload = parsed.model_dump(mode="json")
    if sum(item == payload for item in run.promotion_port.receipts) != 1:
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    summaries = tuple(
        summary
        for summary in run.candidate_summaries
        if summary.candidate_id == parsed.candidate_id
    )
    if len(summaries) != 1:
        raise PublicExportRedactionError("promotion_candidate_owner_binding_invalid")
    summary = summaries[0]
    if (
        parsed.owner_projection.design_problem_binding.problem_content_hash
        != run.design_problem_ref
        or parsed.owner_projection.candidate_summary != summary
    ):
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    issues = validate_canonical_promotion_receipt(
        parsed,
        repo_root=repo_root,
        candidate_summary=summary,
        design_problem=design_problem,
        value_receipt=summary.value_receipt,
        open_world_resolver=resolver,
    )
    if issues:
        code = str(issues[0].get("code") or "promotion_receipt_invalid")
        raise PublicExportRedactionError(code)
    gate = parsed.owner_projection.open_world_gate
    if gate is None:
        raise PublicExportRedactionError("open_world_projection_not_established")
    if gate.status == "established":
        return None
    return OpenWorldRiskPublicLimitation(
        status=gate.status,
        code=gate.limitation_code,
        vector_artifact_ref=gate.vector_artifact_ref,
    )


def project_pre_n9_open_world_limitations(
    *,
    run: GenerationCycleRun,
    design_problem: DesignProblem,
    resolver: OpenWorldRiskGenerationProjectionResolver,
) -> tuple[OpenWorldRiskPublicLimitation, ...]:
    """Replay negative pre-N9 OWR evidence without fabricating a promotion receipt."""

    run_issues = validate_generation_cycle_run(run)
    if run_issues:
        raise PublicExportRedactionError(
            str(run_issues[0].get("code") or "generation_cycle_run_invalid")
        )
    if run.design_problem_ref != gy_content_hash(design_problem.model_dump(mode="json")):
        raise PublicExportRedactionError("open_world_vector_query_mismatch")
    port = run.promotion_port
    if (
        port.status != "not_promoted"
        or port.reason != "epoch_validity_refused:policy_admission_missing"
        or port.receipts
        or port.certified_candidate_ids
    ):
        raise PublicExportRedactionError("open_world_projection_not_established")
    observations = port.pre_n9_open_world_gates
    if not observations:
        raise PublicExportRedactionError("open_world_projection_not_established")
    if len(observations) != len(run.candidate_summaries) or tuple(
        row.ordinal for row in observations
    ) != tuple(range(len(run.candidate_summaries))):
        raise PublicExportRedactionError("open_world_vector_query_mismatch")
    limitations: list[OpenWorldRiskPublicLimitation] = []
    for observation in observations:
        try:
            gate = OpenWorldRiskPromotionGate.model_validate(observation.gate_payload)
        except ValueError as exc:
            raise PublicExportRedactionError(
                "open_world_projection_not_established",
                str(exc),
            ) from exc
        verified = resolver.resolve_verified_for_generation(
            gate=gate,
            expected_problem=design_problem,
            expected_summaries=run.candidate_summaries,
            expected_ordinal=observation.ordinal,
        )
        if isinstance(verified, OpenWorldRiskResolutionNonReceipt):
            raise PublicExportRedactionError(verified.code)
        vector = verified.vector
        if vector.status == "established":
            continue
        limitations.append(
            OpenWorldRiskPublicLimitation(
                status=vector.status,
                code=vector.limitation_code,
                vector_artifact_ref=verified.vector_artifact_ref,
            )
        )
    return tuple(limitations)


def build_public_export_bundle(
    *,
    run_id: str,
    artifacts: Mapping[str, object],
    authority_envelopes: Sequence[AuthorityEnvelopeInput] = (),
    policy_design_case: Mapping[str, object] | None = None,
    runtime_pdc_graph: Mapping[str, object] | None = None,
    projection_payload: Mapping[str, object] | None = None,
    title: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a redacted public projection that cannot satisfy authority gates."""

    tenant_private_refs = _tenant_private_refs_in_payload(artifacts)
    recourse_pointer = None
    if policy_design_case is not None:
        try:
            recourse_pointer = verified_recourse_pointer_for_publication(
                policy_design_case=policy_design_case,
                projection_payload=projection_payload or {},
            )
        except PolicyDesignContestabilityError as exc:
            raise PublicExportRedactionError(exc.code, exc.message) from exc
    _assert_no_unexplained_replay_drift(artifacts)
    _assert_public_export_candidate_firewall(artifacts)
    _assert_public_welfare_frontier_surface(artifacts)
    if projection_payload is not None:
        _assert_public_welfare_frontier_surface(projection_payload)
    (
        sanitized_artifacts,
        secret_pii_scan_reports,
        redactions,
        sanitizer_strangle_receipt,
    ) = _scan_public_export_artifacts(run_id=run_id, artifacts=artifacts)
    authority_surface_decisions = _authority_surface_decisions_for_public_export(artifacts)
    public_authority_surface_decisions = _public_authority_surface_decisions(
        authority_surface_decisions,
        redactions=redactions,
    )
    blocking_decisions = [
        (artifact_key, decision)
        for artifact_key, decision in authority_surface_decisions
        if decision.blocking
    ]
    if blocking_decisions:
        artifact_key, decision = blocking_decisions[0]
        raise PublicExportRedactionError(
            "authority_surface_blocked",
            (f"{artifact_key} cannot be exported for {decision.purpose}: {decision.reason}"),
            authority_surface_decisions=public_authority_surface_decisions,
        )
    rule_evolution_annotations = _iter_rule_evolution_annotations(sanitized_artifacts)
    public_revision_states = _iter_public_revision_states(sanitized_artifacts)
    orchestration_continuity = _public_orchestration_continuity_projection(sanitized_artifacts)
    authority_projections = [_authority_projection(envelope) for envelope in authority_envelopes]
    projection_semantics = None
    projection_contract_verification = None
    s10_verification = None
    s10_projection = None
    s11_verification = None
    s11_projection = None
    s12_verification = None
    s12_projection = None
    s13_verification = None
    s13_projection = None
    s13_public_revision_state = None
    s14_verification = None
    s14_projection = None
    g3_verification = None
    g3_projection = None
    if runtime_pdc_graph is not None:
        projection_semantics = build_policy_design_case_projection_from_runtime_graph(
            runtime_pdc_graph=runtime_pdc_graph,
            surface="public_export",
            generated_at=generated_at,
        )
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
            runtime_pdc_graph=runtime_pdc_graph,
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    elif policy_design_case is not None:
        projection_source: dict[str, object] = {
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
        }
        if projection_payload is not None:
            projection_source.update(dict(projection_payload))
        projection_semantics = build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case,
            surface="public_export",
            source_payload=projection_source,
            source_ref=projection_source.get("source_ref")
            if isinstance(projection_source.get("source_ref"), str)
            else None,
            generated_at=generated_at,
        )
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    if projection_semantics is not None and projection_payload is not None:
        projection_semantics, s9_verification = _apply_s9_projection_faithfulness(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s9_verification is not None and projection_contract_verification is not None:
            projection_contract_verification = {
                **projection_contract_verification,
                "s9_projection_faithfulness": s9_verification,
                "status": "fail"
                if (
                    projection_contract_verification.get("status") == "fail"
                    or s9_verification.get("status") == "fail"
                )
                else "pass",
            }
        projection_semantics, s10_verification, s10_projection = _apply_s10_forecast_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s10_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s10_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s10_forecast_projection_verification.v1"
                        )
                    ),
                    "status": str(s10_verification.get("status") or "fail"),
                    "s10_forecast_projection": s10_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s10_forecast_projection": s10_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s10_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s11_verification, s11_projection = _apply_s11_predictive_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s11_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s11_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s11_predictive_projection_verification.v1"
                        )
                    ),
                    "status": str(s11_verification.get("status") or "fail"),
                    "s11_predictive_projection": s11_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s11_predictive_projection": s11_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s11_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s12_verification, s12_projection = _apply_s12_resource_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s12_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s12_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s12_resource_projection_verification.v1"
                        )
                    ),
                    "status": str(s12_verification.get("status") or "fail"),
                    "s12_resource_projection": s12_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s12_resource_projection": s12_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s12_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s13_verification, s13_projection, s13_public_revision_state = (
            _apply_s13_post_deploy_accountability_projection(
                projection_semantics=projection_semantics,
                projection_payload=projection_payload,
            )
        )
        if s13_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s13_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s13_accountability_projection_verification.v1"
                        )
                    ),
                    "status": str(s13_verification.get("status") or "fail"),
                    "s13_post_deploy_accountability_projection": s13_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s13_post_deploy_accountability_projection": s13_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s13_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s14_verification, s14_projection = _apply_s14_universality_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s14_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s14_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s14_universality_projection_verification.v1"
                        )
                    ),
                    "status": str(s14_verification.get("status") or "fail"),
                    "s14_universality_projection": s14_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s14_universality_projection": s14_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s14_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, g3_verification, g3_projection = (
            _apply_layer3_g3_analytics_search_projection(
                projection_semantics=projection_semantics,
                projection_payload=projection_payload,
            )
        )
        if g3_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        g3_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "layer3_g3_projection_verification.v1"
                        )
                    ),
                    "status": str(g3_verification.get("status") or "fail"),
                    "layer3_g3_analytics_search_projection": g3_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "layer3_g3_analytics_search_projection": g3_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or g3_verification.get("status") == "fail"
                    )
                    else "pass",
                }
    _assert_public_claim_omissions_manifested(sanitized_artifacts, projection_semantics)
    exported_public_revision_states = list(public_revision_states)
    if s13_public_revision_state is not None:
        exported_public_revision_states.append(s13_public_revision_state)
    bundle = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "generated_at": (generated_at or datetime.now(UTC)).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "title": str(title or "Public export bundle"),
        "public_export_classification": "public_redacted_projection",
        "evidence_class": "redacted_derived",
        "authority_role": "projection_only",
        "provenance_kind": "runtime_projection",
        "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "official_use_limits": dict(_OFFICIAL_USE_LIMITS),
        "artifacts": sanitized_artifacts,
        "semantic_audit": {
            "artifact_keys": sorted(str(key) for key in sanitized_artifacts),
            "authority_projection_count": len(authority_projections),
            "authority_projections": authority_projections,
            "runtime_orchestration_continuity": orchestration_continuity,
            "recourse_pointer": recourse_pointer,
            "rule_evolution_annotations": rule_evolution_annotations,
            "public_revision_states": exported_public_revision_states,
            "s10_forecast_projection": s10_projection,
            "s10_forecast_projection_contract_verification": s10_verification,
            "s11_predictive_projection": s11_projection,
            "s11_predictive_projection_contract_verification": s11_verification,
            "s12_resource_projection": s12_projection,
            "s12_resource_projection_contract_verification": s12_verification,
            "s14_universality_projection": s14_projection,
            "s14_universality_projection_contract_verification": s14_verification,
            "layer3_g3_analytics_search_projection": g3_projection,
            "layer3_g3_analytics_search_projection_contract_verification": (g3_verification),
            "authority_surface_decisions": public_authority_surface_decisions,
            "omission_manifest": list(
                projection_semantics.get("omission_manifest", [])
                if projection_semantics is not None
                else []
            ),
            "audit_refs": list(
                projection_semantics.get("audit_refs", [])
                if projection_semantics is not None
                else []
            ),
            "projection_contract_verification": projection_contract_verification,
            "secret_pii_scan_reports": secret_pii_scan_reports,
            "strangle_receipts": [sanitizer_strangle_receipt],
        },
        "redaction_summary": {
            "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
            "redacted_path_count": len(redactions),
            "erased_paths": sorted({item["path"] for item in redactions}),
            "upserted_redactions": redactions,
            "strangle_receipt": sanitizer_strangle_receipt,
        },
    }
    if s13_projection is not None or s13_verification is not None:
        semantic_audit = dict(bundle["semantic_audit"])
        semantic_audit["s13_post_deploy_accountability_projection"] = s13_projection
        semantic_audit["s13_post_deploy_accountability_projection_contract_verification"] = (
            s13_verification
        )
        bundle["semantic_audit"] = semantic_audit
    if projection_semantics is not None:
        bundle["projection_semantics"] = projection_semantics
    assert_public_export_official_use_limits(bundle)
    _assert_no_tenant_private_ref_leak(bundle, tenant_private_refs)
    return bundle


def _scan_public_export_artifacts(
    *,
    run_id: str,
    artifacts: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    sanitizer = PromptSanitizer()
    scan = scan_secret_and_pii(
        dict(artifacts),
        scope="dashboard/public/export packets",
        artifact_ref_or_route=f"public-export://{run_id}",
        sanitizer=sanitizer,
        redact=True,
        block_on_findings=False,
    )
    if not isinstance(scan.redacted_payload, Mapping):
        raise PublicExportRedactionError(
            "public_export_secret_scan_invalid_payload",
            "Canonical secret/PII scan did not preserve public export mapping shape.",
        )
    private_ref_redactions: list[dict[str, str]] = []
    sanitized_artifacts = _redact_tenant_private_refs(
        scan.redacted_payload,
        path="artifacts",
        redactions=private_ref_redactions,
    )
    if not isinstance(sanitized_artifacts, Mapping):
        raise PublicExportRedactionError(
            "public_export_private_ref_scan_invalid_payload",
            "Private-ref scan did not preserve public export mapping shape.",
        )
    placeholder_map = sanitizer.placeholder_map()
    redactions = [
        {
            "path": f"canonical_redaction:{index}",
            "reason": _canonical_redaction_reason(placeholder),
        }
        for index, placeholder in enumerate(sorted(placeholder_map), start=1)
    ]
    redactions.extend(private_ref_redactions)
    return (
        dict(sanitized_artifacts),
        [report.model_dump(mode="json") for report in scan.reports],
        redactions,
        _public_export_sanitizer_strangle_receipt(),
    )


def _redact_tenant_private_refs(
    value: object,
    *,
    path: str,
    redactions: list[dict[str, str]],
) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            raw_key = str(key)
            public_key = _public_mapping_key(raw_key)
            if public_key != raw_key:
                redactions.append(
                    {
                        "path": f"{path}.{public_key}",
                        "reason": "tenant_private_ref",
                    }
                )
            sanitized[public_key] = _redact_tenant_private_refs(
                item,
                path=f"{path}.{public_key}",
                redactions=redactions,
            )
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _redact_tenant_private_refs(
                item,
                path=f"{path}[{index}]",
                redactions=redactions,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str) and _is_tenant_private_ref(value):
        redactions.append({"path": path, "reason": "tenant_private_ref"})
        return {
            "redacted": True,
            "reason": "tenant_private_ref",
            "fingerprint": _fingerprint(value),
        }
    return value


def _is_tenant_private_ref(value: str) -> bool:
    text = value.strip()
    return any(pattern.fullmatch(text) for pattern in _TENANT_PRIVATE_REF_PATTERNS)


def _public_mapping_key(value: str) -> str:
    if not _is_tenant_private_ref(value):
        return value
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:16]
    return f"[REDACTED_TENANT_PRIVATE_REF_KEY_{digest}]"


def _tenant_private_refs_in_payload(value: object) -> frozenset[str]:
    refs: set[str] = set()

    def collect(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                collect(str(key))
                collect(nested)
            return
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for nested in item:
                collect(nested)
            return
        if isinstance(item, str) and _is_tenant_private_ref(item):
            refs.add(item.strip())

    collect(value)
    return frozenset(refs)


def _assert_no_tenant_private_ref_leak(
    value: object,
    tenant_private_refs: frozenset[str],
) -> None:
    if not tenant_private_refs:
        return

    def first_leak_path(item: object, *, path: str) -> str | None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                key_text = str(key)
                if any(ref in key_text for ref in tenant_private_refs):
                    return f"{path}.<key>"
                leak_path = first_leak_path(nested, path=f"{path}.{key_text}")
                if leak_path is not None:
                    return leak_path
            return None
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, nested in enumerate(item):
                leak_path = first_leak_path(nested, path=f"{path}[{index}]")
                if leak_path is not None:
                    return leak_path
            return None
        if isinstance(item, str) and any(ref in item for ref in tenant_private_refs):
            return path
        return None

    leak_path = first_leak_path(value, path="public_export")
    if leak_path is not None:
        raise PublicExportRedactionError(
            "public_export_tenant_private_ref_leak",
            f"Caller private-ref material survived at {leak_path}.",
        )


def _public_authority_surface_decisions(
    decisions: Sequence[tuple[str, AuthoritySurfaceDecision]],
    *,
    redactions: list[dict[str, str]],
) -> list[dict[str, object]]:
    projection = _redact_tenant_private_refs(
        [
            {
                "artifact_key": artifact_key,
                "decision": decision.model_dump(mode="json"),
            }
            for artifact_key, decision in decisions
        ],
        path="semantic_audit.authority_surface_decisions",
        redactions=redactions,
    )
    if not isinstance(projection, list) or not all(
        isinstance(item, Mapping) for item in projection
    ):
        raise PublicExportRedactionError(
            "public_export_authority_decision_scan_invalid_payload",
            "Private-ref scan did not preserve authority decision projection shape.",
        )
    return [dict(item) for item in projection]


def _canonical_redaction_reason(placeholder: str) -> str:
    if "_EMAIL_" in placeholder:
        return "email:redacted_by_canonical_scanner"
    if "_KEYED_SECRET_" in placeholder:
        return "keyed_secret:redacted_by_canonical_scanner"
    return "secret_pii:redacted_by_canonical_scanner"


def _public_export_sanitizer_strangle_receipt() -> dict[str, object]:
    return {
        "predecessor_ref": (
            "runtime.quality.public_export._FORBIDDEN_*_TOKENS._sanitize_public_payload"
        ),
        "replacement_ref": "polisyos.core.llm.sanitization.scan_secret_and_pii",
        "disposition": "deleted_live_path_default_flipped_to_composed_gate",
        "default_before": "public export used a parallel deny-list sanitizer",
        "default_after": (
            "public export redacts through the canonical SecretAndPIIScanReport emitter "
            "and every artifact is admitted through authority_surface_decision"
        ),
        "remaining_callers": [],
    }


def _authority_surface_decisions_for_public_export(
    artifacts: Mapping[str, object],
) -> list[tuple[str, AuthoritySurfaceDecision]]:
    decisions: list[tuple[str, AuthoritySurfaceDecision]] = []
    for key, artifact in artifacts.items():
        if not isinstance(artifact, Mapping):
            continue
        export_decision = authority_surface_decision(
            artifact,
            surface="export",
            artifact_ref_or_route=f"public-export://{key}",
            secret_pii_scope="dashboard/public/export packets",  # noqa: S106
            block_on_secret_findings=False,
            missing_authority_disposition="downgrade",
            missing_boundary_disposition="downgrade",
        )
        public_packet_decision = authority_surface_decision(
            artifact,
            surface="public_packet",
            artifact_ref_or_route=f"public-packet://{key}",
            secret_pii_scope="dashboard/public/export packets",  # noqa: S106
            block_on_secret_findings=False,
            missing_authority_disposition="downgrade",
            missing_boundary_disposition="downgrade",
        )
        for decision in (export_decision, public_packet_decision):
            decisions.append((str(key), decision))
    return decisions


def _apply_s14_universality_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    if not _has_s14_universality_projection(projection_payload):
        return dict(projection_semantics), None, None
    verification = verify_s14_universality_projection_consumer_contract(
        projections={"public": projection_payload},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s14_issue_code(verification),
            "S14 universality projection consumer contract must pass before public release.",
        )
    public_projection = dict(verification.get("public_projection") or {})
    s14_projection = dict(verification.get("s14_universality_projection") or {})
    enriched = dict(projection_semantics)
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_rollout_authority",
            "production_recommendation",
            "recommendation_authority",
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "aggregate_universal_score",
        ]
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            public_projection.get("public_universality_limitation"),
            "S14 universality is projection-only and limited to the declared envelope.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s14_projection.get("s14_universality_assurance_ref"),
            s14_projection.get("universality_claim_gate_ref"),
            s14_projection.get("declared_operation_envelope_ref"),
            s14_projection.get("d4_corpus_track_coverage_ref"),
            s14_projection.get("expert_oracle_bootstrap_ref"),
            s14_projection.get("breadth_floor_config_ref"),
            s14_projection.get("universality_baseline_comparison_ref"),
            s14_projection.get("grounded_authority_coverage_ref"),
            s14_projection.get("evaluation_status_composition_ref"),
            s14_projection.get("axis_scorecard_ref"),
            s14_projection.get("sealed_battery_run_ref"),
            s14_projection.get("mechanism_generality_report_ref"),
            s14_projection.get("rule_version_ref"),
            *_text_list(s14_projection.get("skeptic_defeater_refs")),
            *_text_list(s14_projection.get("s9_projection_faithfulness_refs")),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s14_universality_assurance_ref": s14_projection.get("s14_universality_assurance_ref"),
            "s14_projection_policy": "reads_s14_universality_assurance_as_projection",
            "universality_claim_gate_ref": s14_projection.get("universality_claim_gate_ref"),
        }
    )
    enriched.update(
        {
            "authority_role": "projection_only",
            "universality_claim_disposition": public_projection.get(
                "universality_claim_disposition"
            ),
            "declared_operation_envelope_ref": public_projection.get(
                "declared_operation_envelope_ref"
            ),
            "s14_universality_assurance_ref": public_projection.get(
                "s14_universality_assurance_ref"
            ),
            "universality_claim_gate_ref": public_projection.get("universality_claim_gate_ref"),
            "d4_corpus_track_coverage_ref": public_projection.get("d4_corpus_track_coverage_ref"),
            "d4_corpus_track_coverage_status": public_projection.get(
                "d4_corpus_track_coverage_status"
            ),
            "d4_breadth_limitation_summary": public_projection.get("d4_breadth_limitation_summary"),
            "expert_oracle_bootstrap_ref": public_projection.get("expert_oracle_bootstrap_ref"),
            "expert_oracle_seed_only_layer_refs": public_projection.get(
                "expert_oracle_seed_only_layer_refs"
            ),
            "breadth_floor_config_ref": public_projection.get("breadth_floor_config_ref"),
            "breadth_floor_status": public_projection.get("breadth_floor_status"),
            "excluded_domain_refs": public_projection.get("excluded_domain_refs"),
            "universality_baseline_comparison_ref": public_projection.get(
                "universality_baseline_comparison_ref"
            ),
            "baseline_comparison_status": public_projection.get("baseline_comparison_status"),
            "grounded_authority_coverage_ref": public_projection.get(
                "grounded_authority_coverage_ref"
            ),
            "grounded_authority_status": public_projection.get("grounded_authority_status"),
            "evaluation_status_composition_ref": public_projection.get(
                "evaluation_status_composition_ref"
            ),
            "status_composition_limit_refs": public_projection.get("status_composition_limit_refs"),
            "axis_scorecard_ref": public_projection.get("axis_scorecard_ref"),
            "out_of_envelope_axis_refs": public_projection.get("out_of_envelope_axis_refs"),
            "not_tested_axis_refs": public_projection.get("not_tested_axis_refs"),
            "mechanism_generality_status": public_projection.get("mechanism_generality_status"),
            "sublinear_marginal_bespoke_cost_status": public_projection.get(
                "sublinear_marginal_bespoke_cost_status"
            ),
            "skeptic_defeater_statuses": public_projection.get("skeptic_defeater_statuses"),
            "s9_projection_faithfulness_refs": public_projection.get(
                "s9_projection_faithfulness_refs"
            ),
            "public_universality_limitation": public_projection.get(
                "public_universality_limitation"
            ),
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s14_universality_projection_contract_verification_status": (
                verification.get("status")
            ),
            "s14_universality_projection_contract_verification_ref": (
                verification.get("consumer_contract_ref")
            ),
        }
    )
    return enriched, verification, s14_projection


def _apply_s13_post_deploy_accountability_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    s13_projection = _s13_accountability_projection_record(projection_payload)
    if not s13_projection:
        return dict(projection_semantics), None, None, None
    verification = verify_s13_post_deploy_accountability_projection_consumer_contract(
        projections={"public": s13_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s13_issue_code(verification),
            "S13 accountability projection consumer contract must pass before public release.",
        )
    revision_state = _s13_public_revision_state(projection_payload)
    public_projection = dict(verification.get("public_projection") or {})
    enriched = dict(projection_semantics)
    accountability_note = _text(
        public_projection.get("public_accountability_note")
        or s13_projection.get("public_accountability_note")
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "current_evidence_slot",
            "pre_policy_evidence",
            "production_rollout_authority",
            "recommendation_authority",
            "approval_authority",
            "scorecard_authority",
            "s14_universality",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s13_projection.get("accountability_posture_ref"),
            s13_projection.get("deployment_dossier_ref"),
            s13_projection.get("public_revision_state_ref"),
            s13_projection.get("public_accountability_note_ref"),
            s13_projection.get("rule_version_ref"),
            *_text_list(s13_projection.get("divergence_record_refs")),
            *_text_list(s13_projection.get("learning_update_proposal_refs")),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s13_accountability_posture_ref": s13_projection.get("accountability_posture_ref"),
            "s13_projection_policy": ("reads_post_deploy_accountability_posture_as_revision_note"),
            "s13_public_revision_state_ref": s13_projection.get("public_revision_state_ref"),
        }
    )
    enriched.update(
        {
            "public_accountability_note": accountability_note,
            "public_accountability_note_ref": s13_projection.get("public_accountability_note_ref"),
            "public_revision_state_ref": s13_projection.get("public_revision_state_ref"),
            "envelope_revision_direction": s13_projection.get("envelope_revision_direction"),
            "closed_case_historical_meaning": (
                s13_projection.get("closed_case_historical_meaning") or "preserved"
            ),
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s13_post_deploy_accountability_projection_contract_verification_status": (
                verification.get("status")
            ),
            "s13_post_deploy_accountability_projection_contract_verification_ref": (
                verification.get("consumer_contract_ref")
            ),
        }
    )
    return enriched, verification, s13_projection, revision_state


def _apply_s12_resource_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s12_projection = _s12_resource_projection_record(projection_payload)
    if not s12_projection:
        return dict(projection_semantics), None, None
    verification = verify_s12_resource_projection_consumer_contract(
        projections={"public": s12_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s12_issue_code(verification),
            "S12 resource projection consumer contract must pass before public release.",
        )
    public_projection = dict(verification.get("public_projection") or {})
    enriched = dict(projection_semantics)
    growth_limitation = _text(
        public_projection.get("s12_public_growth_limitation")
        or s12_projection.get("s12_public_growth_limitation")
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            growth_limitation,
            "S12 resource allocation remains allocation-only, not recommendation authority.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s12_projection.get("resource_allocation_policy_ref"),
            s12_projection.get("envelope_growth_ledger_ref"),
            s12_projection.get("growth_thermometer_ref"),
            s12_projection.get("rule_version_ref"),
            *_text_list(s12_projection.get("voi_allocation_refs")),
            *_text_list(s12_projection.get("residual_limitation_refs")),
        ]
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_authority",
            "production_recommendation",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "recommendation_authority",
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s12_resource_posture_ref": s12_projection.get("resource_allocation_policy_ref"),
            "s12_projection_policy": "reads_resource_economics_posture_as_constraint",
            "s12_explore_exploit_posture": s12_projection.get("explore_exploit_posture"),
        }
    )
    enriched.update(
        {
            "explore_exploit_posture": s12_projection.get("explore_exploit_posture"),
            "override_rate_trend": s12_projection.get("override_rate_trend"),
            "reuse_rate_trend": s12_projection.get("reuse_rate_trend"),
            "s12_public_growth_limitation": growth_limitation,
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s12_resource_projection_contract_verification_status": verification.get("status"),
            "s12_resource_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s12_projection


def _apply_s11_predictive_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s11_projection = _s11_predictive_projection_record(projection_payload)
    if not s11_projection:
        return dict(projection_semantics), None, None
    verification = verify_s11_predictive_projection_consumer_contract(
        projections={"public": s11_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s11_issue_code(verification),
            "S11 predictive projection consumer contract must pass before public release.",
        )
    public_projection = dict(verification.get("public_projection") or {})
    enriched = dict(projection_semantics)
    s11_limitation = _text(
        public_projection.get("s11_public_limitation")
        or s11_projection.get("s11_public_limitation")
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            s11_limitation,
            "S11 predictive relaxation remains calibration-limited and not authority.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s11_projection.get("s11_predictive_posture_ref"),
            s11_projection.get("proof_carrying_analytics_ref"),
            s11_projection.get("ir_analytics_bridge_ref"),
            s11_projection.get("rule_version_ref"),
            *_text_list(s11_projection.get("predictive_axis_upgrade_refs")),
            *_text_list(s11_projection.get("residual_limitation_refs")),
        ]
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "runtime_closeout_authority",
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s11_predictive_posture_ref": s11_projection.get("s11_predictive_posture_ref"),
            "s11_projection_policy": "reads_predictive_posture_as_constraint",
            "s11_effective_predictive_posture": s11_projection.get("effective_predictive_posture"),
        }
    )
    enriched.update(
        {
            "effective_predictive_posture": s11_projection.get("effective_predictive_posture"),
            "s11_public_limitation": s11_limitation,
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s11_predictive_projection_contract_verification_status": (verification.get("status")),
            "s11_predictive_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s11_projection


def _apply_layer3_g3_analytics_search_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    g3_projection = _layer3_g3_analytics_search_projection_record(projection_payload)
    if not g3_projection:
        return dict(projection_semantics), None, None
    verification = {
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.layer3_g3_public_projection_verification.v1"
        ),
        "status": "pass",
        "public_projection": g3_projection,
    }
    enriched = dict(projection_semantics)
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(g3_projection.get("may_not_use_for")),
            "claim_authority",
            "policy_recommendation",
            "closeout_authority",
            "publication_authority",
            "search_hit_as_certificate",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            g3_projection.get("certificate_resolution_report_ref"),
            *_text_list(g3_projection.get("search_ledger_refs")),
            *_text_list(g3_projection.get("redacted_search_frontier_refs")),
            *_text_list(g3_projection.get("proof_carrying_analytics_refs")),
            *_text_list(g3_projection.get("ir_analytics_bridge_refs")),
            *_text_list(g3_projection.get("method_requirement_refs")),
            *_text_list(g3_projection.get("s11_predictive_posture_refs")),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "layer3_g3_projection_policy": "reads_projection_only_search_resolution_refs",
            "layer3_g3_certificate_resolution_report_ref": g3_projection.get(
                "certificate_resolution_report_ref"
            ),
            "layer3_g3_public_export_projection_ref": g3_projection.get("projection_ref"),
        }
    )
    enriched.update(
        {
            "layer3_g3_public_export_projection_status": g3_projection.get("status"),
            "layer3_g3_certificate_resolution_report_ref": g3_projection.get(
                "certificate_resolution_report_ref"
            ),
            "layer3_g3_resolved_certificate_count": g3_projection.get("resolved_certificate_count"),
            "layer3_g3_blocked_certificate_count": g3_projection.get("blocked_certificate_count"),
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "layer3_g3_analytics_search_projection_contract_verification_status": (
                verification["status"]
            ),
            "layer3_g3_analytics_search_projection_contract_verification_ref": (
                verification["consumer_contract_ref"]
            ),
        }
    )
    return enriched, verification, g3_projection


def _apply_s10_forecast_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s10_projection = _s10_forecast_projection_record(projection_payload)
    if not s10_projection:
        return dict(projection_semantics), None, None
    missing_refs = _s10_missing_machine_export_refs(s10_projection)
    if missing_refs:
        raise PublicExportRedactionError(
            "s10_machine_export_requires_calibration_and_source_refs",
            "S10 public export requires reconstructable calibration, source, and method refs.",
        )
    verification = verify_s10_forecast_projection_consumer_contract(
        projections={"public": s10_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s10_issue_code(verification),
            "S10 forecast projection consumer contract must pass before public release.",
        )
    enriched = dict(projection_semantics)
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            *_text_list(s10_projection.get("limitations")),
            s10_projection.get("forecast_authority_disposition_reason"),
            "forecast support only; not production recommendation authority",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s10_projection.get("forecast_support_ref"),
            s10_projection.get("forecast_calibration_record_ref"),
            s10_projection.get("design_graph_ref"),
            s10_projection.get("prediction_context_ref"),
            s10_projection.get("source_contract_ref"),
            s10_projection.get("method_validity_ref"),
            s10_projection.get("credible_evaluation_evidence_ref"),
            s10_projection.get("rule_version_ref"),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s10_forecast_support_ref": s10_projection.get("forecast_support_ref"),
            "s10_design_graph_ref": s10_projection.get("design_graph_ref"),
            "s10_prediction_context_ref": s10_projection.get("prediction_context_ref"),
            "s10_projection_policy": "reads_forecast_support_posture",
        }
    )
    enriched.update(
        {
            "forecast_tier": s10_projection.get("forecast_tier"),
            "observable_subset_calibration_status": s10_projection.get(
                "observable_subset_calibration_status"
            ),
            "uncertainty_interval_refs": list(
                _as_sequence(s10_projection.get("uncertainty_interval_refs"))
            ),
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s10_forecast_projection_contract_verification_status": verification.get("status"),
            "s10_forecast_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s10_projection


def _s10_forecast_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("forecast_support_ref"))
        or _text(projection_payload.get("forecast_tier"))
    ):
        return {}
    authority_boundary = dict(
        projection_payload.get("authority_boundary")
        if isinstance(projection_payload.get("authority_boundary"), Mapping)
        else {}
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_forecast_support_posture",
        "forecast_support_ref": _text(projection_payload.get("forecast_support_ref")),
        "forecast_tier": _text(projection_payload.get("forecast_tier")),
        "forecast_authority_disposition_reason": _text(
            projection_payload.get("forecast_authority_disposition_reason")
        ),
        "forecast_support_label": _text(projection_payload.get("forecast_support_label")),
        "forecast_calibration_record_ref": _text(
            projection_payload.get("forecast_calibration_record_ref")
        ),
        "observable_subset_calibration_status": _text(
            projection_payload.get("observable_subset_calibration_status")
            or projection_payload.get("calibration_status")
            or projection_payload.get("forecast_calibration_status")
        ),
        "design_graph_ref": _text(projection_payload.get("design_graph_ref")),
        "prediction_context_ref": _text(projection_payload.get("prediction_context_ref")),
        "policy_context_ref": _text(projection_payload.get("policy_context_ref")),
        "source_contract_ref": _text(projection_payload.get("source_contract_ref")),
        "method_validity_ref": _text(projection_payload.get("method_validity_ref")),
        "credible_evaluation_evidence_ref": _text(
            projection_payload.get("credible_evaluation_evidence_ref")
        ),
        "uncertainty_interval_refs": _text_list(
            projection_payload.get("uncertainty_interval_refs")
        ),
        "welfare_comparison": dict(projection_payload.get("welfare_comparison") or {})
        if isinstance(projection_payload.get("welfare_comparison"), Mapping)
        else {},
        "authority_boundary": authority_boundary,
        "limitations": _text_list(projection_payload.get("limitations")),
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s11_predictive_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("s11_predictive_posture_ref"))
        or _text(projection_payload.get("predictive_knowledge_ref"))
        or _as_sequence(projection_payload.get("predictive_axis_rows"))
    ):
        return {}
    authority_boundary = dict(
        projection_payload.get("authority_boundary")
        if isinstance(projection_payload.get("authority_boundary"), Mapping)
        else {}
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_predictive_posture_as_constraint",
        "s11_predictive_posture_ref": _text(
            projection_payload.get("s11_predictive_posture_ref")
            or projection_payload.get("predictive_knowledge_ref")
        ),
        "effective_predictive_posture": _text(
            projection_payload.get("effective_predictive_posture")
            or projection_payload.get("predictive_authority_status")
        ),
        "predictive_axis_upgrade_refs": _text_list(
            projection_payload.get("predictive_axis_upgrade_refs")
            or projection_payload.get("axis_upgrade_refs")
        ),
        "predictive_axis_rows": [
            dict(row)
            for row in _as_sequence(projection_payload.get("predictive_axis_rows"))
            if isinstance(row, Mapping)
        ],
        "per_axis_predictive_calibration_status": _text(
            projection_payload.get("per_axis_predictive_calibration_status")
        ),
        "per_axis_predictive_calibration_threshold_ref": _text(
            projection_payload.get("per_axis_predictive_calibration_threshold_ref")
        ),
        "proof_carrying_analytics_ref": _text(
            projection_payload.get("proof_carrying_analytics_ref")
        ),
        "ir_analytics_bridge_ref": _text(projection_payload.get("ir_analytics_bridge_ref")),
        "residual_limitation_refs": _text_list(projection_payload.get("residual_limitation_refs")),
        "weakest_boundary_reason": _text(projection_payload.get("weakest_boundary_reason")),
        "s11_public_limitation": _text(projection_payload.get("s11_public_limitation")),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _layer3_g3_analytics_search_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    raw = projection_payload.get("layer3_g3_public_export_projection")
    if not isinstance(raw, Mapping):
        return {}
    authority_boundary = dict(
        raw.get("authority_boundary") if isinstance(raw.get("authority_boundary"), Mapping) else {}
    )
    may_not = _unique_texts(
        [
            *_text_list(raw.get("may_not_use_for")),
            *_text_list(raw.get("may_not_be_used_for")),
            *_text_list(authority_boundary.get("may_not_use_for")),
        ]
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_layer3_g3_resolution_status_as_audit_refs",
        "projection_ref": _text(raw.get("projection_ref")),
        "status": _text(raw.get("status")) or "unknown",
        "certificate_resolution_report_ref": _text(raw.get("certificate_resolution_report_ref")),
        "search_ledger_refs": _text_list(raw.get("search_ledger_refs")),
        "redacted_search_frontier_refs": _text_list(raw.get("redacted_search_frontier_refs")),
        "proof_carrying_analytics_refs": _text_list(raw.get("proof_carrying_analytics_refs")),
        "ir_analytics_bridge_refs": _text_list(raw.get("ir_analytics_bridge_refs")),
        "method_requirement_refs": _text_list(raw.get("method_requirement_refs")),
        "s11_predictive_posture_refs": _text_list(raw.get("s11_predictive_posture_refs")),
        "resolved_certificate_count": _int(raw.get("resolved_certificate_count")),
        "blocked_certificate_count": _int(raw.get("blocked_certificate_count")),
        "authority_boundary": authority_boundary,
        "may_not_use_for": may_not,
        "raw_proof_payload_exported": False,
        "raw_cas_manifest_exported": False,
        "raw_query_ledger_exported": False,
    }


def _s12_resource_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("resource_allocation_policy_ref"))
        or _text(projection_payload.get("s12_resource_posture_ref"))
        or _text(projection_payload.get("explore_exploit_posture"))
    ):
        return {}
    authority_boundary = dict(
        projection_payload.get("authority_boundary")
        if isinstance(projection_payload.get("authority_boundary"), Mapping)
        else {}
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_resource_economics_posture_as_constraint",
        "s12_resource_posture_ref": _text(projection_payload.get("s12_resource_posture_ref")),
        "resource_allocation_policy_ref": _text(
            projection_payload.get("resource_allocation_policy_ref")
            or projection_payload.get("s12_resource_posture_ref")
        ),
        "explore_exploit_posture": _text(projection_payload.get("explore_exploit_posture")),
        "explore_exploit_dial_ref": _text(projection_payload.get("explore_exploit_dial_ref")),
        "voi_allocation_refs": _text_list(projection_payload.get("voi_allocation_refs")),
        "voi_site_count": _int(projection_payload.get("voi_site_count")),
        "typed_budget_refs": _text_list(projection_payload.get("typed_budget_refs")),
        "pareto_archive_ref": _text(projection_payload.get("pareto_archive_ref")),
        "envelope_growth_ledger_ref": _text(projection_payload.get("envelope_growth_ledger_ref")),
        "growth_thermometer_ref": _text(projection_payload.get("growth_thermometer_ref")),
        "override_rate_trend": _text(projection_payload.get("override_rate_trend")),
        "reuse_rate_trend": _text(projection_payload.get("reuse_rate_trend")),
        "held_out_status": _text(projection_payload.get("held_out_status")),
        "resource_allocation_disposition": _text(
            projection_payload.get("resource_allocation_disposition")
        ),
        "residual_limitation_refs": _text_list(projection_payload.get("residual_limitation_refs")),
        "s12_public_growth_limitation": _text(
            projection_payload.get("s12_public_growth_limitation")
        ),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s13_accountability_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("accountability_posture_ref"))
        or _text(projection_payload.get("public_accountability_note_ref"))
    ):
        return {}
    authority_boundary = dict(
        projection_payload.get("authority_boundary")
        if isinstance(projection_payload.get("authority_boundary"), Mapping)
        else {}
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_s13_post_deploy_accountability_posture",
        "accountability_posture_ref": _text(projection_payload.get("accountability_posture_ref")),
        "deployment_dossier_ref": _text(projection_payload.get("deployment_dossier_ref")),
        "divergence_record_refs": _text_list(projection_payload.get("divergence_record_refs")),
        "learning_update_proposal_refs": _text_list(
            projection_payload.get("learning_update_proposal_refs")
        ),
        "envelope_revision_ref": _text(projection_payload.get("envelope_revision_ref")),
        "certified_envelope_delta_ref": _text(
            projection_payload.get("certified_envelope_delta_ref")
        ),
        "assurance_case_delta_ref": _text(projection_payload.get("assurance_case_delta_ref")),
        "attribution_status": _text(projection_payload.get("attribution_status")),
        "attribution_classes": _text_list(projection_payload.get("attribution_classes")),
        "learning_change_control_classes": _text_list(
            projection_payload.get("learning_change_control_classes")
        ),
        "lifecycle_reissue_disposition": _text(
            projection_payload.get("lifecycle_reissue_disposition")
        ),
        "envelope_revision_direction": _text(projection_payload.get("envelope_revision_direction")),
        "assurance_case_change": _text(projection_payload.get("assurance_case_change")),
        "mape_k_trace_ref": _text(projection_payload.get("mape_k_trace_ref")),
        "public_revision_state_ref": _text(projection_payload.get("public_revision_state_ref")),
        "public_accountability_note_ref": _text(
            projection_payload.get("public_accountability_note_ref")
        ),
        "public_accountability_note": _text(projection_payload.get("public_accountability_note")),
        "closed_case_historical_meaning": _text(
            projection_payload.get("closed_case_historical_meaning")
        ),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s13_public_revision_state(
    projection_payload: Mapping[str, object],
) -> dict[str, object] | None:
    revision_state = projection_payload.get("public_revision_state")
    if not isinstance(revision_state, Mapping):
        return None
    state = dict(revision_state)
    claim_ids = _unique_texts(
        [
            *_text_list(state.get("affected_claim_ids")),
            *_text_list(state.get("unaffected_claim_ids")),
        ]
    )
    if not claim_ids:
        claim_ids = ["unknown_claim"]
    validation_state = dict(state)
    if validation_state.get("silent_upgrade_allowed") is not False:
        validation_state["authority_role"] = "projection_only"
    report = {
        "schema_version": LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION,
        "report_id": "s13-public-revision-state-validation",
        "case_id": "s13-post-deploy-accountability",
        "claim_ids": claim_ids,
        "event_impacts": [],
        "claim_revision_states": [],
        "public_revision_state": validation_state,
        "issues": [],
        "status": "review_required",
        "evidence_ref": _text(projection_payload.get("public_revision_state_ref"))
        or "projection_payload",
        "runtime_event_ref": _text(projection_payload.get("accountability_posture_ref"))
        or "projection_payload",
    }
    try:
        validate_lifecycle_reissue_report(report)
    except PolicyDesignLifecycleError as exc:
        raise PublicExportRedactionError(exc.code, str(exc)) from exc
    return state


def _s10_missing_machine_export_refs(
    s10_projection: Mapping[str, object],
) -> list[str]:
    required = (
        "forecast_calibration_record_ref",
        "design_graph_ref",
        "prediction_context_ref",
        "source_contract_ref",
        "method_validity_ref",
        "credible_evaluation_evidence_ref",
        "rule_version_ref",
    )
    missing = [key for key in required if not _text(s10_projection.get(key))]
    if not isinstance(s10_projection.get("authority_boundary"), Mapping):
        missing.append("authority_boundary")
    return missing


def _first_s10_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s10_forecast_projection_failed"


def _first_s11_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s11_predictive_projection_failed"


def _first_s12_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s12_resource_projection_failed"


def _first_s13_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s13_accountability_projection_failed"


def _first_s14_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s14_universality_projection_failed"


def _has_s14_universality_projection(payload: Mapping[str, object]) -> bool:
    return any(
        _text(payload.get(field_name))
        for field_name in (
            "s14_universality_assurance_ref",
            "universality_claim_gate_ref",
            "declared_operation_envelope_ref",
            "axis_scorecard_ref",
            "sealed_battery_run_ref",
        )
    )


def _apply_s9_projection_faithfulness(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    faithfulness = _s9_faithfulness_record(projection_payload)
    if not faithfulness:
        return dict(projection_semantics), None
    verifier_payload = {
        **dict(projection_semantics),
        "projection_policy": "reads_canonical_design_record",
        "source_revision_ref": _text(
            projection_payload.get("source_revision_ref") or faithfulness.get("source_revision_ref")
        ),
        "s9_projection_faithfulness": faithfulness,
    }
    if "omission_manifest" in projection_payload:
        verifier_payload["omission_manifest"] = projection_payload["omission_manifest"]
    verification = verify_s9_projection_faithfulness_for_pdc_consumer_contract(
        projections={"public": verifier_payload},
        expected_closeout_truth=dict(projection_semantics.get("closeout_truth") or {}),
        expected_contested_record_ids=[
            _text(record.get("contested_record_id"))
            for record in _as_sequence(projection_semantics.get("contested_records"))
            if isinstance(record, Mapping)
        ],
    )
    if verification.get("status") != "pass":
        code = _first_s9_issue_code(verification)
        raise PublicExportRedactionError(
            code,
            "S9 projection faithfulness must pass before public release.",
        )
    enriched = dict(projection_semantics)
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            *_s9_audit_refs(faithfulness),
            *_text_list(projection_payload.get("s9_lowering_append_refs")),
            *_text_list(projection_payload.get("lowering_append_refs")),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s9_source_revision_ref": _text(faithfulness.get("source_revision_ref")),
            "s9_canonical_design_record_ref": _text(
                faithfulness.get("canonical_design_record_ref")
            ),
            "s9_canonical_design_record_digest": _text(
                faithfulness.get("canonical_design_record_digest")
            ),
            "s9_projection_policy": "reads_canonical_design_record",
        }
    )
    enriched.update(
        {
            "s9_projection_faithfulness": faithfulness,
            "s9_projection_contract_verification_status": verification.get("status"),
            "s9_projection_contract_verification_ref": verification.get("consumer_contract_ref"),
            "audit_refs": audit_refs,
            "source_state": source_state,
        }
    )
    return enriched, verification


def _s9_faithfulness_record(payload: Mapping[str, object]) -> dict[str, object]:
    record = payload.get("s9_projection_faithfulness")
    if record is None and isinstance(payload.get("s9_projection"), Mapping):
        record = dict(payload["s9_projection"]).get("s9_projection_faithfulness")
    if isinstance(record, Mapping):
        return dict(record)
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {}


def _s9_audit_refs(faithfulness: Mapping[str, object]) -> list[str]:
    return _unique_texts(
        [
            faithfulness.get("faithfulness_ref"),
            faithfulness.get("render_ref"),
            faithfulness.get("request_ref"),
            faithfulness.get("canonical_design_record_ref"),
            faithfulness.get("source_revision_ref"),
        ]
    )


def _first_s9_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s9_projection_faithfulness_failed"


def _assert_public_claim_omissions_manifested(
    artifacts: Mapping[str, object],
    projection_semantics: Mapping[str, object] | None,
) -> None:
    omitted_claim_ids = set(_iter_omitted_claim_ids(artifacts))
    if not omitted_claim_ids:
        return
    manifested_claim_ids: set[str] = set()
    if projection_semantics is not None:
        for row in _as_sequence(projection_semantics.get("omission_manifest")):
            if isinstance(row, Mapping):
                manifested_claim_ids.update(
                    str(value) for value in _as_sequence(row.get("claim_ids"))
                )
    if not omitted_claim_ids <= manifested_claim_ids:
        raise PublicExportRedactionError(
            "public_export_omission_manifest_missing",
            "public exports must manifest omitted blocked claims instead of silently dropping them",
        )


def _assert_public_export_candidate_firewall(artifacts: Mapping[str, object]) -> None:
    hypothesis_ledger = _find_hypothesis_ledger(artifacts)
    issues = candidate_firewall_issues_for_payload(
        artifacts,
        hypothesis_ledger=hypothesis_ledger,
        authority_slots=("projection_authority",),
        surface="public_export",
    )
    if issues:
        issue = issues[0]
        raise PublicExportRedactionError(
            str(issue.get("code") or "candidate_firewall_blocked"),
            str(issue.get("message") or "Candidate content cannot be publicly exported."),
        )


def _assert_public_welfare_frontier_surface(payload: Mapping[str, object]) -> None:
    scalar_keys = {
        key for key, value in payload.items() if key in _SCALAR_WELFARE_KEYS and value is not None
    }
    if not scalar_keys:
        return
    has_frontier = bool(payload.get("frontier") or payload.get("pareto_frontier"))
    has_value_choice = bool(payload.get("value_choice") or payload.get("value_choice_decision"))
    has_provenance = bool(
        payload.get("social_weight_provenance") or payload.get("social_weight_provenance_refs")
    )
    if has_frontier and has_value_choice and has_provenance:
        return
    raise PublicExportRedactionError(
        "scalar_welfare_aggregate_without_frontier",
        "Scalar welfare aggregates cannot be published without Pareto frontier, "
        "value-choice, and social-weight provenance records.",
    )


def _find_hypothesis_ledger(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        ledger = value.get("hypothesis_ledger")
        if isinstance(ledger, Mapping):
            return ledger
        for item in value.values():
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    return None


def _iter_omitted_claim_ids(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in {"omitted_claim_ids", "omitted_blocked_claim_ids"}:
                found.extend(str(claim_id) for claim_id in _as_sequence(item) if str(claim_id))
                continue
            if lowered in {"omitted_claims", "omitted_blocked_claims"}:
                for claim in _as_sequence(item):
                    if isinstance(claim, Mapping):
                        claim_id = str(claim.get("claim_id") or claim.get("id") or "")
                        if claim_id:
                            found.append(claim_id)
                    elif str(claim):
                        found.append(str(claim))
                continue
            found.extend(_iter_omitted_claim_ids(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_omitted_claim_ids(item))
    return sorted(set(found))


def _assert_no_unexplained_replay_drift(artifacts: Mapping[str, object]) -> None:
    for explanation in _iter_drift_explanations(artifacts):
        if _is_unexplained_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unexplained",
                "public exports require typed accepted replay drift or reproduction",
            )
        if _is_unbounded_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unbounded",
                "public exports require replay drift to stay within production impact bounds",
            )


def _iter_drift_explanations(value: object) -> Sequence[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_drift_explanation(value):
            found.append(value)
        for key, item in value.items():
            if key == "drift_explanation" and isinstance(item, Mapping):
                found.append(item)
            else:
                found.extend(_iter_drift_explanations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_drift_explanations(item))
    return found


def _looks_like_drift_explanation(value: Mapping[str, object]) -> bool:
    return (
        value.get("schema_version") == "policyos.drift_explanation.v1"
        or "drift_sources" in value
        or "unexplained_difference_count" in value
    )


def _iter_rule_evolution_annotations(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_rule_evolution_annotation(value):
            found.append(dict(value))
        for item in value.values():
            found.extend(_iter_rule_evolution_annotations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_rule_evolution_annotations(item))
    return found


def _iter_public_revision_states(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_public_revision_state(value):
            found.append(dict(value))
        for item in value.values():
            found.extend(_iter_public_revision_states(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_public_revision_states(item))
    return found


def _public_orchestration_continuity_projection(
    artifacts: Mapping[str, object],
) -> dict[str, object] | None:
    value = artifacts.get("runtime_orchestration_continuity")
    if not isinstance(value, Mapping):
        return None
    return {
        "schema_version": value.get("schema_version"),
        "status": value.get("status"),
        "carrier_ref": value.get("carrier_ref"),
        "concept_spine_ref": value.get("concept_spine_ref"),
        "jurisdiction_spine_ref": value.get("jurisdiction_spine_ref"),
        "runtime_claim_registry_ref": value.get("runtime_claim_registry_ref"),
        "producer_handshake_ledger_ref": value.get("producer_handshake_ledger_ref"),
        "handoff_ref_count": _summary_count(value, "handoff_ref_count"),
        "producer_binding_ref_count": _summary_count(value, "producer_binding_ref_count"),
        "authority_role": "projection_only",
        "may_not_use_for": [
            "producer_domain_truth",
            "runtime_closeout_authority",
            "scorecard_authority",
            "approval_authority",
        ],
    }


def _summary_count(value: Mapping[str, object], key: str) -> int:
    summary = value.get("summary")
    if not isinstance(summary, Mapping):
        return 0
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _looks_like_rule_evolution_annotation(value: Mapping[str, object]) -> bool:
    return value.get("schema_version") == RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION or (
        "public_annotation_state" in value
        and "revalidation_state" in value
        and "silent_upgrade_allowed" in value
    )


def _looks_like_public_revision_state(value: Mapping[str, object]) -> bool:
    return value.get("schema_version") == PUBLIC_REVISION_STATE_SCHEMA_VERSION or (
        "affected_claim_ids" in value
        and "unaffected_claim_ids" in value
        and "silent_upgrade_allowed" in value
        and value.get("authority_role") == "projection_only"
    )


def _is_unexplained_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    unexplained_count = 0
    if isinstance(summary, Mapping):
        try:
            unexplained_count = int(summary.get("unexplained_difference_count") or 0)
        except (TypeError, ValueError):
            unexplained_count = 0
    return status == "unexplained_drift" or (
        readiness in {"blocked", "fail", "failed"} and unexplained_count > 0
    )


def _is_unbounded_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    max_impact = ""
    if isinstance(summary, Mapping):
        max_impact = str(summary.get("max_impact") or "").strip().casefold()
    blocker = explanation.get("blocking_failure")
    blocker_code = str(blocker.get("code") or "").strip() if isinstance(blocker, Mapping) else ""
    return (
        status == "accepted_drift_non_ready"
        or blocker_code == "authority_replay_drift_unbounded"
        or (readiness in {"blocked", "fail", "failed"} and max_impact in {"medium", "high"})
    )


def assert_public_export_official_use_limits(bundle: Mapping[str, object]) -> None:
    """Fail closed if a public export is shaped like authority evidence."""

    evidence_class = str(bundle.get("evidence_class") or "").strip().casefold()
    authority_role = str(bundle.get("authority_role") or "").strip().casefold()
    provenance_kind = str(bundle.get("provenance_kind") or "").strip().casefold()
    if (
        evidence_class not in _PUBLIC_EXPORT_EVIDENCE_CLASSES
        or authority_role in _AUTHORITY_ROLES
        or authority_role not in _PUBLIC_EXPORT_AUTHORITY_ROLES
        or provenance_kind in _AUTHORITY_PROVENANCE_KINDS
    ):
        raise PublicExportRedactionError(
            "public_export_not_authority",
            "public exports must remain redacted projection-only artifacts",
        )

    limits = bundle.get("official_use_limits")
    if not isinstance(limits, Mapping):
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "official-use limits are required",
        )
    disallowed = {
        str(item) for item in _as_sequence(limits.get("may_not_be_used_for")) if str(item).strip()
    }
    required = {
        "approval_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
    if limits.get("official_use") != "public_audit_only" or not required <= disallowed:
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "public export must forbid scorecard, approval, and closeout authority use",
        )


def _authority_projection(envelope: AuthorityEnvelopeInput) -> dict[str, object]:
    validated = deserialize_authority_envelope(envelope)
    closure = validated.same_input_closure
    source_ref = validated.cas_ref or validated.artifact_ref
    return {
        "evidence_id": validated.evidence_id,
        "artifact_kind": validated.artifact_kind,
        "schema_name": validated.schema_name,
        "schema_version": validated.schema_version,
        "producer_component": validated.producer_component,
        "owner": validated.owner,
        "phase": validated.phase,
        "validation_status": validated.validation_status,
        "source_blocking_status": validated.blocking_status,
        "source_authority_role": validated.authority_role,
        "source_evidence_class": validated.evidence_class,
        "source_provenance_kind": validated.provenance_kind,
        "authority_role": "projection_only",
        "evidence_class": "redacted_derived",
        "provenance_kind": "runtime_projection",
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "runtime_event_ref_fingerprint": _fingerprint(validated.runtime_event_ref),
        "source_authority_ref_fingerprint": _fingerprint(source_ref),
        "same_input_closure_status": closure.status,
        "same_input_closure_fingerprint": _fingerprint(
            closure.closure_sha256 or closure.closure_id
        ),
        "tenant_redacted": True,
        "tenant_fingerprint": _fingerprint(validated.tenant_id),
    }


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _text_list(value: object) -> list[str]:
    return _unique_texts(_as_sequence(value))


def _int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _unique_texts(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


__all__ = [
    "PUBLIC_EXPORT_REDACTION_POLICY_REF",
    "PUBLIC_EXPORT_SCHEMA_VERSION",
    "PublicExportRedactionError",
    "assert_public_export_official_use_limits",
    "build_public_export_bundle",
    "project_pre_n9_open_world_limitations",
    "project_promotion_open_world_limitation",
]
