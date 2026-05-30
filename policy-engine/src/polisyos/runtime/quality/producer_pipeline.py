"""Eight-stage producer pipeline orchestrator for Policy Design Case runs."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.runtime.quality.assurance_case import (
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.closeout_reader import (
    CloseoutModuleReaderSpec,
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.concept_spine import (
    ProducerHandshakeValidationError,
    build_producer_handshake_ledger,
    build_producer_handshake_record,
)
from polisyos.runtime.quality.producer_pipeline_corpus_stub import (
    build_corpus_stub_adapter_reports,
    corpus_stub_authority_boundary,
)

PRODUCER_PIPELINE_SCHEMA_VERSION = "policyos.runtime.producer_pipeline.v1"
PRODUCER_PIPELINE_FEATURE_FLAG = "universal_pdc_producer_pipeline_8_stage"

ProducerPipelineState = Literal[
    "requested",
    "preflighted",
    "waiting_on_spine",
    "waiting_on_peer",
    "emitted_context_only",
    "emitted_binding",
    "blocked",
    "timed_out",
    "degraded",
    "rerun_required",
    "abandoned",
]
ProducerPipelineDisposition = Literal[
    "consumed",
    "emitted",
    "selected",
    "rejected",
    "blocked",
    "context_only",
]
ProducerPipelineBindingKind = Literal[
    "concept",
    "requirement",
    "dataset",
    "data_column",
    "norm",
    "method",
    "literature",
    "claim",
    "jurisdiction",
    "time",
    "geography",
    "unit",
    "label",
    "spine",
]

_STAGES: tuple[tuple[str, str], ...] = (
    ("run_contract_and_carrier", "Run contract and carrier"),
    ("spine_bootstrap", "Spine bootstrap"),
    ("parallel_preflight", "Parallel preflight"),
    ("first_pass_context_blocker_emission", "First-pass context/blocker emission"),
    ("provisional_claim_registry", "Provisional claim registry"),
    ("second_pass_authoritative_binding", "Second-pass authoritative binding"),
    ("semantic_closure", "Semantic closure"),
    ("closeout_and_projection", "Closeout and projection"),
)
_AUTHORITY_DISPOSITIONS = frozenset({"emitted", "selected", "rejected"})
_SECOND_PASS_REQUIREMENT_DISPOSITIONS = frozenset({"selected", "rejected", "blocked"})
_LLM_SOURCE_CLASSES = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})
_BLOCKING_STATES = frozenset(
    {
        "blocked",
        "timed_out",
        "degraded",
        "rerun_required",
        "abandoned",
        "waiting_on_peer",
        "waiting_on_spine",
    }
)
_BRIDGE_CLASSES = (
    "transport_carrier",
    "handoff_ledger",
    "binding_assertion",
    "producer_attestation",
    "reader_attestation",
    "diagnostic_projection",
    "closeout_evidence",
)


class ProducerPipelineBinding(BaseModel):
    """Pipeline-owned view of one producer binding before handshake emission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    binding_kind: ProducerPipelineBindingKind
    disposition: ProducerPipelineDisposition
    concept_ref: str | None = None
    requirement_ref: str | None = None
    artifact_ref: str | None = None
    label: str | None = None
    time_role: str | None = None
    bridge_ref: str | None = None
    capability_ref: str | None = None
    construct_ref: str | None = None
    capability_index_ref: str | None = None
    construct_registry_ref: str | None = None
    authority_composition_rule_ref: str | None = None
    conflict_marker_refs: tuple[str, ...] = Field(default=())
    source_class: str = "deterministic_producer"

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "concept_ref",
        "requirement_ref",
        "artifact_ref",
        "label",
        "time_role",
        "bridge_ref",
        "capability_ref",
        "construct_ref",
        "capability_index_ref",
        "construct_registry_ref",
        "authority_composition_rule_ref",
        "source_class",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: object) -> str | None:
        return _optional_text(value)

    @field_validator("conflict_marker_refs", mode="before")
    @classmethod
    def _strip_conflict_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    def to_handshake_binding(self) -> dict[str, Any]:
        """Return the subset accepted by the shared producer handshake contract."""

        payload = self.model_dump(mode="json", exclude_none=True)
        payload.pop("source_class", None)
        payload.pop("capability_ref", None)
        payload.pop("construct_ref", None)
        payload.pop("capability_index_ref", None)
        payload.pop("construct_registry_ref", None)
        payload.pop("authority_composition_rule_ref", None)
        payload.pop("conflict_marker_refs", None)
        return payload

    def to_binding_decision(self, *, producer_component: str) -> dict[str, Any]:
        """Return the pipeline-owned full binding decision payload."""

        payload = self.model_dump(mode="json", exclude_none=True)
        payload["producer_component"] = producer_component
        return payload


class ProducerPipelineProducer(BaseModel):
    """Static producer plan consumed by the eight-stage orchestrator.

    The model describes the producer handshake rather than reimplementing the
    producer. Family adapters remain the authority for data, legal, method,
    scholar, or participation truth; this object only carries their bounded
    liveness and binding declarations through W7.F.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer_component: str = Field(min_length=1)
    consumed_concept_refs: tuple[str, ...] = Field(default=())
    consumed_requirement_refs: tuple[str, ...] = Field(default=())
    expected_output_families: tuple[str, ...] = Field(default=())
    first_pass_state: ProducerPipelineState | None = None
    first_pass_bindings: tuple[ProducerPipelineBinding, ...] = Field(default=())
    first_pass_wait_conditions: tuple[Mapping[str, Any], ...] = Field(default=())
    second_pass_state: ProducerPipelineState | None = None
    second_pass_bindings: tuple[ProducerPipelineBinding, ...] = Field(default=())
    second_pass_wait_conditions: tuple[Mapping[str, Any], ...] = Field(default=())
    requested_deadline_s: float | None = Field(default=None, gt=0.0)
    requested_retries: int | None = Field(default=None, ge=0)
    required: bool = True

    @field_validator("producer_component")
    @classmethod
    def _strip_producer(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "consumed_concept_refs",
        "consumed_requirement_refs",
        "expected_output_families",
        mode="before",
    )
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


def run_eight_stage_producer_pipeline(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    request_ref: str,
    authority_profile: str,
    spine_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    producers: Sequence[ProducerPipelineProducer | Mapping[str, Any]],
    scenario_refs: Sequence[Any] = (),
    universal_grammar_compilation: Mapping[str, Any] | None = None,
    obligation_graph: Mapping[str, Any] | None = None,
    claim_decomposition: Mapping[str, Any] | None = None,
    liveness_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run W7.F staged producer orchestration over predeclared producer adapters.

    Args:
        run_id: Runtime run identifier.
        job_id: Runtime control-plane job identifier.
        tenant_id: Tenant or workspace identifier.
        request_ref: Stable request/carrier reference.
        authority_profile: Runtime authority profile requested by the run.
        spine_context: W6/W2 producer spine read context.
        claims: Claim records from claim decomposition or a compatible fixture.
        producers: Producer declarations for W7.A-E family adapters.
        scenario_refs: Optional scenario and baseline refs carried by the run.
        universal_grammar_compilation: Optional W6.A artifact reference payload.
        obligation_graph: Optional W6.C artifact reference payload.
        claim_decomposition: Optional W6.D artifact reference payload.
        liveness_config: Optional governed bounded-liveness config.

    Returns:
        A JSON-serializable producer pipeline report. The report is a bridge
        authority artifact: it can prove stage order, liveness state, and
        boundary continuity, never producer-domain truth.
    """

    run = {
        "run_id": _required_text(run_id),
        "job_id": _required_text(job_id),
        "tenant_id": _required_text(tenant_id),
        "request_ref": _required_text(request_ref),
        "authority_profile": _required_text(authority_profile),
    }
    producer_models = tuple(_producer_model(item) for item in producers)
    claim_rows = [dict(row) for row in claims if isinstance(row, Mapping)]
    scenario_ref_tuple = _text_tuple(scenario_refs)
    pipeline_ref = _stable_ref(
        "producer-pipeline",
        {
            **run,
            "scenario_refs": scenario_ref_tuple,
            "producer_components": [item.producer_component for item in producer_models],
        },
    )
    carrier = _run_contract_carrier(
        run=run,
        pipeline_ref=pipeline_ref,
        scenario_refs=scenario_ref_tuple,
        spine_context=spine_context,
    )
    spine_bootstrap = _spine_bootstrap(
        run=run,
        spine_context=spine_context,
        claims=claim_rows,
        universal_grammar_compilation=universal_grammar_compilation,
        obligation_graph=obligation_graph,
        claim_decomposition=claim_decomposition,
    )

    issues: list[dict[str, Any]] = []
    issues.extend(dict(blocker) for blocker in spine_bootstrap["blockers"])
    liveness_blockers: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    state_history: dict[str, list[str]] = {
        item.producer_component: [] for item in producer_models
    }
    blocked_producers: set[str] = set()

    for producer in producer_models:
        _append_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            state="requested",
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            issues=issues,
            liveness_blockers=liveness_blockers,
        )

    preflight_records = []
    for producer in producer_models:
        if spine_bootstrap["status"] != "pass":
            issue = _issue(
                "producer_pipeline_spine_bootstrap_blocked",
                (
                    "Producer preflight cannot proceed until shared W6/W2 spine "
                    "bootstrap inputs are pass."
                ),
                producer_component=producer.producer_component,
                phase="parallel_preflight",
                capability_label="bridge_missing",
                refs=tuple(
                    str(blocker.get("code"))
                    for blocker in spine_bootstrap["blockers"]
                    if isinstance(blocker, Mapping) and blocker.get("code")
                ),
            )
            issues.append(issue)
            record = _append_blocked_handshake(
                records=records,
                state_history=state_history,
                producer=producer,
                run=run,
                spine_context=spine_context,
                liveness_config=liveness_config,
                code=str(issue["code"]),
                message=str(issue["message"]),
            )
            blocked_producers.add(producer.producer_component)
            preflight_records.append(record)
            continue
        preflight_issue = _preflight_declaration_issue(producer)
        if preflight_issue is not None:
            issues.append(preflight_issue)
            record = _append_blocked_handshake(
                records=records,
                state_history=state_history,
                producer=producer,
                run=run,
                spine_context=spine_context,
                liveness_config=liveness_config,
                code=str(preflight_issue["code"]),
                message=str(preflight_issue["message"]),
            )
            blocked_producers.add(producer.producer_component)
            preflight_records.append(record)
            continue
        record = _append_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            state="preflighted",
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            issues=issues,
            liveness_blockers=liveness_blockers,
        )
        if _record_blocking(record):
            blocked_producers.add(producer.producer_component)
        preflight_records.append(record)
    preflight = _preflight_report(preflight_records, producer_models)

    first_pass_records: list[dict[str, Any]] = []
    for producer in producer_models:
        if producer.producer_component in blocked_producers:
            continue
        record = _first_pass_handshake(
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            issues=issues,
            liveness_blockers=liveness_blockers,
            records=records,
            state_history=state_history,
        )
        first_pass_records.append(record)
        if _record_blocking(record):
            blocked_producers.add(producer.producer_component)

    provisional_registry = _provisional_claim_registry(
        run=run,
        pipeline_ref=pipeline_ref,
        claims=claim_rows,
        producers=producer_models,
        first_pass_records=first_pass_records,
    )
    issues.extend(dict(issue) for issue in provisional_registry.get("issues", ()))

    second_pass_records: list[dict[str, Any]] = []
    for producer in producer_models:
        if producer.producer_component in blocked_producers:
            continue
        record = _second_pass_handshake(
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            issues=issues,
            liveness_blockers=liveness_blockers,
            records=records,
            state_history=state_history,
        )
        second_pass_records.append(record)
        if _record_blocking(record):
            blocked_producers.add(producer.producer_component)

    required_producers = tuple(
        producer.producer_component for producer in producer_models if producer.required
    )
    handshake_ledger = build_producer_handshake_ledger(
        records,
        required_producers=required_producers,
        run_id=run["run_id"],
    )
    selected_refs = _binding_refs(records, "selected_binding_refs")
    emitted_refs = _binding_refs(records, "emitted_binding_refs")
    rejected_refs = _binding_refs(records, "rejected_binding_refs")
    blocked_refs = _binding_refs(records, "blocked_binding_refs")
    context_only_refs = _binding_refs(records, "context_only_label_refs")
    producer_binding_decisions = _producer_binding_decisions(records)
    cross_modal_consistency = _cross_modal_consistency(producer_binding_decisions)

    pipeline_status = _pipeline_status(
        issues=issues,
        ledger=handshake_ledger,
        state_history=state_history,
        producer_models=producer_models,
    )
    semantic_closure = _semantic_closure(
        run=run,
        pipeline_ref=pipeline_ref,
        handshake_ledger=handshake_ledger,
        claims=claim_rows,
        selected_refs=(*selected_refs, *emitted_refs),
        rejected_refs=rejected_refs,
        blocked_refs=blocked_refs,
        context_only_refs=context_only_refs,
        status=pipeline_status,
    )
    readiness = _readiness_report(
        run=run,
        pipeline_ref=pipeline_ref,
        status=pipeline_status,
        issues=issues,
        liveness_blockers=liveness_blockers,
    )
    closeout = build_can_i_closeout_verdict(
        run_id=run["run_id"],
        module_readers=(
            CloseoutModuleReaderSpec(
                module_id="semantic_closure",
                reader_contract="polisyos.runtime.quality.producer_pipeline#semantic_closure",
                owner="team-runtime-quality",
                stubbed=False,
            ),
        ),
        module_records={"semantic_closure": semantic_closure},
        readiness_record=readiness,
    )
    projection = _projection_bridge(
        run=run,
        pipeline_ref=pipeline_ref,
        status=pipeline_status,
        closeout=closeout,
        selected_refs=selected_refs,
        blocked_refs=blocked_refs,
    )
    bundle_assembly = _bundle_assembly(pipeline_ref=pipeline_ref, status=pipeline_status)
    inspection = _inspection_report(pipeline_ref=pipeline_ref, status=pipeline_status)
    replay = _replay_patch(
        pipeline_ref=pipeline_ref,
        carrier=carrier,
        handshake_ledger=handshake_ledger,
        provisional_registry=provisional_registry,
    )
    control_plane = _control_plane_patch(
        pipeline_ref=pipeline_ref,
        readiness=readiness,
        handshake_ledger=handshake_ledger,
    )

    stage_issues = _issues_by_stage(issues)
    stages = [
        _stage(1, "run_contract_and_carrier", "pass", outputs=(carrier["carrier_ref"],)),
        _stage(
            2,
            "spine_bootstrap",
            "pass" if spine_bootstrap["status"] == "pass" else "blocked",
            outputs=(spine_bootstrap["spine_bootstrap_ref"],),
            issues=stage_issues.get("spine_bootstrap", ()),
        ),
        _stage(
            3,
            "parallel_preflight",
            (
                "pass"
                if all(not _record_blocking(record) for record in preflight_records)
                else "blocked"
            ),
            outputs=tuple(record["handshake_id"] for record in preflight_records),
            issues=stage_issues.get("parallel_preflight", ()),
        ),
        _stage(
            4,
            "first_pass_context_blocker_emission",
            (
                "pass"
                if all(not _record_blocking(record) for record in first_pass_records)
                else "blocked"
            ),
            outputs=tuple(record["handshake_id"] for record in first_pass_records),
            issues=stage_issues.get("first_pass_context_blocker_emission", ()),
        ),
        _stage(
            5,
            "provisional_claim_registry",
            provisional_registry["status"],
            outputs=(provisional_registry["provisional_claim_registry_ref"],),
            issues=stage_issues.get("provisional_claim_registry", ()),
        ),
        _stage(
            6,
            "second_pass_authoritative_binding",
            (
                "pass"
                if all(not _record_blocking(record) for record in second_pass_records)
                else "blocked"
            ),
            outputs=tuple(record["handshake_id"] for record in second_pass_records),
            issues=stage_issues.get("second_pass_authoritative_binding", ()),
        ),
        _stage(
            7,
            "semantic_closure",
            semantic_closure["status"],
            outputs=(semantic_closure["semantic_closure_ref"],),
            issues=stage_issues.get("semantic_closure", ()),
        ),
        _stage(
            8,
            "closeout_and_projection",
            "pass" if readiness["status"] == "pass" else "blocked",
            outputs=(projection["projection_ref"],),
            issues=stage_issues.get("closeout_and_projection", ()),
        ),
    ]

    report = {
        "schema_version": PRODUCER_PIPELINE_SCHEMA_VERSION,
        "producer_pipeline_ref": pipeline_ref,
        "feature_flag": PRODUCER_PIPELINE_FEATURE_FLAG,
        "status": pipeline_status,
        "capability_reality_label": "implemented",
        **run,
        "scenario_refs": list(scenario_ref_tuple),
        "run_contract_carrier": carrier,
        "spine_bootstrap": spine_bootstrap,
        "preflight": preflight,
        "stages": stages,
        "producer_handshake_records": records,
        "producer_binding_decisions": producer_binding_decisions,
        "cross_modal_consistency": cross_modal_consistency,
        "producer_handshake_ledger": handshake_ledger,
        "bounded_liveness_resolutions": _bounded_liveness_resolutions(records),
        "producer_state_summary": _producer_state_summary(state_history),
        "provisional_claim_registry": provisional_registry,
        "semantic_closure": semantic_closure,
        "closeout": closeout,
        "projection": projection,
        "readiness": readiness,
        "control_plane": control_plane,
        "replay": replay,
        "bundle_assembly": bundle_assembly,
        "inspection": inspection,
        "bridge_class_table": _bridge_class_table(),
        "authority_boundary": _pipeline_authority_boundary(),
        "liveness_blockers": liveness_blockers,
        "issues": issues,
        "summary": {
            "producer_count": len(producer_models),
            "stage_count": len(stages),
            "handshake_record_count": len(records),
            "selected_binding_count": len(selected_refs),
            "rejected_binding_count": len(rejected_refs),
            "blocked_binding_count": len(blocked_refs),
            "context_only_label_count": len(context_only_refs),
            "issue_count": len(issues),
            "liveness_blocker_count": len(liveness_blockers),
        },
    }
    report["report_fingerprint"] = _stable_ref(
        "producer-pipeline-report",
        {key: value for key, value in report.items() if key != "report_fingerprint"},
    )
    return report


def run_requirement_spec_producer_pipeline(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    request_ref: str,
    authority_profile: str,
    spine_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    data_requirement_specs: Sequence[Any] = (),
    source_contract_candidates: Sequence[Mapping[str, Any]] = (),
    legal_authority_requirement_specs: Sequence[Any] = (),
    candidate_norms: Sequence[Mapping[str, Any]] = (),
    method_validity_requirement_specs: Sequence[Any] = (),
    candidate_methods: Sequence[Mapping[str, Any]] = (),
    scholar_support_requirement_specs: Sequence[Any] = (),
    scholar_evidence_bundle: Mapping[str, Any] | None = None,
    participation_provenance_requirement_specs: Sequence[Any] = (),
    participation_records: Sequence[Any] = (),
    capability_bindings: Sequence[Mapping[str, Any] | object] = (),
    observation_to_contract_manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    target_context: Mapping[str, Any] | None = None,
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
    voi_report: object | None = None,
    scenario_refs: Sequence[Any] = (),
    universal_grammar_compilation: Mapping[str, Any] | None = None,
    obligation_graph: Mapping[str, Any] | None = None,
    claim_decomposition: Mapping[str, Any] | None = None,
    liveness_config: Mapping[str, Any] | None = None,
    corpus_stub_responses: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the W7 producer pipeline over actual compiled RequirementSpec interfaces.

    This is the bridge from W7.A-E family adapters into W7.F. It does not mint
    producer-domain truth; each family adapter still decides selected/rejected/
    blocked semantics. The bridge only translates those adapter reports into the
    bounded-liveness producer handshakes consumed by the eight-stage orchestrator
    and attaches W7.G requirement-gap acquisition routing.
    """

    normalized_claims = [dict(row) for row in claims if isinstance(row, Mapping)]
    context = {
        "authority_profile": authority_profile,
        "as_of": _optional_text(_nested(spine_context, ("as_of",))) or "2026-05-23",
        **dict(target_context or {}),
    }
    concept_refs = _concept_refs_from_inputs(
        spine_context=spine_context,
        claims=normalized_claims,
        specs=(
            *data_requirement_specs,
            *legal_authority_requirement_specs,
            *method_validity_requirement_specs,
            *scholar_support_requirement_specs,
            *participation_provenance_requirement_specs,
        ),
    )

    if corpus_stub_responses is not None:
        stub_reports = build_corpus_stub_adapter_reports(
            run_id=run_id,
            responses=corpus_stub_responses,
            data_requirement_specs=data_requirement_specs,
            legal_authority_requirement_specs=legal_authority_requirement_specs,
            method_validity_requirement_specs=method_validity_requirement_specs,
            scholar_support_requirement_specs=scholar_support_requirement_specs,
            participation_provenance_requirement_specs=(
                participation_provenance_requirement_specs
            ),
            capability_index_ref=_capability_index_ref_from_bindings(
                capability_bindings
            ),
            construct_registry_ref=_construct_registry_ref_from_bindings(
                capability_bindings
            ),
            authority_composition_rule_ref=(
                _authority_composition_rule_ref_from_bindings(capability_bindings)
            ),
        )
        fabric_report = stub_reports["fabric"]
        lex_report = stub_reports["lex"]
        foundry_report = stub_reports["foundry"]
        scholar_report = stub_reports["scholar"]
        participation_report = stub_reports["participation"]
    else:
        fabric_report = _fabric_requirement_report(
            data_requirement_specs=data_requirement_specs,
            source_contract_candidates=source_contract_candidates,
            capability_bindings=capability_bindings,
        )
        lex_report = _lex_requirement_report(
            target_context=context,
            claims=normalized_claims,
            legal_authority_requirement_specs=legal_authority_requirement_specs,
            candidate_norms=candidate_norms,
            jurisdiction_fallback_config=jurisdiction_fallback_config,
            capability_bindings=capability_bindings,
        )
        foundry_report = _foundry_requirement_report(
            method_validity_requirement_specs=method_validity_requirement_specs,
            candidate_methods=candidate_methods,
            capability_bindings=capability_bindings,
            observation_to_contract_manifest=observation_to_contract_manifest,
        )
        scholar_report = _scholar_requirement_report(
            scholar_support_requirement_specs=scholar_support_requirement_specs,
            scholar_evidence_bundle=scholar_evidence_bundle,
            run_id=run_id,
            capability_bindings=capability_bindings,
        )
        participation_report = _participation_requirement_report(
            participation_provenance_requirement_specs=participation_provenance_requirement_specs,
            participation_records=participation_records,
            capability_bindings=capability_bindings,
        )

    producers = (
        _producer_from_adapter_report(
            component="fabric",
            requirement_refs=_requirement_ids(data_requirement_specs),
            concept_refs=concept_refs,
            output_family="fabric.source_contract_requirement_binding.v1",
            bindings=_fabric_pipeline_bindings(fabric_report),
        ),
        _producer_from_adapter_report(
            component="lex",
            requirement_refs=_requirement_ids(legal_authority_requirement_specs),
            concept_refs=concept_refs,
            output_family="lex.legal_authority_requirement_binding.v1",
            bindings=_lex_pipeline_bindings(lex_report),
        ),
        _producer_from_adapter_report(
            component="foundry",
            requirement_refs=_requirement_ids(method_validity_requirement_specs),
            concept_refs=concept_refs,
            output_family="foundry.method_requirement_selection.v1",
            bindings=_foundry_pipeline_bindings(foundry_report),
        ),
        _producer_from_adapter_report(
            component="scholar",
            requirement_refs=_requirement_ids(scholar_support_requirement_specs),
            concept_refs=concept_refs,
            output_family="scholar.support_requirement_binding.v1",
            bindings=_scholar_pipeline_bindings(scholar_report),
        ),
        _producer_from_adapter_report(
            component="participation",
            requirement_refs=_requirement_ids(participation_provenance_requirement_specs),
            concept_refs=concept_refs,
            output_family="participation.provenance_requirement_evaluation.v1",
            bindings=_participation_pipeline_bindings(participation_report),
        ),
    )

    report = run_eight_stage_producer_pipeline(
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        request_ref=request_ref,
        authority_profile=authority_profile,
        spine_context=spine_context,
        claims=normalized_claims,
        producers=producers,
        scenario_refs=scenario_refs,
        universal_grammar_compilation=universal_grammar_compilation,
        obligation_graph=obligation_graph,
        claim_decomposition=claim_decomposition,
        liveness_config=liveness_config,
    )

    acquisition_report = _requirement_gap_acquisition_report(
        run_id=run_id,
        data_requirement_specs=data_requirement_specs,
        legal_authority_requirement_specs=legal_authority_requirement_specs,
        method_validity_requirement_specs=method_validity_requirement_specs,
        scholar_support_requirement_specs=scholar_support_requirement_specs,
        participation_provenance_requirement_specs=participation_provenance_requirement_specs,
        voi_report=voi_report,
    )
    interfaces = {
        "fabric": fabric_report,
        "lex": lex_report,
        "foundry": foundry_report,
        "scholar": scholar_report,
        "participation": participation_report,
    }
    exit_gate = _compiled_requirement_exit_gate(
        specs_by_family={
            "data_requirement": data_requirement_specs,
            "legal_authority_requirement": legal_authority_requirement_specs,
            "method_validity_requirement": method_validity_requirement_specs,
            "scholar_support_requirement": scholar_support_requirement_specs,
            "participation_provenance_requirement": participation_provenance_requirement_specs,
        },
        producers=producers,
    )
    try:
        from polisyos.pdc import compile_runtime_policy_design_case

        runtime_pdc_graph = compile_runtime_policy_design_case(
            run_id=run_id,
            job_id=job_id,
            tenant_id=tenant_id,
            policy_design_case=_runtime_pdc_policy_design_case_profile(
                run_id=run_id,
                job_id=job_id,
                tenant_id=tenant_id,
                request_ref=request_ref,
                authority_profile=authority_profile,
                spine_context=spine_context,
                claims=normalized_claims,
            ),
            claims=normalized_claims,
            claim_registry=report.get("provisional_claim_registry")
            if isinstance(report.get("provisional_claim_registry"), Mapping)
            else None,
            semantic_binding=report.get("semantic_closure")
            if isinstance(report.get("semantic_closure"), Mapping)
            else None,
            closeout_verdict=report.get("closeout")
            if isinstance(report.get("closeout"), Mapping)
            else None,
            producer_pipeline_report=report,
            obligation_graph=obligation_graph,
            claim_decomposition=claim_decomposition,
        )
        report["runtime_pdc_graph"] = runtime_pdc_graph.model_dump(
            mode="json",
            exclude_none=True,
        )
    except ValueError as exc:
        code = getattr(exc, "code", "runtime_pdc_graph_compile_failed")
        report["runtime_pdc_graph_error"] = {
            "code": code,
            "severity": "blocked",
            "phase": "compiled_pdc_graph",
            "typed_integration_blocker": True,
            "capability_reality_label": "bridge_missing",
            "message": str(exc),
        }
    graph_smoke = _compiled_pdc_graph_smoke(report)
    report.update(
        {
            "compiled_requirement_interfaces": interfaces,
            "compiled_requirement_exit_gate": exit_gate,
            "acquisition_planner": acquisition_report,
            "compiled_pdc_graph_smoke": graph_smoke,
        }
    )
    if corpus_stub_responses is not None:
        report["corpus_stub"] = corpus_stub_authority_boundary(corpus_stub_responses)
    report["capability_reality_label"] = (
        "implemented"
        if exit_gate["status"] == "pass"
        and graph_smoke["status"] in {"pass", "blocked"}
        and report.get("capability_reality_label") == "implemented"
        else "bridge_missing"
    )
    report["report_fingerprint"] = _stable_ref(
        "producer-pipeline-report",
        {key: value for key, value in report.items() if key != "report_fingerprint"},
    )
    return report


def build_producer_pipeline_quality_evidence_surfaces(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a W7.F report into runtime quality evidence surface payloads.

    The projection is a wiring surface for control-plane progress, replay
    manifests, bundle assembly, inspection, and readiness readers. It does not
    upgrade producer-domain truth; the original report authority boundary is
    preserved inside the `producer_pipeline` payload.
    """

    _validate_pipeline_report(report)
    return {
        "producer_pipeline": dict(report),
        "producer_handshake_ledger": dict(_required_mapping(report, "producer_handshake_ledger")),
        "producer_pipeline_readiness": dict(_required_mapping(report, "readiness")),
        "producer_pipeline_control_plane": dict(_required_mapping(report, "control_plane")),
        "producer_pipeline_replay": dict(_required_mapping(report, "replay")),
        "producer_pipeline_bundle_assembly": dict(
            _required_mapping(report, "bundle_assembly")
        ),
        "producer_pipeline_inspection": dict(_required_mapping(report, "inspection")),
    }


def merge_producer_pipeline_quality_evidence_surfaces(
    quality_evidence: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Return `quality_evidence` with W7.F bridge surfaces added."""

    merged = dict(quality_evidence)
    merged.update(build_producer_pipeline_quality_evidence_surfaces(report))
    return merged


def _first_pass_handshake(
    *,
    producer: ProducerPipelineProducer,
    run: Mapping[str, str],
    spine_context: Mapping[str, Any],
    liveness_config: Mapping[str, Any] | None,
    issues: list[dict[str, Any]],
    liveness_blockers: list[dict[str, Any]],
    records: list[dict[str, Any]],
    state_history: dict[str, list[str]],
) -> dict[str, Any]:
    state = producer.first_pass_state
    if state in {"waiting_on_peer", "waiting_on_spine"}:
        return _append_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            state=state,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            wait_conditions=producer.first_pass_wait_conditions,
            issues=issues,
            liveness_blockers=liveness_blockers,
        )
    if not producer.first_pass_bindings:
        issue = _issue(
            "producer_pipeline_first_pass_missing",
            "Producer did not emit a first-pass context label or typed blocker.",
            producer_component=producer.producer_component,
            phase="first_pass_context_blocker_emission",
            capability_label="implemented_but_not_orchestrated",
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    if any(_first_pass_authority(binding) for binding in producer.first_pass_bindings):
        issue = _issue(
            "producer_pipeline_first_pass_authority_blocked",
            "First-pass producer output may emit context labels or typed blockers only.",
            producer_component=producer.producer_component,
            phase="first_pass_context_blocker_emission",
            capability_label="semantic_test_missing",
            refs=tuple(binding.binding_id for binding in producer.first_pass_bindings),
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    next_state: ProducerPipelineState = (
        "blocked"
        if any(binding.disposition == "blocked" for binding in producer.first_pass_bindings)
        else "emitted_context_only"
    )
    return _append_handshake(
        records=records,
        state_history=state_history,
        producer=producer,
        state=state or next_state,
        run=run,
        spine_context=spine_context,
        liveness_config=liveness_config,
        bindings=producer.first_pass_bindings,
        issues=issues,
        liveness_blockers=liveness_blockers,
    )


def _second_pass_handshake(
    *,
    producer: ProducerPipelineProducer,
    run: Mapping[str, str],
    spine_context: Mapping[str, Any],
    liveness_config: Mapping[str, Any] | None,
    issues: list[dict[str, Any]],
    liveness_blockers: list[dict[str, Any]],
    records: list[dict[str, Any]],
    state_history: dict[str, list[str]],
) -> dict[str, Any]:
    if producer.second_pass_state in {"waiting_on_peer", "waiting_on_spine"}:
        return _append_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            state=producer.second_pass_state,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            wait_conditions=producer.second_pass_wait_conditions,
            issues=issues,
            liveness_blockers=liveness_blockers,
        )
    if not producer.second_pass_bindings:
        issue = _issue(
            "producer_pipeline_second_pass_binding_missing",
            "Producer completed first pass but did not emit selected/rejected/blocked bindings.",
            producer_component=producer.producer_component,
            phase="second_pass_authoritative_binding",
            capability_label="implemented_but_not_orchestrated",
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    if not any(
        binding.disposition in _SECOND_PASS_REQUIREMENT_DISPOSITIONS
        for binding in producer.second_pass_bindings
    ):
        issue = _issue(
            "producer_pipeline_second_pass_authoritative_binding_missing",
            "Second-pass producer output must emit selected, rejected, or blocked bindings.",
            producer_component=producer.producer_component,
            phase="second_pass_authoritative_binding",
            capability_label="bridge_missing",
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    llm_bindings = [
        binding
        for binding in producer.second_pass_bindings
        if binding.disposition in _AUTHORITY_DISPOSITIONS
        and (binding.source_class or "").casefold() in _LLM_SOURCE_CLASSES
    ]
    if llm_bindings:
        issue = _issue(
            "producer_pipeline_llm_candidate_authority_blocked",
            "LLM candidate output cannot satisfy second-pass producer authority.",
            producer_component=producer.producer_component,
            phase="second_pass_authoritative_binding",
            capability_label="semantic_test_missing",
            refs=tuple(binding.binding_id for binding in llm_bindings),
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    missing_requirement = [
        binding.binding_id
        for binding in producer.second_pass_bindings
        if binding.disposition in _SECOND_PASS_REQUIREMENT_DISPOSITIONS
        and not binding.requirement_ref
    ]
    if missing_requirement:
        issue = _issue(
            "producer_pipeline_requirement_binding_missing",
            "Second-pass producer bindings must name the compiled RequirementSpec they answer.",
            producer_component=producer.producer_component,
            phase="second_pass_authoritative_binding",
            capability_label="bridge_missing",
            refs=tuple(missing_requirement),
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    unmatched_requirement = [
        binding.binding_id
        for binding in producer.second_pass_bindings
        if binding.disposition in _SECOND_PASS_REQUIREMENT_DISPOSITIONS
        and binding.requirement_ref not in producer.consumed_requirement_refs
    ]
    if unmatched_requirement:
        issue = _issue(
            "producer_pipeline_requirement_binding_unmatched",
            (
                "Second-pass producer bindings must answer one of the producer's "
                "declared compiled RequirementSpecs."
            ),
            producer_component=producer.producer_component,
            phase="second_pass_authoritative_binding",
            capability_label="bridge_missing",
            refs=tuple(unmatched_requirement),
        )
        issues.append(issue)
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=issue["code"],
            message=issue["message"],
        )
    state: ProducerPipelineState = producer.second_pass_state or (
        "blocked"
        if all(binding.disposition == "blocked" for binding in producer.second_pass_bindings)
        else "emitted_binding"
    )
    return _append_handshake(
        records=records,
        state_history=state_history,
        producer=producer,
        state=state,
        run=run,
        spine_context=spine_context,
        liveness_config=liveness_config,
        bindings=producer.second_pass_bindings,
        issues=issues,
        liveness_blockers=liveness_blockers,
    )


def _append_handshake(
    *,
    records: list[dict[str, Any]],
    state_history: dict[str, list[str]],
    producer: ProducerPipelineProducer,
    state: ProducerPipelineState,
    run: Mapping[str, str],
    spine_context: Mapping[str, Any],
    liveness_config: Mapping[str, Any] | None,
    issues: list[dict[str, Any]],
    liveness_blockers: list[dict[str, Any]],
    bindings: Sequence[ProducerPipelineBinding] = (),
    wait_conditions: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    try:
        record = build_producer_handshake_record(
            producer_component=producer.producer_component,
            run_id=run["run_id"],
            job_id=run["job_id"],
            tenant_id=run["tenant_id"],
            state=state,
            spine_context=spine_context,
            consumed_concept_refs=producer.consumed_concept_refs,
            consumed_requirement_refs=producer.consumed_requirement_refs,
            bindings=[binding.to_handshake_binding() for binding in bindings],
            wait_conditions=wait_conditions,
            liveness_config=liveness_config,
            requested_deadline_s=producer.requested_deadline_s,
            requested_retries=producer.requested_retries,
        )
    except (ProducerHandshakeValidationError, ValueError) as exc:
        code = getattr(exc, "code", "producer_handshake_validation_failed")
        issue = _issue(
            str(code),
            str(exc),
            producer_component=producer.producer_component,
            phase=_phase_for_state(state),
            state=state,
            capability_label="implemented_but_not_orchestrated",
        )
        issues.append(issue)
        liveness_blockers.append(
            _liveness_blocker(
                code=str(code),
                producer=producer,
                state=state,
                wait_conditions=wait_conditions,
                message=str(exc),
            )
        )
        return _append_blocked_handshake(
            records=records,
            state_history=state_history,
            producer=producer,
            run=run,
            spine_context=spine_context,
            liveness_config=liveness_config,
            code=str(code),
            message=str(exc),
        )
    if bindings:
        record["binding_decisions"] = [
            binding.to_binding_decision(producer_component=producer.producer_component)
            for binding in bindings
        ]
    records.append(record)
    state_history.setdefault(producer.producer_component, []).append(str(record["state"]))
    return record


def _append_blocked_handshake(
    *,
    records: list[dict[str, Any]],
    state_history: dict[str, list[str]],
    producer: ProducerPipelineProducer,
    run: Mapping[str, str],
    spine_context: Mapping[str, Any],
    liveness_config: Mapping[str, Any] | None,
    code: str,
    message: str,
) -> dict[str, Any]:
    blocker_ref = _stable_ref(
        "producer-pipeline-blocker",
        {
            "producer": producer.producer_component,
            "code": code,
            "message": message,
            "run_id": run["run_id"],
        },
    )
    binding = ProducerPipelineBinding(
        binding_id=blocker_ref,
        binding_kind="requirement",
        disposition="blocked",
        concept_ref=_first_ref(producer.consumed_concept_refs),
        requirement_ref=_first_ref(producer.consumed_requirement_refs)
        or f"producer-pipeline:{producer.producer_component}:requirement",
        label=code,
    )
    record = build_producer_handshake_record(
        producer_component=producer.producer_component,
        run_id=run["run_id"],
        job_id=run["job_id"],
        tenant_id=run["tenant_id"],
        state="blocked",
        spine_context=spine_context,
        consumed_concept_refs=producer.consumed_concept_refs,
        consumed_requirement_refs=producer.consumed_requirement_refs,
        bindings=[binding.to_handshake_binding()],
        liveness_config=liveness_config,
        requested_deadline_s=producer.requested_deadline_s,
        requested_retries=producer.requested_retries,
    )
    record["pipeline_blocker"] = {"code": code, "message": message, "blocker_ref": blocker_ref}
    records.append(record)
    state_history.setdefault(producer.producer_component, []).append("blocked")
    return record


def _run_contract_carrier(
    *,
    run: Mapping[str, str],
    pipeline_ref: str,
    scenario_refs: Sequence[str],
    spine_context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.producer_pipeline.run_contract_carrier.v1",
        "carrier_ref": f"{pipeline_ref}:carrier",
        "producer_pipeline_ref": pipeline_ref,
        **dict(run),
        "scenario_refs": list(scenario_refs),
        "concept_spine_boot_ref": _optional_text(spine_context.get("context_id"))
        or _optional_text(spine_context.get("concept_spine_ref")),
        "concept_spine_ref": _optional_text(spine_context.get("concept_spine_ref")),
        "jurisdiction_spine_ref": _optional_text(spine_context.get("jurisdiction_spine_ref")),
        "authority_boundary": _pipeline_authority_boundary(),
    }


def _spine_bootstrap(
    *,
    run: Mapping[str, str],
    spine_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    universal_grammar_compilation: Mapping[str, Any] | None,
    obligation_graph: Mapping[str, Any] | None,
    claim_decomposition: Mapping[str, Any] | None,
) -> dict[str, Any]:
    concept_ref = _optional_text(spine_context.get("concept_spine_ref"))
    jurisdiction_ref = _optional_text(spine_context.get("jurisdiction_spine_ref"))
    universal_grammar_ref = _payload_ref(universal_grammar_compilation)
    obligation_graph_ref = _payload_ref(obligation_graph)
    claim_decomposition_ref = _payload_ref(claim_decomposition)
    blockers = []
    if not concept_ref or not jurisdiction_ref:
        blockers.append(
            _issue(
                "producer_pipeline_spine_bootstrap_missing",
                "Shared run-level concept and jurisdiction spine refs are required.",
                phase="spine_bootstrap",
                severity="fail",
            )
        )
    if not universal_grammar_ref:
        blockers.append(
            _issue(
                "producer_pipeline_universal_grammar_missing",
                "W7.F spine bootstrap requires a W6.A universal grammar compilation ref.",
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
            )
        )
    elif blocked_status := _payload_blocked_status(universal_grammar_compilation):
        blockers.append(
            _issue(
                "producer_pipeline_universal_grammar_blocked",
                (
                    "W6.A universal grammar compilation is not pass and cannot feed "
                    "producer authority."
                ),
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
                refs=(universal_grammar_ref, blocked_status),
            )
        )
    if not obligation_graph_ref:
        blockers.append(
            _issue(
                "producer_pipeline_obligation_graph_missing",
                "W7.F spine bootstrap requires a W6.C obligation graph ref.",
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
            )
        )
    elif blocked_status := _payload_blocked_status(obligation_graph):
        blockers.append(
            _issue(
                "producer_pipeline_obligation_graph_blocked",
                (
                    "W6.C obligation graph is not pass and cannot feed producer "
                    "authority."
                ),
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
                refs=(obligation_graph_ref, blocked_status),
            )
        )
    if not claim_decomposition_ref:
        blockers.append(
            _issue(
                "producer_pipeline_claim_decomposition_missing",
                "W7.F spine bootstrap requires a W6.D claim decomposition ref.",
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
            )
        )
    elif blocked_status := _payload_blocked_status(claim_decomposition):
        blockers.append(
            _issue(
                "producer_pipeline_claim_decomposition_blocked",
                (
                    "W6.D claim decomposition is not pass and cannot feed producer "
                    "authority."
                ),
                phase="spine_bootstrap",
                severity="fail",
                capability_label="bridge_missing",
                refs=(claim_decomposition_ref, blocked_status),
            )
        )
    status = "pass" if not blockers else "blocked"
    payload = {
        "schema_version": "policyos.runtime.producer_pipeline.spine_bootstrap.v1",
        "run_id": run["run_id"],
        "status": status,
        "concept_spine_ref": concept_ref,
        "jurisdiction_spine_ref": jurisdiction_ref,
        "universal_grammar_compilation_ref": universal_grammar_ref,
        "obligation_graph_ref": obligation_graph_ref,
        "claim_decomposition_ref": claim_decomposition_ref,
        "claim_refs": [_claim_id(claim, index) for index, claim in enumerate(claims)],
        "blockers": blockers,
    }
    payload["spine_bootstrap_ref"] = _stable_ref("producer-pipeline-spine", payload)
    return payload


def _preflight_report(
    records: Sequence[Mapping[str, Any]],
    producers: Sequence[ProducerPipelineProducer],
) -> dict[str, Any]:
    records_by_producer = {
        _optional_text(record.get("producer_component")): record for record in records
    }
    declarations = []
    for producer in producers:
        record = records_by_producer.get(producer.producer_component) or {}
        declarations.append(
            {
                "producer_component": producer.producer_component,
                "consumed_concept_refs": list(producer.consumed_concept_refs),
                "consumed_requirement_refs": list(producer.consumed_requirement_refs),
                "expected_output_families": list(producer.expected_output_families),
                "deadline_s": _nested(record, ("liveness", "deadline_s")),
                "retry_ceiling": _nested(record, ("liveness", "retry_ceiling")),
                "handshake_id": record.get("handshake_id"),
            }
        )
    return {
        "schema_version": "policyos.runtime.producer_pipeline.preflight.v1",
        "status": "pass" if all(not _record_blocking(row) for row in records) else "blocked",
        "declarations": declarations,
    }


def _preflight_declaration_issue(
    producer: ProducerPipelineProducer,
) -> dict[str, Any] | None:
    missing_fields = []
    if not producer.consumed_concept_refs:
        missing_fields.append("consumed_concept_refs")
    if not producer.consumed_requirement_refs:
        missing_fields.append("consumed_requirement_refs")
    if not producer.expected_output_families:
        missing_fields.append("expected_output_families")
    if not missing_fields:
        return None
    issue = _issue(
        "producer_pipeline_preflight_declaration_missing",
        (
            "Parallel preflight producers must declare consumed concepts, "
            "compiled requirements, and expected output families before "
            "first-pass emission."
        ),
        producer_component=producer.producer_component,
        phase="parallel_preflight",
        capability_label="bridge_missing",
    )
    issue["missing_fields"] = missing_fields
    return issue


def _provisional_claim_registry(
    *,
    run: Mapping[str, str],
    pipeline_ref: str,
    claims: Sequence[Mapping[str, Any]],
    producers: Sequence[ProducerPipelineProducer],
    first_pass_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    producer_requirement_refs = [
        requirement
        for producer in producers
        for requirement in producer.consumed_requirement_refs
    ]
    context_only_refs = _binding_refs(first_pass_records, "context_only_label_refs")
    blocker_refs = _binding_refs(first_pass_records, "blocked_binding_refs")
    claim_payloads = []
    registry_issues = []
    for index, claim in enumerate(claims):
        requirement_refs = tuple(
            dict.fromkeys(
                [
                    *_refs_for(claim, "requirement_refs", "scenario_requirement_refs"),
                    *producer_requirement_refs,
                ]
            )
        )
        facet_refs = _refs_for(claim, "facet_refs")
        baseline_refs = _refs_for(claim, "baseline_refs")
        alternative_refs = _refs_for(claim, "alternative_refs")
        missing_binding_fields = [
            field_name
            for field_name, refs in (
                ("facet_refs", facet_refs),
                ("requirement_refs", requirement_refs),
                ("baseline_refs", baseline_refs),
                ("alternative_refs", alternative_refs),
            )
            if not refs
        ]
        if missing_binding_fields:
            issue = _issue(
                "producer_pipeline_claim_registry_binding_missing",
                (
                    "Provisional claim registry entries must bind claims to facets, "
                    "compiled requirements, baseline refs, and alternative refs."
                ),
                phase="provisional_claim_registry",
                refs=(_claim_id(claim, index),),
                capability_label="bridge_missing",
            )
            issue["missing_fields"] = missing_binding_fields
            registry_issues.append(issue)
        claim_payloads.append(
            {
                "claim_id": _claim_id(claim, index),
                "facet_refs": list(facet_refs),
                "requirement_refs": list(requirement_refs),
                "baseline_refs": list(baseline_refs),
                "alternative_refs": list(alternative_refs),
                "context_only_label_refs": list(context_only_refs),
                "selected_binding_refs": [],
                "blocker_refs": list(blocker_refs),
                "missing_binding_fields": missing_binding_fields,
            }
        )
    effective_blocker_refs = [
        *blocker_refs,
        *(str(issue["code"]) for issue in registry_issues),
    ]
    registry = {
        "schema_version": "policyos.runtime.producer_pipeline.provisional_claim_registry.v1",
        "run_id": run["run_id"],
        "producer_pipeline_ref": pipeline_ref,
        "status": "blocked" if effective_blocker_refs else "pass",
        "claims": claim_payloads,
        "issues": registry_issues,
        "authority_boundary": {
            "authoritative_for": ["claim_requirement_bridge"],
            "may_not_use_for": [
                "claim_authority",
                "producer_domain_truth",
                "public_projection_authority",
                "runtime_closeout_authority",
            ],
        },
    }
    registry["provisional_claim_registry_ref"] = _stable_ref(
        "producer-pipeline-provisional-claims",
        registry,
    )
    return registry


def _semantic_closure(
    *,
    run: Mapping[str, str],
    pipeline_ref: str,
    handshake_ledger: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    selected_refs: Sequence[str],
    rejected_refs: Sequence[str],
    blocked_refs: Sequence[str],
    context_only_refs: Sequence[str],
    status: str,
) -> dict[str, Any]:
    closure_status = (
        "pass"
        if status == "pass" and handshake_ledger.get("status") == "pass"
        else "blocked"
    )
    closure = {
        "schema_version": "policyos.runtime.producer_pipeline.semantic_closure.v1",
        "run_id": run["run_id"],
        "producer_pipeline_ref": pipeline_ref,
        "status": closure_status,
        "authority_role": "reader_attestation",
        "provenance_kind": "runtime_emitted",
        "producer_handshake_ledger_ref": handshake_ledger.get("producer_handshake_ledger_ref"),
        "selected_binding_refs": list(dict.fromkeys(selected_refs)),
        "rejected_binding_refs": list(dict.fromkeys(rejected_refs)),
        "blocked_binding_refs": list(dict.fromkeys(blocked_refs)),
        "context_only_label_refs": list(dict.fromkeys(context_only_refs)),
        "portfolio_refs": list(
            dict.fromkeys(ref for claim in claims for ref in _refs_for(claim, "portfolio_refs"))
        ),
        "effective_independence_refs": list(
            dict.fromkeys(
                ref
                for claim in claims
                for ref in _refs_for(claim, "effective_independence_refs", "independence_refs")
            )
        ),
        "argument_graph_refs": list(
            dict.fromkeys(
                ref
                for claim in claims
                for ref in (
                    *_refs_for(claim, "argument_refs"),
                    *_refs_for(claim, "warrant_refs"),
                )
            )
        ),
        "blockers": [
            {
                "code": "producer_pipeline_semantic_closure_blocked",
                "severity": "fail",
                "phase": "semantic_closure",
                "refs": list(dict.fromkeys(blocked_refs)),
            }
        ]
        if closure_status != "pass"
        else [],
        "authoritative_for": ["semantic_closure_bridge"],
        "may_not_use_for": [
            "producer_domain_truth",
            "claim_authority",
            "public_projection_authority",
            "evidence_strength",
        ],
    }
    closure["semantic_closure_ref"] = _stable_ref("producer-pipeline-semantic-closure", closure)
    return closure


def _readiness_report(
    *,
    run: Mapping[str, str],
    pipeline_ref: str,
    status: str,
    issues: Sequence[Mapping[str, Any]],
    liveness_blockers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    readiness_status = "pass" if status == "pass" else "blocked"
    return {
        "schema_version": "policyos.runtime.producer_pipeline.readiness.v1",
        "run_id": run["run_id"],
        "status": readiness_status,
        "producer_pipeline_ref": pipeline_ref,
        "authority_role": "readiness_input",
        "blocking_issue_codes": [
            str(issue["code"]) for issue in issues if issue.get("severity") == "fail"
        ],
        "liveness_blocker_count": len(liveness_blockers),
        "next_action": None
        if readiness_status == "pass"
        else "Repair the first failing producer pipeline blocker and rerun W7.F.",
    }


def _projection_bridge(
    *,
    run: Mapping[str, str],
    pipeline_ref: str,
    status: str,
    closeout: Mapping[str, Any],
    selected_refs: Sequence[str],
    blocked_refs: Sequence[str],
) -> dict[str, Any]:
    projection = {
        "schema_version": "policyos.runtime.producer_pipeline.projection_bridge.v1",
        "run_id": run["run_id"],
        "status": "pass" if status == "pass" else "blocked",
        "producer_pipeline_ref": pipeline_ref,
        "closeout_ref": _stable_ref("producer-pipeline-closeout", closeout),
        "selected_binding_refs": list(dict.fromkeys(selected_refs)),
        "blocked_binding_refs": list(dict.fromkeys(blocked_refs)),
        "authority_role": "diagnostic_projection",
        "provenance_kind": "runtime_projection",
        "authoritative_for": ["projection_ref_preservation"],
        "may_not_use_for": [
            "producer_domain_truth",
            "claim_authority",
            "runtime_closeout_authority",
        ],
    }
    projection["projection_ref"] = _stable_ref("producer-pipeline-projection", projection)
    return projection


def _bundle_assembly(*, pipeline_ref: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.producer_pipeline.bundle_assembly.v1",
        "status": "pass" if status == "pass" else "blocked",
        "producer_pipeline_ref": pipeline_ref,
        "authority_role": "packaging_only",
        "files": {
            "quality_evidence": {
                "producer_pipeline": "quality_evidence/producer_pipeline.json",
                "producer_handshake_ledger": "quality_evidence/producer_handshake_ledger.json",
                "producer_pipeline_readiness": "quality_evidence/producer_pipeline_readiness.json",
            }
        },
    }


def _inspection_report(*, pipeline_ref: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.producer_pipeline.inspection.v1",
        "status": "pass" if status == "pass" else "blocked",
        "components": [
            {
                "component_id": "producer_pipeline",
                "status": "pass" if status == "pass" else "blocked",
                "evidence_refs": ["quality_evidence/producer_pipeline.json"],
                "producer_pipeline_ref": pipeline_ref,
                "authority_role": "diagnostic_only",
            }
        ],
    }


def _replay_patch(
    *,
    pipeline_ref: str,
    carrier: Mapping[str, Any],
    handshake_ledger: Mapping[str, Any],
    provisional_registry: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.producer_pipeline.replay_patch.v1",
        "orchestration_continuity": {
            "producer_pipeline_ref": pipeline_ref,
            "carrier_ref": carrier.get("carrier_ref"),
            "concept_spine_ref": carrier.get("concept_spine_ref"),
            "jurisdiction_spine_ref": carrier.get("jurisdiction_spine_ref"),
            "producer_handshake_ledger_ref": handshake_ledger.get(
                "producer_handshake_ledger_ref"
            ),
            "provisional_claim_registry_ref": provisional_registry.get(
                "provisional_claim_registry_ref"
            ),
        },
        "manifest_patch": {
            "orchestration": {
                "producer_pipeline_ref": pipeline_ref,
                "producer_handshake_ledger_ref": handshake_ledger.get(
                    "producer_handshake_ledger_ref"
                ),
            }
        },
    }


def _control_plane_patch(
    *,
    pipeline_ref: str,
    readiness: Mapping[str, Any],
    handshake_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.producer_pipeline.control_plane_patch.v1",
        "progress_patch": {
            "producer_pipeline_ref": pipeline_ref,
            "producer_handshake_ledger_ref": handshake_ledger.get(
                "producer_handshake_ledger_ref"
            ),
            "producer_pipeline_readiness": readiness,
        },
        "workflow_state_patch": {
            "producer_pipeline_ref": pipeline_ref,
            "producer_handshake_ledger": handshake_ledger,
        },
    }


def _stage(
    sequence: int,
    stage_id: str,
    status: str,
    *,
    inputs: Sequence[str] = (),
    outputs: Sequence[str] = (),
    issues: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    title = dict(_STAGES)[stage_id]
    return {
        "stage": sequence,
        "stage_id": stage_id,
        "title": title,
        "status": status,
        "input_refs": list(inputs),
        "output_refs": list(outputs),
        "issue_codes": [
            str(issue.get("code")) for issue in issues if _optional_text(issue.get("code"))
        ],
    }


def _producer_state_summary(state_history: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    final_states = {
        producer: states[-1] if states else "abandoned"
        for producer, states in sorted(state_history.items())
    }
    counts = Counter(final_states.values())
    return {
        "final_states": final_states,
        "state_counts": dict(sorted(counts.items())),
        "state_history": {key: list(value) for key, value in sorted(state_history.items())},
    }


def _pipeline_status(
    *,
    issues: Sequence[Mapping[str, Any]],
    ledger: Mapping[str, Any],
    state_history: Mapping[str, Sequence[str]],
    producer_models: Sequence[ProducerPipelineProducer],
) -> str:
    if not producer_models:
        return "blocked"
    if any(issue.get("severity") == "fail" for issue in issues):
        return "blocked"
    if str(ledger.get("status") or "").casefold() != "pass":
        return "blocked"
    final_states = [states[-1] if states else "abandoned" for states in state_history.values()]
    if any(state in _BLOCKING_STATES for state in final_states):
        return "blocked"
    return "pass"


def _liveness_blocker(
    *,
    code: str,
    producer: ProducerPipelineProducer,
    state: str,
    wait_conditions: Sequence[Mapping[str, Any]],
    message: str,
) -> dict[str, Any]:
    first_wait = dict(wait_conditions[0]) if wait_conditions else {}
    required_fields = _text_tuple(first_wait.get("required_fields"))
    return {
        "code": code,
        "severity": "fail",
        "phase": _phase_for_state(state),
        "state": state,
        "producer_component": producer.producer_component,
        "peer_producer": _optional_text(first_wait.get("peer_producer")),
        "artifact_family": _optional_text(first_wait.get("artifact_family")),
        "required_fields": list(required_fields),
        "deadline_missing": first_wait.get("deadline_s") is None
        and _optional_text(first_wait.get("deadline_at")) is None,
        "message": message,
        "capability_label": "implemented_but_not_orchestrated",
        "next_action": (
            "Emit a finite wait condition naming peer producer, artifact family, "
            "required fields, and deadline before producer orchestration can proceed."
        ),
    }


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "fail",
    phase: str = "producer_pipeline",
    producer_component: str | None = None,
    refs: Sequence[Any] = (),
    state: str | None = None,
    capability_label: str | None = None,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "phase": phase,
        "message": message,
        "next_action": "Repair producer pipeline input and rerun W7.F.",
    }
    if producer_component is not None:
        payload["producer_component"] = producer_component
    if refs:
        payload["refs"] = list(_text_tuple(refs))
    if state is not None:
        payload["state"] = state
    if capability_label is not None:
        payload["capability_label"] = capability_label
    return payload


def _issues_by_stage(
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for issue in issues:
        grouped.setdefault(str(issue.get("phase") or "producer_pipeline"), []).append(issue)
    return {key: tuple(value) for key, value in grouped.items()}


def _first_pass_authority(binding: ProducerPipelineBinding) -> bool:
    if binding.disposition in _AUTHORITY_DISPOSITIONS:
        return True
    return binding.disposition == "context_only" and binding.artifact_ref is not None


def _record_blocking(record: Mapping[str, Any]) -> bool:
    status = str(record.get("status") or "").casefold()
    state = str(record.get("state") or "").casefold()
    return status in {"blocked", "fail", "failed"} or state in _BLOCKING_STATES


def _binding_refs(records: Sequence[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            ref for record in records for ref in _text_tuple(record.get(key))
        )
    )


def _producer_binding_decisions(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for record in records:
        for row in _rows(record.get("binding_decisions")):
            if _optional_text(row.get("disposition")) == "context_only":
                continue
            decisions.append(row)
    return decisions


def _cross_modal_consistency(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    capability_rows = [
        dict(row)
        for row in decisions
        if _optional_text(row.get("capability_ref"))
        and _optional_text(row.get("construct_ref"))
    ]
    conflict_refs = list(
        dict.fromkeys(
            ref
            for row in capability_rows
            for ref in _text_tuple(row.get("conflict_marker_refs"))
        )
    )
    construct_refs = sorted(
        {
            str(row["construct_ref"])
            for row in capability_rows
            if _optional_text(row.get("construct_ref"))
        }
    )
    capability_index_refs = sorted(
        {
            str(row["capability_index_ref"])
            for row in capability_rows
            if _optional_text(row.get("capability_index_ref"))
        }
    )
    construct_registry_refs = sorted(
        {
            str(row["construct_registry_ref"])
            for row in capability_rows
            if _optional_text(row.get("construct_registry_ref"))
        }
    )
    mismatches = []
    if len(capability_index_refs) > 1:
        mismatches.append("capability_index_ref_mismatch")
    if len(construct_registry_refs) > 1:
        mismatches.append("construct_registry_ref_mismatch")
    status = "blocked" if mismatches else "contested" if conflict_refs else "pass"
    return {
        "schema_version": "policyos.runtime.producer_pipeline.cross_modal_consistency.v1",
        "status": status,
        "construct_refs": construct_refs,
        "capability_index_refs": capability_index_refs,
        "construct_registry_refs": construct_registry_refs,
        "conflict_marker_refs": conflict_refs,
        "mismatch_codes": mismatches,
        "binding_count": len(capability_rows),
        "authority_boundary": {
            "authoritative_for": ["cross_modal_ref_consistency"],
            "may_not_use_for": ["silent_conflict_resolution", "producer_domain_truth"],
        },
    }


def _bounded_liveness_resolutions(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for record in records:
        liveness = record.get("liveness")
        if not isinstance(liveness, Mapping):
            continue
        key = json.dumps(dict(liveness), sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(liveness))
    return rows


def _bridge_class_table() -> list[dict[str, Any]]:
    continuity_classes = {
        "handoff_ledger",
        "binding_assertion",
        "producer_attestation",
        "reader_attestation",
        "closeout_evidence",
    }
    return [
        {
            "bridge_class": bridge_class,
            "authoritative_for": ["boundary_continuity"]
            if bridge_class in continuity_classes
            else [],
            "may_not_use_for": [
                "producer_domain_truth",
                "claim_authority",
                "public_projection_authority",
                "evidence_strength",
            ],
        }
        for bridge_class in _BRIDGE_CLASSES
    ]


def _pipeline_authority_boundary() -> dict[str, Any]:
    return {
        "authority_role": "producer_pipeline_bridge",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": [
            "producer_pipeline_stage_order",
            "producer_liveness_state",
            "boundary_continuity",
        ],
        "may_not_use_for": [
            "producer_domain_truth",
            "claim_authority",
            "legal_authority",
            "data_authority",
            "method_validity",
            "participation_authority",
            "public_projection_authority",
            "evidence_strength",
        ],
    }


def _fabric_requirement_report(
    *,
    data_requirement_specs: Sequence[Any],
    source_contract_candidates: Sequence[Mapping[str, Any]],
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> dict[str, Any]:
    from polisyos.fabric import build_source_contract_requirement_bindings

    return build_source_contract_requirement_bindings(
        data_requirement_specs=data_requirement_specs,
        source_contract_candidates=source_contract_candidates,
        capability_bindings=capability_bindings,
        selected_candidate_refs=(
            _optional_text(candidate.get("candidate_ref")) or ""
            for candidate in source_contract_candidates
        ),
    )


def _lex_requirement_report(
    *,
    target_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    legal_authority_requirement_specs: Sequence[Any],
    candidate_norms: Sequence[Mapping[str, Any]],
    jurisdiction_fallback_config: Mapping[str, Any] | None,
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> dict[str, Any]:
    from polisyos.lex import build_legal_authority_report

    report = build_legal_authority_report(
        target_context=target_context,
        candidate_norms=candidate_norms,
        recommendation_claims=claims,
        legal_requirement_specs=legal_authority_requirement_specs,
        jurisdiction_fallback_config=jurisdiction_fallback_config,
        capability_bindings=capability_bindings,
    )
    records = list(_rows(report.get("legal_authority_records")))
    report["summary"] = {
        **dict(report.get("summary") if isinstance(report.get("summary"), Mapping) else {}),
        "selected": sum(1 for row in records if _legal_disposition(row) == "selected"),
        "rejected": sum(1 for row in records if _legal_disposition(row) == "rejected"),
        "blocked": sum(1 for row in records if _legal_disposition(row) == "blocked"),
    }
    return report


def _foundry_requirement_report(
    *,
    method_validity_requirement_specs: Sequence[Any],
    candidate_methods: Sequence[Mapping[str, Any]],
    capability_bindings: Sequence[Mapping[str, Any] | object],
    observation_to_contract_manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    from polisyos.foundry import select_method_candidates_for_requirements

    return select_method_candidates_for_requirements(
        candidate_methods=candidate_methods,
        method_requirements=method_validity_requirement_specs,
        capability_bindings=capability_bindings,
        observation_to_contract_manifest=observation_to_contract_manifest,
    )


def _scholar_requirement_report(
    *,
    scholar_support_requirement_specs: Sequence[Any],
    scholar_evidence_bundle: Mapping[str, Any] | None,
    run_id: str,
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> dict[str, Any]:
    if capability_bindings:
        from polisyos.scholar_requirement import (
            build_scholar_capability_requirement_bindings,
        )

        return build_scholar_capability_requirement_bindings(
            scholar_support_requirement_specs=scholar_support_requirement_specs,
            capability_bindings=capability_bindings,
        )
    if scholar_evidence_bundle is None:
        return {
            "schema_version": "policyos.scholar.academic_evidence_report.v1",
            "status": "blocked" if scholar_support_requirement_specs else "pass",
            "support_links": [],
            "literature_deficit_blockers": [
                {
                    "code": "scholar_requirement_evidence_bundle_missing",
                    "severity": "fail",
                    "requirement_id": requirement_id,
                    "capability_reality_label": "bridge_missing",
                }
                for requirement_id in _requirement_ids(scholar_support_requirement_specs)
            ],
            "support_requirement_specs": [
                _spec_payload(spec) for spec in scholar_support_requirement_specs
            ],
            "summary": {
                "support_link_count": 0,
                "blocked": len(scholar_support_requirement_specs),
            },
        }
    from polisyos.scholar import (
        build_scholar_academic_evidence_report_from_web_bundle,
    )

    evidence_ref = _sha256_ref(
        {
            "run_id": run_id,
            "producer": "scholar",
            "requirement_refs": _requirement_ids(scholar_support_requirement_specs),
        }
    )
    report = build_scholar_academic_evidence_report_from_web_bundle(
        scholar_evidence_ref=evidence_ref,
        bundle=scholar_evidence_bundle,
        corpus_snapshot_ref=f"corpus-snapshot:{_slug(run_id)}",
        lineage_ref=f"scholar-lineage:{_slug(run_id)}",
        requirement_specs=scholar_support_requirement_specs,
    )
    blockers = _rows(report.get("literature_deficit_blockers"))
    report["summary"] = {
        **dict(report.get("summary") if isinstance(report.get("summary"), Mapping) else {}),
        "support_link_count": len(_rows(report.get("support_links"))),
        "blocked": len(blockers),
    }
    return report


def _participation_requirement_report(
    *,
    participation_provenance_requirement_specs: Sequence[Any],
    participation_records: Sequence[Any],
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> dict[str, Any]:
    from polisyos.participation_requirement import evaluate_participation_requirement

    evaluations = [
        evaluate_participation_requirement(
            requirement,
            participation_records,
            capability_bindings=capability_bindings,
        )
        for requirement in participation_provenance_requirement_specs
    ]
    rows = [evaluation.model_dump(mode="json") for evaluation in evaluations]
    return {
        "schema_version": "policyos.participation_requirement.pipeline_evaluations.v1",
        "status": "blocked"
        if any(row["status"] in {"blocked", "missing"} for row in rows)
        else "pass",
        "evaluations": rows,
        "summary": {
            "satisfied": sum(1 for row in rows if row["status"] == "satisfied"),
            "downgraded": sum(1 for row in rows if row["status"] == "downgraded"),
            "blocked": sum(1 for row in rows if row["status"] in {"blocked", "missing"}),
        },
    }


def _requirement_gap_acquisition_report(
    *,
    run_id: str,
    data_requirement_specs: Sequence[Any],
    legal_authority_requirement_specs: Sequence[Any],
    method_validity_requirement_specs: Sequence[Any],
    scholar_support_requirement_specs: Sequence[Any],
    participation_provenance_requirement_specs: Sequence[Any],
    voi_report: object | None,
) -> dict[str, Any]:
    from polisyos.runtime.quality.acquisition_planner import (
        plan_requirement_gap_acquisition,
        requirement_gaps_from_compiled_specs,
    )

    gaps = requirement_gaps_from_compiled_specs(
        data_requirement_specs=data_requirement_specs,
        legal_authority_requirement_specs=legal_authority_requirement_specs,
        method_validity_requirement_specs=method_validity_requirement_specs,
        scholar_support_requirement_specs=scholar_support_requirement_specs,
        participation_provenance_requirement_specs=participation_provenance_requirement_specs,
    )
    return plan_requirement_gap_acquisition(
        run_id=run_id,
        requirement_gaps=gaps,
        voi_report=voi_report,
    ).model_dump(mode="json")


def _producer_from_adapter_report(
    *,
    component: str,
    requirement_refs: Sequence[str],
    concept_refs: Sequence[str],
    output_family: str,
    bindings: Sequence[ProducerPipelineBinding | Mapping[str, Any]],
) -> ProducerPipelineProducer:
    refs = _text_tuple(requirement_refs)
    first_pass = (
        ProducerPipelineBinding(
            binding_id=f"label.{component}.compiled_requirement_context",
            binding_kind="label",
            disposition="context_only",
            concept_ref=_first_ref(_text_tuple(concept_refs)),
            label=f"{component} consumed compiled RequirementSpec inputs",
            bridge_ref=f"bridge:{component}:compiled-requirements",
        ),
    )
    second_pass = tuple(
        binding
        if isinstance(binding, ProducerPipelineBinding)
        else ProducerPipelineBinding.model_validate(binding)
        for binding in bindings
    )
    if not second_pass and refs:
        second_pass = tuple(
            ProducerPipelineBinding(
                binding_id=f"binding.{component}.{_slug(ref)}.blocked",
                binding_kind="requirement",
                disposition="blocked",
                concept_ref=_first_ref(_text_tuple(concept_refs)),
                requirement_ref=ref,
                artifact_ref=f"blocker:{component}:{_slug(ref)}",
                label="adapter_emitted_no_requirement_binding",
            )
            for ref in refs
        )
    return ProducerPipelineProducer(
        producer_component=component,
        consumed_concept_refs=_text_tuple(concept_refs)
        or ("concept:compiled-policy-design-case",),
        consumed_requirement_refs=refs,
        expected_output_families=(output_family,),
        first_pass_bindings=first_pass,
        second_pass_bindings=second_pass,
        requested_deadline_s=5.0,
    )


def _fabric_pipeline_bindings(
    report: Mapping[str, Any],
) -> tuple[ProducerPipelineBinding, ...]:
    bindings: list[ProducerPipelineBinding] = []
    for row in _rows(report.get("source_contract_bindings") or report.get("bindings")):
        status = _optional_text(row.get("binding_status"))
        if status not in _SECOND_PASS_REQUIREMENT_DISPOSITIONS:
            continue
        requirement_ref = _optional_text(
            row.get("requirement_id") or row.get("data_requirement_id")
        )
        bindings.append(
            ProducerPipelineBinding(
                binding_id=(
                    f"binding.fabric."
                    f"{_slug(requirement_ref or row.get('source_family'))}.{status}"
                ),
                binding_kind="dataset",
                disposition=status,  # type: ignore[arg-type]
                requirement_ref=requirement_ref,
                artifact_ref=_optional_text(row.get("candidate_ref"))
                or _optional_text(row.get("source_family"))
                or f"fabric:{status}",
                label=_optional_text(row.get("reason_code")),
                bridge_ref="bridge:fabric:data_requirement",
                **_capability_binding_kwargs(row),
            )
        )
    return tuple(bindings)


def _lex_pipeline_bindings(
    report: Mapping[str, Any],
) -> tuple[ProducerPipelineBinding, ...]:
    bindings: list[ProducerPipelineBinding] = []
    for row in _rows(report.get("legal_authority_records")):
        disposition = _legal_disposition(row)
        requirement_ref = _optional_text(row.get("legal_requirement_ref"))
        bindings.append(
            ProducerPipelineBinding(
                binding_id=(
                    "binding.lex."
                    f"{_slug(row.get('legal_authority_record_id') or requirement_ref)}"
                ),
                binding_kind="norm",
                disposition=disposition,
                requirement_ref=requirement_ref,
                artifact_ref=_optional_text(row.get("norm_ref"))
                or _first_ref(_text_tuple(row.get("no_anchor_refs")))
                or _optional_text(row.get("blocker_ref"))
                or f"lex:{disposition}",
                label=_optional_text(row.get("legal_admissibility_grade")),
                bridge_ref="bridge:lex:legal_requirement",
                **_capability_binding_kwargs(row),
            )
        )
    return tuple(bindings)


def _foundry_pipeline_bindings(
    report: Mapping[str, Any],
) -> tuple[ProducerPipelineBinding, ...]:
    bindings: list[ProducerPipelineBinding] = []
    for method in _rows(report.get("selected_methods")):
        requirement_refs = _text_tuple(method.get("method_requirement_refs"))
        for requirement_ref in requirement_refs:
            bindings.append(
                ProducerPipelineBinding(
                    binding_id=f"binding.foundry.{_slug(method.get('method_id'))}.{_slug(requirement_ref)}",
                    binding_kind="method",
                    disposition="selected",
                    requirement_ref=requirement_ref,
                    artifact_ref=_optional_text(method.get("method_id"))
                    or f"method:{requirement_ref}",
                    label="method_requirement_satisfied",
                    bridge_ref="bridge:foundry:method_requirement",
                    **_capability_binding_kwargs(method),
                )
            )
    for rejected in _rows(report.get("rejected_methods")):
        requirement_ref = _optional_text(rejected.get("method_requirement_ref"))
        if not requirement_ref:
            continue
        bindings.append(
            ProducerPipelineBinding(
                binding_id=f"binding.foundry.{_slug(rejected.get('method_id'))}.{_slug(requirement_ref)}.rejected",
                binding_kind="method",
                disposition="rejected",
                requirement_ref=requirement_ref,
                artifact_ref=_optional_text(rejected.get("method_id"))
                or f"method-rejected:{requirement_ref}",
                label=_optional_text(rejected.get("reason_code")),
                bridge_ref="bridge:foundry:method_requirement",
                **_capability_binding_kwargs(rejected),
            )
        )
    for issue in _rows(report.get("issues")):
        requirement_ref = _optional_text(issue.get("method_requirement_ref"))
        if requirement_ref and not any(
            binding.requirement_ref == requirement_ref for binding in bindings
        ):
            bindings.append(
                ProducerPipelineBinding(
                    binding_id=f"binding.foundry.{_slug(requirement_ref)}.blocked",
                    binding_kind="method",
                    disposition="blocked",
                    requirement_ref=requirement_ref,
                    artifact_ref=f"blocker:foundry:{_slug(requirement_ref)}",
                    label=_optional_text(issue.get("code")),
                    bridge_ref="bridge:foundry:method_requirement",
                )
            )
    return tuple(bindings)


def _scholar_pipeline_bindings(
    report: Mapping[str, Any],
) -> tuple[ProducerPipelineBinding, ...]:
    blockers_by_requirement = {
        _optional_text(row.get("requirement_id") or row.get("support_requirement_ref"))
        for row in _rows(report.get("literature_deficit_blockers"))
    }
    bindings: list[ProducerPipelineBinding] = []
    for link in _rows(report.get("support_links")):
        requirement_ref = _optional_text(link.get("requirement_id"))
        if not requirement_ref:
            continue
        disposition: ProducerPipelineDisposition = (
            "blocked" if requirement_ref in blockers_by_requirement else "selected"
        )
        bindings.append(
            ProducerPipelineBinding(
                binding_id=f"binding.scholar.{_slug(requirement_ref)}.{disposition}",
                binding_kind="literature",
                disposition=disposition,
                requirement_ref=requirement_ref,
                artifact_ref=_optional_text(link.get("support_link_ref"))
                or _optional_text(link.get("evidence_ref"))
                or f"scholar:{requirement_ref}",
                label=_optional_text(link.get("support_status")) or "scholar_support",
                bridge_ref="bridge:scholar:support_requirement",
                **_capability_binding_kwargs(link),
            )
        )
    for blocker in _rows(report.get("literature_deficit_blockers")):
        requirement_ref = _optional_text(
            blocker.get("requirement_id") or blocker.get("support_requirement_ref")
        )
        if requirement_ref and not any(
            binding.requirement_ref == requirement_ref for binding in bindings
        ):
            bindings.append(
                ProducerPipelineBinding(
                    binding_id=f"binding.scholar.{_slug(requirement_ref)}.blocked",
                    binding_kind="literature",
                    disposition="blocked",
                    requirement_ref=requirement_ref,
                    artifact_ref=f"blocker:scholar:{_slug(requirement_ref)}",
                    label=_optional_text(blocker.get("code")),
                    bridge_ref="bridge:scholar:support_requirement",
                )
            )
    return tuple(bindings)


def _participation_pipeline_bindings(
    report: Mapping[str, Any],
) -> tuple[ProducerPipelineBinding, ...]:
    bindings: list[ProducerPipelineBinding] = []
    for row in _rows(report.get("evaluations")):
        status = _optional_text(row.get("status")) or "missing"
        disposition: ProducerPipelineDisposition = (
            "selected"
            if status in {"satisfied", "downgraded"}
            else "blocked"
            if status in {"blocked", "missing"}
            else "rejected"
        )
        requirement_ref = _optional_text(row.get("requirement_id"))
        bindings.append(
            ProducerPipelineBinding(
                binding_id=f"binding.participation.{_slug(requirement_ref)}.{disposition}",
                binding_kind="claim",
                disposition=disposition,
                requirement_ref=requirement_ref,
                artifact_ref=_optional_text(row.get("participation_ref"))
                or _optional_text(row.get("raw_material_ref"))
                or f"participation:{status}",
                label=_optional_text(row.get("blocker_code"))
                or _optional_text(row.get("downgrade_reason"))
                or status,
                bridge_ref="bridge:participation:provenance_requirement",
                **_capability_binding_kwargs(row),
            )
        )
    return tuple(bindings)


def _legal_disposition(row: Mapping[str, Any]) -> ProducerPipelineDisposition:
    grade = _optional_text(row.get("legal_admissibility_grade")) or "blocked"
    if grade in {"admissible", "proxy_with_limitation", "contested"}:
        return "selected"
    if grade in {"context_only", "out_of_scope"}:
        return "rejected"
    return "blocked"


def _capability_binding_kwargs(row: Mapping[str, Any]) -> dict[str, Any]:
    capability_ref = _optional_text(
        row.get("capability_ref") or row.get("selected_capability_ref")
    )
    payload: dict[str, Any] = {}
    for target, source in (
        ("capability_ref", capability_ref),
        ("construct_ref", row.get("construct_ref")),
        ("capability_index_ref", row.get("capability_index_ref")),
        ("construct_registry_ref", row.get("construct_registry_ref")),
        (
            "authority_composition_rule_ref",
            row.get("authority_composition_rule_ref") or row.get("rule_version_ref"),
        ),
    ):
        text = _optional_text(source)
        if text is not None:
            payload[target] = text
    conflict_refs = _text_tuple(
        row.get("conflict_marker_refs")
        or [
            ref
            for marker in _rows(row.get("conflict_markers"))
            if (ref := _optional_text(marker.get("conflict_id") or marker.get("marker_id")))
        ]
    )
    if conflict_refs:
        payload["conflict_marker_refs"] = conflict_refs
    return payload


def _capability_index_ref_from_bindings(
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> str | None:
    return _first_binding_text(capability_bindings, "capability_index_ref")


def _construct_registry_ref_from_bindings(
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> str | None:
    return _first_binding_text(capability_bindings, "construct_registry_ref")


def _authority_composition_rule_ref_from_bindings(
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> str | None:
    return _first_binding_text(
        capability_bindings,
        "authority_composition_rule_ref",
        "rule_version_ref",
    )


def _first_binding_text(
    capability_bindings: Sequence[Mapping[str, Any] | object],
    *keys: str,
) -> str | None:
    for raw in capability_bindings:
        row = _spec_payload(raw)
        if not isinstance(row, Mapping):
            continue
        for key in keys:
            text = _optional_text(row.get(key))
            if text is not None:
                return text
    return None


def _compiled_requirement_exit_gate(
    *,
    specs_by_family: Mapping[str, Sequence[Any]],
    producers: Sequence[ProducerPipelineProducer],
) -> dict[str, Any]:
    missing_specs = [family for family, specs in specs_by_family.items() if not specs]
    missing_bindings = [
        producer.producer_component
        for producer in producers
        if not any(
            binding.disposition in _SECOND_PASS_REQUIREMENT_DISPOSITIONS
            for binding in producer.second_pass_bindings
        )
    ]
    status = "pass" if not missing_specs and not missing_bindings else "blocked"
    return {
        "schema_version": "policyos.runtime.producer_pipeline.compiled_requirement_exit_gate.v1",
        "status": status,
        "missing_spec_families": missing_specs,
        "missing_binding_producers": missing_bindings,
        "requirement_counts": {
            family: len(specs) for family, specs in specs_by_family.items()
        },
        "adapter_binding_counts": {
            producer.producer_component: len(producer.second_pass_bindings)
            for producer in producers
        },
        "capability_reality_label": "implemented" if status == "pass" else "bridge_missing",
    }


def _runtime_pdc_policy_design_case_profile(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    request_ref: str,
    authority_profile: str,
    spine_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    first_claim = next((claim for claim in claims if isinstance(claim, Mapping)), {})
    claim_text = _optional_text(first_claim.get("text") or first_claim.get("claim_text"))
    jurisdiction_refs = _refs_for(spine_context, "jurisdiction_refs", "jurisdiction")
    period_refs = _refs_for(spine_context, "period_refs", "policy_time")
    intent = build_policy_intent_envelope(
        intent_id=request_ref,
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        policy_problem=_optional_text(first_claim.get("policy_problem"))
        or f"Compiled policy request {request_ref}",
        desired_outcome=_optional_text(first_claim.get("desired_outcome"))
        or claim_text
        or "Compile an admissible policy design case.",
        proposed_intervention=_optional_text(first_claim.get("proposed_intervention"))
        or claim_text
        or "Compiled policy intervention",
        jurisdiction=jurisdiction_refs[0] if jurisdiction_refs else "runtime_jurisdiction",
        target_population=_optional_text(first_claim.get("population_scope"))
        or "affected_population",
        policy_time=period_refs[0] if period_refs else "runtime_policy_time",
        data_time=_optional_text(first_claim.get("data_time")) or "runtime_data_time",
        requester_preferred_conclusion=None,
        requested_authority_level=authority_profile,
        authoring_provenance={"request_ref": request_ref},
    )
    return build_policy_design_case_profile(
        case_id=f"runtime-pdc:{run_id}",
        run_id=run_id,
        job_id=job_id,
        tenant_id=tenant_id,
        effective_execution_profile=authority_profile,
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": f"runtime-pdc-profile:{run_id}",
            "runtime_event_ref": f"event://runtime-pdc-profile/{run_id}",
            "same_input_closure_ref": f"same-input:{run_id}",
            "effective_mode_ref": f"effective-mode:{authority_profile}",
            "schema_compatibility_ref": "schema-compatibility:runtime-pdc-profile",
        },
        capability_ledger={
            "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
            "ledger_ref": f"capability-ledger:{run_id}",
            "literature_evidence_required": True,
            "duties": [
                {
                    "capability": capability,
                    "state": "selected",
                    "owner": f"team-{capability}",
                    "evidence_ref": f"evidence:{run_id}:{capability}",
                    "runtime_event_ref": f"event://runtime-pdc-profile/{run_id}/{capability}",
                    "required": True,
                }
                for capability in (
                    "lex",
                    "fabric",
                    "scholar",
                    "foundry",
                    "scientist",
                    "compiler",
                    "review",
                    "publication",
                    "audit",
                )
            ],
        },
        intent_envelope=intent,
    )


def _compiled_pdc_graph_smoke(report: Mapping[str, Any]) -> dict[str, Any]:
    graph = report.get("runtime_pdc_graph")
    if isinstance(graph, Mapping):
        try:
            from polisyos.pdc import RuntimePolicyDesignCase

            typed = RuntimePolicyDesignCase.model_validate(dict(graph))
        except ValueError as exc:
            return {
                "schema_version": "policyos.runtime.compiled_pdc_graph_smoke.v1",
                "status": "blocked",
                "runtime_pdc_graph_ref": None,
                "blockers": [
                    {
                        "code": getattr(exc, "code", "i8_compiled_pdc_graph_invalid"),
                        "severity": "blocked",
                        "phase": "compiled_pdc_graph",
                        "typed_integration_blocker": True,
                        "capability_reality_label": "bridge_missing",
                        "message": str(exc),
                    }
                ],
                "capability_reality_label": "bridge_missing",
            }
        return {
            "schema_version": "policyos.runtime.compiled_pdc_graph_smoke.v1",
            "status": "pass",
            "runtime_pdc_graph_ref": typed.graph_ref,
            "claim_count": len(typed.claim_graph.claims),
            "edge_count": len(typed.claim_graph.edges),
            "warrant_structure_count": len(typed.warrant_structures),
            "authority_envelope": typed.authority_envelope.model_dump(mode="json"),
            "argument_graph_refs": [
                ref
                for structure in typed.warrant_structures
                for ref in (*structure.argument_refs, *structure.warrant_refs)
            ],
            "blockers": [],
            "capability_reality_label": "implemented",
        }
    graph_error = report.get("runtime_pdc_graph_error")
    if isinstance(graph_error, Mapping):
        blocker = dict(graph_error)
        blocker.setdefault("code", "i8_compiled_pdc_graph_compile_failed")
        blocker.setdefault("typed_integration_blocker", True)
        blocker.setdefault("capability_reality_label", "bridge_missing")
        return {
            "schema_version": "policyos.runtime.compiled_pdc_graph_smoke.v1",
            "status": "blocked",
            "runtime_pdc_graph_ref": None,
            "blockers": [blocker],
            "capability_reality_label": "bridge_missing",
        }
    return {
        "schema_version": "policyos.runtime.compiled_pdc_graph_smoke.v1",
        "status": "blocked",
        "runtime_pdc_graph_ref": None,
        "argument_graph_refs": [],
        "blockers": [
            {
                "code": "i8_compiled_pdc_graph_not_available",
                "severity": "blocked",
                "phase": "semantic_closure",
                "typed_integration_blocker": True,
                "capability_reality_label": "bridge_missing",
                "message": (
                    "Wave 7 compiled RequirementSpec pipeline reached semantic closure, "
                    "but Wave 8 RuntimePolicyDesignCase graph assembly is not available "
                    "for this fixture."
                ),
            }
        ],
        "capability_reality_label": "bridge_missing",
    }


def _concept_refs_from_inputs(
    *,
    spine_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    specs: Sequence[Any],
) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_text_tuple(spine_context.get("canonical_concept_refs")))
    refs.extend(_text_tuple(spine_context.get("concept_spine_ref")))
    for claim in claims:
        refs.extend(_refs_for(claim, "concept_spine_refs", "concept_refs"))
    for spec in specs:
        payload = _spec_payload(spec)
        refs.extend(_text_tuple(payload.get("concept_spine_refs")))
    return _text_tuple(refs) or ("concept:compiled-policy-design-case",)


def _requirement_ids(specs: Sequence[Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for spec in specs:
        ref = _optional_text(_spec_payload(spec).get("requirement_id"))
        if ref:
            refs.append(ref)
    return _text_tuple(refs)


def _spec_payload(spec: object) -> Mapping[str, Any]:
    if isinstance(spec, Mapping):
        return dict(spec)
    if hasattr(spec, "model_dump"):
        return spec.model_dump(mode="json")
    return {}


def _rows(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    rows = value if isinstance(value, (list, tuple)) else (value,)
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _producer_model(
    value: ProducerPipelineProducer | Mapping[str, Any],
) -> ProducerPipelineProducer:
    if isinstance(value, ProducerPipelineProducer):
        return value
    return ProducerPipelineProducer.model_validate(dict(value))


def _validate_pipeline_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != PRODUCER_PIPELINE_SCHEMA_VERSION:
        raise ValueError("producer pipeline report schema_version is unsupported")
    if not _optional_text(report.get("producer_pipeline_ref")):
        raise ValueError("producer pipeline report must include producer_pipeline_ref")


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"producer pipeline report is missing mapping field: {key}")
    return value


def _phase_for_state(state: str) -> str:
    if state in {"requested", "preflighted"}:
        return "parallel_preflight"
    if state in {"waiting_on_peer", "waiting_on_spine", "emitted_context_only", "blocked"}:
        return "first_pass_context_blocker_emission"
    return "second_pass_authoritative_binding"


def _payload_ref_or_default(payload: Mapping[str, Any] | None, default: str) -> str:
    if not isinstance(payload, Mapping):
        return default
    return _payload_ref(payload) or default


def _payload_ref(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    return (
        _optional_text(payload.get("ref"))
        or _optional_text(payload.get("artifact_ref"))
        or _optional_text(payload.get("cas_ref"))
        or _optional_text(payload.get("graph_ref"))
        or _stable_ref("producer-pipeline-input", payload)
    )


def _payload_blocked_status(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    status = str(payload.get("status") or "").strip().casefold()
    if status in {"blocked", "failed", "fail", "rejected", "timed_out", "degraded"}:
        return status
    return None


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _optional_text(claim.get("claim_id") or claim.get("id")) or f"claim-{index + 1}"


def _refs_for(claim: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_text_tuple(claim.get(key)))
    return tuple(dict.fromkeys(refs))


def _nested(payload: Mapping[str, Any], path: Sequence[str]) -> object:
    current: object = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _first_ref(values: Sequence[str]) -> str | None:
    return next((value for value in values if value), None)


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("value must be non-empty text")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, (list, tuple, set)) else (value,)
    refs: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _optional_text(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        refs.append(text)
    return tuple(refs)


def _slug(value: object) -> str:
    text = _optional_text(value) or "missing"
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-") or "missing"


def _stable_ref(prefix: str, payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(rendered).hexdigest()[:16]}"


def _sha256_ref(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(rendered).hexdigest()}"


__all__ = [
    "PRODUCER_PIPELINE_FEATURE_FLAG",
    "PRODUCER_PIPELINE_SCHEMA_VERSION",
    "ProducerPipelineBinding",
    "ProducerPipelineProducer",
    "build_producer_pipeline_quality_evidence_surfaces",
    "merge_producer_pipeline_quality_evidence_surfaces",
    "run_eight_stage_producer_pipeline",
    "run_requirement_spec_producer_pipeline",
]
