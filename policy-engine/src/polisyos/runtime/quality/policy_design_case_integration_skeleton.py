"""Wave 2 I2 walking skeleton over reusable Policy Design Case carriers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_REQUIRED_CAPABILITIES,
    build_capability_duty_record,
    build_capability_selection_ledger,
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry
from polisyos.runtime.quality.closeout_reader import (
    CloseoutModuleReaderSpec,
    build_closeout_reader_skeleton,
)
from polisyos.runtime.quality.concept_spine import (
    build_hybrid_concept_spine_carrier,
    build_producer_handshake_ledger,
    build_producer_handshake_record,
)
from polisyos.runtime.quality.cost_degradation import (
    build_cost_degradation_telemetry_from_quality_context,
)
from polisyos.runtime.quality.evidence_spine_handoff import (
    EvidenceSpineHandoff,
    build_evidence_spine_handoff_ledger,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_semantics,
)
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from polisyos.runtime.quality.soft_gate_telemetry import build_soft_gate_telemetry_report

WAVE2_I2_SCHEMA_VERSION = "policyos.runtime.policy_design_case.wave2_i2.v1"
WAVE2_I2_MANIFEST_SCHEMA_VERSION = "policyos.runtime.policy_design_case.wave2_i2_manifest.v1"


def build_wave2_policy_design_case_walking_skeleton(
    *,
    run_id: str = "run-wave2-i2",
    job_id: str = "job-wave2-i2",
    tenant_id: str = "tenant-wave2-i2",
    case_id: str = "pdc-wave2-i2",
    generated_at: datetime | None = None,
    include_projection_closeout_negative: bool = False,
) -> dict[str, Any]:
    """Build the Wave 2 I2 runtime seam using existing W2 carriers.

    The fixture is intentionally tiny, but it is not schema-only: the request
    becomes a concept-spine carrier, the deterministic producer emits a
    handshake, the claim registry consumes the spine context, the closeout
    reader consumes module-owned records, and a projection is derived from the
    validated Policy Design Case profile.
    """

    now = (generated_at or datetime(2026, 5, 22, 12, 0, tzinfo=UTC)).astimezone(UTC)
    authority_profile = "research"
    request_ref = _sha("1")
    concept_ref = _sha("2")
    jurisdiction_ref = _sha("3")
    producer_ref = _sha("4")
    registry_ref = _sha("5")
    case_ref = _sha("6")

    intent = build_policy_intent_envelope(
        intent_id="intent-wave2-i2",
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        policy_problem="MSME survival depends on targeted emergency credit access.",
        desired_outcome="Improve MSME survival without laundering prior cases into evidence.",
        proposed_intervention="Target a small credit guarantee to eligible wartime MSMEs.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-22",
        data_time="2025-Q4",
        requester_preferred_conclusion=None,
        requested_authority_level=authority_profile,
        affected_stakeholders=["wartime MSMEs", "public finance reviewers"],
        objectives=["prove the Wave 2 runtime seam"],
        assumptions=["deterministic fixture producer is narrow and non-general"],
        evidence_expectations=["claim-bound refs are current-run producer outputs"],
        authoring_provenance={
            "captured_by": "policyos.runtime.quality.wave2_walking_skeleton",
            "capture_ref": request_ref,
        },
        generated_at=now,
    )
    concept_spine = _concept_spine(
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        authority_profile=authority_profile,
        concept_ref=concept_ref,
        generated_at=now,
    )
    producer_fixture = _deterministic_producer_fixture(
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        producer_ref=producer_ref,
        concept_ref=concept_ref,
        jurisdiction_ref=jurisdiction_ref,
        generated_at=now,
    )
    handshake = build_producer_handshake_record(
        producer_component=producer_fixture["producer_component"],
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        state="emitted_binding",
        concept_spine_ref=concept_ref,
        jurisdiction_spine_ref=jurisdiction_ref,
        consumed_concept_refs=["concept.msme_survival_rate"],
        consumed_requirement_refs=["scenario.req.msme_credit_guarantee"],
        bindings=producer_fixture["bindings"],
        liveness_config={
            "default_deadline_s": 30.0,
            "default_retry_ceiling": 1,
        },
    )
    handshake_ledger = build_producer_handshake_ledger(
        [handshake],
        required_producers=(producer_fixture["producer_component"],),
        run_id=run_id,
    )
    claim_registry = _claim_registry(
        run_id=run_id,
        registry_ref=registry_ref,
        concept_ref=concept_ref,
        handshake_ledger=handshake_ledger,
        handshake=handshake,
    )
    handoff_ledger = _handoff_ledger(
        request_ref=request_ref,
        concept_spine=concept_spine,
        handshake=handshake,
        handshake_ledger=handshake_ledger,
        claim_registry=claim_registry,
        generated_at=now,
    )
    rule_evolution = build_rule_evolution_registry(
        registry_id="wave2-i2-rule-registry",
        version="2026.05.22",
        effective_at=now.isoformat(),
        rule_refs=[
            {
                "requirement_id": "scenario.req.msme_credit_guarantee",
                "logic": {"predicate": "eligible_wartime_msme", "threshold": "deterministic"},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation.v1",
                "version": "2026.05.22",
                "ref": _sha("7"),
            }
        ],
        evidence_ref=_sha("8"),
        runtime_event_ref="event://wave2-i2/rule-evolution",
    )
    cost_telemetry = build_cost_degradation_telemetry_from_quality_context(
        quality_evidence={},
        case={"run_id": run_id, "job_id": job_id},
        evidence_ref=_sha("9"),
        runtime_event_ref="event://wave2-i2/cost-degradation",
        canary_kind=authority_profile,
        now=now,
    )
    cost_telemetry["status"] = "observe"
    cost_telemetry["authority_role"] = "diagnostic_only"
    cost_telemetry["provenance_kind"] = "runtime_emitted"
    soft_gate_telemetry = build_soft_gate_telemetry_report(
        run_id=run_id,
        job_id=job_id,
        gates=[],
        generated_at=now,
    )
    historical_prior_firewall = _firewall_record(
        "historical_prior_firewall",
        "Historical priors are influence-only and cannot enter current claim evidence slots.",
    )
    memory_influence_firewall = _firewall_record(
        "memory_influence_firewall",
        (
            "Balanced memory guides future search/review and cannot enter current "
            "claim evidence slots."
        ),
    )
    pdc_profile = _policy_design_case(
        case_id=case_id,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        authority_profile=authority_profile,
        case_ref=case_ref,
        intent=intent,
        concept_spine=concept_spine,
        producer_fixture=producer_fixture,
        claim_registry=claim_registry,
        generated_at=now,
    )
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=pdc_profile,
        surface="final_artifact",
        source_payload={
            "artifact_kind": "publishable_decision_artifact",
            "publishability": "publishable",
            "decision_context": {"public_export_status": "publishable"},
            "authority_role": "final_decision_artifact",
        },
        source_ref=_sha("a"),
        generated_at=now,
    )
    closeout = build_closeout_reader_skeleton(
        run_id=run_id,
        module_readers=_wave2_closeout_readers(),
        module_records={
            "concept_spine": concept_spine,
            "evidence_spine_handoff": handoff_ledger,
            "producer_handshake": handshake_ledger,
            "claim_registry": claim_registry,
            "pdc_record_family_status": {"status": "pass", "schema_version": "wave2-i2.pdc"},
            "rule_evolution": rule_evolution,
            "cost_degradation_telemetry": cost_telemetry,
            "soft_gate_telemetry": soft_gate_telemetry,
            "historical_prior_firewall": historical_prior_firewall,
            "memory_influence_firewall": memory_influence_firewall,
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            },
        },
    )
    semantic_negative = _historical_prior_negative(run_id=run_id)
    artifacts = {
        "request": intent,
        "concept_spine": concept_spine,
        "deterministic_producer_fixture": producer_fixture,
        "producer_handshake_ledger": handshake_ledger,
        "evidence_spine_handoff_ledger": handoff_ledger,
        "claim_registry": claim_registry,
        "rule_evolution_registry": rule_evolution,
        "cost_degradation_telemetry": cost_telemetry,
        "soft_gate_telemetry": soft_gate_telemetry,
        "historical_prior_firewall": historical_prior_firewall,
        "memory_influence_firewall": memory_influence_firewall,
        "policy_design_case": pdc_profile,
        "closeout_verdict": closeout,
        "typed_projection": projection,
    }
    skeleton = {
        "schema_version": WAVE2_I2_SCHEMA_VERSION,
        "integration_slice": "I2",
        "status": (
            "pass" if closeout["can_closeout"] and semantic_negative["status"] == "fail" else "fail"
        ),
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "generated_at": now.isoformat(),
        "pattern_pass": {
            "relevant_patterns": ["P01", "P02", "P08", "P10", "P12", "P15"],
            "target_correct_pattern": "runtime seam proof over W2 carriers",
            "missing_capability_labels": [],
            "acceptance_signal": (
                "request -> concept spine -> producer handshake -> claim registry -> "
                "closeout reader -> projection, with historical-prior negative"
            ),
        },
        "capability_closures": {
            "W2.A": "implemented",
            "W2.B": "implemented",
            "W2.C": "implemented",
            "W2.D": "implemented",
            "W2.E": "implemented",
            "W2.F": "implemented",
        },
        "artifacts": artifacts,
        "semantic_negative": semantic_negative,
    }
    if include_projection_closeout_negative:
        skeleton["projection_closeout_negative"] = build_closeout_reader_skeleton(
            run_id=run_id,
            module_readers=(
                CloseoutModuleReaderSpec(
                    module_id="closeout_compatibility",
                    reader_contract="polisyos.runtime.quality.closeout_compatibility",
                    owner="team-quality-closeout",
                    stubbed=False,
                ),
            ),
            module_records={
                "closeout_compatibility": {
                    "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                    "status": "pass",
                    "producer_reader_matrix": [],
                    "issues": [],
                },
            },
            substitute_records=[projection],
        )
    return skeleton


def persist_wave2_policy_design_case_walking_skeleton(
    skeleton: Mapping[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    """Persist the I2 walking skeleton artifact set to a local evidence directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        str(key): value
        for key, value in (skeleton.get("artifacts") or {}).items()
        if isinstance(key, str)
    }
    artifact_paths: dict[str, str] = {}
    for key, payload in artifacts.items():
        filename = f"{_slug(key)}.json"
        path = output_dir / filename
        path.write_text(_json(payload), encoding="utf-8")
        artifact_paths[key] = filename
    for key in ("semantic_negative", "projection_closeout_negative"):
        payload = skeleton.get(key)
        if isinstance(payload, Mapping):
            filename = f"{_slug(key)}.json"
            (output_dir / filename).write_text(_json(payload), encoding="utf-8")
            artifact_paths[key] = filename
    closeout = artifacts.get("closeout_verdict") if isinstance(artifacts, Mapping) else {}
    concept_spine = artifacts.get("concept_spine") if isinstance(artifacts, Mapping) else {}
    handshake = artifacts.get("producer_handshake_ledger") if isinstance(artifacts, Mapping) else {}
    manifest = {
        "schema_version": WAVE2_I2_MANIFEST_SCHEMA_VERSION,
        "integration_slice": skeleton.get("integration_slice"),
        "status": skeleton.get("status"),
        "run_id": skeleton.get("run_id"),
        "artifact_count": len(artifact_paths),
        "artifact_paths": artifact_paths,
        "refs": {
            "concept_spine": _mapping(concept_spine).get("concept_spine_ref"),
            "producer_handshake_ledger": _mapping(handshake).get(
                "producer_handshake_ledger_ref"
            ),
            "closeout_verdict": _mapping(_mapping(closeout).get("authority_envelope")).get(
                "reader_contract"
            ),
        },
    }
    (output_dir / "manifest.json").write_text(_json(manifest), encoding="utf-8")
    return manifest


def _concept_spine(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    authority_profile: str,
    concept_ref: str,
    generated_at: datetime,
) -> dict[str, Any]:
    return build_hybrid_concept_spine_carrier(
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        authority_profile=authority_profile,
        concept_spine_ref=concept_ref,
        generated_at=generated_at.isoformat(),
        governed_namespace_refs=[
            _namespace("policyos.metric.v1", "metric"),
            _namespace("policyos.population.v1", "population"),
            _namespace("policyos.time_role.v1", "time_role"),
        ],
        reconciled_concepts=[
            {
                "concept_id": "concept.msme_survival_rate",
                "concept_type": "metric",
                "label": "MSME survival rate",
                "namespace_refs": ["policyos.metric.v1"],
                "source_refs": ["request:intent-wave2-i2"],
                "producer_refs": ["deterministic_policy_fixture"],
                "status": "resolved",
                "time_roles": {
                    "policy_time": "2026-05-22",
                    "data_time": "2025-Q4",
                    "replay_time": generated_at.isoformat(),
                },
                "geography_refs": ["UA"],
                "population_refs": ["wartime-msmes"],
                "unit_refs": ["unit:rate"],
            }
        ],
    )


def _deterministic_producer_fixture(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    producer_ref: str,
    concept_ref: str,
    jurisdiction_ref: str,
    generated_at: datetime,
) -> dict[str, Any]:
    bindings = [
        _binding("binding.fixture.dataset", "dataset", "fixture.data.msme_panel"),
        _binding("binding.fixture.norm", "norm", "fixture.norm.msme_credit_eligibility"),
        _binding("binding.fixture.method", "method", "fixture.method.deterministic_delta"),
        _binding("binding.fixture.claim", "claim", "fixture.claim.msme_survival"),
    ]
    return {
        "schema_version": "policyos.runtime.policy_design_case.deterministic_producer_fixture.v1",
        "status": "pass",
        "producer_component": "deterministic_policy_fixture",
        "producer_ref": producer_ref,
        "cas_ref": producer_ref,
        "runtime_event_ref": "event://wave2-i2/deterministic-producer",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "concept_spine_ref": concept_ref,
        "jurisdiction_spine_ref": jurisdiction_ref,
        "generated_at": generated_at.isoformat(),
        "bindings": bindings,
    }


def _claim_registry(
    *,
    run_id: str,
    registry_ref: str,
    concept_ref: str,
    handshake_ledger: Mapping[str, Any],
    handshake: Mapping[str, Any],
) -> dict[str, Any]:
    return build_runtime_claim_registry(
        run_id=run_id,
        registry_ref=registry_ref,
        spine_context={
            "concept_spine_ref": concept_ref,
            "producer_handshake_ledger_ref": handshake_ledger["producer_handshake_ledger_ref"],
            "producer_handshake_refs": [handshake["handshake_id"]],
        },
        claims=[_positive_claim()],
    )


def _handoff_ledger(
    *,
    request_ref: str,
    concept_spine: Mapping[str, Any],
    handshake: Mapping[str, Any],
    handshake_ledger: Mapping[str, Any],
    claim_registry: Mapping[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    return build_evidence_spine_handoff_ledger(
        [
            EvidenceSpineHandoff(
                handoff_kind="concept_spine_to_producer",
                producer_ref="runtime.concept_spine",
                consumer_ref="deterministic_policy_fixture",
                parent_spine_ref=request_ref,
                input_refs=[request_ref],
                output_refs=[concept_spine["concept_spine_ref"]],
                carrier_ref=concept_spine["carrier_ref"],
                concept_spine_ref=concept_spine["concept_spine_ref"],
                bridge_authority_ref=concept_spine["bridge_authority"]["bridge_ref"],
            ),
            EvidenceSpineHandoff(
                handoff_kind="producer_to_claim_registry",
                producer_ref="deterministic_policy_fixture",
                consumer_ref="runtime.claim_registry",
                parent_spine_ref=concept_spine["concept_spine_ref"],
                input_refs=[handshake["handshake_id"]],
                output_refs=[claim_registry["runtime_claim_registry_ref"]],
                carrier_ref=handshake_ledger["producer_handshake_ledger_ref"],
                concept_spine_ref=concept_spine["concept_spine_ref"],
                producer_handshake_refs=[handshake["handshake_id"]],
                bridge_authority_ref=handshake["bridge_authority"]["bridge_ref"],
            ),
        ],
        required_handoff_kinds=("concept_spine_to_producer", "producer_to_claim_registry"),
        generated_at=generated_at,
    )


def _policy_design_case(
    *,
    case_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    authority_profile: str,
    case_ref: str,
    intent: Mapping[str, Any],
    concept_spine: Mapping[str, Any],
    producer_fixture: Mapping[str, Any],
    claim_registry: Mapping[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    capability_ledger = build_capability_selection_ledger(
        ledger_ref=_sha("b"),
        literature_evidence_required=False,
        duties=[
            build_capability_duty_record(
                capability=capability,
                state="selected",
                evidence_ref=_sha(_HEX_CHARS[index]),
                runtime_event_ref=f"event://wave2-i2/capability/{capability}",
                cas_ref=_sha(_HEX_CHARS[index]),
                reason="I2 deterministic fixture proves Wave 2 carrier wiring.",
            )
            for index, capability in enumerate(POLICY_DESIGN_REQUIRED_CAPABILITIES)
        ],
    )
    case = build_policy_design_case_profile(
        case_id=case_id,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        effective_execution_profile=authority_profile,
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": case_ref,
            "runtime_event_ref": "event://wave2-i2/policy-design-case",
            "same_input_closure_ref": _sha("c"),
            "effective_mode_ref": _sha("d"),
            "schema_compatibility_ref": _sha("e"),
        },
        capability_ledger=capability_ledger,
        intent_envelope=intent,
        nodes=[
            {"node_type": "policy_intent", "cas_ref": _sha("1"), **dict(intent)},
            {"node_type": "concept_spine", **dict(concept_spine)},
            {"node_type": "producer_evidence", **dict(producer_fixture)},
            {"node_type": "claim", **dict(claim_registry["claims"][0])},
        ],
        generated_at=generated_at,
    )
    case["major_claims"] = [
        {
            "claim_id": "claim.msme_credit_survival",
            "claim_ref": "fixture.claim.msme_survival",
            "major": True,
            "runtime_claim_registry_ref": claim_registry["runtime_claim_registry_ref"],
        }
    ]
    return case


def _historical_prior_negative(*, run_id: str) -> dict[str, Any]:
    registry = build_runtime_claim_registry(
        run_id=run_id,
        claims=[
            {
                **_positive_claim(),
                "data_refs": ["historical-prior-influence:msme-credit-v1"],
            }
        ],
    )
    return {
        "schema_version": "policyos.runtime.policy_design_case.wave2_i2_semantic_negative.v1",
        "negative_control": "historical_prior_claim_evidence_slot",
        "status": registry["status"],
        "issues": registry["issues"],
    }


def _positive_claim() -> dict[str, Any]:
    return {
        "claim_id": "claim.msme_credit_survival",
        "scenario_requirement_refs": ["scenario.req.msme_credit_guarantee"],
        "data_refs": ["fixture.data.msme_panel"],
        "selected_norm_refs": ["fixture.norm.msme_credit_eligibility"],
        "method_output_refs": ["fixture.method.deterministic_delta"],
        "portfolio_refs": ["fixture.portfolio.single"],
        "argument_refs": ["fixture.argument.credit_support"],
        "warrant_refs": ["fixture.warrant.admissible"],
        "rebuttal_refs": ["fixture.rebuttal.none_found"],
        "counter_evidence_refs": ["fixture.counter.stress_case"],
        "limitation_refs": ["fixture.limit.toy_policy_scope"],
        "accepted_deficit_refs": ["fixture.deficit.toy_scope_accepted"],
    }


def _wave2_closeout_readers() -> tuple[CloseoutModuleReaderSpec, ...]:
    return (
        _reader("concept_spine", "polisyos.runtime.quality.concept_spine"),
        _reader("evidence_spine_handoff", "polisyos.runtime.quality.evidence_spine_handoff"),
        _reader("producer_handshake", "polisyos.runtime.quality.concept_spine"),
        _reader("claim_registry", "polisyos.runtime.quality.claim_registry"),
        _reader("pdc_record_family_status", "polisyos.runtime.quality.policy_design_case"),
        _reader("rule_evolution", "polisyos.runtime.quality.rule_evolution"),
        _reader(
            "cost_degradation_telemetry",
            "polisyos.runtime.quality.cost_degradation",
            required=False,
        ),
        _reader(
            "soft_gate_telemetry",
            "polisyos.runtime.quality.soft_gate_telemetry",
            required=False,
        ),
        _reader("historical_prior_firewall", "polisyos.runtime.quality.calibration_ledger"),
        _reader("memory_influence_firewall", "polisyos.runtime.quality.memory_influence"),
        _reader("closeout_compatibility", "polisyos.runtime.quality.closeout_compatibility"),
    )


def _reader(module_id: str, contract: str, *, required: bool = True) -> CloseoutModuleReaderSpec:
    return CloseoutModuleReaderSpec(
        module_id=module_id,
        reader_contract=contract,
        owner="team-policyos-runtime",
        required=required,
        stubbed=False,
        next_wave_target="W2.I2",
    )


def _binding(binding_id: str, binding_kind: str, artifact_ref: str) -> dict[str, str]:
    return {
        "binding_id": binding_id,
        "binding_kind": binding_kind,
        "disposition": "selected",
        "concept_ref": "concept.msme_survival_rate",
        "requirement_ref": "scenario.req.msme_credit_guarantee",
        "artifact_ref": artifact_ref,
        "time_role": "policy_time",
    }


def _namespace(namespace_id: str, namespace_type: str) -> dict[str, object]:
    return {
        "namespace_id": namespace_id,
        "namespace_type": namespace_type,
        "scheme_owner": "team-policy-semantics",
        "scheme_version": "2026-05-22",
        "definition_ref": f"repo://policy-engine/architecture/concept-namespaces#{namespace_id}",
        "governed": True,
    }


def _firewall_record(record_id: str, statement: str) -> dict[str, Any]:
    return {
        "schema_version": f"policyos.runtime.policy_design_case.{record_id}.v1",
        "record_id": record_id,
        "status": "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "statement": statement,
        "may_not_use_for": ["claim_support", "current_run_evidence_closure"],
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sha(char: str) -> str:
    return "sha256:" + char * 64


_HEX_CHARS = "abcdef123"


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "artifact"


def _json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


__all__ = [
    "WAVE2_I2_MANIFEST_SCHEMA_VERSION",
    "WAVE2_I2_SCHEMA_VERSION",
    "build_wave2_policy_design_case_walking_skeleton",
    "persist_wave2_policy_design_case_walking_skeleton",
]
