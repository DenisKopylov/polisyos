#!/usr/bin/env python3
"""Build deterministic replay refs for a sanitized canary evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.replay import (
    build_replay_manifest,
    explain_replay_drift,
    persist_drift_explanation,
    persist_replay_manifest,
    sanitize_for_replay,
)

SCHEMA_VERSION = "policyos.replay_canary_bundle.v1"
ROOT_CAUSE_FIXTURE_STATUS = "root_cause_fixture"
FEATURE_FLAG_KEYS = (
    "POLISYOS_EXECUTION_PROFILE",
    "POLISYOS_LLM_SIMULATION_MODE",
    "POLISYOS_SCIENTIST_REFLEXION_ENABLED",
    "POLISYOS_SCIENTIST_SWARM_ENABLED",
    "POLISYOS_SCIENTIST_V2_ENABLED",
)
DEPENDENCY_FILES = (
    "uv.lock",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
)
SEED_RE = re.compile(r"(seed|random_state|rng)", re.IGNORECASE)


def replay_canary_bundle(
    bundle_path: str | Path,
    *,
    cas_root: str | Path | None = None,
    baseline_manifest_ref: str | None = None,
    accepted_differences: list[dict[str, Any]] | None = None,
    json_output: str | Path | None = None,
) -> dict[str, Any]:
    """Persist replay manifest and drift explanation refs for one bundle."""

    bundle_dir = Path(bundle_path).expanduser()
    store = FileSystemCAS(Path(cas_root).expanduser() if cas_root else bundle_dir / ".replay_cas")
    manifest = build_replay_manifest_for_bundle(bundle_dir)
    replay_manifest_ref = persist_replay_manifest(manifest, store=store)
    baseline_manifest = (
        _load_manifest_ref(store, baseline_manifest_ref)
        if baseline_manifest_ref
        else manifest
    )
    explanation = explain_replay_drift(
        baseline_manifest=baseline_manifest,
        replay_manifest=manifest,
        accepted_differences=accepted_differences or [],
    )
    drift_explanation_ref = persist_drift_explanation(explanation, store=store)

    result = {
        "schema_version": SCHEMA_VERSION,
        "bundle_path": str(bundle_dir),
        "replay_manifest_ref": str(replay_manifest_ref.artifact_id),
        "drift_explanation_ref": str(drift_explanation_ref.artifact_id),
        "status": explanation["status"],
        "production_readiness": explanation["production_readiness"],
        "summary": explanation["summary"],
        "files": {"replay_result": "replay.json"},
        "drift_explanation": explanation,
    }
    result = sanitize_for_replay(result)
    replay_path = bundle_dir / "replay.json"
    _write_json(replay_path, result)
    _link_from_bundle(
        bundle_dir,
        replay_manifest_ref=str(replay_manifest_ref.artifact_id),
        drift_explanation_ref=str(drift_explanation_ref.artifact_id),
    )
    if json_output is not None:
        _write_json(Path(json_output).expanduser(), result)
    return result


def replay_root_cause_fixture(
    fixture_path: str | Path,
    *,
    json_output: str | Path | None = None,
) -> dict[str, Any]:
    """Render a compact root-cause fixture as a replay failure envelope."""

    path = Path(fixture_path).expanduser()
    fixture = _load_required_json(path)
    summary = _root_cause_fixture_summary(fixture)
    failure_envelope = _root_cause_failure_envelope(fixture)
    result = {
        "schema_version": SCHEMA_VERSION,
        "bundle_path": _string_or_none(fixture.get("bundle_path")),
        "root_cause_fixture_path": str(path),
        "status": ROOT_CAUSE_FIXTURE_STATUS,
        "production_readiness": "fail",
        "summary": summary,
        "files": {"root_cause_fixture": str(path)},
        "failure_envelope": failure_envelope,
        "drift_explanation": {
            "schema_version": "policyos.drift_explanation.v1",
            "status": ROOT_CAUSE_FIXTURE_STATUS,
            "production_readiness": "fail",
            "execution_summary_match": False,
            "quality_summary_match": False,
            "differences": [],
            "summary": summary,
        },
        "root_cause_summary": fixture,
    }
    result = sanitize_for_replay(result)
    if json_output is not None:
        _write_json(Path(json_output).expanduser(), result)
    return result


def build_replay_manifest_for_bundle(bundle_path: str | Path) -> dict[str, Any]:
    """Derive a replay manifest from sanitized bundle files only."""

    bundle_dir = Path(bundle_path).expanduser()
    bundle = _load_json(bundle_dir / "bundle.json")
    files = bundle.get("files") if isinstance(bundle.get("files"), dict) else {}
    request = _load_json(bundle_dir / str(files.get("request") or "request.sanitized.json"))
    env = _load_json(bundle_dir / str(files.get("env") or "env.sanitized.json"))
    artifacts = _load_json(bundle_dir / str(files.get("artifacts") or "artifacts.json"))
    scorecard = _load_scorecard(bundle_dir, bundle, files)
    refs = _refs_from_artifacts(artifacts)
    run_params = _run_params(bundle)

    return build_replay_manifest(
        request_payload=request,
        git_sha=_string_or_none(bundle.get("git_sha")),
        dependency_fingerprints=_dependency_fingerprints(),
        feature_flags=_feature_flags(env),
        provider_model_metadata=_provider_model_metadata(env, bundle, scorecard),
        prompt_template_fingerprints=refs["prompt_template_fingerprints"],
        data_refs=refs["data_refs"],
        source_refs=refs["source_refs"],
        norm_refs=refs["norm_refs"],
        cas_refs=refs["cas_refs"],
        random_seeds=_random_seeds(run_params),
        run_params=run_params,
        quality_scorecard_ref=_quality_scorecard_ref(bundle, files),
        execution_summary=_execution_summary(bundle, scorecard),
        quality_summary=_quality_summary(scorecard, bundle),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {"payload": payload}


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Root-cause fixture does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Root-cause fixture must be a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            sanitize_for_replay(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _load_manifest_ref(store: FileSystemCAS, ref: str | None) -> dict[str, Any]:
    if not ref:
        return {}
    payload = from_canonical_bytes(store.get_bytes(ref))
    return dict(payload) if isinstance(payload, dict) else {}


def _load_scorecard(
    bundle_dir: Path,
    bundle: dict[str, Any],
    files: dict[str, Any],
) -> dict[str, Any]:
    quality_files = files.get("quality_evidence")
    scorecard_path: str | None = None
    if isinstance(quality_files, dict):
        raw = quality_files.get("quality_scorecard")
        if isinstance(raw, str) and raw.strip():
            scorecard_path = raw
    if scorecard_path is None:
        raw = bundle.get("quality_scorecard_ref")
        scorecard_path = raw if isinstance(raw, str) and raw.endswith(".json") else None
    return _load_json(bundle_dir / (scorecard_path or "quality_evidence/quality_scorecard.json"))


def _quality_scorecard_ref(bundle: dict[str, Any], files: dict[str, Any]) -> str | None:
    raw = bundle.get("quality_scorecard_ref")
    if isinstance(raw, str) and raw.strip():
        return raw
    quality_files = files.get("quality_evidence")
    if isinstance(quality_files, dict):
        raw = quality_files.get("quality_scorecard")
        if isinstance(raw, str) and raw.strip():
            return raw
    return None


def _dependency_fingerprints() -> dict[str, str]:
    root = _repo_root()
    fingerprints: dict[str, str] = {}
    for filename in DEPENDENCY_FILES:
        path = root / filename
        if path.exists():
            fingerprints[filename] = _file_fingerprint(path)
    return fingerprints


def _file_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _feature_flags(env: dict[str, Any]) -> dict[str, Any]:
    return {
        key: env[key]
        for key in FEATURE_FLAG_KEYS
        if key in env and env[key] is not None
    }


def _provider_model_metadata(
    env: dict[str, Any],
    bundle: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    provider = (
        _string_or_none(env.get("POLISYOS_LLM_GATEWAY_PROVIDER"))
        or _nested_string(scorecard, "provider")
        or _nested_string(bundle, "provider")
    )
    model = _nested_string(scorecard, "model") or _nested_string(bundle, "model")
    metadata: dict[str, Any] = {}
    if provider:
        metadata["provider"] = provider
    if model:
        metadata["model"] = model
    for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens"):
        found = _nested_value(scorecard, key)
        if found is not None:
            metadata[key] = found
    return metadata


def _refs_from_artifacts(artifacts: dict[str, Any]) -> dict[str, dict[str, str]]:
    buckets = {
        "prompt_template_fingerprints": {},
        "data_refs": {},
        "source_refs": {},
        "norm_refs": {},
        "cas_refs": {},
    }
    refs = artifacts.get("refs")
    if isinstance(refs, list):
        for raw in refs:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("path") or "")
            value = _string_or_none(raw.get("value"))
            if not value:
                continue
            name = _ref_name(path)
            bucket = _bucket_for_ref(name=name, path=path)
            buckets[bucket][name] = value
    quality_resolution = artifacts.get("quality_ref_resolution")
    if isinstance(quality_resolution, dict) and isinstance(quality_resolution.get("refs"), dict):
        for raw_name, raw_value in quality_resolution["refs"].items():
            value = _string_or_none(raw_value)
            if not value:
                continue
            name = str(raw_name)
            buckets["cas_refs"][name] = value
            if "norm" in name:
                buckets["norm_refs"].setdefault(name, value)
            if "fabric" in name or "source" in name:
                buckets["source_refs"].setdefault(name, value)
    return buckets


def _bucket_for_ref(*, name: str, path: str) -> str:
    haystack = f"{path} {name}".lower()
    if "prompt" in haystack or "template" in haystack:
        return "prompt_template_fingerprints"
    if "source_refs" in haystack or "source" in name.lower() or "fabric" in name.lower():
        return "source_refs"
    if "norm_refs" in haystack or "norm" in name.lower():
        return "norm_refs"
    if "data" in name.lower() or "input_bindings" in name.lower():
        return "data_refs"
    return "cas_refs"


def _ref_name(path: str) -> str:
    text = path.strip()
    if not text:
        return "ref"
    text = text.replace("[", ".").replace("]", "")
    return text.rsplit(".", 1)[-1].strip("$") or "ref"


def _run_params(bundle: dict[str, Any]) -> dict[str, Any]:
    command = bundle.get("command")
    if not isinstance(command, dict):
        return {}
    params = command.get("run_params")
    run_params = dict(params) if isinstance(params, dict) else {}
    argv = command.get("argv")
    if isinstance(argv, list):
        run_params["argv"] = [str(item) for item in argv]
    return run_params


def _random_seeds(run_params: dict[str, Any]) -> dict[str, Any]:
    seeds: dict[str, Any] = {}
    for key, value in run_params.items():
        if SEED_RE.search(str(key)):
            seeds[str(key)] = value
    return seeds


def _execution_summary(
    bundle: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "status": bundle.get("execution_status") or bundle.get("status"),
            "job_id": bundle.get("job_id"),
            "run_id": bundle.get("run_id"),
            "scorecard_execution_status": scorecard.get("execution_status"),
        }.items()
        if value is not None
    }


def _quality_summary(
    scorecard: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "quality_status": scorecard.get("quality_status") or bundle.get("quality_status"),
    }
    for key in (
        "overall_score",
        "stage_scores",
        "blocking_quality_failures",
        "warnings",
        "approval_state",
        "performance_status",
    ):
        if key in scorecard:
            summary[key] = scorecard[key]
    return {key: value for key, value in summary.items() if value is not None}


def _nested_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_value(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _nested_value(value, key)
            if found is not None:
                return found
    return None


def _nested_string(payload: Any, key: str) -> str | None:
    return _string_or_none(_nested_value(payload, key))


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _link_from_bundle(
    bundle_dir: Path,
    *,
    replay_manifest_ref: str,
    drift_explanation_ref: str,
) -> None:
    bundle_path = bundle_dir / "bundle.json"
    bundle = _load_json(bundle_path)
    if not bundle:
        return
    bundle["replay_manifest_ref"] = replay_manifest_ref
    bundle["drift_explanation_ref"] = drift_explanation_ref
    files = bundle.get("files")
    if not isinstance(files, dict):
        files = {}
        bundle["files"] = files
    files["replay"] = "replay.json"
    _write_json(bundle_path, bundle)


def _root_cause_fixture_summary(fixture: dict[str, Any]) -> dict[str, Any]:
    expected = _string_list(fixture.get("expected_source_families"))
    selected = _string_list(fixture.get("selected_source_families"))
    scorecard_codes = _string_list(fixture.get("scorecard_codes"))
    missing_pdc_records = _string_list(
        fixture.get("policy_design_case_missing_record_family_codes")
    )
    semantic_error = _string_or_none(fixture.get("semantic_binding_error"))
    return {
        "status": "fail",
        "readiness_state": "not_ready",
        "root_cause_fixture_schema": _string_or_none(fixture.get("schema_version")),
        "scorecard_failure_count": _int_or_zero(
            fixture.get("blocking_quality_failure_count")
        ),
        "scorecard_code_count": len(scorecard_codes),
        "hds_unknown_provenance_count": _int_or_zero(
            fixture.get("hds_unknown_provenance_count")
        ),
        "expected_source_family_count": len(expected),
        "selected_source_family_count": len(selected),
        "lex_candidate_norm_count": _int_or_zero(
            fixture.get("lex_candidate_norm_count")
        ),
        "semantic_binding_error": semantic_error,
        "policy_design_missing_record_family_count": len(missing_pdc_records),
        "root_cause_axes": [
            "scenario_evidence_bridge",
            "lex_query_normalization",
            "authority_classification",
            "semantic_binding_closure",
            "policy_design_record_families",
            "provider_quality_interpretation",
        ],
    }


def _root_cause_failure_envelope(fixture: dict[str, Any]) -> dict[str, Any]:
    raw = fixture.get("failure_envelope")
    if isinstance(raw, dict):
        envelope = dict(raw)
    else:
        envelope = {
            "type": "cloud_production_debug_root_cause_fixture",
            "code": "cloud_prod_debug_root_causes_preserved",
            "readiness_state": "not_ready",
            "phase": "root_cause_regression",
            "owner": "team-runtime-quality",
            "next_action": (
                "Implement evidence-binding remediation waves before using this "
                "lane as production approval evidence."
            ),
        }
    envelope.setdefault("type", "cloud_production_debug_root_cause_fixture")
    envelope.setdefault("code", "cloud_prod_debug_root_causes_preserved")
    envelope.setdefault("readiness_state", "not_ready")
    envelope.setdefault("phase", "root_cause_regression")
    envelope.setdefault("owner", "team-runtime-quality")
    envelope.setdefault("next_action", "Implement evidence-binding remediation waves.")
    return envelope


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _load_accepted_differences(path: str) -> list[dict[str, Any]]:
    if not path:
        return []
    payload = _load_json(Path(path).expanduser())
    raw = payload.get("accepted_differences")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(payload, dict) and {"path", "drift_source"} <= set(payload):
        return [payload]
    return []


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--bundle", help="Sanitized canary evidence bundle path.")
    input_group.add_argument(
        "--root-cause-fixture",
        default="",
        help="Compact root-cause fixture to render as a replay failure envelope.",
    )
    parser.add_argument("--cas-root", default="", help="CAS root used for replay artifacts.")
    parser.add_argument(
        "--baseline-manifest-ref",
        default="",
        help="Optional baseline replay manifest CAS ref to compare against.",
    )
    parser.add_argument(
        "--accepted-differences",
        default="",
        help="Optional JSON file with accepted_differences entries.",
    )
    parser.add_argument("--json-output", default="", help="Optional replay summary output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.root_cause_fixture:
        result = replay_root_cause_fixture(
            args.root_cause_fixture,
            json_output=args.json_output or None,
        )
        print(f"Root-cause fixture: {result['root_cause_fixture_path']}")
        print(f"Production readiness: {result['production_readiness']}")
        print(
            "Failure envelope: "
            + json.dumps(
                result["failure_envelope"],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result["production_readiness"] == "pass" else 2

    result = replay_canary_bundle(
        args.bundle,
        cas_root=args.cas_root or None,
        baseline_manifest_ref=args.baseline_manifest_ref or None,
        accepted_differences=_load_accepted_differences(args.accepted_differences),
        json_output=args.json_output or None,
    )
    print(f"Replay manifest: {result['replay_manifest_ref']}")
    print(f"Drift explanation: {result['drift_explanation_ref']}")
    print(f"Production readiness: {result['production_readiness']}")
    return 0 if result["production_readiness"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
