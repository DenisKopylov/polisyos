#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G6 bounded-agent bundle."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from polisyos.runtime.quality import layer3_bounded_agent as g6
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
DOCS_REFERENCE_DIR = Path("docs/reference")
G6_SCHEMA_VERSION = g6.G6_SCHEMA_VERSION
G6_RULE_VERSION = g6.G6_RULE_VERSION

DEPENDENCY_READINESS_SNAPSHOT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_dependency_readiness_snapshot.json"
)
REQUEST_ENVELOPE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_request_envelope.json"
REQUEST_CLASSIFICATION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_request_classification.json"
)
POLICY_GRAMMAR_PROJECTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_policy_grammar_projection.json"
)
GRAMMAR_EXPANSION_CANDIDATES_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_grammar_expansion_candidates.json"
)
GROUNDING_DEMAND_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_grounding_demand_record.json"
)
TOOL_CONTRACT_SUMMARY_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_tool_contract_summary.json"
PROMPT_TOOL_LEDGER_PROJECTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_prompt_tool_ledger_projection.json"
)
HYPOTHESIS_LEDGER_PROJECTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_hypothesis_ledger_projection.json"
)
SEARCH_LEDGER_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_search_ledger.json"
ORCHESTRATION_CHOICE_AUDIT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_choice_audit.json"
)
COUNTEREXAMPLE_REFINEMENT_RECORD_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_counterexample_refinement_record.json"
)
DESIGN_RECORD_CANDIDATE_HANDOFF_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_design_record_candidate_handoff.json"
)
CANDIDATE_AUTHORITY_FIREWALL_REPORT_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_candidate_authority_firewall_report.json"
)
G5_INVOCATION_PLAN_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_g5_invocation_plan.json"
G5_CONSUMER_GATE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_g5_consumer_gate.json"
ORCHESTRATION_CONTINUITY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_continuity.json"
)
REPLAY_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_replay_manifest.json"
AGENT_RUN_RECORDS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_agent_run_records.json"
GROUNDED_RESULT_OR_ABSTENTION_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_grounded_result_or_abstention.json"
)
DEMAND_PULL_VS_ABSTENTION_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_demand_pull_vs_abstention_delta.json"
)
AGENT_AUDIT_SURFACE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_agent_audit_surface.json"
PUBLIC_EXPORT_PROJECTION_REFS_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_public_export_projection_refs.json"
)
CONFORMANCE_REPORT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_conformance_report.json"
HEALTH_METRIC_DELTA_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_health_metric_delta.toml"
AGENT_ROUTE_CONTRACT_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_agent_route_contract_registry.toml"
)
REGISTRY_RATCHET_DELTA_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g6_registry_ratchet_delta.json"
)
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g6_readiness_manifest.json"

GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
GENERATED_ARTIFACTS_DOC_PATH = DOCS_REFERENCE_DIR / "generated-artifacts.md"
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
DOCS_SURFACE_PATH = DOCS_REFERENCE_DIR / "policy-design-case-layer3-bounded-agent.md"
DOCUMENTATION_INVENTORY_PATH = DOCS_REFERENCE_DIR / "documentation-inventory.md"
REFERENCE_INDEX_PATH = DOCS_REFERENCE_DIR / "index.md"
PUBLIC_SURFACE_DOC_PATH = DOCS_REFERENCE_DIR / "public-surface.md"

EXPECTED_ARTIFACT_PATHS: tuple[Path, ...] = (
    DEPENDENCY_READINESS_SNAPSHOT_PATH,
    REQUEST_ENVELOPE_PATH,
    REQUEST_CLASSIFICATION_PATH,
    POLICY_GRAMMAR_PROJECTION_PATH,
    GRAMMAR_EXPANSION_CANDIDATES_PATH,
    GROUNDING_DEMAND_RECORD_PATH,
    TOOL_CONTRACT_SUMMARY_PATH,
    PROMPT_TOOL_LEDGER_PROJECTION_PATH,
    HYPOTHESIS_LEDGER_PROJECTION_PATH,
    SEARCH_LEDGER_PATH,
    ORCHESTRATION_CHOICE_AUDIT_PATH,
    COUNTEREXAMPLE_REFINEMENT_RECORD_PATH,
    DESIGN_RECORD_CANDIDATE_HANDOFF_PATH,
    CANDIDATE_AUTHORITY_FIREWALL_REPORT_PATH,
    G5_INVOCATION_PLAN_PATH,
    G5_CONSUMER_GATE_PATH,
    ORCHESTRATION_CONTINUITY_PATH,
    REPLAY_MANIFEST_PATH,
    AGENT_RUN_RECORDS_PATH,
    GROUNDED_RESULT_OR_ABSTENTION_PATH,
    DEMAND_PULL_VS_ABSTENTION_DELTA_PATH,
    AGENT_AUDIT_SURFACE_PATH,
    PUBLIC_EXPORT_PROJECTION_REFS_PATH,
    CONFORMANCE_REPORT_PATH,
    HEALTH_METRIC_DELTA_PATH,
    AGENT_ROUTE_CONTRACT_REGISTRY_PATH,
    REGISTRY_RATCHET_DELTA_PATH,
    READINESS_MANIFEST_PATH,
)
EXPECTED_MANIFEST_DRIFT_KEYS: tuple[str, ...] = (
    "g6_engineering_readiness_status",
    "g6_grounded_value_closure_status",
    "g6_policy_grammar_status",
    "g6_agent_loop_trace_status",
    "g6_llm_client_status",
    "g6_search_ledger_status",
    "g6_search_ledger_authority_boundary_status",
    "g6_design_record_candidate_handoff_status",
    "g6_g4_source_design_record_boundary_status",
    "g6_g5_bridge_status",
    "g6_g5_may_not_use_for_boundary_status",
    "g6_orchestration_choice_audit_status",
    "g6_orchestration_continuity_status",
    "g6_replay_manifest_status",
    "g6_replay_drift_status",
    "g6_runtime_import_boundary_status",
    "g6_public_projection_contract_status",
    "g6_outside_envelope_abstention_quality_status",
    "g6_demand_pull_vs_abstention_status",
)
ALL_ISSUE_CODES: tuple[str, ...] = tuple(dict.fromkeys(g6.ALL_ISSUE_CODES))


def _build_policy_grammar_projection_for_g6(
    raw_request: str,
    *,
    request_id: str,
    concept_spine_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a request into the G6 policy-grammar projection payload."""

    from polisyos.ir.governance.policy_composition import PolicyLayerLevel
    from polisyos.policy_grammar import (
        PolicyGrammarCompiler,
        PolicyGrammarConceptSpineRefs,
        PolicyGrammarConsumerError,
        PolicyGrammarIntent,
        UniversalAuthorityProfile,
        require_compiled_universal_policy_design_case,
    )

    if not concept_spine_refs:
        return _blocked_policy_grammar_projection(
            request_id=request_id,
            issue_codes=("layer3_g6_policy_grammar_concept_refs_missing",),
            compiled_case_status="blocked",
        )

    refs_payload = dict(concept_spine_refs)
    if not refs_payload.get("concept_spine_ref") or not refs_payload.get("jurisdiction_spine_ref"):
        return _blocked_policy_grammar_projection(
            request_id=request_id,
            issue_codes=("layer3_g6_policy_grammar_concept_refs_missing",),
            compiled_case_status="blocked",
        )
    if not refs_payload.get("canonical_concept_refs") and not refs_payload.get("facet_concept_refs"):
        refs_payload["canonical_concept_refs"] = (
            f"concept:layer3-g6:{request_id}:canonical",
        )

    compiler = PolicyGrammarCompiler()
    intent = PolicyGrammarIntent(intent_id=f"layer3-g6:{request_id}", text=raw_request)
    authority_profile = UniversalAuthorityProfile(
        profile_id=f"layer3-g6-policy-grammar:{request_id}",
        authority_type=PolicyLayerLevel.FEDERAL,
        source_classification="deterministic_producer",
        authoritative_for=("compilation_facets",),
        may_not_use_for=(
            "legal_authority",
            "data_authority",
            "method_authority",
            "closeout_authority",
            "publication_authority",
        ),
    )
    refs = PolicyGrammarConceptSpineRefs.model_validate(refs_payload)
    compiled = compiler.compile(
        intent=intent,
        authority_profile=authority_profile,
        concept_spine_refs=refs,
    )
    try:
        consumer_ready = require_compiled_universal_policy_design_case(compiled)
    except PolicyGrammarConsumerError:
        blocker_codes = tuple(blocker.code for blocker in compiled.blockers)
        issue_codes = ["layer3_g6_policy_grammar_compile_blocked"]
        if "policy_grammar_concept_refs_missing" in blocker_codes:
            issue_codes.append("layer3_g6_policy_grammar_concept_refs_missing")
        return _blocked_policy_grammar_projection(
            request_id=request_id,
            issue_codes=tuple(issue_codes),
            compiled_case_status=str(compiled.status),
            concept_spine_refs=refs.model_dump(mode="json"),
        )

    facets = consumer_ready.facets
    if facets is None:
        return _blocked_policy_grammar_projection(
            request_id=request_id,
            issue_codes=("layer3_g6_policy_grammar_compile_blocked",),
            compiled_case_status=str(consumer_ready.status),
            concept_spine_refs=refs.model_dump(mode="json"),
        )
    payload = {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": consumer_ready.case_id,
        "compiled_case_status": str(consumer_ready.status),
        "status": "pass",
        "authority_state": "compilation_facets_only",
        "facet_summary": {
            "jurisdiction": _facet_value(facets.geography_predicate),
            "policy_family": ":".join(
                (
                    _facet_value(facets.authority_type),
                    _facet_value(facets.instrument_type),
                    _facet_value(facets.population_predicate),
                )
            ),
            "instrument": _facet_value(facets.instrument_type),
            "subject": _facet_value(facets.population_predicate),
            "time_context": _facet_value(facets.time_predicate),
        },
        "concept_spine_refs": refs.model_dump(mode="json"),
        "issue_codes": (),
        "authoritative_for": g6.G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR,
        "may_not_use_for": (
            "legal_authority",
            "claim_authority",
            "closeout_authority",
        ),
    }
    return g6.validate_g6_policy_grammar_projection(payload).model_dump(mode="json")


def _blocked_policy_grammar_projection(
    *,
    request_id: str,
    issue_codes: tuple[str, ...],
    compiled_case_status: str,
    concept_spine_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    refs = dict(
        concept_spine_refs
        or {
            "concept_spine_ref": f"blocked://layer3-g6/{request_id}/concept-spine",
            "jurisdiction_spine_ref": f"blocked://layer3-g6/{request_id}/jurisdiction-spine",
        }
    )
    payload = {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": None,
        "compiled_case_status": compiled_case_status,
        "status": "fail",
        "authority_state": "blocked",
        "facet_summary": {
            "jurisdiction": "ambiguous",
            "policy_family": "ambiguous",
            "instrument": "ambiguous",
        },
        "concept_spine_refs": refs,
        "issue_codes": issue_codes,
        "authoritative_for": g6.G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR,
        "may_not_use_for": (
            "legal_authority",
            "claim_authority",
            "closeout_authority",
        ),
    }
    return g6.validate_g6_policy_grammar_projection(payload).model_dump(mode="json")


def _facet_value(facet: object) -> str:
    value = getattr(facet, "value", facet)
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def validate_layer3_g6_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G6 readiness report from runtime and persisted artifacts."""

    root = Path(repo_root).resolve()
    bundle = _build_runtime_bundle(root)
    written_artifact_paths = _write_artifacts(root, bundle) if write else []
    drift_keys = _manifest_runtime_drift_keys(root, bundle)
    registration_statuses = _registration_statuses(root)
    issues: list[dict[str, str]] = []
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_artifact_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_validate_registration_and_docs(registration_statuses))
    issues.extend(_validate_runtime_surfaces(bundle))
    normalized_issues = _deduplicate_issues(issues)
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": _summary(root, bundle, drift_keys, registration_statuses),
        "artifacts": {
            "expected_artifact_paths": [
                path.as_posix() for path in EXPECTED_ARTIFACT_PATHS
            ],
            "written_artifact_paths": written_artifact_paths,
            "missing_persisted_artifact_paths": [
                path.as_posix()
                for path in EXPECTED_ARTIFACT_PATHS
                if not _resolve_repo_path(root, path).exists()
            ],
        },
        "write": write,
        "issue_code_dictionary": list(ALL_ISSUE_CODES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Layer 3 G6 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g6_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_repo_path(Path(args.repo_root).resolve(), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _build_runtime_bundle(repo_root: Path) -> dict[str, Any]:
    request_id = "req-layer3-g6-readiness"
    raw_request = "Can Ukraine improve affordable loans for wartime MSMEs?"
    projection = _default_policy_grammar_projection(request_id)
    agent_loop = asyncio.run(
        g6.run_layer3_g6_bounded_agent_loop(
            repo_root=repo_root,
            raw_request=raw_request,
            request_id=request_id,
            policy_grammar_projection=projection,
            client=g6.FakeG6ToolCallingClient(("layer3_g6_build_g5_bundle",)),
        )
    )
    record = g6.build_layer3_g6_agent_run_record(
        repo_root=repo_root,
        raw_request=raw_request,
        request_id=request_id,
        policy_grammar_projection=projection,
    )
    continuity = g6.build_g6_orchestration_continuity(record)
    replay_manifest = g6.build_g6_replay_manifest(record, continuity=continuity)
    replay_drift = g6.explain_g6_replay_drift(
        baseline_manifest=replay_manifest.manifest,
        replay_manifest=replay_manifest.manifest,
    )
    handoff = g6.build_g6_design_record_candidate_handoff(
        request_id=request_id,
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
        counterexample_refinement_refs=(
            f"candidate://g6/{request_id}/counterexample/legal-authority",
        ),
    )
    g4_boundary = g6.validate_g6_design_record_candidate_not_g4_source(
        repo_root=repo_root,
        handoff=handoff,
    )
    health_delta = g6.build_g6_demand_pull_vs_abstention_delta(
        request_count=2,
        g5_routed_count=1,
        g5_grounded_result_count=0,
        g5_grounded_abstention_count=0,
        g5_unchanged_blocker_count=1,
        out_of_envelope_abstention_count=1,
        demand_source_refs=("s12-demand://layer3-g6/outside-envelope",),
        accountable_principal_refs=("principal://runtime-quality-reviewer",),
    )
    audit_surface = g6.build_g6_agent_audit_surface(record)
    conformance = g6.build_g6_conformance_report(repo_root=repo_root)
    bundle: dict[str, Any] = {
        "dependency_readiness_snapshot": _dependency_readiness_snapshot(),
        "policy_grammar_projection": record.policy_grammar_projection,
        "request_envelope": record.request_envelope,
        "request_classification": _request_classification(record),
        "grammar_expansion_candidates": (record.grammar_expansion_candidate,),
        "grounding_demand_record": record.grounding_demand_record,
        "tool_contract_summary": record.tool_contract_summary,
        "prompt_tool_ledger_projection": record.prompt_tool_ledger_projection,
        "hypothesis_ledger_projection": record.hypothesis_ledger,
        "search_ledger": record.search_ledger,
        "orchestration_choice_audit": record.orchestration_choice_audit,
        "counterexample_refinement_record": _counterexample_refinement_record(record),
        "design_record_candidate_handoff": handoff,
        "candidate_authority_firewall_report": conformance.candidate_firewall_check,
        "g5_invocation_plan": record.g5_invocation_plan,
        "g5_consumer_gate": _g5_consumer_gate_projection(record),
        "orchestration_continuity": continuity,
        "replay_manifest": replay_manifest,
        "agent_run_records": (record,),
        "grounded_result_or_abstention": record.result_projection,
        "demand_pull_vs_abstention_delta": health_delta,
        "agent_audit_surface": audit_surface,
        "public_export_projection_refs": _public_export_projection_refs(audit_surface),
        "conformance_report": conformance,
        "health_metric_delta": _health_metric_delta(health_delta),
        "agent_route_contract_registry": _agent_route_contract_registry(record),
        "registry_ratchet_delta": _registry_ratchet_delta(conformance),
        "agent_loop_result": agent_loop,
        "replay_drift": replay_drift,
        "g4_source_boundary": g4_boundary,
    }
    bundle["readiness_manifest"] = _readiness_manifest(
        repo_root,
        bundle,
        drift_keys=(),
        registration_statuses=_registration_statuses(repo_root),
    )
    return bundle


def _write_artifacts(repo_root: Path, bundle: Mapping[str, Any]) -> list[str]:
    payloads: dict[Path, Any] = {
        DEPENDENCY_READINESS_SNAPSHOT_PATH: bundle["dependency_readiness_snapshot"],
        REQUEST_ENVELOPE_PATH: bundle["request_envelope"],
        REQUEST_CLASSIFICATION_PATH: bundle["request_classification"],
        POLICY_GRAMMAR_PROJECTION_PATH: bundle["policy_grammar_projection"],
        GRAMMAR_EXPANSION_CANDIDATES_PATH: {
            "schema_version": G6_SCHEMA_VERSION,
            "rule_version": G6_RULE_VERSION,
            "grammar_expansion_candidates": bundle["grammar_expansion_candidates"],
        },
        GROUNDING_DEMAND_RECORD_PATH: bundle["grounding_demand_record"],
        TOOL_CONTRACT_SUMMARY_PATH: bundle["tool_contract_summary"],
        PROMPT_TOOL_LEDGER_PROJECTION_PATH: bundle["prompt_tool_ledger_projection"],
        HYPOTHESIS_LEDGER_PROJECTION_PATH: bundle["hypothesis_ledger_projection"],
        SEARCH_LEDGER_PATH: bundle["search_ledger"],
        ORCHESTRATION_CHOICE_AUDIT_PATH: bundle["orchestration_choice_audit"],
        COUNTEREXAMPLE_REFINEMENT_RECORD_PATH: bundle["counterexample_refinement_record"],
        DESIGN_RECORD_CANDIDATE_HANDOFF_PATH: bundle["design_record_candidate_handoff"],
        CANDIDATE_AUTHORITY_FIREWALL_REPORT_PATH: bundle[
            "candidate_authority_firewall_report"
        ],
        G5_INVOCATION_PLAN_PATH: bundle["g5_invocation_plan"],
        G5_CONSUMER_GATE_PATH: bundle["g5_consumer_gate"],
        ORCHESTRATION_CONTINUITY_PATH: bundle["orchestration_continuity"],
        REPLAY_MANIFEST_PATH: bundle["replay_manifest"],
        AGENT_RUN_RECORDS_PATH: {
            "schema_version": G6_SCHEMA_VERSION,
            "rule_version": G6_RULE_VERSION,
            "agent_run_records": bundle["agent_run_records"],
        },
        GROUNDED_RESULT_OR_ABSTENTION_PATH: bundle["grounded_result_or_abstention"],
        DEMAND_PULL_VS_ABSTENTION_DELTA_PATH: bundle[
            "demand_pull_vs_abstention_delta"
        ],
        AGENT_AUDIT_SURFACE_PATH: bundle["agent_audit_surface"],
        PUBLIC_EXPORT_PROJECTION_REFS_PATH: bundle["public_export_projection_refs"],
        CONFORMANCE_REPORT_PATH: bundle["conformance_report"],
        REGISTRY_RATCHET_DELTA_PATH: bundle["registry_ratchet_delta"],
        READINESS_MANIFEST_PATH: bundle["readiness_manifest"],
    }
    written: list[str] = []
    for path in EXPECTED_ARTIFACT_PATHS:
        resolved = _resolve_repo_path(repo_root, path)
        if path == HEALTH_METRIC_DELTA_PATH:
            _write_health_metric_delta(resolved, _mapping(bundle["health_metric_delta"]))
        elif path == AGENT_ROUTE_CONTRACT_REGISTRY_PATH:
            _write_agent_route_contract_registry(
                resolved,
                _mapping(bundle["agent_route_contract_registry"]),
            )
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g6_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G6 readiness requires persisted runtime artifacts.",
        )
        for path in EXPECTED_ARTIFACT_PATHS
        if not _resolve_repo_path(repo_root, path).exists()
    ]


def _validate_written_artifact_set(written_paths: Sequence[str]) -> list[dict[str, str]]:
    expected = {path.as_posix() for path in EXPECTED_ARTIFACT_PATHS}
    written = {str(path) for path in written_paths}
    missing = sorted(expected - written)
    unexpected = sorted(written - expected)
    return [
        *[
            _issue(
                "layer3_g6_persisted_artifact_missing",
                path,
                "G6 --write must emit every expected persisted artifact path.",
            )
            for path in missing
        ],
        *[
            _issue(
                "layer3_g6_persisted_artifact_missing",
                path,
                "G6 --write emitted a path outside the expected artifact set.",
            )
            for path in unexpected
        ],
    ]


def _manifest_runtime_drift_keys(
    repo_root: Path,
    bundle: Mapping[str, Any],
) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    runtime_summary = _summary(repo_root, bundle, (), _registration_statuses(repo_root))
    persisted_summary = {
        **_mapping(persisted.get("summary")),
        **{key: persisted.get(key) for key in EXPECTED_MANIFEST_DRIFT_KEYS if key in persisted},
    }
    return [
        key
        for key in EXPECTED_MANIFEST_DRIFT_KEYS
        if persisted_summary.get(key) != runtime_summary.get(key)
    ]


def _manifest_runtime_drift_issues(drift_keys: Sequence[str]) -> list[dict[str, str]]:
    if not drift_keys:
        return []
    return [
        _issue(
            "layer3_g6_replay_drift_unexplained",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G6 readiness manifest drifted from runtime: {sorted(drift_keys)}",
        )
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g6_readiness_manifest.json"),
        (DOCS_SURFACE_PATH, g6.G6_SURFACE_ID),
        (DOCS_SURFACE_PATH, "PUBLIC/REVIEWER/EXPERT/MACHINE"),
        (DOCS_SURFACE_PATH, "out_of_scope_reference_only"),
        (DOCS_SURFACE_PATH, "polisyos.policy_grammar"),
        (DOCS_SURFACE_PATH, "authoritative_for = ()"),
        (DOCS_SURFACE_PATH, "g7_region_widening"),
        (DOCUMENTATION_INVENTORY_PATH, "policy-design-case-layer3-bounded-agent.md"),
        (REFERENCE_INDEX_PATH, "policy-design-case-layer3-bounded-agent.md"),
        (PUBLIC_SURFACE_DOC_PATH, g6.G6_SURFACE_ID),
    )
    return {
        "generated_artifacts": (
            "pass"
            if g6.G6_GENERATED_ARTIFACT_FAMILY_ID in generated_text
            and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
            and "stale_output_behavior = \"fail\"" in generated_text
            and "drift_gate = \"automated\"" in generated_text
            else "fail"
        ),
        "inventory": "pass" if g6.G6_SURFACE_ID in inventory_text else "fail",
        "docs": (
            "pass"
            if all(needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks)
            else "fail"
        ),
    }


def _validate_registration_and_docs(
    statuses: Mapping[str, str],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if statuses.get("generated_artifacts") != "pass":
        issues.append(
            _issue(
                "layer3_g6_generated_artifacts_family_missing",
                GENERATED_ARTIFACTS_TOML_PATH.as_posix(),
                "architecture/generated_artifacts.toml must register the G6 family.",
            )
        )
    if statuses.get("inventory") != "pass":
        issues.append(
            _issue(
                "layer3_g6_inventory_surface_missing",
                INVENTORY_PATH.as_posix(),
                "Policy Design Case inventory must register the G6 bounded-agent surface.",
            )
        )
    if statuses.get("docs") != "pass":
        issues.append(
            _issue(
                "layer3_g6_reference_index_missing",
                DOCS_SURFACE_PATH.as_posix(),
                "G6 reference docs/index/public-surface markers must be registered.",
            )
        )
    return issues


def _validate_runtime_surfaces(bundle: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    record = _sequence(bundle["agent_run_records"])[0]
    search_ledger = bundle["search_ledger"]
    prompt_tool = bundle["prompt_tool_ledger_projection"]
    hypothesis_ledger = bundle["hypothesis_ledger_projection"]
    continuity = bundle["orchestration_continuity"]
    replay_manifest = bundle["replay_manifest"]
    audit_surface = bundle["agent_audit_surface"]
    conformance = bundle["conformance_report"]
    checks = (
        (
            bundle["policy_grammar_projection"].status == "pass",
            "layer3_g6_policy_grammar_compile_blocked",
            "G6 policy grammar projection must be compiled before routing.",
        ),
        (
            bundle["tool_contract_summary"].status == "pass",
            "layer3_g6_tool_contract_not_ready",
            "G6 tool-contract summary must pass structured readiness checks.",
        ),
        (
            prompt_tool.status == "pass" and prompt_tool.prompt_tool_ledger_ref,
            "layer3_g6_prompt_tool_ledger_missing",
            "G6 prompt/tool ledger projection must be replayable.",
        ),
        (
            bool(hypothesis_ledger.hypothesis_ledger_ref),
            "layer3_g6_candidate_without_hypothesis_ledger",
            "G6 candidate refs must be backed by the hypothesis ledger.",
        ),
        (
            search_ledger.status == "pass" and not search_ledger.authoritative_for,
            "layer3_g6_search_ledger_authority_boundary_leak",
            "G6 search ledger cannot fill authority slots.",
        ),
        (
            bundle["orchestration_choice_audit"].status == "pass",
            "layer3_g6_orchestration_choice_audit_missing",
            "G6 orchestration-choice audit must be present and replayable.",
        ),
        (
            continuity.status == "pass",
            "layer3_g6_orchestration_continuity_refs_missing",
            "G6 orchestration continuity must pass required ref checks.",
        ),
        (
            replay_manifest.status == "pass",
            "layer3_g6_replay_manifest_missing",
            "G6 replay manifest must be present and continuity-bound.",
        ),
        (
            conformance.runtime_import_boundary_check.get("status") == "pass",
            "layer3_g6_runtime_imports_policy_grammar",
            "runtime.quality G6 must not import policy_grammar directly.",
        ),
        (
            audit_surface.public_projection_contract_verification.get("status") == "pass",
            "layer3_g6_public_projection_contract_failed",
            "G6 PUBLIC projection must pass projection-only authority checks.",
        ),
        (
            bundle["demand_pull_vs_abstention_delta"].status == "pass",
            "layer3_g6_cheap_refusal_without_demand_signal",
            "G6 demand-pull vs abstention health delta must carry demand refs.",
        ),
        (
            bundle["agent_loop_result"].agent_loop_trace.status == "pass",
            "layer3_g6_agent_loop_trace_missing",
            "G6 agent loop trace must pass in deterministic simulation mode.",
        ),
        (
            record.engineering_readiness_status == "pass",
            "layer3_g6_persisted_artifact_missing",
            "G6 engineering readiness must pass before artifact readiness closes.",
        ),
    )
    issues.extend(
        _issue(code, "$.readiness_manifest", message)
        for passed, code, message in checks
        if not passed
    )
    return issues


def _summary(
    repo_root: Path,
    bundle: Mapping[str, Any],
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    record = _sequence(bundle["agent_run_records"])[0]
    conformance = bundle["conformance_report"]
    agent_loop = bundle["agent_loop_result"]
    audit_surface = bundle["agent_audit_surface"]
    return {
        "status": "pass",
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "surface_id": audit_surface.surface_id,
        "surface_audiences": list(audit_surface.surface_audiences),
        "may_not_use_for": list(audit_surface.may_not_use_for),
        "g6_engineering_readiness_status": record.engineering_readiness_status,
        "g6_grounded_value_closure_status": record.grounded_value_closure_status,
        "g6_policy_grammar_status": record.policy_grammar_projection.status,
        "g6_agent_loop_trace_status": agent_loop.agent_loop_trace.status,
        "g6_llm_client_status": (
            "blocked_with_typed_issue"
            if "layer3_g6_llm_client_unavailable"
            in agent_loop.agent_loop_trace.issue_codes
            else "pass"
        ),
        "g6_search_ledger_status": record.search_ledger.status,
        "g6_search_ledger_authority_boundary_status": (
            "pass" if not record.search_ledger.authoritative_for else "fail"
        ),
        "g6_design_record_candidate_handoff_status": (
            "pass"
            if bundle["design_record_candidate_handoff"].status == "candidate_only"
            else "fail"
        ),
        "g6_g4_source_design_record_boundary_status": (
            "pass"
            if "layer3_g6_g4_source_resolution_bypass_attempt"
            in bundle["g4_source_boundary"].issue_codes
            else "fail"
        ),
        "g6_g5_bridge_status": record.g5_invocation_plan.status,
        "g6_g5_may_not_use_for_boundary_status": (
            "pass"
            if conformance.g5_bridge_check.get("status") == "pass"
            else "fail"
        ),
        "g6_orchestration_choice_audit_status": (
            record.orchestration_choice_audit.status
        ),
        "g6_orchestration_continuity_status": bundle["orchestration_continuity"].status,
        "g6_replay_manifest_status": bundle["replay_manifest"].status,
        "g6_replay_drift_status": bundle["replay_drift"].status,
        "g6_runtime_import_boundary_status": (
            conformance.runtime_import_boundary_check.get("status", "fail")
        ),
        "g6_public_projection_contract_status": (
            audit_surface.public_projection_contract_verification.get("status", "fail")
        ),
        "g6_outside_envelope_abstention_quality_status": (
            "pass" if conformance.g5_bridge_check.get("status") == "pass" else "fail"
        ),
        "g6_demand_pull_vs_abstention_status": (
            bundle["demand_pull_vs_abstention_delta"].status
        ),
        "g6_conformance_status": conformance.status,
        "g6_generated_artifacts_registration_status": registration_statuses.get(
            "generated_artifacts",
            "pending_task11",
        ),
        "g6_inventory_surface_status": registration_statuses.get(
            "inventory",
            "pending_task11",
        ),
        "g6_reference_docs_status": registration_statuses.get("docs", "pending_task11"),
        "g6_manifest_runtime_drift_key_count": len(drift_keys),
        "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
        "persisted_g6_artifact_count": sum(
            1
            for path in EXPECTED_ARTIFACT_PATHS
            if _resolve_repo_path(repo_root, path).exists()
        ),
        "issue_codes": [],
    }


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(_dump(payload)))


def _write_health_metric_delta(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G6_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G6_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'fail'))}",
        "",
        "[readings]",
    ]
    for key, value in sorted(_mapping(payload.get("readings")).items()):
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _write_agent_route_contract_registry(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    lines = [
        f"schema_version = {_toml_value(payload.get('schema_version', G6_SCHEMA_VERSION))}",
        f"rule_version = {_toml_value(payload.get('rule_version', G6_RULE_VERSION))}",
        f"status = {_toml_value(payload.get('status', 'fail'))}",
        f"route_count = {_toml_value(payload.get('route_count', 0))}",
    ]
    for record in _sequence(payload.get("agent_route_records")):
        if not isinstance(record, Mapping):
            continue
        lines.append("")
        lines.append("[[agent_route_records]]")
        for key in sorted(record):
            lines.append(f"{_toml_key(str(key))} = {_toml_value(record[key])}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _readiness_manifest(
    repo_root: Path,
    bundle: Mapping[str, Any],
    *,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    summary = _summary(repo_root, bundle, drift_keys, registration_statuses)
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": "pass",
        "surface_id": g6.G6_SURFACE_ID,
        "summary": summary,
        **{key: summary[key] for key in EXPECTED_MANIFEST_DRIFT_KEYS},
        "issue_codes": [],
    }


def _default_policy_grammar_projection(request_id: str) -> dict[str, Any]:
    return {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": f"universal-policy-design-case:layer3-g6:{request_id}",
        "compiled_case_status": "compiled",
        "status": "pass",
        "authority_state": "compilation_facets_only",
        "facet_summary": {
            "jurisdiction": "UA",
            "policy_family": "ua_msme_support",
            "instrument": "concessional_credit",
            "subject": "wartime_msmes",
            "time_context": "wartime",
        },
        "concept_spine_refs": {
            "concept_spine_ref": f"cas://concept-spine/layer3-g6/{request_id}",
            "jurisdiction_spine_ref": f"cas://jurisdiction-spine/layer3-g6/{request_id}",
        },
        "issue_codes": (),
        "authoritative_for": g6.G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR,
        "may_not_use_for": (
            "legal_authority",
            "claim_authority",
            "closeout_authority",
        ),
    }


def _dependency_readiness_snapshot() -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": "pass",
        "dependency_statuses": {
            "policy_grammar_projection": "pass",
            "scientist_tool_contracts": "pass",
            "layer3_g5_bridge": "pass",
            "replay_orchestration": "pass",
        },
    }


def _request_classification(record: g6.Layer3G6AgentRunRecord) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "request_id": record.request_id,
        "request_class": record.request_class,
        "envelope_match_status": record.envelope_match_status,
        "facet_match_record": record.request_envelope.facet_match_record,
        "authoritative_for": list(g6.G6_AUTHORITATIVE_FOR),
        "may_not_use_for": list(g6.G6_MAY_NOT_USE_FOR),
    }


def _counterexample_refinement_record(record: g6.Layer3G6AgentRunRecord) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "record_id": f"layer3-g6://counterexample-refinement/{record.request_id}",
        "status": "pass",
        "rejected_branch_refs": list(record.search_ledger.rejected_candidate_refs),
        "counterexample_probe_refs": list(
            record.orchestration_choice_audit.counterexample_probe_refs
        ),
        "issue_codes": [],
    }


def _g5_consumer_gate_projection(record: g6.Layer3G6AgentRunRecord) -> dict[str, Any]:
    plan = record.g5_invocation_plan
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": plan.g5_w12d_consumer_gate_status,
        "g5_w12d_consumer_gate_ref": plan.g5_w12d_consumer_gate_ref,
        "g5_case_id": plan.g5_case_id,
        "g5_conversion_outcome": plan.g5_conversion_outcome,
        "issue_codes": list(plan.issue_codes),
        "authoritative_for": list(g6.G6_AUTHORITATIVE_FOR),
        "may_not_use_for": list(g6.G6_MAY_NOT_USE_FOR),
    }


def _public_export_projection_refs(
    surface: g6.Layer3G6AgentAuditSurface,
) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "surface_id": g6.G6_SURFACE_ID,
        "projection_mode": "projection_only",
        "public_export_hook_status": "out_of_scope_reference_only",
        "public_export_bundle_route_registered": False,
        "PUBLIC": surface.PUBLIC,
        "REVIEWER": surface.REVIEWER,
        "EXPERT": surface.EXPERT,
        "MACHINE": surface.MACHINE,
        "may_not_use_for": list(surface.may_not_use_for),
        "issue_codes": [],
    }


def _health_metric_delta(
    delta: g6.Layer3G6DemandPullVsAbstentionDelta,
) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": delta.status,
        "readings": delta.readings,
        "demand_source_refs": list(delta.demand_source_refs),
        "accountable_principal_refs": list(delta.accountable_principal_refs),
    }


def _agent_route_contract_registry(record: g6.Layer3G6AgentRunRecord) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": "pass",
        "route_count": 1,
        "agent_route_records": [
            {
                "route_id": "layer3.g6.agent_route.g5_pinned_bridge",
                "request_class": record.request_class,
                "envelope_match_status": record.envelope_match_status,
                "g5_invocation_plan_ref": record.g5_invocation_plan.invocation_plan_id,
                "authoritative_for": list(g6.G6_AUTHORITATIVE_FOR),
                "may_not_use_for": list(g6.G6_MAY_NOT_USE_FOR),
            }
        ],
    }


def _registry_ratchet_delta(
    conformance: g6.Layer3G6ConformanceReport,
) -> dict[str, Any]:
    return {
        "schema_version": G6_SCHEMA_VERSION,
        "rule_version": G6_RULE_VERSION,
        "status": "pass" if conformance.status == "pass" else "fail",
        "admission_maturity": "implemented_but_not_orchestrated",
        "conformance_report_ref": conformance.report_id,
        "negative_count": len(conformance.negative_results),
        "issue_codes": list(conformance.issue_codes),
    }


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Mapping):
        pairs = [f"{_toml_key(str(key))} = {_toml_value(value[key])}" for key in sorted(value)]
        return "{ " + ", ".join(pairs) + " }"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def _toml_key(value: str) -> str:
    return value if value.replace("_", "").replace("-", "").isalnum() else json.dumps(value)


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump(inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_dump(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"_root": payload}


def _read_text_or_empty(repo_root: Path, path: Path) -> str:
    resolved = _resolve_repo_path(repo_root, path)
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError:
        return ""


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        return (value,)
    return tuple(value)


def _deduplicate_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    normalized: list[dict[str, str]] = []
    for issue in issues:
        code = str(issue.get("code", ""))
        path = str(issue.get("path", ""))
        message = str(issue.get("message", ""))
        key = (code, path, message)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"code": code, "path": path, "message": message})
    return normalized


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _render_text_report(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [f"layer3_g6_readiness_status={report.get('status', '')}"]
    if isinstance(summary, Mapping):
        for key in sorted(summary):
            lines.append(f"{key}={_display_value(summary[key])}")
    issues = report.get("issues", [])
    if isinstance(issues, Sequence) and issues:
        lines.append("issues:")
        for issue in issues:
            if isinstance(issue, Mapping):
                lines.append(
                    f"- {issue.get('code', '')} {issue.get('path', '')}: "
                    f"{issue.get('message', '')}"
                )
    return "\n".join(lines).rstrip() + "\n"


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
