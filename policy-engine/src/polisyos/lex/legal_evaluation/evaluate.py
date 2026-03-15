from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import ComponentId
from polisyos.core.contracts.lex import (
    ChangeProposalRef,
    LegalEvaluationRequest,
    LegalReportRef,
)
from polisyos.core.contracts.trinity import ModelSpecRef, PolicySpecRef
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_world_node_facts,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.kernel.base import ID_PATTERN
from polisyos.ir.trinity import TrinityBundle as TrinityPayloadBundle
from polisyos.ir.world.abi import NodeKind
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import artifact_id_to_world_id
from polisyos.lex.errors import LexNotReadyError, LexValidationError
from polisyos.lex.legal_evaluation.backends.simple_v1 import (
    RuleFinding,
    evaluate_rule_simple_v1,
)
from polisyos.lex.legal_evaluation.change_proposals import propose_changes_impl
from polisyos.lex.legal_evaluation.context_builder import LegalContextBuilder
from polisyos.lex.normpack.select_sources import normalize_as_of

logger = get_logger(__name__)

_ID_RE = re.compile(ID_PATTERN)


def _artifact_ref_payload(ref: Any) -> dict[str, Any]:
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": str(ref.kind),
    }


def _summary_from_findings(
    *,
    findings: list[RuleFinding],
    strict: bool,
) -> tuple[dict[str, int], str]:
    counts = {
        "pass": 0,
        "fail": 0,
        "unknown": 0,
        "not_applicable": 0,
    }
    for finding in findings:
        if finding.status == "PASS":
            counts["pass"] += 1
        elif finding.status == "FAIL":
            counts["fail"] += 1
        elif finding.status == "UNKNOWN":
            counts["unknown"] += 1
        elif finding.status == "NOT_APPLICABLE":
            counts["not_applicable"] += 1

    if counts["fail"] > 0:
        grade = "fail"
    elif counts["unknown"] > 0:
        grade = "fail" if strict else "partial"
    else:
        grade = "pass"
    return counts, grade


def _load_trinity_bundle_refs(
    *,
    cas: FileSystemCAS,
    trinity_bundle_ref: Any,
) -> tuple[PolicySpecRef, ModelSpecRef | None]:
    artifact_id = str(trinity_bundle_ref.artifact_id)
    try:
        payload = from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(artifact_id)))
    except FileNotFoundError as exc:
        raise LexNotReadyError(
            "missing trinity_bundle artifact",
            details={"artifact_id": artifact_id},
        ) from exc
    except Exception as exc:
        raise LexValidationError(
            "failed to read trinity_bundle artifact",
            details={"artifact_id": artifact_id},
        ) from exc

    if not isinstance(payload, dict):
        raise LexValidationError("trinity_bundle payload must be a JSON object")

    try:
        from polisyos.core.contracts.trinity import TrinityBundle as TrinityRefsBundle


        refs_bundle = TrinityRefsBundle.model_validate(payload)
        return refs_bundle.policy_spec_ref, refs_bundle.model_spec_ref
    except Exception as exc:
        logger.debug("Ignored exception: %s", exc)

    try:
        trinity_bundle = TrinityPayloadBundle.model_validate(payload)
    except Exception as exc:
        raise LexValidationError(
            "trinity_bundle payload is not a supported Trinity bundle shape"
        ) from exc

    policy_ref = cas.put_json(
        trinity_bundle.policy_spec.model_dump(mode="python"),
        opts=PutOptions(
            kind="ir.policy_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.PolicySpec",
                version=trinity_bundle.policy_spec.schema_version,
            ),
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate(artifact_id),
                    role="trinity_bundle",
                )
            ],
        ),
    )
    model_ref = cas.put_json(
        trinity_bundle.model_spec.model_dump(mode="python"),
        opts=PutOptions(
            kind="ir.model_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.ModelSpec",
                version=trinity_bundle.model_spec.schema_version,
            ),
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate(artifact_id),
                    role="trinity_bundle",
                )
            ],
        ),
    )
    return (
        PolicySpecRef(artifact_id=policy_ref.artifact_id),
        ModelSpecRef(artifact_id=model_ref.artifact_id),
    )


def _normalize_request(
    *,
    cas: FileSystemCAS,
    request: LegalEvaluationRequest,
) -> tuple[LegalEvaluationRequest, str, str, PolicySpecRef, ModelSpecRef | None]:
    jurisdiction_norm = request.jurisdiction.strip().casefold()
    if _ID_RE.fullmatch(jurisdiction_norm) is None:
        raise LexValidationError(f"jurisdiction must match {ID_PATTERN}: {request.jurisdiction!r}")

    as_of_norm = normalize_as_of(request.as_of)

    if request.norm_pack_ref.kind != "lex.norm_pack":
        raise LexValidationError(
            f"norm_pack_ref.kind must be 'lex.norm_pack', got {request.norm_pack_ref.kind!r}"
        )

    eval_policy_id = request.eval_policy_id.strip()
    if not eval_policy_id:
        raise LexValidationError("eval_policy_id is required")
    try:
        _ = ComponentId.parse(eval_policy_id)
    except Exception:
        if _ID_RE.fullmatch(eval_policy_id) is None:
            raise LexValidationError(
                f"eval_policy_id must be base_id ({ID_PATTERN}) or ComponentId"
            ) from None

    policy_spec_ref: PolicySpecRef | None = request.policy_spec_ref
    model_spec_ref: ModelSpecRef | None = request.model_spec_ref

    if request.trinity_bundle_ref is not None:
        if request.policy_spec_ref is not None or request.model_spec_ref is not None:
            raise LexValidationError(
                "exactly one policy input source is allowed: use trinity_bundle_ref OR policy refs"
            )
        policy_spec_ref, model_spec_ref = _load_trinity_bundle_refs(
            cas=cas,
            trinity_bundle_ref=request.trinity_bundle_ref,
        )
    elif policy_spec_ref is None:
        raise LexValidationError("policy_spec_ref is required when trinity_bundle_ref is not set")

    assert policy_spec_ref is not None
    normalized_request = LegalEvaluationRequest(
        schema_version=request.schema_version,
        jurisdiction=jurisdiction_norm,
        as_of=as_of_norm,
        trinity_bundle_ref=request.trinity_bundle_ref,
        policy_spec_ref=policy_spec_ref,
        model_spec_ref=model_spec_ref,
        simulation_result_ref=request.simulation_result_ref,
        norm_pack_ref=request.norm_pack_ref,
        eval_policy_id=eval_policy_id,
        strict=bool(request.strict),
    )
    return normalized_request, jurisdiction_norm, as_of_norm, policy_spec_ref, model_spec_ref


def _report_inputs(
    *,
    request: LegalEvaluationRequest,
    policy_spec_ref: PolicySpecRef,
    model_spec_ref: ModelSpecRef | None,
    metrics_artifact_id: str | None,
) -> list[InputRef]:
    inputs: list[InputRef] = [
        InputRef(
            artifact_id=ArtifactID.model_validate(str(policy_spec_ref.artifact_id)),
            role="policy_spec",
        ),
        InputRef(
            artifact_id=ArtifactID.model_validate(str(request.simulation_result_ref.artifact_id)),
            role="simulation_result",
        ),
        InputRef(
            artifact_id=ArtifactID.model_validate(str(request.norm_pack_ref.artifact_id)),
            role="norm_pack",
        ),
    ]
    if metrics_artifact_id is not None:
        inputs.append(
            InputRef(artifact_id=ArtifactID.model_validate(metrics_artifact_id), role="metrics")
        )
    if model_spec_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=ArtifactID.model_validate(str(model_spec_ref.artifact_id)),
                role="model_spec",
            )
        )
    return inputs


def evaluate_legality_impl(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: LegalEvaluationRequest,
    segment_name: str | None = None,
) -> tuple[LegalReportRef, list[ChangeProposalRef]]:
    (
        normalized_request,
        jurisdiction_norm,
        as_of_norm,
        policy_spec_ref,
        model_spec_ref,
    ) = _normalize_request(cas=cas, request=request)

    context = LegalContextBuilder(
        cas=cas,
        request=normalized_request,
        jurisdiction_norm=jurisdiction_norm,
        as_of_norm=as_of_norm,
        policy_spec_ref=policy_spec_ref,
    ).build()

    findings: list[RuleFinding] = []
    backend_quality_issues: list[dict[str, Any]] = []
    for rule in sorted(context.norm_pack.norms, key=lambda row: row.norm_id):
        observation = context.observations_by_rule_id[rule.norm_id]
        finding, rule_issues = evaluate_rule_simple_v1(
            rule=rule,
            observation=observation,
            strict=normalized_request.strict,
        )
        findings.append(finding)
        backend_quality_issues.extend(rule_issues)

    findings.sort(key=lambda row: row.rule_id)
    quality_issues = list(context.quality_issues) + backend_quality_issues
    quality_issues.sort(
        key=lambda issue: (
            str(issue.get("rule_id", "")),
            str(issue.get("code", "")),
            str(issue.get("details", "")),
        )
    )

    findings_payload = [
        {
            "rule_id": finding.rule_id,
            "status": finding.status,
            "severity": finding.severity,
            "norm_citations": finding.norm_citations,
            "observed_evidence_refs": finding.observed_evidence_refs,
            "observed_value": finding.observed_value,
            "expected": finding.expected,
            "rationale": finding.rationale,
        }
        for finding in findings
    ]

    counts, compliance_grade = _summary_from_findings(
        findings=findings,
        strict=normalized_request.strict,
    )

    artifacts_used = list(context.artifacts_used)
    if model_spec_ref is not None:
        model_artifact_id = str(model_spec_ref.artifact_id)
        if model_artifact_id not in artifacts_used:
            artifacts_used.append(model_artifact_id)

    report_payload = {
        "schema_version": "1.0",
        "request": {
            "jurisdiction": jurisdiction_norm,
            "as_of": as_of_norm,
            "policy_spec_ref": _artifact_ref_payload(policy_spec_ref),
            "model_spec_ref": _artifact_ref_payload(model_spec_ref) if model_spec_ref else None,
            "simulation_result_ref": _artifact_ref_payload(
                normalized_request.simulation_result_ref
            ),
            "norm_pack_ref": _artifact_ref_payload(normalized_request.norm_pack_ref),
            "eval_policy_id": normalized_request.eval_policy_id,
            "strict": normalized_request.strict,
        },
        "summary": {
            "counts": counts,
            "compliance_grade": compliance_grade,
        },
        "findings": findings_payload,
        "quality_issues": quality_issues,
        "artifacts_used": artifacts_used,
    }

    report_ref_payload = cas.put_json(
        report_payload,
        opts=PutOptions(
            kind="lex.legal_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.lex.LegalReport", version="1.0"),
            inputs=_report_inputs(
                request=normalized_request,
                policy_spec_ref=policy_spec_ref,
                model_spec_ref=model_spec_ref,
                metrics_artifact_id=str(context.simulation_result.metrics_ref.artifact_id),
            ),
        ),
    )
    report_ref = LegalReportRef(artifact_id=report_ref_payload.artifact_id)

    proposal_refs = propose_changes_impl(
        cas=cas,
        fact_log_root=fact_log_root,
        based_on_report_ref=report_ref,
        segment_name=segment_name,
    )

    semantic_facts: list[Any] = []
    report_world_id = artifact_id_to_world_id(
        prefix="artifact",
        artifact_id=str(report_ref.artifact_id),
    )
    semantic_facts.extend(
        emit_world_node_facts(
            node_id=report_world_id,
            kind=NodeKind.ARTIFACT,
            label=None,
            artifact_id=str(report_ref.artifact_id),
            props_ref=None,
            provenance=stable_world_provenance_v1(),
        )
    )

    proposal_world_ids: list[str] = []
    for proposal_ref in proposal_refs:
        proposal_world_id = artifact_id_to_world_id(
            prefix="artifact",
            artifact_id=str(proposal_ref.artifact_id),
        )
        proposal_world_ids.append(proposal_world_id)
        semantic_facts.extend(
            emit_world_node_facts(
                node_id=proposal_world_id,
                kind=NodeKind.ARTIFACT,
                label=None,
                artifact_id=str(proposal_ref.artifact_id),
                props_ref=None,
                provenance=stable_world_provenance_v1(),
            )
        )

    policy_world_id = artifact_id_to_world_id(
        prefix="artifact",
        artifact_id=str(policy_spec_ref.artifact_id),
    )
    simulation_world_id = artifact_id_to_world_id(
        prefix="artifact",
        artifact_id=str(normalized_request.simulation_result_ref.artifact_id),
    )
    norm_pack_world_id = artifact_id_to_world_id(
        prefix="artifact",
        artifact_id=str(normalized_request.norm_pack_ref.artifact_id),
    )
    inputs: list[WorldObjectRef] = [
        WorldObjectRef(world_id=policy_world_id),
        WorldObjectRef(world_id=simulation_world_id),
        WorldObjectRef(world_id=norm_pack_world_id),
        WorldObjectRef(artifact_id=str(context.simulation_result.metrics_ref.artifact_id)),
    ]
    if model_spec_ref is not None:
        inputs.append(
            WorldObjectRef(
                world_id=artifact_id_to_world_id(
                    prefix="artifact",
                    artifact_id=str(model_spec_ref.artifact_id),
                )
            )
        )

    outputs = [WorldObjectRef(world_id=report_world_id)] + [
        WorldObjectRef(world_id=world_id) for world_id in proposal_world_ids
    ]

    event_time = datetime.fromisoformat(f"{as_of_norm}T00:00:00+00:00")
    event = build_deterministic_world_event(
        event_kind=EventKind.EVALUATE_LEGALITY,
        agent_id="prov.agent.lex_legal_eval",
        agent_type=ProvAgentType.SYSTEM,
        agent_label="Lex Legal Evaluation",
        activity_id="prov.activity.lex_legal_eval.evaluate",
        activity_type=ProvActivityType.EVALUATE_LEGALITY,
        activity_label="Evaluate legality",
        inputs=inputs,
        outputs=outputs,
        props={
            "jurisdiction": jurisdiction_norm,
            "as_of": as_of_norm,
            "eval_policy_id": normalized_request.eval_policy_id,
            "strict": normalized_request.strict,
            "counts": counts,
            "compliance_grade": compliance_grade,
        },
        started_at=event_time,
        ended_at=event_time,
    )

    facts = list(semantic_facts)
    persist_world_event_with_facts(cas=cas, event=event, facts=facts)
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "lex_legal_evaluate",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    return report_ref, proposal_refs


__all__ = [
    "evaluate_legality_impl",
]
