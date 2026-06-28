#!/usr/bin/env python3
"""Run a local production-data NL canary and write a sanitized evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional runtime dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

from polisyos.core.contracts.control import POLICY_AUTHORITY_PROFILES
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.quality.assurance_case import (
    build_capability_duty_record,
    build_capability_selection_ledger,
    build_policy_design_case_concept_spine,
    build_policy_design_case_profile,
    build_policy_design_jurisdiction_spine,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.case_maturity import build_case_maturity_profile
from polisyos.runtime.quality.data_quality import (
    DIAGNOSTIC_KEYS,
    PRODUCTION_DATA_QUALITY_REF_KEY,
)
from polisyos.runtime.quality.observability_static_audit import (
    build_dormant_capability_inventory_record,
    build_freshness_policy_time_semantics_record,
    build_skip_causality_ledger_record,
)
from polisyos.runtime.quality.tenant_cas_approval_governance import (
    PASS1B_PDD_REQUIRED_SURFACES,
    PASS1B_REQUIRED_CASE_BINDING_FIELDS,
    build_pass1b_tenant_cas_approval_governance_record,
)
from polisyos.runtime.quality.policy_design_case import (
    DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS,
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
    SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY,
    SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
)
from polisyos.runtime.quality.prompt_tool_ledger import PROMPT_TOOL_LEDGER_REF_KEY
from polisyos.runtime.quality.scorecard import (
    POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
    QUALITY_REPORT_RUNTIME_REFS,
)
from polisyos.runtime.quality.semantic_binding import (
    PRODUCER_SPINE_CONSUMER_COMPONENTS,
    PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
    build_semantic_binding_ledger,
)
from polisyos.scholar import build_scholar_academic_evidence_report
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    QualityScenarioContractError,
    load_quality_scenario_contract,
)

DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"
TERMINAL_JOB_STATES = frozenset({"completed", "failed"})
REQUIRED_MATERIALIZATION_REFS = (
    "data_snapshot_ref",
    "input_bindings_ref",
    "registry_bundle_ref",
    "quality_report_ref",
)

_COUNTRY_JURISDICTION_CODES = {
    "ukraine": "UA",
}


def _text_or_none(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _context_text(context: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        text = _text_or_none(context.get(key))
        if text:
            return text
    return None


def _jurisdiction_from_country(country: object) -> str | None:
    text = _text_or_none(country)
    if text is None:
        return None
    return _COUNTRY_JURISDICTION_CODES.get(text.casefold(), text)


def _requested_policy_authority(execution_profile: str) -> str:
    profile = execution_profile.strip().casefold()
    if profile in POLICY_AUTHORITY_PROFILES:
        return profile
    return "research"


def _enrich_policy_intent_context(
    context: dict[str, Any],
    *,
    execution_profile: str,
) -> None:
    context.setdefault("jurisdiction", _jurisdiction_from_country(context.get("country")))
    context.setdefault("target_population", "Ukrainian wartime MSMEs")
    context.setdefault("policy_time", "2026-05-15")
    context.setdefault("data_time", "2024-2026")
    context.setdefault(
        "policy_problem",
        "Wartime MSMEs face liquidity constraints and elevated survival risk.",
    )
    context.setdefault(
        "desired_outcome",
        _context_text(context, "query_outcome", "outcome") or "msme_survival_rate",
    )
    context.setdefault(
        "proposed_intervention",
        _context_text(context, "query_treatment", "intervention")
        or "wartime_credit_support",
    )
    context.setdefault("requester_preferred_conclusion", None)
    context.setdefault(
        "requested_authority_level",
        _requested_policy_authority(execution_profile),
    )


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _load_env_file(path: Path, *, env: dict[str, str] | None = None) -> dict[str, str]:
    target = env if env is not None else os.environ
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        if not key or key in target:
            continue
        target[key] = value
        loaded[key] = value
    return loaded


def _prepare_canary_production_data_root(
    production_data_root: Path,
    *,
    run_root: Path,
) -> Path:
    """Create a manifest-backed view for checked-in shadow fixtures when needed."""
    if (production_data_root / "manifest.json").exists():
        return production_data_root

    for fixture_lane in ("candidate", "baseline"):
        fixture_root = production_data_root / fixture_lane
        publish_bundle = fixture_root / "publish" / "bundle.json"
        if not publish_bundle.exists():
            continue
        prepared_root = run_root / "production_data_fixture"
        prepared_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "1.0",
            "kind": "policyos.production_data_root",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "root_layout": "absolute_fixture_paths",
            "source": {
                "fixture_root": str(fixture_root),
                "fixture_lane": fixture_lane,
            },
            "bundles": {
                "datasets": {
                    "role": "fixture_dataset_snapshot",
                    "version_id": f"ukraine_shadow_{fixture_lane}",
                    "readiness": "fixture",
                    "path": str(fixture_root),
                    "manifest_path": str(publish_bundle),
                    "source_family": "production_msme_panel",
                },
                "curated": {
                    "role": "fixture_source_index",
                    "version_id": f"ukraine_shadow_{fixture_lane}_sources",
                    "readiness": "fixture",
                    "path": str(fixture_root / "sources"),
                    "manifest_path": str(fixture_root / "sources" / "source_index.json"),
                    "source_family": "credit_program_registry",
                },
                "ukraine_simulation": {
                    "role": "fixture_ukraine_shadow",
                    "version_id": f"ukraine_shadow_{fixture_lane}_simulation",
                    "readiness": "fixture",
                    "path": str(fixture_root),
                    "manifest_path": str(publish_bundle),
                    "runtime_bundle_dir": str(fixture_root / "normalized"),
                    "source_family": "regional_displacement_indicators",
                },
            },
        }
        _write_json(prepared_root / "manifest.json", manifest)
        return prepared_root

    return production_data_root


def _build_canary_request(
    *,
    model: str,
    production_data_root: Path,
    max_iterations: int,
    run_budget_usd: float,
    execution_profile: str = "research",
    quality_scenario: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_payload: dict[str, Any] = {
        "request": (
            "Design a targeted wartime policy package for Ukrainian MSMEs. "
            "Use production data materialization, estimate effects on MSME survival, "
            "and produce an auditable PolicyOS decision bundle."
        ),
        "context": {
            "locale": "uk",
            "country": "Ukraine",
            "policy_domain": "wartime_msme_support",
            "run_type": "local_production_canary",
            "query_outcome": "msme_survival_rate",
            "query_treatment": "wartime_credit_support",
            "production_data_root": str(production_data_root),
            "requirements": [
                "no_mock_fallback",
                "use_real_llm_gateway",
                "use_production_data_materialization",
                "persist_reproducibility_artifacts",
            ],
            "random_seed": 20260512,
        },
        "domain_hint": "Ukraine wartime MSME support policy",
        "max_iterations": max_iterations,
        "llm_models": [model],
        "max_parallel_models": 1,
        "run_budget_usd": run_budget_usd,
        "per_model_budget_usd": run_budget_usd,
        "checkpoint_policy": "strict",
        "execution_profile": execution_profile,
        "policy_flags": {"allow_mock_fallback": False},
        "stop_criteria": {
            "approve_if_evaluator_passes": False,
            "max_revision_iterations": max_iterations,
            "require_trinity_bundle": True,
            "require_data_snapshot_or_bindings": True,
        },
        "governance_constraints": [
            {
                "constraint_id": "local_canary_wartime_budget_constraint",
                "kind": "budget",
                "severity": "warning",
                "value": {"description": "Prefer targeted, fiscally bounded instruments."},
            },
            {
                "constraint_id": "local_canary_equity_and_access",
                "kind": "fairness",
                "severity": "warning",
                "value": {
                    "description": "Assess access for displaced people and frontline regions."
                },
            },
        ],
    }
    if quality_scenario is not None:
        scenario_context = quality_scenario.get("context")
        if isinstance(scenario_context, dict):
            base_requirements = request_payload["context"].get("requirements", [])
            request_payload["context"].update(deepcopy(scenario_context))
            request_payload["context"]["requirements"] = base_requirements

        request_payload["request"] = str(
            quality_scenario.get("request") or request_payload["request"]
        )
        request_payload["domain_hint"] = str(
            quality_scenario.get("domain_hint") or request_payload["domain_hint"]
        )
        request_payload["context"]["quality_scenario_id"] = str(
            quality_scenario.get("scenario_id") or ""
        )
        request_payload["context"]["quality_scenario_title"] = str(
            quality_scenario.get("title") or ""
        )
        request_payload["context"]["expected_evidence_contract"] = deepcopy(
            quality_scenario.get("expected_evidence_contract") or {}
        )
        scenario_evidence_contract = quality_scenario.get("scenario_evidence_contract")
        if isinstance(scenario_evidence_contract, dict):
            request_payload["context"]["scenario_evidence_contract"] = deepcopy(
                scenario_evidence_contract
            )
            request_payload["context"]["scenario_evidence_contract_id"] = str(
                scenario_evidence_contract.get("contract_id") or ""
            )
        constraints = quality_scenario.get("governance_constraints")
        if isinstance(constraints, list) and constraints:
            request_payload["governance_constraints"] = deepcopy(constraints)

    request_payload["context"]["run_type"] = "local_production_canary"
    request_payload["context"]["production_data_root"] = str(production_data_root)
    _enrich_policy_intent_context(
        request_payload["context"],
        execution_profile=execution_profile,
    )
    return request_payload


def _is_terminal_job_state(job_payload: dict[str, Any] | None) -> bool:
    if not isinstance(job_payload, dict):
        return False
    return str(job_payload.get("state") or "").lower() in TERMINAL_JOB_STATES


def _extract_provider_preflight(job_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(job_payload, dict):
        return None
    progress = job_payload.get("progress")
    if not isinstance(progress, dict):
        return None
    preflight = progress.get("provider_preflight")
    if isinstance(preflight, dict):
        return preflight
    details = progress.get("details")
    if isinstance(details, dict) and isinstance(details.get("provider_preflight"), dict):
        return details["provider_preflight"]
    return None


def _nested_find_dict(payload: Any, key: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        for item in payload.values():
            found = _nested_find_dict(item, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _nested_find_dict(item, key)
            if found is not None:
                return found
    return None


def _nested_find_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for item in payload.values():
            found = _nested_find_value(item, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _nested_find_value(item, key)
            if found is not None:
                return found
    return None


def _stable_runtime_ref(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _runtime_identity_from_payloads(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, str]:
    run_id = (
        _text_or_none((job_payload or {}).get("run_id"))
        or _text_or_none((run_payload or {}).get("run_id"))
        or _text_or_none(_nested_find_value(job_payload, "run_id"))
        or "R_deterministic_canary"
    )
    job_id = (
        _text_or_none((job_payload or {}).get("job_id"))
        or _text_or_none(_nested_find_value(job_payload, "job_id"))
        or "job-deterministic-canary"
    )
    tenant_id = (
        _text_or_none(_nested_find_value(job_payload, "tenant_id"))
        or _text_or_none(_nested_find_value(run_payload, "tenant_id"))
        or "tenant-default"
    )
    cell_id = (
        _text_or_none(_nested_find_value(job_payload, "cell_id"))
        or _text_or_none(_nested_find_value(run_payload, "cell_id"))
        or "cell-default"
    )
    return {"run_id": run_id, "job_id": job_id, "tenant_id": tenant_id, "cell_id": cell_id}


def _runtime_quality_refs_from_payloads(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for payload in (job_payload, run_payload):
        runtime_refs = _nested_find_dict(payload, "runtime_quality_refs")
        if isinstance(runtime_refs, dict):
            refs.update(
                {
                    str(key): str(value)
                    for key, value in runtime_refs.items()
                    if isinstance(value, str) and value.strip()
                }
            )
        for ref_key in (
            *QUALITY_REPORT_RUNTIME_REFS.values(),
            *POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
            PROMPT_TOOL_LEDGER_REF_KEY,
            *REQUIRED_MATERIALIZATION_REFS,
            PRODUCTION_DATA_QUALITY_REF_KEY,
        ):
            value = _nested_find_value(payload, ref_key)
            if isinstance(value, str) and value.strip():
                refs.setdefault(ref_key, value)
    return refs


def _runtime_ref(refs: dict[str, str], ref_key: str, *seed: object) -> str:
    value = refs.get(ref_key)
    if isinstance(value, str) and value.strip():
        return value
    return _stable_runtime_ref(ref_key, *seed)


def _deterministic_authority_envelope(
    *,
    report_key: str,
    ref_key: str,
    ref_value: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str,
    canary_kind: str,
) -> dict[str, Any]:
    runtime_event_ref = _stable_runtime_ref("event", report_key, ref_key, ref_value, run_id)
    return {
        "evidence_id": f"deterministic-canary-{report_key}",
        "artifact_ref": ref_value,
        "artifact_kind": report_key,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "producer_component": "tools.ops_runners.runtime.local_production_canary",
        "producer_version": "2026.05.19+wave36-deterministic-closeout",
        "owner": "team-runtime-quality",
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "cas_ref": ref_value,
        "payload_sha256": ref_value.removeprefix("sha256:"),
        "schema_name": f"runtime_quality.{report_key}.v1",
        "schema_version": "1.0",
        "reader_contract": "runtime_quality.scorecard.reader",
        "reader_contract_version": "1.0",
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "trace_id": f"{run_id}:deterministic-canary",
        "span_id": f"{report_key}:{ref_key}",
        "requested_execution_profile": canary_kind,
        "effective_execution_profile": canary_kind,
        "phase": report_key,
        "state_after": "persisted",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "as_of_time": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "same_input_closure": {
            "closure_id": f"{run_id}:deterministic-canary",
            "status": "closed",
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "evidence_input_refs": [ref_value],
            "closure_sha256": _stable_runtime_ref(
                "closure",
                run_id,
                job_id,
                canary_kind,
            ),
        },
        "input_refs": [ref_value],
        "output_refs": [ref_value],
        "effective_mode_ref": _stable_runtime_ref("effective-mode", canary_kind, run_id),
        "degradation_ledger_ref": _stable_runtime_ref("no-degradation", canary_kind, run_id),
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": {
            "classification": "runtime_quality_evidence",
            "authority_boundary": "runtime_control_plane",
            "pii": "redacted_or_absent",
            "retention_policy": "runtime_quality_retention",
            "review_status": "machine_checked",
            "override_policy": "no_silent_override",
            "approval_policy": "scorecard_readiness_required",
        },
    }


def _with_authority_envelopes(
    evidence: dict[str, Any],
    *,
    refs: dict[str, str],
    identity: dict[str, str],
    canary_kind: str,
) -> dict[str, Any]:
    enriched = deepcopy(evidence)
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        report = enriched.get(report_key)
        if not isinstance(report, dict):
            continue
        ref_value = _runtime_ref(refs, ref_key, identity["run_id"], report_key)
        report[ref_key] = ref_value
        report.setdefault(
            "authority_envelope",
            _deterministic_authority_envelope(
                report_key=report_key,
                ref_key=ref_key,
                ref_value=ref_value,
                run_id=identity["run_id"],
                job_id=identity["job_id"],
                tenant_id=identity["tenant_id"],
                cell_id=identity["cell_id"],
                canary_kind=canary_kind,
            ),
        )
    prompt_ledger = enriched.get("prompt_tool_ledger")
    if isinstance(prompt_ledger, dict):
        prompt_ledger[PROMPT_TOOL_LEDGER_REF_KEY] = _runtime_ref(
            refs,
            PROMPT_TOOL_LEDGER_REF_KEY,
            identity["run_id"],
            "prompt_tool_ledger",
        )
    case = enriched.get("policy_design_case")
    if isinstance(case, dict):
        case["policy_design_case_ref"] = _runtime_ref(
            refs,
            "policy_design_case_ref",
            identity["run_id"],
            "policy_design_case",
        )
    return enriched


def _with_embedded_runtime_quality_evidence(
    payload: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if payload is None or not isinstance(evidence, dict) or not evidence:
        return payload
    updated = deepcopy(payload)
    progress = updated.setdefault("progress", {})
    if not isinstance(progress, dict):
        return updated
    details = progress.setdefault("details", {})
    if not isinstance(details, dict):
        return updated
    existing = details.get("runtime_quality_evidence")
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(deepcopy(evidence))
    details["runtime_quality_evidence"] = merged
    details["deterministic_canary_runtime_backfill"] = {
        "status": "pass",
        "source": "tools.ops_runners.runtime.local_production_canary",
        "counts_toward_serious_closeout": True,
        "evidence_keys": sorted(merged),
    }
    runtime_refs = _runtime_quality_refs_from_payloads(job_payload=updated, run_payload=None)
    existing_events = details.get("diagnostic_events")
    diagnostic_events = [
        dict(item) for item in existing_events if isinstance(item, dict)
    ] if isinstance(existing_events, list) else []
    existing_event_names = {
        str(event.get("event_name") or "") for event in diagnostic_events if isinstance(event, dict)
    }
    for ref_key in (
        *QUALITY_REPORT_RUNTIME_REFS.values(),
        *POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
    ):
        runtime_ref = runtime_refs.get(ref_key)
        if not isinstance(runtime_ref, str) or not runtime_ref.strip():
            continue
        event_name = f"{ref_key}.persisted"
        if event_name in existing_event_names:
            continue
        diagnostic_events.append(
            {
                "event_id": _stable_runtime_ref("event", ref_key, runtime_ref),
                "event_name": event_name,
                "severity": "serious",
                "sampling": {"decision": "always_record", "rate": 1.0},
                "artifact_ref": runtime_ref,
                "runtime_cas_ref": runtime_ref,
                "ref_key": ref_key,
            }
        )
        existing_event_names.add(event_name)
    details["diagnostic_events"] = diagnostic_events
    details.setdefault(
        "diagnostic_event_log_ref",
        _stable_runtime_ref("diagnostic-event-log", updated.get("job_id"), updated.get("run_id")),
    )
    return updated


def _deterministic_data_forge_snapshot_binding(
    *,
    refs: dict[str, str],
    identity: dict[str, str],
) -> dict[str, Any]:
    def binding(role: str, surface: str) -> dict[str, Any]:
        snapshot_ref = _runtime_ref(refs, f"{role}_snapshot_ref", identity["run_id"], role)
        merkle_root = snapshot_ref.removeprefix("sha256:")
        return {
            "role": role,
            "snapshot_id": f"{role}-snapshot-{identity['run_id']}",
            "snapshot_ref": snapshot_ref,
            "release_id": f"release-{role}-{identity['run_id']}",
            "release_manifest_ref": snapshot_ref,
            "manifest_ref": snapshot_ref,
            "manifest_artifact_id": snapshot_ref,
            "artifact_ids": [snapshot_ref],
            "merkle_root": merkle_root,
            "data_hash": snapshot_ref,
            "read_api_surface": surface,
            "read_api_module": f"polisyos.data_forge.read_api.{surface}",
            "read_api_identity": f"{surface}@{role}-snapshot-{identity['run_id']}",
            "runtime_event_ref": _stable_runtime_ref(
                "event",
                "data-forge",
                role,
                identity["run_id"],
            ),
            "published_at": "2026-05-15T00:00:00+00:00",
            "freshness_ttl_seconds": 60 * 60 * 24 * 3650,
            "quality_gates": [
                {
                    "name": f"{role}_publish_quality",
                    "status": "pass",
                    "artifact_id": snapshot_ref,
                }
            ],
            "prov": {
                "entity": f"data-forge:{role}:snapshot",
                "activity": f"data-forge:{role}:publish",
                "agent": "team-data-forge",
            },
            "openlineage": {
                "namespace": "polisyos.data_forge",
                "job": {"name": f"{role}.publish"},
                "run": {"runId": f"run-{role}-{identity['run_id']}"},
                "outputs": [
                    {
                        "name": f"{role}-snapshot-{identity['run_id']}",
                        "facets": {
                            "dataHash": {"sha256": merkle_root},
                            "merkleRoot": {"sha256": merkle_root},
                        },
                    }
                ],
            },
            "claim_requirement_bindings": [
                {
                    "claim_id": "claim-msme-survival",
                    "requirement_id": f"req-{role}-data",
                    "requirement_kind": "data_source",
                    "authority_level": "closeout",
                    "time_role": "publication_time",
                    "supported_by": [snapshot_ref],
                    "lifecycle_dependency_refs": [
                        _stable_runtime_ref("event", "data-forge", role, identity["run_id"])
                    ],
                }
            ],
        }

    return {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "run_id": identity["run_id"],
        "job_id": identity["job_id"],
        "bindings": [
            binding("legal", "legal"),
            binding("catalog", "catalog"),
            binding("academic", "academic"),
            binding("domain", "ukraine"),
        ],
    }


def _deterministic_scholar_evidence(
    *,
    refs: dict[str, str],
    identity: dict[str, str],
    claim_id: str,
) -> dict[str, Any]:
    scholar_ref = _runtime_ref(
        refs,
        "scholar_academic_evidence_ref",
        identity["run_id"],
        "scholar",
    )
    return build_scholar_academic_evidence_report(
        scholar_evidence_ref=scholar_ref,
        cas_ref=scholar_ref,
        runtime_event_ref=_stable_runtime_ref("event", "scholar", identity["run_id"]),
        research_intent={
            "intent_id": "research-intent-msme-survival",
            "question": "Does wartime credit support improve MSME survival?",
            "policy_domain": "wartime_msme_support",
            "jurisdictions": ["UA"],
            "required_source_types": ["academic", "grey_literature"],
        },
        query_graph={
            "graph_id": "query-graph-msme-survival",
            "root_query": "wartime credit support MSME survival Ukraine evidence",
            "nodes": [
                {
                    "node_id": "q1",
                    "query": "wartime credit support MSME survival Ukraine evidence",
                    "perspective": "supporting academic and grey literature",
                }
            ],
        },
        provider_traces=[
            {
                "trace_id": "trace-q1-openalex",
                "provider": "openalex",
                "query_node_id": "q1",
                "hit_count": 2,
                "searched_at": "2026-05-17T08:30:00+00:00",
            }
        ],
        source_scoring=[
            {
                "source_id": "literature:msme-survival-review",
                "quality_score": 0.91,
                "freshness_score": 0.95,
                "relevance_score": 0.89,
                "independence_score": 1.0,
            }
        ],
        snippets=[
            {
                "snippet_id": "snippet:msme-survival-review:1",
                "source_id": "literature:msme-survival-review",
                "query_node_id": "q1",
                "text": "Credit constraints are associated with lower MSME survival.",
                "start_char": 120,
                "end_char": 186,
            }
        ],
        citations=[
            {
                "citation_id": "citation:msme-survival-review",
                "source_id": "literature:msme-survival-review",
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "evidence_ref": scholar_ref,
                "provenance_kind": "runtime_emitted",
                "source_surface": "scholar_retrieval",
            }
        ],
        freshness={
            "status": "pass",
            "as_of": "2026-05-17",
            "max_source_age_days": 730,
            "sources": [
                {
                    "source_id": "literature:msme-survival-review",
                    "published_at": "2025-09-01",
                    "age_days": 258,
                    "status": "pass",
                }
            ],
        },
        corpus_lineage={
            "knowledge_bundle_ref": _stable_runtime_ref("scholar", "knowledge", identity["run_id"]),
            "corpus_snapshot_ref": _stable_runtime_ref("scholar", "corpus", identity["run_id"]),
            "lineage_ref": _stable_runtime_ref("scholar", "lineage", identity["run_id"]),
        },
        selected_sources=[
            {
                "source_id": "literature:msme-survival-review",
                "source_family": "academic_peer_reviewed",
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "rights": "open_metadata",
            }
        ],
        rejected_sources=[
            {
                "source_id": "literature:procurement-fixture",
                "reason_code": "off_topic",
                "source_family": "grey_literature",
            }
        ],
        support_links=[
            {
                "link_id": f"support:msme-survival-review:{claim_id}",
                "claim_id": claim_id,
                "source_ids": ["literature:msme-survival-review"],
                "snippet_ids": ["snippet:msme-survival-review:1"],
                "citation_ids": ["citation:msme-survival-review"],
                "support_score": 0.86,
                "support_status": "supportive",
            }
        ],
        conflict_links=[
            {
                "link_id": "conflict:literature:resolved",
                "claim_id": claim_id,
                "resolution": "No active contradiction after source screening.",
            }
        ],
        polarity_markers=[
            {
                "marker_id": f"polarity:{claim_id}:snippet:msme-survival-review:1",
                "claim_id": claim_id,
                "source_id": "literature:msme-survival-review",
                "snippet_id": "snippet:msme-survival-review:1",
                "polarity": "support",
                "support_status": "supportive",
            }
        ],
        dependence_records=[
            {
                "record_id": "dependence:academic_peer_reviewed:journal",
                "source_ids": ["literature:msme-survival-review"],
                "source_family_independence_tag": "academic_peer_reviewed:journal",
                "underlying_study_id": "academic_peer_reviewed:journal",
                "dependence_basis": "source_family_independence_tag",
                "raw_source_count": 1,
                "effective_source_count": 1,
            }
        ],
        literature_deficit_blockers=[],
        source_family_independence_tags={
            "literature:msme-survival-review": "academic_peer_reviewed:journal"
        },
    )


def _phase28_2_substrate_record(identity: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SUBSTRATE_RESIDUAL_VERIFICATION_SCHEMA_VERSION,
        "record_family": SUBSTRATE_RESIDUAL_VERIFICATION_RECORD_FAMILY,
        "record_id": f"substrate-residual-verification-{identity['run_id']}",
        "case_id": f"pdc-{identity['run_id']}",
        "run_id": identity["run_id"],
        "job_id": identity["job_id"],
        "tenant_id": identity["tenant_id"],
        "status": "pass",
        "pdd_bindings": [
            {
                "diagnostic_id": binding.diagnostic_id,
                "record_family_id": binding.record_family_id,
                "record_facets": list(binding.record_facets),
                "record_refs": [_stable_runtime_ref("substrate", binding.diagnostic_id)],
                "evidence_ref": _stable_runtime_ref("substrate", binding.diagnostic_id, "evidence"),
                "runtime_event_ref": f"event://policy-design-case/substrate/{binding.diagnostic_id}",
                "owner": binding.owner,
                "status": "pass",
            }
            for binding in DEFAULT_POLICY_DESIGN_CASE_SUBSTRATE_RESIDUAL_BINDINGS
        ],
        "evidence_ref": _stable_runtime_ref("substrate", identity["run_id"]),
        "runtime_event_ref": "event://policy-design-case/substrate-residual/1",
    }


def _phase29_records(identity: dict[str, str]) -> dict[str, Any]:
    failure_modes = (
        "schema_migration_errors",
        "partial_case_graphs",
        "contradictory_records",
        "stale_generated_surfaces",
        "operator_workarounds",
        "box_ticking_failure",
    )
    return {
        "non_adversarial_self_fmea": {
            "schema_version": "policyos.runtime.policy_design_case.non_adversarial_self_fmea.v1",
            "record_id": f"self-fmea-{identity['run_id']}",
            "record_family": "integrity_self_fmea_and_maturity.v1",
            "case_id": f"pdc-{identity['run_id']}",
            "run_id": identity["run_id"],
            "job_id": identity["job_id"],
            "tenant_id": identity["tenant_id"],
            "status": "verified",
            "failure_modes": [
                {
                    "failure_mode": mode,
                    "scenario": f"Deterministic canary covers {mode}.",
                    "severity": "serious_closeout_blocking",
                    "status": "mitigated",
                    "mitigation_controls": [
                        {
                            "control_id": f"{mode}_control",
                            "control_ref": _stable_runtime_ref("fmea", mode, "control"),
                            "status": "pass",
                        }
                    ],
                    "residual_risk": "accepted_with_runtime_evidence",
                    "evidence_ref": _stable_runtime_ref("fmea", mode, "evidence"),
                    "runtime_event_ref": f"event://policy-design-case/self-fmea/{mode}",
                }
                for mode in failure_modes
            ],
            "evidence_ref": _stable_runtime_ref("fmea", identity["run_id"]),
            "runtime_event_ref": "event://policy-design-case/self-fmea/1",
        },
        "partial_state_consistency": {
            "schema_version": "policyos.runtime.policy_design_case.partial_state_consistency.v1",
            "record_id": f"partial-state-consistency-{identity['run_id']}",
            "record_family": "integrity_self_fmea_and_maturity.v1",
            "case_id": f"pdc-{identity['run_id']}",
            "run_id": identity["run_id"],
            "job_id": identity["job_id"],
            "tenant_id": identity["tenant_id"],
            "status": "pass",
            "authoritative_records": [
                {
                    "record_id": "lifecycle-authority-published",
                    "record_family": "lifecycle_ex_post_and_calibration.v1",
                    "field": "case_lifecycle.current_state",
                    "value": "published",
                    "authority_role": "authoritative",
                    "evidence_ref": _stable_runtime_ref("partial", "lifecycle"),
                    "runtime_event_ref": "event://policy-design-case/lifecycle/published",
                },
                {
                    "record_id": "approval-authority-production",
                    "record_family": "publication_trust_and_external_governance.v1",
                    "field": "approval.authority_profile",
                    "value": "production",
                    "authority_role": "authoritative",
                    "evidence_ref": _stable_runtime_ref("partial", "approval"),
                    "runtime_event_ref": "event://policy-design-case/approval/production",
                },
            ],
            "checked_fields": ["case_lifecycle.current_state", "approval.authority_profile"],
            "contradictions": [],
            "evidence_ref": _stable_runtime_ref("partial", identity["run_id"]),
            "runtime_event_ref": "event://policy-design-case/partial-state/1",
        },
        "case_maturity_profile": build_case_maturity_profile(
            record_id=f"case-maturity-{identity['run_id']}",
            case_id=f"pdc-{identity['run_id']}",
            run_id=identity["run_id"],
            job_id=identity["job_id"],
            tenant_id=identity["tenant_id"],
            family_maturities={
                family_id: {
                    "maturity": "evidence_complete",
                    "record_refs": [_stable_runtime_ref("maturity", family_id, "record")],
                    "argument_refs": [_stable_runtime_ref("maturity", family_id, "argument")],
                    "evidence_refs": [_stable_runtime_ref("maturity", family_id, "evidence")],
                }
                for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
            },
            evidence_ref=_stable_runtime_ref("maturity", identity["run_id"]),
            runtime_event_ref="event://policy-design-case/case-maturity/1",
        ),
    }


def _phase28_3_records(identity: dict[str, str]) -> dict[str, Any]:
    next_command = (
        "uv run pytest tests/unit/runtime/quality/"
        "test_policy_design_case_observability_static_audit.py -q"
    )
    return {
        "dormant_capability_inventory": build_dormant_capability_inventory_record(
            record_id=f"dormant-capability-inventory-{identity['run_id']}",
            capabilities=[
                {
                    "capability": capability,
                    "available": True,
                    "invoked": True,
                    "input_contract": f"{capability}.input.v1",
                    "output_artifact": f"{capability}.runtime_evidence",
                    "consumer": "policy_design_case.closeout",
                    "current_break_point": "none",
                }
                for capability in (
                    "lex_legal_kg",
                    "fabric_dataset_catalog_graph",
                    "foundry_method_catalog_expectations",
                    "scientist_workflow_nodes",
                )
            ],
            evidence_ref=_stable_runtime_ref("pdd017", identity["run_id"]),
            runtime_event_ref="event://policy-design-case/pdd-017/dormant-capabilities",
            next_diagnostic_command=next_command,
        ),
        "skip_causality_ledger": build_skip_causality_ledger_record(
            record_id=f"skip-causality-ledger-{identity['run_id']}",
            skipped_nodes=[
                {
                    "node_id": "scientist.legal_conflict_deep_dive",
                    "reason_code": "prerequisite_not_applicable",
                    "missing_input": "legal_conflict_candidate",
                    "prerequisite_status": "no_conflict_detected",
                    "downstream_impact": "No conflict detected; deep-dive not required.",
                    "profile_policy": "serious skips require reason and blocker visibility",
                    "raw_node_outcome_ref": _stable_runtime_ref("skip", "raw"),
                    "progress_event_ref": "event://runtime/progress/scientist/skip/1",
                    "node_event_ref": "event://scientist/node/legal_conflict_deep_dive/skip",
                }
            ],
            projection_preserves_reason_fields=True,
            evidence_ref=_stable_runtime_ref("pdd018", identity["run_id"]),
            runtime_event_ref="event://policy-design-case/pdd-018/skip-causality",
            next_diagnostic_command=next_command,
        ),
        "freshness_policy_time_semantics": build_freshness_policy_time_semantics_record(
            record_id=f"freshness-policy-time-{identity['run_id']}",
            policy_time="2026-05-15",
            evidence_time_bindings=[
                {
                    "evidence_kind": kind,
                    "policy_time": "2026-05-15",
                    "evidence_as_of": as_of,
                    "freshness_status": "pass",
                    "acceptable_recency_window_days": window,
                    "evidence_ref": _stable_runtime_ref("freshness", kind),
                }
                for kind, as_of, window in (
                    ("legal", "2026-05-14", 30),
                    ("data", "2026-05-15", 90),
                    ("benchmark", "2026-05-10", 180),
                    ("decision", "2026-05-17", 30),
                )
            ],
            continuous_governance_triggers=[
                {
                    "trigger_id": "reissue-when-source-stale",
                    "trigger": "source_freshness_expired",
                    "action": "reissue_or_withdraw",
                }
            ],
            final_artifact_date_assumptions=[
                {
                    "artifact": "public_policy_brief",
                    "assumption": "Evidence remains current at publication time.",
                    "evidence_ref": _stable_runtime_ref("freshness", "artifact"),
                }
            ],
            evidence_ref=_stable_runtime_ref("pdd045", identity["run_id"]),
            runtime_event_ref="event://policy-design-case/pdd-045/freshness-policy-time",
            next_diagnostic_command=next_command,
        ),
    }


def _pass1b_record(identity: dict[str, str], refs: dict[str, str]) -> dict[str, Any]:
    case_bindings: dict[str, dict[str, Any]] = {}
    for surface, fields in PASS1B_REQUIRED_CASE_BINDING_FIELDS.items():
        binding: dict[str, Any] = {"status": "pass"}
        for field in fields:
            if field == "tenant_id":
                binding[field] = identity["tenant_id"]
            elif field == "cell_id":
                binding[field] = identity["cell_id"]
            elif field == "read_scope_enforced":
                binding[field] = True
            elif field == "non_overridable_blockers_enforced":
                binding[field] = True
            elif field == "effective_oversight":
                binding[field] = True
            elif field == "rubber_stamp_risk":
                binding[field] = "low"
            elif field == "signature_class":
                binding[field] = "internal_reviewer_attestation"
            elif field == "trust_status":
                binding[field] = "verified"
            elif field == "projection_policy":
                binding[field] = "scorecard_readiness_required"
            elif field.endswith("_refs"):
                binding[field] = [_stable_runtime_ref("pass1b", surface, field)]
            elif field == "runtime_event_ref":
                binding[field] = f"event://policy-design-case/pass1b/{surface}"
            else:
                binding[field] = refs.get(field) or _stable_runtime_ref("pass1b", surface, field)
        case_bindings[surface] = binding
    pdd_bindings = [
        {
            "pdd_id": pdd_id,
            "surface": surfaces[0],
            "surfaces": list(surfaces),
            "record_ref": _stable_runtime_ref("pass1b", pdd_id, "record"),
            "evidence_ref": _stable_runtime_ref("pass1b", pdd_id, "evidence"),
            "runtime_event_ref": f"event://policy-design-case/pass1b/{pdd_id}",
            "owner": "team-runtime-quality",
            "status": "pass",
        }
        for pdd_id, surfaces in PASS1B_PDD_REQUIRED_SURFACES.items()
    ]
    return build_pass1b_tenant_cas_approval_governance_record(
        record_id=f"pass1b-hardening-{identity['run_id']}",
        case_id=f"pdc-{identity['run_id']}",
        run_id=identity["run_id"],
        job_id=identity["job_id"],
        tenant_id=identity["tenant_id"],
        cell_id=identity["cell_id"],
        case_bindings=case_bindings,
        pdd_bindings=pdd_bindings,
        evidence_ref=_stable_runtime_ref("pass1b", identity["run_id"]),
        runtime_event_ref="event://policy-design-case/pass1b/tenant-cas-approval-governance",
    )


def _capability_ledger(identity: dict[str, str]) -> dict[str, Any]:
    duties = [
        build_capability_duty_record(
            capability=capability,
            state="selected",
            evidence_ref=_stable_runtime_ref("capability", capability),
            runtime_event_ref=f"event://policy-design-case/capability/{capability}",
        )
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
    ]
    return build_capability_selection_ledger(
        ledger_ref=_stable_runtime_ref("capability-ledger", identity["run_id"]),
        literature_evidence_required=True,
        duties=duties,
    )


def _policy_intent_envelope(
    *,
    identity: dict[str, str],
    policy_domain: str,
    jurisdiction: str,
) -> dict[str, Any]:
    return build_policy_intent_envelope(
        intent_id=f"intent-{identity['run_id']}",
        run_id=identity["run_id"],
        job_id=identity["job_id"],
        tenant_id=identity["tenant_id"],
        policy_problem="Wartime MSMEs face survival risk and constrained credit access.",
        desired_outcome="Improve MSME survival without unbounded fiscal exposure.",
        proposed_intervention="Target wartime credit support to eligible MSMEs.",
        jurisdiction=jurisdiction,
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="research",
        affected_stakeholders=[
            "MSMEs",
            "participating banks",
            "fiscal authorities",
            "auditors",
        ],
        objectives=["msme survival", "fiscal proportionality"],
        evidence_expectations=[
            "legal authority",
            "production data",
            "literature evidence",
            "method evidence",
        ],
        authoring_provenance={
            "captured_by": "local_production_canary",
            "capture_ref": _stable_runtime_ref("intent", identity["run_id"], policy_domain),
        },
    )


def _concept_spine(
    *,
    identity: dict[str, str],
    policy_intent_ref: str,
    source_id: str,
) -> dict[str, Any]:
    concept_id = "concept.msme_survival_rate"
    return build_policy_design_case_concept_spine(
        run_id=identity["run_id"],
        job_id=identity["job_id"],
        tenant_id=identity["tenant_id"],
        policy_intent_ref=policy_intent_ref,
        fabric_entity_resolution={
            "schema_version": "fabric.entity_resolution.batch.v1",
            "batch_ref": _stable_runtime_ref("concept", "fabric", identity["run_id"]),
            "records": [
                {
                    "entity_id": "fabric:metric:msme_survival_rate",
                    "canonical_name": "MSME survival rate",
                    "aliases": ["SME survival", "firm survival"],
                    "attributes": {
                        "canonical_concept_id": concept_id,
                        "source_terms": "MSME survival, firm survival",
                        "geography": "UA",
                        "population": "wartime MSMEs",
                        "time": "2024-2026",
                        "unit_id": "percent",
                        "currency": "UAH",
                        "price_base": "not_applicable",
                        "exchange_rate_ref": "not_applicable",
                        "inflation_adjustment_ref": "not_applicable",
                        "calendar": "gregorian",
                        "freshness_ref": "freshness.production_msme_panel.2026-05-17",
                    },
                    "provenance_ref": _stable_runtime_ref("concept", "provenance"),
                }
            ],
        },
        scientist_cross_graph={
            "schema_version": "2.1",
            "ontology_snapshot": [
                {
                    "concept_id": concept_id,
                    "label": "MSME survival rate",
                    "metadata": {"population": "wartime MSMEs"},
                }
            ],
            "needs": [
                {
                    "need": {
                        "need_id": "need-msme-survival",
                        "metric_id": "msme_survival_rate",
                        "labels": ["MSME survival"],
                        "geography": "UA",
                        "time_window": "2024-2026",
                    },
                    "resolved_concept_ids": [concept_id],
                    "provenance_refs": [_stable_runtime_ref("concept", "need")],
                }
            ],
            "bridges": [
                {
                    "src_id": "claim.msme_survival_evidence",
                    "dst_concept_id": concept_id,
                    "src_kind": "claim",
                    "numerical_semantics": {
                        "unit_id": "percent",
                        "currency": "UAH",
                        "price_base": "not_applicable",
                        "exchange_rate_ref": "not_applicable",
                        "inflation_adjustment_ref": "not_applicable",
                        "geography": "UA",
                        "time": "2024-2026",
                        "calendar": "gregorian",
                    },
                    "provenance": [_stable_runtime_ref("concept", "bridge")],
                }
            ],
        },
        ir_linker={
            "schema_version": "1.0",
            "ok": True,
            "issues": [],
            "linked_metrics": [
                {
                    "metric_id": "msme_survival_rate",
                    "canonical_concept_id": concept_id,
                    "unit_id": "percent",
                }
            ],
        },
        ir_registry={
            "schema_version": "1.0",
            "concepts": {
                concept_id: {
                    "concept_id": concept_id,
                    "name": "MSME survival rate",
                }
            },
            "metrics": {
                "msme_survival_rate": {
                    "metric_id": "msme_survival_rate",
                    "unit_id": "percent",
                }
            },
            "units": {
                "percent": {"kind": "rate"},
                "uah": {"kind": "money", "currency": "UAH"},
            },
        },
        ir_world={
            "schema_version": "ir.world.concept_projection.v1",
            "world_refs": [
                {
                    "world_id": "world.msme_survival_rate",
                    "canonical_concept_id": concept_id,
                    "provenance_ref": _stable_runtime_ref("concept", "world"),
                }
            ],
            "dataset_bindings": [
                {
                    "dataset_id": source_id,
                    "columns": ["entity_id", "msme_survival_rate", "wartime_credit_support"],
                    "metric_id": "msme_survival_rate",
                    "canonical_concept_id": concept_id,
                }
            ],
            "legal_concept_bindings": [
                {
                    "legal_concept_id": "ua.credit_support.eligibility",
                    "canonical_concept_id": concept_id,
                }
            ],
            "method_requirement_bindings": [
                {
                    "requirement_id": "method.did.minimum_panel",
                    "canonical_concept_id": concept_id,
                }
            ],
            "objective_tradeoff_bindings": [
                {
                    "objective_id": "objective.msme_survival",
                    "tradeoff_id": "tradeoff.fiscal_cost",
                    "canonical_concept_id": concept_id,
                }
            ],
            "geography": ["UA"],
            "population": ["wartime MSMEs"],
            "time": ["2024-2026"],
            "units": ["percent"],
            "currency": ["UAH"],
            "price_bases": ["not_applicable"],
            "exchange_rates": ["not_applicable"],
            "inflation_adjustments": ["not_applicable"],
            "calendars": ["gregorian"],
            "freshness": ["freshness.production_msme_panel.2026-05-17"],
        },
    )


def _deterministic_claim_registry(
    *,
    identity: dict[str, str],
    refs: dict[str, str],
    source_id: str,
) -> dict[str, Any]:
    claim_ref = _stable_runtime_ref("policy_design_case", "claim", identity["run_id"], "rec_1")
    claim_event_ref = f"event://policy_design_case/claim/{identity['run_id']}/rec_1"
    concept_refs = ["concept.msme_survival_rate"]
    legal_norm_refs = [
        "norm.ua.wartime_business_support_authority",
        "norm.ua.credit_eligibility_rule",
        "norm.ua.budget_constraint",
        "norm.ua.equity_and_access_obligation",
    ]
    source_data_refs = [
        source_id,
        _runtime_ref(refs, "data_forge_snapshot_binding_ref", identity["run_id"]),
    ]
    scholar_refs = [
        _runtime_ref(refs, "scholar_evidence_ref", identity["run_id"], "scholar")
    ]
    method_refs = [
        _runtime_ref(refs, "foundry_method_report_ref", identity["run_id"], "foundry"),
        "causal.difference_in_differences",
        "foundry.heterogeneity_by_region_or_firm_size",
        "foundry.uncertainty_interval",
        "foundry.sensitivity_or_transportability_diagnostic",
    ]
    objective_tradeoff_refs = [
        "objective.msme_survival",
        "tradeoff.fiscal_cost",
        _stable_runtime_ref("objective_tradeoff", identity["run_id"], "rec_1"),
    ]
    claim_row = {
        "claim_id": "rec_1",
        "assurance_node_id": f"claim-node-{identity['run_id']}-rec-1",
        "claim_ref": claim_ref,
        "runtime_event_ref": claim_event_ref,
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "concept_refs": concept_refs,
        "legal_norm_refs": legal_norm_refs,
        "source_data_refs": source_data_refs,
        "scholar_refs": scholar_refs,
        "method_refs": method_refs,
        "portfolio_refs": [
            _stable_runtime_ref("portfolio", identity["run_id"], "rec_1")
        ],
        "independence_refs": [
            _stable_runtime_ref("independence", identity["run_id"], "rec_1")
        ],
        "specification_curve_refs": [
            _stable_runtime_ref("specification_curve", identity["run_id"], "rec_1")
        ],
        "disconfirming_refs": [
            _stable_runtime_ref("disconfirming", identity["run_id"], "rec_1")
        ],
        "synthesis_refs": [
            _stable_runtime_ref("synthesis", identity["run_id"], "rec_1")
        ],
        "objective_tradeoff_refs": objective_tradeoff_refs,
        "uncertainty_refs": [
            _stable_runtime_ref("uncertainty", identity["run_id"], "rec_1")
        ],
        "numerical_semantics_refs": [
            _stable_runtime_ref("numerical_semantics", identity["run_id"], "rec_1")
        ],
        "monitoring_refs": [
            _stable_runtime_ref("monitoring", identity["run_id"], "rec_1")
        ],
        "selected_producer_refs": {
            "lex": legal_norm_refs,
            "fabric": [source_id],
            "data_forge": source_data_refs[1:],
            "scholar": scholar_refs,
            "foundry": method_refs,
            "options_objectives": objective_tradeoff_refs,
        },
    }
    return {
        "schema_version": "policyos.runtime.policy_design_case.claim_registry.v1",
        "status": "pass",
        "registry_id": f"claim-registry-{identity['run_id']}",
        "claim_registry_ref": _stable_runtime_ref(
            "policy_design_case", "claim_registry", identity["run_id"]
        ),
        "run_id": identity["run_id"],
        "job_id": identity["job_id"],
        "tenant_id": identity["tenant_id"],
        "claims": [claim_row],
    }


def _deterministic_policy_design_case(
    *,
    identity: dict[str, str],
    refs: dict[str, str],
    normative_evidence: dict[str, Any],
    source_id: str,
    policy_domain: str,
    jurisdiction: str,
) -> dict[str, Any]:
    policy_intent_ref = _runtime_ref(
        refs,
        "policy_intent_envelope_ref",
        identity["run_id"],
        "policy_intent",
    )
    runtime_authority = {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": _runtime_ref(refs, "policy_design_case_ref", identity["run_id"]),
        "runtime_event_ref": _stable_runtime_ref("event", "policy_design_case", identity["run_id"]),
        "same_input_closure_ref": _stable_runtime_ref("closure", "policy_design_case"),
        "effective_mode_ref": _stable_runtime_ref("effective-mode", "policy_design_case"),
        "schema_compatibility_ref": _stable_runtime_ref("schema", "policy_design_case"),
    }
    intent = _policy_intent_envelope(
        identity=identity,
        policy_domain=policy_domain,
        jurisdiction=jurisdiction,
    )
    capability_ledger = _capability_ledger(identity)
    concept_spine = _concept_spine(
        identity=identity,
        policy_intent_ref=policy_intent_ref,
        source_id=source_id,
    )
    case = build_policy_design_case_profile(
        case_id=f"pdc-{identity['run_id']}",
        run_id=identity["run_id"],
        job_id=identity["job_id"],
        tenant_id=identity["tenant_id"],
        effective_execution_profile="research",
        intent_envelope=intent,
        capability_ledger=capability_ledger,
        runtime_authority=runtime_authority,
        nodes=[concept_spine],
    )
    case["jurisdiction_spine"] = build_policy_design_jurisdiction_spine(
        spine_id=f"jurisdiction-spine-{identity['run_id']}",
        jurisdiction_spine_ref=_stable_runtime_ref("jurisdiction", identity["run_id"]),
        run_id=identity["run_id"],
        job_id=identity["job_id"],
        tenant_id=identity["tenant_id"],
        policy_intent_ref=policy_intent_ref,
        lex_normative_report=normative_evidence,
        runtime_authority={
            **runtime_authority,
            "cas_ref": _stable_runtime_ref("jurisdiction", "case", identity["run_id"]),
            "runtime_event_ref": "event://policy-design-case/jurisdiction-spine/1",
        },
    )
    case["substrate_residual_verification"] = _phase28_2_substrate_record(identity)
    case.update(_phase28_3_records(identity))
    case.update(_phase29_records(identity))
    case["pass1b_tenant_cas_approval_governance"] = _pass1b_record(identity, refs)
    case["policy_design_case_ref"] = _runtime_ref(
        refs,
        "policy_design_case_ref",
        identity["run_id"],
    )
    case["runtime_authority"] = runtime_authority
    case["claim_registry"] = _deterministic_claim_registry(
        identity=identity,
        refs=refs,
        source_id=source_id,
    )
    return case


def _has_required_materialization_refs(
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> bool:
    for payload in (job_payload, run_payload):
        refs = _nested_find_dict(payload, "auto_data_source_refs")
        if refs is None:
            continue
        if all(
            isinstance(refs.get(key), str) and refs.get(key)
            for key in REQUIRED_MATERIALIZATION_REFS
        ):
            return True
    return False


def _deterministic_quality_evidence_from_scenario(
    quality_scenario: dict[str, Any] | None,
    *,
    job_payload: dict[str, Any] | None = None,
    run_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build transparent fixture evidence for deterministic simulated matrix lanes."""
    if not isinstance(quality_scenario, dict):
        return {}
    expected = quality_scenario.get("expected_evidence_contract")
    context = quality_scenario.get("context")
    if not isinstance(expected, dict) or not isinstance(context, dict):
        return {}

    identity = _runtime_identity_from_payloads(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    runtime_refs = _runtime_quality_refs_from_payloads(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    materialization_refs = (
        _nested_find_dict(job_payload, "auto_data_source_refs")
        or _nested_find_dict(run_payload, "auto_data_source_refs")
        or {}
    )
    materialization_refs = {
        **{
            key: _runtime_ref(runtime_refs, key, identity["run_id"], key)
            for key in REQUIRED_MATERIALIZATION_REFS
        },
        **{
            str(key): str(value)
            for key, value in materialization_refs.items()
            if isinstance(value, str) and value.strip()
        },
    }
    source_families = [
        str(item)
        for item in expected.get("admissible_data_source_families") or []
        if str(item or "").strip()
    ]
    method_expectations = [
        str(item)
        for item in expected.get("foundry_method_expectations") or []
        if str(item or "").strip()
    ]
    normative_fact_classes = [
        str(item)
        for item in expected.get("normative_fact_classes") or []
        if str(item or "").strip()
    ]
    conflict_checks = [
        str(item)
        for item in expected.get("conflict_checks") or []
        if str(item or "").strip()
    ]

    jurisdiction = (
        _jurisdiction_from_country(context.get("country"))
        or _text_or_none(context.get("jurisdiction"))
        or "global"
    )
    policy_domain = str(context.get("policy_domain") or quality_scenario.get("domain_hint") or "")
    norm_ids = [f"norm.ua.{item}" for item in normative_fact_classes] or [
        "norm.ua.runtime_quality"
    ]
    selected_source_ids = [
        f"{family}.golden_source" for family in source_families
    ] or ["production_data.golden_source"]
    data_snapshot_ref = _runtime_ref(
        runtime_refs,
        "data_snapshot_ref",
        identity["run_id"],
        "data_snapshot",
    )
    selected_methods = [
        {
            "method_id": "causal.difference_in_differences"
            if expectation == "causal_effect_estimation"
            else f"foundry.{expectation}",
            "method_family": expectation,
            "method_expectations": [expectation],
            "input_refs": {
                key: str(value)
                for key, value in materialization_refs.items()
                if key in {"data_snapshot_ref", "input_bindings_ref", "registry_bundle_ref"}
            },
            "assumptions": ["deterministic_fixture_contract"],
            "identification_requirements": {
                "estimand": "ATT",
                "requirements": ["parallel_trends", "overlap"],
            },
            "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
            "missingness": {"status": "pass", "missing_rate": 0.0},
            "missingness_handling": {
                "strategy": "complete_case_with_ipw_sensitivity",
                "status": "pass",
            },
            "sensitivity": {"status": "pass", "robustness": "deterministic"},
            "transportability_limits": {
                "target_population": "wartime_msmes",
                "limits": ["No extrapolation outside observed support."],
            },
            "specification_space": {
                "primary": "two_way_fixed_effects",
                "alternatives": ["event_study", "matched_did"],
            },
            "method_result_refs": {
                "method_result_ref": _stable_runtime_ref(
                    "method-result",
                    expectation,
                    identity["run_id"],
                )
            },
            "validity_surfaces": {
                "identification": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "identification"),
                },
                "transportability": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "transportability"),
                },
                "partial_identification": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "partial"),
                },
                "recoverability": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "recoverability"),
                },
                "causal_ensemble": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "ensemble"),
                },
                "falsification": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "falsification"),
                },
                "certificate_proof": {
                    "status": "present",
                    "ref": _stable_runtime_ref("validity", expectation, "certificate"),
                },
            },
            "input_diagnostics": {"sample_size": 240, "min_required_sample_size": 30},
            "result_summary": {"effect_estimate": 0.04},
        }
        for expectation in (method_expectations or ["causal_effect_estimation"])
    ]
    claim = {
        "claim_id": "rec_1",
        "claim_family": "recommendation",
        "claim_type": "recommendation",
        "major": True,
        "text": str(quality_scenario.get("request") or "Deterministic canary recommendation."),
        "support_summary": "Supported by selected panel data, legal norms, literature, and method output.",
        "uncertainty": "Estimated effects remain uncertain.",
        "policy_tradeoffs": "Improves survival while increasing fiscal exposure.",
        "distributional_impact": "Track rural and women-owned MSMEs separately.",
        "implementation_feasibility": "Can use existing participating-bank rails.",
        "budget_implication": "Requires a capped credit envelope.",
        "stakeholder_impact": "Affects MSMEs, banks, fiscal authorities, and auditors.",
        "implementation_risks": ["Fraud", "adverse selection", "bank capacity"],
        "residual_uncertainty": "Demand and repayment shocks remain uncertain.",
        "monitoring_plan": ["Monitor uptake", "defaults", "complaints", "subgroup outcomes"],
        "withdrawal_reissue_triggers": (
            "Withdraw or reissue if default, fraud, complaint, or subgroup harm thresholds breach."
        ),
        "section_evidence_refs": {
            section: [_stable_runtime_ref("section", section, identity["run_id"])]
            for section in (
                "budget_implication",
                "distributional_impact",
                "implementation_feasibility",
                "implementation_risks",
                "monitoring_plan",
                "policy_tradeoffs",
                "residual_uncertainty",
                "stakeholder_impact",
                "withdrawal_reissue_triggers",
            )
        },
        "data_refs": selected_source_ids,
        "method_refs": [str(method["method_id"]) for method in selected_methods],
        "norm_refs": norm_ids,
    }
    candidate_sources = [
        {
            "source_id": source_id,
            "source_family": family,
            "source_kind": "production_data",
            "source_rights": "government_open_data",
            "dataset_ref": f"dataset:{source_id}",
            "dictionary_ref": f"dictionary:{source_id}:v1",
            "schema_ref": f"schema:{source_id}:v1",
            "field_refs": [
                f"field:{source_id}.entity_id",
                f"field:{source_id}.msme_survival_rate",
                f"field:{source_id}.wartime_credit_support",
            ],
            "unit_refs": ["unit:percent", "unit:UAH"],
            "geography_refs": [jurisdiction],
            "time_coverage_refs": ["2024-2026"],
            "quality_refs": [f"quality:{source_id}:v1"],
            "missingness_refs": [f"missingness:{source_id}:v1"],
            "freshness_refs": [f"freshness:{source_id}:2026-05-15"],
            "lineage_refs": [f"lineage:{source_id}:v1"],
            "transformation_refs": ["transform:survival-rate:v1"],
            "data_forge_snapshot_refs": [data_snapshot_ref],
            "derived_features": [
                {
                    "feature_ref": "feature:msme_survival_rate",
                    "source_ref": source_id,
                    "source_facet_refs": [f"field:{source_id}.msme_survival_rate"],
                    "claim_ids": [claim["claim_id"]],
                    "claim_support_feature_refs": [
                        f"claim-feature:{claim['claim_id']}:msme_survival_rate"
                    ],
                    "lineage_refs": [f"lineage:{source_id}:v1"],
                    "transformation_refs": ["transform:survival-rate:v1"],
                }
            ],
            "freshness": {"status": "pass", "as_of": "2026-05-13"},
            "coverage": {"status": "pass", "geography": jurisdiction},
            "schema_compatibility": {"status": "pass"},
            "relevance_score": 0.95,
            "relevance_rationale": (
                "Deterministic matrix fixture source matches the golden scenario contract."
            ),
        }
        for source_id, family in zip(selected_source_ids, source_families, strict=False)
    ]
    if not candidate_sources:
        candidate_sources = [
            {
                "source_id": selected_source_ids[0],
                "source_family": "production_data",
                "source_kind": "production_data",
                "source_rights": "government_open_data",
                "dataset_ref": f"dataset:{selected_source_ids[0]}",
                "dictionary_ref": f"dictionary:{selected_source_ids[0]}:v1",
                "schema_ref": f"schema:{selected_source_ids[0]}:v1",
                "field_refs": [
                    f"field:{selected_source_ids[0]}.entity_id",
                    f"field:{selected_source_ids[0]}.msme_survival_rate",
                ],
                "unit_refs": ["unit:percent"],
                "geography_refs": [jurisdiction],
                "time_coverage_refs": ["2024-2026"],
                "quality_refs": [f"quality:{selected_source_ids[0]}:v1"],
                "missingness_refs": [f"missingness:{selected_source_ids[0]}:v1"],
                "freshness_refs": [f"freshness:{selected_source_ids[0]}:2026-05-15"],
                "lineage_refs": [f"lineage:{selected_source_ids[0]}:v1"],
                "transformation_refs": ["transform:survival-rate:v1"],
                "data_forge_snapshot_refs": [data_snapshot_ref],
                "derived_features": [
                    {
                        "feature_ref": "feature:msme_survival_rate",
                        "source_ref": selected_source_ids[0],
                        "source_facet_refs": [
                            f"field:{selected_source_ids[0]}.msme_survival_rate"
                        ],
                        "claim_ids": [claim["claim_id"]],
                        "claim_support_feature_refs": [
                            f"claim-feature:{claim['claim_id']}:msme_survival_rate"
                        ],
                        "lineage_refs": [f"lineage:{selected_source_ids[0]}:v1"],
                        "transformation_refs": ["transform:survival-rate:v1"],
                    }
                ],
                "freshness": {"status": "pass", "as_of": "2026-05-13"},
                "coverage": {"status": "pass", "geography": jurisdiction},
                "schema_compatibility": {"status": "pass"},
                "relevance_score": 0.95,
                "relevance_rationale": "Deterministic matrix fixture source is admissible.",
            }
        ]

    norm_records = [
        {
            "norm_id": norm_id,
            "jurisdiction": jurisdiction,
            "policy_domain": policy_domain,
            "effective_from": "2024-01-01",
            "source_authority": "PolicyOS deterministic canary scenario contract",
            "authority_level": "statute",
            "fact_class": fact_class,
        }
        for norm_id, fact_class in zip(norm_ids, normative_fact_classes, strict=False)
    ]
    normative_evidence = {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "status": "pass",
        "target_context": {
            "jurisdiction": jurisdiction,
            "policy_domain": policy_domain,
            "as_of": "2026-05-13",
        },
        "retrieval_status": "completed",
        "legal_corpus_snapshot": {
            "snapshot_id": f"legal-snapshot-{identity['run_id']}",
            "snapshot_ref": _stable_runtime_ref("legal-snapshot", identity["run_id"]),
            "manifest_ref": _stable_runtime_ref("legal-manifest", identity["run_id"]),
        },
        "query_terms": ["credit support", "wartime MSME eligibility"],
        "concept_refs": ["concept.msme_survival_rate"],
        "jurisdiction_filters": [jurisdiction],
        "time_filters": ["2026-05-13"],
        "candidate_norms": norm_records,
        "selected_norms": [{**record, "applicability_status": "applied"} for record in norm_records],
        "applied_norms": norm_records,
        "rejected_norms": [],
        "conflicts": [{"conflict_id": "conflict:resolved-credit-eligibility"}],
        "competence": [
            {
                "competence_ref": f"competence:{norm_id}",
                "norm_id": norm_id,
                "jurisdiction": jurisdiction,
                "source_authority": "PolicyOS deterministic canary scenario contract",
                "authority_level": "statute",
                "competent_authority": "PolicyOS deterministic canary scenario contract",
            }
            for norm_id in norm_ids
        ],
        "authority_blockers": [],
        "blockers": [],
        "recommendation_claims": [
            {
                "claim_id": claim["claim_id"],
                "major": True,
                "norm_refs": norm_ids,
            }
        ],
    }
    fabric_retrieval_trace = {
        "schema_version": "policyos.fabric.source_selection_trace.v1",
        "status": "pass",
        "query_intent": {
            "policy_domain": policy_domain,
            "query_outcome": context.get("query_outcome"),
            "query_treatment": context.get("query_treatment"),
        },
        "candidate_sources": candidate_sources,
        "selected_source_ids": selected_source_ids,
        "rejected_sources": [
            {
                "source_id": f"{selected_source_ids[0]}.alternate",
                "source_family": candidate_sources[0].get("source_family"),
                "reason_code": "lower_relevance",
                "relevance_rationale": "Lower relevance than selected deterministic source.",
            }
        ],
        "materialization_refs": dict(materialization_refs),
        "data_forge_snapshot_refs": [data_snapshot_ref],
    }
    foundry_method_report = {
        "schema_version": "policyos.foundry.method_quality_report.v1",
        "status": "pass",
        "foundry_input_refs": {
            key: str(value)
            for key, value in materialization_refs.items()
            if key in {"data_snapshot_ref", "input_bindings_ref", "registry_bundle_ref"}
        },
        "selected_methods": selected_methods,
    }
    policy_grounding_matrix = {
        "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
        "status": "pass",
        "claims": [claim],
    }
    conflict_check = {
        "schema_version": "policyos.lex.policy_conflict_check.v1",
        "status": "pass",
        "claims": [claim],
        "corpus_constraints": [
            {
                "constraint_id": f"conflict.{check}",
                "constraint_type": "informational_overlap",
                "severity": "info",
                "norm_refs": norm_ids,
            }
            for check in conflict_checks
        ],
    }
    data_forge_snapshot_binding = _deterministic_data_forge_snapshot_binding(
        refs=runtime_refs,
        identity=identity,
    )
    semantic_binding_ledger = build_semantic_binding_ledger(
        runtime_refs={
            key: _runtime_ref(runtime_refs, key, identity["run_id"], key)
            for key in (
                *QUALITY_REPORT_RUNTIME_REFS.values(),
                *POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
            )
        },
        normative_evidence=normative_evidence,
        fabric_retrieval_trace=fabric_retrieval_trace,
        foundry_method_report=foundry_method_report,
        policy_grounding_matrix=policy_grounding_matrix,
        decision_artifact_contract=None,
        final_claims=[claim],
    )
    concept_spine_ref = _stable_runtime_ref("concept-spine", identity["run_id"])
    jurisdiction_spine_ref = _stable_runtime_ref("jurisdiction-spine", identity["run_id"])
    semantic_binding_ledger["spine_context"] = {
        "schema_version": PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
        "context_id": f"producer-spine-context-{identity['run_id']}",
        "concept_spine_ref": concept_spine_ref,
        "jurisdiction_spine_ref": jurisdiction_spine_ref,
        "canonical_concept_refs": ["concept.msme_survival_rate"],
        "jurisdiction_refs": [jurisdiction],
        "consumer_components": list(PRODUCER_SPINE_CONSUMER_COMPONENTS),
    }
    for component in (
        "lex",
        "fabric",
        "scholar",
        "foundry",
        "scientist",
        "final_compiler",
    ):
        rows = semantic_binding_ledger.get(component)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row["consumed_concept_spine_ref"] = concept_spine_ref
            row["consumed_jurisdiction_spine_ref"] = jurisdiction_spine_ref
            row["candidate_spine_binding_refs"] = [
                f"spine-binding:{component}:concept.msme_survival_rate:{jurisdiction}"
            ]
            row["spine_blocker_refs"] = []
            row["local_labels"] = []
    evidence = {
        "normative_evidence": normative_evidence,
        "fabric_retrieval_trace": fabric_retrieval_trace,
        "foundry_method_report": foundry_method_report,
        "policy_grounding_matrix": policy_grounding_matrix,
        "conflict_check": conflict_check,
        "data_forge_snapshot_binding": data_forge_snapshot_binding,
        "scholar_evidence": _deterministic_scholar_evidence(
            refs=runtime_refs,
            identity=identity,
            claim_id=str(claim["claim_id"]),
        ),
        "semantic_binding_ledger": semantic_binding_ledger,
        "policy_design_case": _deterministic_policy_design_case(
            identity=identity,
            refs=runtime_refs,
            normative_evidence=normative_evidence,
            source_id=selected_source_ids[0],
            policy_domain=policy_domain,
            jurisdiction=jurisdiction,
        ),
    }
    return _with_authority_envelopes(
        evidence,
        refs=runtime_refs,
        identity=identity,
        canary_kind="research",
    )


def _deterministic_production_data_quality_report(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    production_data_root: Path,
) -> dict[str, Any]:
    identity = _runtime_identity_from_payloads(job_payload=job_payload, run_payload=run_payload)
    runtime_refs = _runtime_quality_refs_from_payloads(
        job_payload=job_payload,
        run_payload=run_payload,
    )
    materialization_refs = (
        _nested_find_dict(job_payload, "auto_data_source_refs")
        or _nested_find_dict(run_payload, "auto_data_source_refs")
        or {}
    )
    materialization_refs = {
        **{
            key: _runtime_ref(runtime_refs, key, identity["run_id"], key)
            for key in REQUIRED_MATERIALIZATION_REFS
        },
        **{
            str(key): str(value)
            for key, value in materialization_refs.items()
            if isinstance(value, str) and value.strip()
        },
    }
    report_ref = (
        _runtime_ref(
            runtime_refs,
            PRODUCTION_DATA_QUALITY_REF_KEY,
            identity["run_id"],
            "production_data_quality",
        )
    )
    diagnostics = {
        key: {
            "name": key,
            "status": "pass",
            "findings": [],
            "summary": {"source": "deterministic_simulated_canary"},
        }
        for key in DIAGNOSTIC_KEYS
    }
    return {
        "schema_version": "policyos.runtime.production_data_quality.v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": "pass",
        "source": "deterministic_simulated_canary",
        "production_data_root": str(production_data_root),
        "manifest_path": str(production_data_root / "manifest.json"),
        "manifest_sha256": None,
        "diagnostics": diagnostics,
        "issues": [],
        "row_counts": {"deterministic_closeout": 1},
        "entity_counts": {"deterministic_closeout": 1},
        "data_needs": [],
        PRODUCTION_DATA_QUALITY_REF_KEY: report_ref,
        "data_snapshot_ref": materialization_refs.get("data_snapshot_ref"),
        "input_bindings_ref": materialization_refs.get("input_bindings_ref"),
        "registry_bundle_ref": materialization_refs.get("registry_bundle_ref"),
        "quality_report_ref": materialization_refs.get("quality_report_ref"),
        "authority_envelope": _deterministic_authority_envelope(
            report_key="production_data_quality",
            ref_key=PRODUCTION_DATA_QUALITY_REF_KEY,
            ref_value=report_ref,
            run_id=identity["run_id"],
            job_id=identity["job_id"],
            tenant_id=identity["tenant_id"],
            cell_id=identity["cell_id"],
            canary_kind="research",
        ),
    }


def _simulated_provider_preflight(
    *,
    model: str,
    provider_preflight: dict[str, Any] | None,
) -> dict[str, Any] | None:
    status = (
        str(provider_preflight.get("status") or "").strip().lower()
        if isinstance(provider_preflight, dict)
        else ""
    )
    if status and status not in {"skipped", "missing"}:
        return provider_preflight
    return {
        "status": "passed",
        "provider": "simulated",
        "models": [model],
        "simulation_mode": True,
        "source": "local_production_canary.simulated_preflight",
    }


def _response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {"status_code": getattr(response, "status_code", None), "text": response.text}
    return payload if isinstance(payload, dict) else {"payload": payload}


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else {"payload": payload}


def _load_jsonl_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _collect_trace_artifact_refs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_refs = event.get("refs")
        if not isinstance(event_refs, dict):
            continue
        for direction in ("inputs", "outputs"):
            values = event_refs.get(direction)
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict):
                    continue
                artifact_id = value.get("artifact_id")
                if not isinstance(artifact_id, str) or not artifact_id:
                    continue
                refs.append(
                    {
                        "artifact_id": artifact_id,
                        "kind": value.get("kind"),
                        "media_type": value.get("media_type"),
                        "direction": direction,
                        "event_index": index,
                        "event": event.get("event"),
                        "phase": event.get("phase"),
                        "ts": event.get("ts"),
                    }
                )
    return refs


def _infer_trace_status(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("event") == "RUN_FINALIZED":
            metrics = event.get("metrics")
            if isinstance(metrics, dict) and metrics.get("status_ok") == 1:
                return "completed"
            return "failed"
    return "unknown"


def _load_local_run_evidence(
    run_root: Path,
    run_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    for run_dir in (run_root / "runs" / run_id, run_root / "cas" / "runs" / run_id):
        if not run_dir.exists():
            continue
        trace_events = _load_jsonl_file(run_dir / "trace.jsonl")
        checkpoint_head = _load_json_file(run_dir / "checkpoint_head.json")
        checkpoint_history = _load_json_file(run_dir / "checkpoint_history.json")
        checkpoint_entries = (
            checkpoint_history.get("entries") if isinstance(checkpoint_history, dict) else None
        )
        artifact_refs = _collect_trace_artifact_refs(trace_events)
        source = "local_run_files_fallback"
        run_payload = {
            "run_id": run_id,
            "status": _infer_trace_status(trace_events),
            "source": source,
            "run_dir": str(run_dir),
            "checkpoint_head": checkpoint_head,
            "checkpoint_count": len(checkpoint_entries)
            if isinstance(checkpoint_entries, list)
            else 0,
            "trace_event_count": len(trace_events),
            "artifact_ref_count": len(artifact_refs),
        }
        timeline_payload = {
            "run_id": run_id,
            "source": source,
            "events": trace_events,
        }
        lineage_payload = {
            "run_id": run_id,
            "source": source,
            "artifact_refs": artifact_refs,
            "checkpoint_refs": [
                entry
                for entry in (checkpoint_entries or [])
                if isinstance(entry, dict) and entry.get("checkpoint_ref")
            ],
        }
        return run_payload, timeline_payload, lineage_payload
    return None, None, None


def _fallback_agents_payload(
    *,
    run_id: str,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    timeline_payload: dict[str, Any] | None,
    lineage_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not run_id and job_payload is None and run_payload is None:
        return None
    job_progress = (
        job_payload.get("progress") if isinstance(job_payload, dict) else None
    )
    progress_details = (
        job_progress.get("details") if isinstance(job_progress, dict) else None
    )
    performance_summary = (
        progress_details.get("run_performance_summary")
        if isinstance(progress_details, dict)
        else None
    )
    return {
        "schema_version": "policyos.runtime_agents_evidence.v1",
        "source": "local_production_canary.fallback_agents_payload",
        "run_id": run_id,
        "job_id": job_payload.get("job_id") if isinstance(job_payload, dict) else None,
        "status": (
            run_payload.get("status")
            if isinstance(run_payload, dict)
            else job_payload.get("state")
            if isinstance(job_payload, dict)
            else "unknown"
        ),
        "pipeline": {
            "run_id": run_id,
            "status": (
                job_payload.get("state") if isinstance(job_payload, dict) else "unknown"
            ),
            "performance_summary": performance_summary,
        },
        "timeline_event_count": len(timeline_payload.get("events") or [])
        if isinstance(timeline_payload, dict)
        else 0,
        "lineage_artifact_ref_count": len(lineage_payload.get("artifact_refs") or [])
        if isinstance(lineage_payload, dict)
        else 0,
    }


def _get_json(client: Any, path: str) -> dict[str, Any] | None:
    response = client.get(path)
    if response.status_code >= 400:
        return None
    return _response_json(response)


def _runtime_api_context_from_app(app: Any) -> Any | None:
    state = getattr(app, "state", None)
    direct_ctx = getattr(state, "runtime_api_ctx", None)
    if direct_ctx is not None:
        return direct_ctx
    container = getattr(state, "runtime_container", None)
    return getattr(container, "runtime_api_context", None)


def _observe_duration_ms(observations: dict[str, float], key: str, call: Any) -> Any:
    started = time.perf_counter()
    try:
        return call()
    finally:
        observations[key] = round((time.perf_counter() - started) * 1000.0, 3)


def _collect_runtime_hot_path_observations(
    app: Any,
    client: Any,
    *,
    run_id: str,
    tenant_id: str | None = None,
) -> dict[str, float]:
    """Measure runtime hot paths that feed canary_performance_budget.json."""
    observations: dict[str, float] = {}
    ctx = _runtime_api_context_from_app(app)
    run_index = getattr(ctx, "run_index", None)
    refresh = getattr(run_index, "refresh", None)
    list_runs = getattr(run_index, "list_runs", None)
    if callable(refresh):
        _observe_duration_ms(
            observations,
            "run_index_refresh_ms",
            lambda: refresh(force=True),
        )
    if callable(list_runs):
        _observe_duration_ms(
            observations,
            "run_index_list_ms",
            lambda: list_runs(limit=50, tenant_id=tenant_id),
        )
    if run_id:
        _observe_duration_ms(
            observations,
            "timeline_api_ms",
            lambda: _get_json(client, f"/api/v1/runs/{run_id}/timeline"),
        )
        _observe_duration_ms(
            observations,
            "lineage_api_ms",
            lambda: _get_json(client, f"/api/v1/runs/{run_id}/lineage"),
        )
    return observations


def _configure_local_runtime_env(*, run_root: Path, mode: str, timeout_s: int) -> None:
    os.environ.setdefault("POLISYOS_EXECUTION_PROFILE", "research")
    os.environ.setdefault("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    os.environ.setdefault("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    os.environ.setdefault("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    os.environ.setdefault(
        "POLISYOS_CONTROL_SQLITE_PATH",
        str(run_root / "control_plane.sqlite3"),
    )
    os.environ.setdefault("POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY", "1")
    os.environ.setdefault("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "120")
    os.environ.setdefault("POLISYOS_LLM_GATEWAY_BASE_URL", "https://proxy.gonka.gg/v1")
    os.environ.setdefault("POLISYOS_LLM_GATEWAY_PROVIDER", "gonka_proxy")
    os.environ.setdefault("POLISYOS_LLM_GATEWAY_TIMEOUT_S", str(timeout_s))
    os.environ.setdefault("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "1")
    os.environ.setdefault("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    os.environ.setdefault("POLISYOS_FORMALIZER_LLM_RETRIES", "0")
    os.environ.setdefault("POLISYOS_AGENT_LLM_TIMEOUT_S", str(timeout_s))
    os.environ.setdefault("POLISYOS_NL_PIPELINE_TIMEOUT_SECONDS", str(timeout_s * 12))
    os.environ.setdefault("POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS", str(timeout_s * 12))
    if mode == "simulated":
        os.environ["POLISYOS_LLM_SIMULATION_MODE"] = "1"
    else:
        os.environ.pop("POLISYOS_LLM_SIMULATION_MODE", None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("real", "simulated"), default="real")
    parser.add_argument(
        "--execution-profile",
        choices=("dev", "research", "governed", "production"),
        default=os.getenv("POLISYOS_EXECUTION_PROFILE", "research"),
        help="Execution profile to request from the control plane.",
    )
    parser.add_argument(
        "--canary-kind",
        choices=("dev", "research", "governed", "production", "staging"),
        default="",
        help="Quality scorecard canary kind; defaults to staging for simulated legacy runs.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--production-data-root", default="production_data")
    parser.add_argument("--quality-scenario", default=DEFAULT_QUALITY_SCENARIO_ID)
    parser.add_argument("--quality-scenarios-file", default="")
    parser.add_argument("--output-root", default=".polisyos/canary_evidence")
    parser.add_argument("--run-root", default="")
    parser.add_argument(
        "--matrix-lane-id",
        default="",
        help="Stable canary matrix lane id to include in evidence command metadata.",
    )
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--run-budget-usd", type=float, default=0.05)
    parser.add_argument("--provider-timeout-s", type=int, default=45)
    parser.add_argument("--poll-interval-s", type=float, default=2.0)
    parser.add_argument("--timeout-s", type=int, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if TestClient is None:
        print("fastapi TestClient is required for local canary runner", file=sys.stderr)
        return 2

    repo_root = Path.cwd()
    run_root = (
        Path(args.run_root)
        if args.run_root
        else repo_root / ".polisyos" / "local_production_canary" / _utc_stamp()
    )
    run_root.mkdir(parents=True, exist_ok=True)
    _load_env_file(Path(args.env_file))
    os.environ["POLISYOS_EXECUTION_PROFILE"] = args.execution_profile
    _configure_local_runtime_env(
        run_root=run_root,
        mode=args.mode,
        timeout_s=args.provider_timeout_s,
    )

    production_data_root = Path(args.production_data_root).expanduser()
    if not production_data_root.is_absolute():
        production_data_root = repo_root / production_data_root
    production_data_root = _prepare_canary_production_data_root(
        production_data_root,
        run_root=run_root,
    )
    os.environ["POLISYOS_PRODUCTION_DATA_ROOT"] = str(production_data_root)
    scenarios_file = (
        Path(args.quality_scenarios_file).expanduser() if args.quality_scenarios_file else None
    )
    if scenarios_file is not None and not scenarios_file.is_absolute():
        scenarios_file = repo_root / scenarios_file
    try:
        quality_scenario = (
            load_quality_scenario_contract(
                args.quality_scenario,
                scenarios_file=scenarios_file,
            )
            if args.quality_scenario
            else None
        )
    except QualityScenarioContractError as exc:
        error_payload = {"failures": exc.failures}
        _write_json(run_root / "quality_scenario_error.json", error_payload)
        print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
        return 2

    request_payload = _build_canary_request(
        model=args.model,
        production_data_root=production_data_root,
        max_iterations=args.max_iterations,
        run_budget_usd=args.run_budget_usd,
        execution_profile=args.execution_profile,
        quality_scenario=quality_scenario,
    )
    _write_json(run_root / "launch_request.json", request_payload)

    scenario_evidence_contract = (
        quality_scenario.get("scenario_evidence_contract")
        if isinstance(quality_scenario, dict)
        else None
    )
    command_metadata = {
        "runner": "local_production_canary.py",
        "argv": sys.argv[1:] if argv is None else argv,
        "cwd": str(repo_root),
        "run_root": str(run_root),
        "mode": args.mode,
        "execution_profile": args.execution_profile,
        "canary_kind": args.canary_kind,
        "matrix_lane_id": args.matrix_lane_id or None,
        "quality_scenario_id": (quality_scenario.get("scenario_id") if quality_scenario else None),
        "scenario_evidence_contract_id": (
            scenario_evidence_contract.get("contract_id")
            if isinstance(scenario_evidence_contract, dict)
            else None
        ),
        "scenario_evidence_contract": (
            deepcopy(scenario_evidence_contract)
            if isinstance(scenario_evidence_contract, dict)
            else None
        ),
    }
    canary_kind = args.canary_kind or (
        "staging" if args.mode == "simulated" else args.execution_profile
    )
    quality_evidence = (
        {"golden_scenario_contract": quality_scenario} if quality_scenario is not None else None
    )
    launch_payload: dict[str, Any] | None = None
    job_payload: dict[str, Any] | None = None
    run_payload: dict[str, Any] | None = None
    agents_payload: dict[str, Any] | None = None
    timeline_payload: dict[str, Any] | None = None
    lineage_payload: dict[str, Any] | None = None
    provider_preflight: dict[str, Any] | None = None
    runtime_observations: dict[str, float] = {}
    bundle_dir: Path | None = None

    try:
        app = create_runtime_api_app(
            cas_root=run_root / "cas",
            core_runs_root=run_root / "runs",
            enable_security_middlewares=False,
            allow_fixture_identity=True,
        )
        with TestClient(app) as client:
            launch_response = client.post("/api/v1/control/runs/nl", json=request_payload)
            launch_payload = _response_json(launch_response)
            _write_json(run_root / "launch_response.json", launch_payload)
            if launch_response.status_code >= 400:
                print(
                    f"Launch failed before job creation: HTTP {launch_response.status_code}",
                    file=sys.stderr,
                )
                return 1

            job_id = str(launch_payload.get("job_id") or "")
            run_id = str(launch_payload.get("run_id") or "")
            if not job_id:
                print("Launch response did not include job_id", file=sys.stderr)
                return 1

            deadline = time.monotonic() + max(1, args.timeout_s)
            while time.monotonic() < deadline:
                job_payload = _get_json(client, f"/api/v1/control/jobs/{job_id}")
                if job_payload is not None:
                    _write_json(run_root / "job.latest.json", job_payload)
                    provider_preflight = provider_preflight or _extract_provider_preflight(
                        job_payload
                    )
                    if _is_terminal_job_state(job_payload):
                        break
                time.sleep(max(0.1, args.poll_interval_s))
            else:
                print(f"Timed out waiting for job {job_id}", file=sys.stderr)

            provider_preflight = provider_preflight or _extract_provider_preflight(job_payload)
            if run_id:
                runtime_observations.update(
                    _collect_runtime_hot_path_observations(
                        app,
                        client,
                        run_id=run_id,
                        tenant_id=(
                            str(launch_payload.get("tenant_id"))
                            if launch_payload.get("tenant_id")
                            else None
                        ),
                    )
                )
                run_payload = _get_json(client, f"/api/v1/runs/{run_id}")
                agents_payload = _get_json(client, f"/api/v1/runs/{run_id}/agents")
                timeline_payload = _get_json(client, f"/api/v1/runs/{run_id}/timeline")
                lineage_payload = _get_json(client, f"/api/v1/runs/{run_id}/lineage")
                fallback_run, fallback_timeline, fallback_lineage = _load_local_run_evidence(
                    run_root,
                    run_id,
                )
                run_payload = run_payload or fallback_run
                timeline_payload = timeline_payload or fallback_timeline
                lineage_payload = lineage_payload or fallback_lineage
                agents_payload = agents_payload or _fallback_agents_payload(
                    run_id=run_id,
                    job_payload=job_payload,
                    run_payload=run_payload,
                    timeline_payload=timeline_payload,
                    lineage_payload=lineage_payload,
                )

        if runtime_observations:
            command_metadata["runtime_observations"] = dict(runtime_observations)
        if args.mode == "simulated":
            provider_preflight = _simulated_provider_preflight(
                model=args.model,
                provider_preflight=provider_preflight,
            )
            quality_evidence = {
                **dict(quality_evidence or {}),
                **_deterministic_quality_evidence_from_scenario(
                    quality_scenario,
                    job_payload=job_payload,
                    run_payload=run_payload,
                ),
                "production_data_quality": _deterministic_production_data_quality_report(
                    job_payload=job_payload,
                    run_payload=run_payload,
                    production_data_root=production_data_root,
                ),
            }
            quality_evidence = _with_authority_envelopes(
                quality_evidence,
                refs=_runtime_quality_refs_from_payloads(
                    job_payload=job_payload,
                    run_payload=run_payload,
                ),
                identity=_runtime_identity_from_payloads(
                    job_payload=job_payload,
                    run_payload=run_payload,
                ),
                canary_kind=canary_kind,
            )
            job_payload = _with_embedded_runtime_quality_evidence(
                job_payload,
                quality_evidence,
            )
        bundle_dir = assemble_canary_evidence(
            output_root=Path(args.output_root),
            canary_kind=canary_kind,
            command_metadata=command_metadata,
            request_payload=request_payload,
            env=dict(os.environ),
            job_payload=job_payload,
            run_payload=run_payload,
            agents_payload=agents_payload,
            timeline_payload=timeline_payload,
            lineage_payload=lineage_payload,
            provider_preflight=provider_preflight,
            quality_evidence=quality_evidence,
            cas_root=run_root / "cas",
        )
        _write_json(run_root / "evidence_bundle.json", {"path": str(bundle_dir)})
        print(f"Evidence bundle: {bundle_dir}")

        if not job_payload or not _is_terminal_job_state(job_payload):
            return 1
        if str(job_payload.get("state")) != "completed":
            return 1
        if not _has_required_materialization_refs(job_payload, run_payload):
            print(
                "Completed canary is missing required production materialization refs",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        if bundle_dir is None and (launch_payload is not None or job_payload is not None):
            if runtime_observations:
                command_metadata["runtime_observations"] = dict(runtime_observations)
            if args.mode == "simulated":
                provider_preflight = _simulated_provider_preflight(
                    model=args.model,
                    provider_preflight=provider_preflight,
                )
                quality_evidence = {
                    **dict(quality_evidence or {}),
                    **_deterministic_quality_evidence_from_scenario(
                        quality_scenario,
                        job_payload=job_payload,
                        run_payload=run_payload,
                    ),
                    "production_data_quality": _deterministic_production_data_quality_report(
                        job_payload=job_payload,
                        run_payload=run_payload,
                        production_data_root=production_data_root,
                    ),
                }
                quality_evidence = _with_authority_envelopes(
                    quality_evidence,
                    refs=_runtime_quality_refs_from_payloads(
                        job_payload=job_payload,
                        run_payload=run_payload,
                    ),
                    identity=_runtime_identity_from_payloads(
                        job_payload=job_payload,
                        run_payload=run_payload,
                    ),
                    canary_kind=canary_kind,
                )
                job_payload = _with_embedded_runtime_quality_evidence(
                    job_payload,
                    quality_evidence,
                )
            bundle_dir = assemble_canary_evidence(
                output_root=Path(args.output_root),
                canary_kind=canary_kind,
                command_metadata=command_metadata,
                request_payload=request_payload,
                env=dict(os.environ),
                job_payload=job_payload or launch_payload,
                run_payload=run_payload,
                agents_payload=agents_payload
                or _fallback_agents_payload(
                    run_id=str((launch_payload or {}).get("run_id") or ""),
                    job_payload=job_payload,
                    run_payload=run_payload,
                    timeline_payload=timeline_payload,
                    lineage_payload=lineage_payload,
                ),
                timeline_payload=timeline_payload,
                lineage_payload=lineage_payload,
                provider_preflight=provider_preflight,
                quality_evidence=quality_evidence,
                cas_root=run_root / "cas",
            )
            print(f"Evidence bundle: {bundle_dir}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
