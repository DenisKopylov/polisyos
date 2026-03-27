from __future__ import annotations

from typing import Any, Mapping

from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.evidence_sources import normalize_evidence_sources_config
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)

_EXTERNAL_EVIDENCE_MARKERS: frozenset[str] = frozenset(
    {
        "external",
        "external_report",
        "external_literature",
        "literature_external",
    }
)
_SERIOUS_EXECUTION_PROFILES: frozenset[str] = frozenset({"research", "governed", "production"})


def resolve_workflow_id(initial_state: ExperimentState) -> str:
    explicit = str(initial_state.params.get("workflow_id", "") or "").strip().lower()
    if explicit == "scientist_discovery":
        return "scientist_discovery"
    if explicit == "scientist_policy_design":
        return "scientist_policy_design"
    if explicit == "scientist_policy_verified":
        return "scientist_policy_verified"
    if _should_use_discovery(initial_state):
        return "scientist_discovery"
    if _should_use_policy_design(initial_state):
        return "scientist_policy_design"
    if _should_use_policy_verified(initial_state):
        return "scientist_policy_verified"
    if _execution_profile_requires_serious_workflow(initial_state):
        return "scientist_causal_full"
    if explicit == "scientist_causal_full":
        return "scientist_causal_full"
    if _should_auto_escalate_to_causal_full(initial_state):
        return "scientist_causal_full"
    return "scientist_default"


def _should_use_policy_verified(state: ExperimentState) -> bool:
    params = state.params
    answer_mode = str(params.get("policy_answer_mode", "") or "").strip().lower()
    execution_profile = str(state.execution_profile or params.get("execution_profile") or "").strip().lower()
    if answer_mode == "verified_async" or execution_profile == "policy_verified_async":
        return True
    has_trinity = INPUT_TRINITY_BUNDLE_REF in state.inputs
    has_policy_request = any(
        (
            INPUT_RESEARCH_INTENT_REF in state.inputs,
            bool(str(params.get("policy_question", "") or "").strip()),
            bool(str(params.get("policy_request", "") or "").strip()),
            bool(str(params.get("problem_statement", "") or "").strip()),
            bool(str(params.get("research_question", "") or "").strip()),
        )
    )
    return (not has_trinity) and has_policy_request


def _should_use_policy_design(state: ExperimentState) -> bool:
    params = state.params
    execution_profile = str(state.execution_profile or params.get("execution_profile") or "").strip().lower()
    if execution_profile == "policy_design":
        return True
    raw = params.get("policy_mode")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _should_use_discovery(state: ExperimentState) -> bool:
    params = state.params
    execution_profile = str(state.execution_profile or params.get("execution_profile") or "").strip().lower()
    if execution_profile == "discovery":
        return True
    if bool(params.get("discovery_mode")):
        return True
    return bool(params.get("discovery_data")) and bool(params.get("discovery_variable_names"))


def _should_auto_escalate_to_causal_full(state: ExperimentState) -> bool:
    params = state.params
    if _as_bool(params.get("transport_required")):
        return True
    if _contexts_require_transport(params.get("source_context"), params.get("target_context")):
        return True
    if _has_external_evidence_marker(params):
        return True
    if _as_bool(params.get("cross_context_causal_reuse")):
        return True
    config = params.get("cross_graph_evidence_config")
    if isinstance(config, Mapping) and bool(config.get("enabled", True)):
        return True
    evidence_sources = normalize_evidence_sources_config(params)
    if any(
        str(value or "").strip()
        for value in (
            evidence_sources.academic_db_path,
            evidence_sources.datasets_db_path,
            evidence_sources.legal_db_path,
            evidence_sources.benchmark_suite_path,
            evidence_sources.benchmark_report_path,
        )
    ):
        return True
    if _as_bool(params.get("cross_graph_evidence_expected")):
        return True
    return INPUT_KNOWLEDGE_BUNDLE_REF in state.inputs


def _contexts_require_transport(source_raw: Any, target_raw: Any) -> bool:
    source = _context_fingerprint(source_raw)
    target = _context_fingerprint(target_raw)
    return source is not None and target is not None and source != target


def _context_fingerprint(raw: Any) -> str | None:
    if not isinstance(raw, Mapping):
        return None
    context_id = str(raw.get("context_id") or "").strip()
    countries = tuple(str(item).strip().upper() for item in raw.get("countries", []) if str(item).strip())
    time_period = str(raw.get("time_period") or "").strip()
    publication_year = str(raw.get("publication_year") or "").strip()
    if not any((context_id, countries, time_period, publication_year)):
        return None
    return "|".join((context_id, ",".join(countries), time_period, publication_year))


def _has_external_evidence_marker(params: Mapping[str, Any]) -> bool:
    for key in ("source_type", "evidence_source", "causal_source_type", "causal_source"):
        value = params.get(key)
        if not isinstance(value, str):
            continue
        if value.strip().lower() in _EXTERNAL_EVIDENCE_MARKERS:
            return True
    return False


def _execution_profile_requires_serious_workflow(state: ExperimentState) -> bool:
    profile = str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    return profile in _SERIOUS_EXECUTION_PROFILES


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


__all__ = ["resolve_workflow_id"]
