"""Deterministic canary replay manifests and drift explanations."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

REPLAY_MANIFEST_KIND = "runtime.replay_manifest"
REPLAY_MANIFEST_SCHEMA = "polisyos.runtime.ReplayManifest"
REPLAY_MANIFEST_SCHEMA_VERSION = "policyos.replay_manifest.v1"
DRIFT_EXPLANATION_KIND = "runtime.drift_explanation"
DRIFT_EXPLANATION_SCHEMA = "polisyos.runtime.DriftExplanation"
DRIFT_EXPLANATION_SCHEMA_VERSION = "policyos.drift_explanation.v1"

DRIFT_SOURCES = (
    "assurance",
    "authority",
    "code",
    "data",
    "config",
    "cas",
    "degradation",
    "dependency",
    "event_log",
    "model",
    "mode",
    "norm",
    "nondeterminism",
    "prompt",
    "prompt_tool_parser",
    "provider",
    "registry",
    "schema",
    "semantic_binding",
    "source",
)
IMPACTS = ("none", "low", "medium", "high")

_SECRET_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|bearer|credential|password|refresh[_-]?token|secret|token)",
    re.IGNORECASE,
)
_SAFE_SECRET_LIKE_KEYS = {
    "cached_tokens",
    "completion_tokens",
    "input_tokens",
    "max_completion_tokens",
    "max_tokens",
    "output_tokens",
    "prompt_tokens",
    "reasoning_tokens",
    "token_usage",
    "total_tokens",
}
_SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IGNORED_COMPARISON_PATHS = {
    "$.deterministic_fingerprint",
    "$.manifest_fingerprint",
}


def build_replay_manifest(
    *,
    request_payload: Any | None = None,
    git_sha: str | None = None,
    dependency_fingerprints: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    provider_model_metadata: Mapping[str, Any] | None = None,
    prompt_template_fingerprints: Mapping[str, Any] | None = None,
    data_refs: Mapping[str, Any] | None = None,
    source_refs: Mapping[str, Any] | None = None,
    norm_refs: Mapping[str, Any] | None = None,
    cas_refs: Mapping[str, Any] | None = None,
    random_seeds: Mapping[str, Any] | None = None,
    run_params: Mapping[str, Any] | None = None,
    quality_scorecard_ref: str | None = None,
    runtime_event_log: Mapping[str, Any] | None = None,
    authority_envelopes: Sequence[Mapping[str, Any]] | None = None,
    schema_compatibility_decisions: Mapping[str, Any] | None = None,
    effective_mode_ledger: Mapping[str, Any] | None = None,
    degradation_ledger: Mapping[str, Any] | None = None,
    semantic_binding_ledger: Mapping[str, Any] | None = None,
    prompt_tool_parser_ledger: Mapping[str, Any] | None = None,
    assurance_case: Mapping[str, Any] | None = None,
    registry_refs: Mapping[str, Any] | None = None,
    execution_summary: Mapping[str, Any] | None = None,
    quality_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stable replay contract for one canary execution."""

    sanitized_request = sanitize_for_replay(request_payload or {})
    manifest = {
        "schema_version": REPLAY_MANIFEST_SCHEMA_VERSION,
        "request_fingerprint": _fingerprint(sanitized_request),
        "request_keys": _mapping_keys(sanitized_request),
        "git_sha": _clean_scalar(git_sha),
        "dependency_fingerprints": _stable_mapping(dependency_fingerprints),
        "feature_flags": _stable_mapping(feature_flags),
        "provider_model_metadata": _stable_mapping(provider_model_metadata),
        "prompt_template_fingerprints": _stable_mapping(prompt_template_fingerprints),
        "data_refs": _stable_mapping(data_refs),
        "source_refs": _stable_mapping(source_refs),
        "norm_refs": _stable_mapping(norm_refs),
        "cas_refs": _stable_mapping(cas_refs),
        "random_seeds": _stable_mapping(random_seeds),
        "run_params": _stable_mapping(run_params),
        "quality_scorecard_ref": _clean_scalar(quality_scorecard_ref),
        "runtime_event_log": _stable_mapping(runtime_event_log),
        "authority_envelopes": _stable_sequence(authority_envelopes),
        "schema_compatibility_decisions": _stable_mapping(
            schema_compatibility_decisions
        ),
        "effective_mode_ledger": _stable_mapping(effective_mode_ledger),
        "degradation_ledger": _stable_mapping(degradation_ledger),
        "semantic_binding_ledger": _stable_mapping(semantic_binding_ledger),
        "prompt_tool_parser_ledger": _stable_mapping(prompt_tool_parser_ledger),
        "assurance_case": _stable_mapping(assurance_case),
        "registry_refs": _stable_mapping(registry_refs),
        "execution_summary": _stable_mapping(execution_summary),
        "quality_summary": _stable_mapping(quality_summary),
    }
    manifest["deterministic_fingerprint"] = _fingerprint(
        {
            key: value
            for key, value in manifest.items()
            if key not in {"deterministic_fingerprint", "manifest_fingerprint"}
        }
    )
    return manifest


def explain_replay_drift(
    *,
    baseline_manifest: Mapping[str, Any],
    replay_manifest: Mapping[str, Any],
    accepted_differences: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare two replay manifests and explain every deterministic difference."""

    acceptance = _acceptance_rules(accepted_differences or ())
    differences = [
        _explain_difference(difference, acceptance)
        for difference in _iter_differences(
            sanitize_for_replay(dict(baseline_manifest)),
            sanitize_for_replay(dict(replay_manifest)),
            path="$",
        )
    ]
    unexplained = [
        difference for difference in differences if difference["status"] == "unexplained"
    ]
    accepted = [
        difference
        for difference in differences
        if str(difference["status"]).startswith("accepted")
    ]
    accepted_non_ready = [
        difference
        for difference in differences
        if difference["status"] == "accepted_non_ready"
    ]
    execution_summary_match = _fingerprint(
        baseline_manifest.get("execution_summary") or {}
    ) == _fingerprint(replay_manifest.get("execution_summary") or {})
    quality_summary_match = _fingerprint(
        baseline_manifest.get("quality_summary") or {}
    ) == _fingerprint(replay_manifest.get("quality_summary") or {})

    if unexplained:
        status = "unexplained_drift"
        production_readiness = "fail"
    elif accepted_non_ready:
        status = "accepted_drift_non_ready"
        production_readiness = "fail"
    elif accepted:
        status = "accepted_drift"
        production_readiness = "pass"
    else:
        status = "match"
        production_readiness = "pass"

    payload = {
        "schema_version": DRIFT_EXPLANATION_SCHEMA_VERSION,
        "status": status,
        "production_readiness": production_readiness,
        "execution_summary_match": execution_summary_match,
        "quality_summary_match": quality_summary_match,
        "summary": {
            "difference_count": len(differences),
            "accepted_difference_count": len(accepted),
            "unexplained_difference_count": len(unexplained),
            "drift_sources": sorted(
                {str(difference["drift_source"]) for difference in differences}
            ),
            "max_impact": _max_impact(differences),
        },
        "differences": differences,
    }
    if accepted_non_ready:
        payload["blocking_failure"] = {
            "code": "authority_replay_drift_unbounded",
            "owner": "team-runtime-ops",
            "phase": "runtime_replay",
            "cause": "accepted replay drift exceeds production readiness impact bounds",
            "downstream_impact": "approval and public export are blocked until drift is explained with bounded impact",
            "refs": [str(difference["path"]) for difference in accepted_non_ready],
            "next_command": "uv run pytest tests/unit/runtime/quality/test_replay.py -q",
        }
    return payload


def persist_replay_manifest(
    manifest: Mapping[str, Any],
    *,
    store: Any,
) -> ArtifactRef:
    """Persist a replay manifest and return its CAS ref."""

    return store.put_json(
        sanitize_for_replay(dict(manifest)),
        ArtifactWriteOptions(
            kind=REPLAY_MANIFEST_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=REPLAY_MANIFEST_SCHEMA, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_drift_explanation(
    explanation: Mapping[str, Any],
    *,
    store: Any,
) -> ArtifactRef:
    """Persist a drift explanation and return its CAS ref."""

    return store.put_json(
        sanitize_for_replay(dict(explanation)),
        ArtifactWriteOptions(
            kind=DRIFT_EXPLANATION_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=DRIFT_EXPLANATION_SCHEMA, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def sanitize_for_replay(value: Any, *, key_hint: str | None = None) -> Any:
    """Sanitize replay payloads while preserving deterministic comparison shape."""

    if (
        key_hint
        and _SECRET_KEY_RE.search(key_hint)
        and not _is_safe_secret_like_key(key_hint)
        and not _is_safe_secret_metadata(value)
    ):
        return _redacted_secret(value, key_hint=key_hint)
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_for_replay(item, key_hint=str(key))
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple):
        return [sanitize_for_replay(item, key_hint=key_hint) for item in value]
    if isinstance(value, list):
        return [sanitize_for_replay(item, key_hint=key_hint) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _stable_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    sanitized = sanitize_for_replay(dict(value or {}))
    return sanitized if isinstance(sanitized, dict) else {}


def _stable_sequence(value: Sequence[Mapping[str, Any]] | None) -> list[Any]:
    return sanitize_for_replay(list(value or []))


def _mapping_keys(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return sorted(str(key) for key in value)


def _clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    if _SECRET_KEY_RE.search(text):
        return None
    return text


def _redacted_secret(value: Any, *, key_hint: str) -> dict[str, Any]:
    return {
        "present": bool(value),
        "env_var": key_hint if key_hint.isupper() else None,
        "fingerprint": _fingerprint(str(value)) if value else None,
    }


def _is_safe_secret_metadata(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    keys = set(value)
    return bool(keys) and keys <= {"present", "env_var", "fingerprint"}


def _is_safe_secret_like_key(key_hint: str) -> bool:
    normalized = key_hint.replace("-", "_").lower()
    return (
        normalized in _SAFE_SECRET_LIKE_KEYS
        or normalized.endswith("_tokens")
        or normalized == "fingerprint"
        or normalized.endswith("_fingerprint")
    )


def _fingerprint(value: Any) -> str:
    data = to_canonical_bytes(sanitize_for_replay(value), CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _value_fingerprint(value: Any) -> str:
    if isinstance(value, str) and _SHA256_REF_RE.match(value):
        return value
    return _fingerprint(value)


def _iter_differences(
    baseline: Any,
    replay: Any,
    *,
    path: str,
) -> list[dict[str, Any]]:
    if path in _IGNORED_COMPARISON_PATHS:
        return []
    if isinstance(baseline, Mapping) and isinstance(replay, Mapping):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(baseline) | set(replay)):
            child_path = f"{path}.{key}"
            if child_path in _IGNORED_COMPARISON_PATHS:
                continue
            if key not in baseline or key not in replay:
                differences.append(
                    {
                        "path": child_path,
                        "baseline": baseline.get(key),
                        "replay": replay.get(key),
                    }
                )
                continue
            differences.extend(
                _iter_differences(baseline[key], replay[key], path=child_path)
            )
        return differences
    if baseline != replay:
        return [{"path": path, "baseline": baseline, "replay": replay}]
    return []


def _acceptance_rules(
    accepted_differences: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for raw in accepted_differences:
        path = str(raw.get("path") or "").strip()
        path_prefix = str(raw.get("path_prefix") or "").strip()
        drift_source = str(raw.get("drift_source") or "").strip()
        if not (path or path_prefix) or drift_source not in DRIFT_SOURCES:
            continue
        impact = str(raw.get("impact") or raw.get("max_impact") or "low").strip()
        if impact not in IMPACTS:
            continue
        accepted.append(
            {
                "path": path,
                "path_prefix": path_prefix,
                "drift_source": drift_source,
                "impact": impact,
                "reason": str(raw.get("reason") or "").strip()
                or "Accepted replay drift.",
            }
        )
    return accepted


def _matching_acceptance(
    path: str,
    acceptance: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for rule in acceptance:
        rule_path = str(rule.get("path") or "")
        rule_prefix = str(rule.get("path_prefix") or "")
        if rule_path.endswith(".*"):
            rule_prefix = rule_path[:-2]
            rule_path = ""
        if path == rule_path or (rule_prefix and path.startswith(rule_prefix)):
            return rule
    return None


def _explain_difference(
    difference: Mapping[str, Any],
    acceptance: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    path = str(difference["path"])
    drift_source = _classify_drift_source(path)
    impact = _impact_for_path(path)
    accepted = _matching_acceptance(path, acceptance)
    status = "unexplained"
    reason: str | None = None
    if (
        accepted is not None
        and accepted["drift_source"] == drift_source
        and _impact_rank(impact) <= _impact_rank(str(accepted["impact"]))
    ):
        status = "accepted_non_ready" if _impact_rank(impact) >= _impact_rank("medium") else "accepted"
        reason = str(accepted["reason"])

    payload = {
        "path": path,
        "drift_source": drift_source,
        "impact": impact,
        "status": status,
        "baseline_fingerprint": _value_fingerprint(difference.get("baseline")),
        "replay_fingerprint": _value_fingerprint(difference.get("replay")),
    }
    if reason is not None:
        payload["reason"] = reason
    return payload


def _classify_drift_source(path: str) -> str:
    if path == "$.git_sha" or path.startswith("$.code"):
        return "code"
    if path.startswith("$.registry_refs"):
        return "registry"
    if path.startswith("$.runtime_event_log"):
        return "event_log"
    if path.startswith("$.authority_envelopes"):
        return "authority"
    if path.startswith("$.schema_compatibility_decisions"):
        return "schema"
    if path.startswith("$.effective_mode_ledger"):
        return "mode"
    if path.startswith("$.degradation_ledger"):
        return "degradation"
    if path.startswith("$.semantic_binding_ledger"):
        return "semantic_binding"
    if path.startswith("$.prompt_tool_parser_ledger"):
        return "prompt_tool_parser"
    if path.startswith("$.assurance_case"):
        return "assurance"
    if path.startswith("$.dependency_fingerprints"):
        return "dependency"
    if path.startswith("$.data_refs"):
        return "data"
    if path.startswith("$.source_refs"):
        return "source"
    if path.startswith("$.norm_refs"):
        return "norm"
    if path.startswith("$.cas_refs") or path == "$.quality_scorecard_ref":
        return "cas"
    if path.startswith("$.provider_model_metadata.provider"):
        return "provider"
    if path.startswith("$.provider_model_metadata.model"):
        return "model"
    if path.startswith("$.provider_model_metadata"):
        return "provider"
    if path.startswith("$.prompt_template_fingerprints"):
        return "prompt"
    if (
        path.startswith("$.feature_flags")
        or path.startswith("$.run_params")
        or path == "$.request_fingerprint"
        or path.startswith("$.request_keys")
    ):
        return "config"
    if path.startswith("$.random_seeds"):
        return "nondeterminism"
    if path.startswith("$.execution_summary") or path.startswith("$.quality_summary"):
        return "nondeterminism"
    return "nondeterminism"


def _impact_for_path(path: str) -> str:
    if path.startswith(
        (
            "$.registry_refs",
            "$.runtime_event_log",
            "$.authority_envelopes",
            "$.schema_compatibility_decisions",
            "$.effective_mode_ledger",
            "$.degradation_ledger",
            "$.semantic_binding_ledger",
            "$.prompt_tool_parser_ledger",
            "$.assurance_case",
        )
    ):
        return "high"
    if path.endswith(".quality_status") or path.endswith(".execution_status"):
        return "medium"
    if path.startswith("$.quality_summary.blocking_quality_failures"):
        return "medium"
    if path.startswith("$.quality_summary.overall_score"):
        return "medium"
    if path.startswith("$.execution_summary.status"):
        return "medium"
    return "low"


def _impact_rank(impact: str) -> int:
    try:
        return IMPACTS.index(impact)
    except ValueError:
        return len(IMPACTS)


def _max_impact(differences: Sequence[Mapping[str, Any]]) -> str:
    if not differences:
        return "none"
    return max((str(item["impact"]) for item in differences), key=_impact_rank)


__all__ = [
    "DRIFT_EXPLANATION_SCHEMA_VERSION",
    "DRIFT_SOURCES",
    "REPLAY_MANIFEST_SCHEMA_VERSION",
    "build_replay_manifest",
    "explain_replay_drift",
    "persist_drift_explanation",
    "persist_replay_manifest",
    "sanitize_for_replay",
]
