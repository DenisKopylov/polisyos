#!/usr/bin/env python3
"""Validate the GY agent workflow event-backing audit artifact.

This check protects the Task 0 distinction between runtime-visible NL agent
telemetry, CAS-backed parser lineage, real Scientist tool-loop execution, and
G6 readiness projections.

Usage:
    python3 tools/quality/validation/check_layer3_gy_agent_workflow_event_backing_audit.py [--json]
"""
from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

DEFAULT_AUDIT = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_agent_workflow_event_backing_audit.json"
)

REQUIRED_PATTERNS = {"P01", "P02", "P03", "P05", "P10", "P15", "P25"}
REQUIRED_COMPONENT_CLASSIFICATIONS = {
    "pi_agent": "runtime_step_telemetry_only",
    "data_need_extractor": "covered_runtime_step_plus_data_need_contract_elsewhere",
    "drafter": "runtime_step_telemetry_only",
    "formalizer": "runtime_step_plus_output_artifact_not_g6_role_record",
    "critic": "runtime_step_telemetry_plus_embedded_payload_only",
    "prompt_tool_ledger": "runtime_cas_backed_parser_ledger_not_tool_loop",
    "scientist_tool_loop": "implemented_but_not_orchestrated_in_nl_run",
    "g6_agent_run_records": "projection_only_not_nl_runtime_event_backed",
}
REQUIRED_ROLE_STEPS = {
    ("pi_agent", "create_problem_frame"),
    ("data_need_extractor", "extract_data_need"),
    ("drafter", "draft_policy"),
    ("formalizer", "formalize"),
    ("critic", "critique"),
}
REQUIRED_NEGATIVES = {
    "do_not_count_variant_steps_as_g6_agent_run_records",
    "do_not_count_prompt_tool_ledger_as_tool_loop",
    "do_not_count_g6_readiness_projection_as_live_nl_run",
    "serious_profile_parser_ledger_is_conditional",
}
REQUIRED_ACCEPTANCE_PHRASES = {
    "dedicated persisted role event artifact",
    "ToolLoopResult",
    "live runtime run_id/job_id",
    "parser/status lineage",
    "/runs/{run_id}/agents as telemetry",
}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _rows_by_id(rows: object, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get(key), str):
            out[str(row[key])] = row
    return out


def _steps(probe: dict[str, Any]) -> set[tuple[str, str]]:
    rows = probe.get("steps")
    if not isinstance(rows, list):
        return set()
    return {
        (str(row.get("agent")), str(row.get("action")))
        for row in rows
        if isinstance(row, dict)
    }


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    violations: list[dict[str, Any]] = []

    if audit.get("schema_version") != "layer3_gy_agent_workflow_event_backing_audit.v1":
        violations.append({"code": "bad_schema_version", "detail": audit.get("schema_version")})

    methodology = audit.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    expected_methodology = {
        "agents_used": False,
        "network_fetches_run": False,
        "runtime_server_started": False,
        "runtime_nl_probe_run": True,
        "execution_probe_profile_count": 2,
    }
    for key, expected in expected_methodology.items():
        if methodology.get(key) != expected:
            violations.append({
                "code": "methodology_drift",
                "detail": f"{key}={methodology.get(key)!r}; expected {expected!r}",
            })
    if methodology.get("probe_type") != "source_static_probe_plus_temp_simulated_nl_execution":
        violations.append({"code": "probe_type_drift", "detail": methodology.get("probe_type")})

    classification = audit.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "runtime_visible_agent_steps_without_g6_event_backing",
        "gap_class": "partial",
        "capability_label": (
            "runtime_step_telemetry_plus_parser_ledger_but_g6_role_event_bridge_missing"
        ),
        "route_pinned": True,
        "repair_before_downstream_governance": True,
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })
    patterns = set(classification.get("patterns") or [])
    if not patterns >= REQUIRED_PATTERNS:
        violations.append({"code": "pattern_coverage_drift", "detail": sorted(patterns)})

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}
    expected_summary = {
        "nl_pipeline_instantiates_pi_data_need_drafter_formalizer_critic": True,
        "nl_pipeline_has_role_call_events": True,
        "nl_pipeline_persists_llm_model_variant_steps": True,
        "runtime_debug_agents_surface_reads_variant_steps": True,
        "runtime_run_agents_endpoint_exists": True,
        "serious_profile_persists_prompt_tool_parser_ledger_to_cas": True,
        "dev_profile_persists_prompt_tool_parser_ledger_to_cas": False,
        "prompt_tool_ledger_is_real_tool_loop_transcript": False,
        "nl_pipeline_calls_scientist_tool_loop": False,
        "g6_agent_run_records_bound_to_live_nl_run": False,
        "g6_agent_run_record_count": 1,
        "g6_projection_request_id": "req-layer3-g6-readiness",
        "g6_projection_run_id": "layer3-g6-run:req-layer3-g6-readiness",
        "runtime_visible_agent_role_count": 5,
        "runtime_visible_non_role_step_count": 8,
        "dedicated_role_event_artifact_count": 0,
        "cas_backed_parser_ledger_count_on_serious_probe": 1,
        "nl_tool_loop_invocation_count": 0,
        "g6_records_bound_to_live_nl_run_count": 0,
        "overall_status": "partial_event_backing_with_projection_gap",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    probes = _rows_by_id(audit.get("execution_probes"), "probe_id")
    dev_probe = probes.get("dev_simulated_nl_variant_steps")
    research_probe = probes.get("research_simulated_nl_prompt_tool_ledger")
    if not isinstance(dev_probe, dict):
        violations.append({"code": "missing_dev_execution_probe", "detail": "dev probe missing"})
        dev_probe = {}
    if not isinstance(research_probe, dict):
        violations.append({
            "code": "missing_research_execution_probe",
            "detail": "research probe missing",
        })
        research_probe = {}

    for probe_id, probe in (
        ("dev_simulated_nl_variant_steps", dev_probe),
        ("research_simulated_nl_prompt_tool_ledger", research_probe),
    ):
        if probe.get("status") != "pass":
            violations.append({"code": "execution_probe_not_pass", "detail": probe_id})
        if probe.get("agent_circuit") is not True:
            violations.append({"code": "agent_circuit_not_observed", "detail": probe_id})
        if probe.get("step_count") != 13:
            violations.append({
                "code": "execution_probe_step_count_drift",
                "detail": f"{probe_id}={probe.get('step_count')!r}",
            })
        observed_steps = _steps(probe)
        if not observed_steps >= REQUIRED_ROLE_STEPS:
            violations.append({
                "code": "required_role_step_missing",
                "detail": {"probe_id": probe_id, "steps": sorted(observed_steps)},
            })

    if dev_probe.get("prompt_tool_ledger_ref") is not None:
        violations.append({
            "code": "dev_prompt_ledger_greenwash",
            "detail": dev_probe.get("prompt_tool_ledger_ref"),
        })
    research_ref = research_probe.get("prompt_tool_ledger_ref")
    if not isinstance(research_ref, str) or not SHA256_RE.fullmatch(research_ref):
        violations.append({"code": "research_prompt_ledger_ref_missing", "detail": research_ref})
    if research_probe.get("prompt_tool_authority_status") != "pass":
        violations.append({
            "code": "research_prompt_ledger_status_drift",
            "detail": research_probe.get("prompt_tool_authority_status"),
        })
    if research_probe.get("prompt_tool_step_count") != 13:
        violations.append({
            "code": "research_prompt_ledger_step_count_drift",
            "detail": research_probe.get("prompt_tool_step_count"),
        })
    if research_probe.get("prompt_tool_tool_names") != []:
        violations.append({
            "code": "parser_ledger_tool_loop_laundering",
            "detail": research_probe.get("prompt_tool_tool_names"),
        })
    if research_probe.get("reports_index_has_prompt_tool_ledger_ref") is not True:
        violations.append({
            "code": "reports_index_prompt_ledger_missing",
            "detail": research_probe.get("reports_index_has_prompt_tool_ledger_ref"),
        })

    static = audit.get("static_probes")
    if not isinstance(static, dict):
        violations.append({"code": "missing_static_probes", "detail": "static probes missing"})
        static = {}
    if _nested(static, ("nl_pipeline_tool_loop_references", "match_count")) != 0:
        violations.append({
            "code": "nl_tool_loop_invocation_greenwash",
            "detail": static.get("nl_pipeline_tool_loop_references"),
        })
    if _nested(static, ("g6_bounded_agent_tool_loop", "tool_loop_call_site")) != (
        "src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py:1346"
    ):
        violations.append({
            "code": "g6_tool_loop_call_site_drift",
            "detail": static.get("g6_bounded_agent_tool_loop"),
        })
    g6_records = static.get("committed_g6_agent_run_records")
    if not isinstance(g6_records, dict):
        violations.append({"code": "missing_g6_record_probe", "detail": "G6 record probe missing"})
        g6_records = {}
    if g6_records.get("classification") != "projection_only_not_nl_runtime_event_backed":
        violations.append({
            "code": "g6_record_laundering",
            "detail": g6_records.get("classification"),
        })
    if g6_records.get("request_id") != "req-layer3-g6-readiness":
        violations.append({"code": "g6_request_id_drift", "detail": g6_records.get("request_id")})
    if g6_records.get("count") != 1:
        violations.append({"code": "g6_record_count_drift", "detail": g6_records.get("count")})
    projection = static.get("committed_g6_prompt_tool_ledger_projection")
    if not isinstance(projection, dict):
        violations.append({
            "code": "missing_g6_prompt_ledger_projection_probe",
            "detail": "projection probe missing",
        })
        projection = {}
    if projection.get("classification") != "g6_candidate_projection_not_runtime_tool_loop_backing":
        violations.append({
            "code": "g6_prompt_projection_laundering",
            "detail": projection.get("classification"),
        })
    if projection.get("nested_prompt_tool_ledger_summary_status") != "fail":
        violations.append({
            "code": "g6_nested_ledger_status_drift",
            "detail": projection.get("nested_prompt_tool_ledger_summary_status"),
        })
    if projection.get("outer_status") != "pass":
        violations.append({"code": "g6_outer_status_drift", "detail": projection.get("outer_status")})

    components = _rows_by_id(audit.get("roles"), "component_id")
    if set(components) != set(REQUIRED_COMPONENT_CLASSIFICATIONS):
        violations.append({"code": "component_set_drift", "detail": sorted(components)})
    for component_id, expected_classification in REQUIRED_COMPONENT_CLASSIFICATIONS.items():
        row = components.get(component_id)
        if not isinstance(row, dict):
            continue
        if row.get("classification") != expected_classification:
            violations.append({
                "code": "component_classification_drift",
                "detail": (
                    f"{component_id}={row.get('classification')!r}; "
                    f"expected {expected_classification!r}"
                ),
            })
        if component_id in {"pi_agent", "drafter", "critic"}:
            if row.get("dedicated_persisted_role_artifact") is not None:
                violations.append({
                    "code": "role_artifact_greenwash",
                    "detail": component_id,
                })
        if component_id == "formalizer" and row.get("dedicated_persisted_role_artifact") is not None:
            violations.append({
                "code": "formalizer_role_artifact_greenwash",
                "detail": row.get("dedicated_persisted_role_artifact"),
            })
        if component_id == "prompt_tool_ledger":
            if row.get("g6_asset_backing") != "parser_ledger_only_not_tool_loop":
                violations.append({
                    "code": "prompt_ledger_tool_loop_greenwash",
                    "detail": row.get("g6_asset_backing"),
                })
        if component_id == "scientist_tool_loop":
            if row.get("nl_route_invoked") is not False:
                violations.append({
                    "code": "tool_loop_nl_invocation_greenwash",
                    "detail": row.get("nl_route_invoked"),
                })
        if component_id == "g6_agent_run_records":
            if row.get("nl_route_invoked") is not False:
                violations.append({
                    "code": "g6_records_nl_invocation_greenwash",
                    "detail": row.get("nl_route_invoked"),
                })
            if row.get("g6_asset_backing") != "projection_only_not_nl_runtime_event_backed":
                violations.append({
                    "code": "g6_asset_backing_laundering",
                    "detail": row.get("g6_asset_backing"),
                })

    negative_ids = set(_rows_by_id(audit.get("negative_assertions"), "id"))
    if not negative_ids >= REQUIRED_NEGATIVES:
        violations.append({"code": "missing_negative_assertions", "detail": sorted(negative_ids)})

    acceptance_text = "\n".join(str(item) for item in audit.get("acceptance_signal") or [])
    for phrase in REQUIRED_ACCEPTANCE_PHRASES:
        if phrase not in acceptance_text:
            violations.append({"code": "missing_acceptance_guardrail", "detail": phrase})

    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the validator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    violations = validate(audit)
    if args.json:
        print(json.dumps({"ok": not violations, "violations": violations}, indent=2))
    elif violations:
        print("FAIL layer3_gy_agent_workflow_event_backing_audit")
        for violation in violations:
            print(f"- {violation['code']}: {violation.get('detail')}")
    else:
        print("PASS layer3_gy_agent_workflow_event_backing_audit")
    return 1 if violations else 0


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
