#!/usr/bin/env python3
"""Smoke-test Policy Design Case walking-skeleton readiness."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.assurance_case import (  # noqa: E402
    POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
    PolicyDesignCaseAuthorityError,
    validate_policy_design_case_profile,
)
from polisyos.runtime.quality.scorecard import build_quality_scorecard  # noqa: E402

SCHEMA_VERSION = "policyos.policy_design_case.walking_skeleton_readiness.v1"
TOOL_NAME = "quality.validation.check-policy-design-case-walking-skeleton"
DEFAULT_FIXTURE = Path(
    "tests/fixtures/policy_design_case/walking_skeleton_case_contract/"
    "walking_skeleton_case_contract_pass.json"
)
DEFAULT_OUTPUT = Path(
    "_build/policy-design-case/rebaseline/wave-7/walking_skeleton_readiness.json"
)
PROFILE_ORDER = ("research", "governed", "production")
REF_PATH_EDGES = (
    "intent -> stub spine",
    "stub spine -> stub producer",
    "stub producer -> claim",
    "single_line_evidence_deficit -> claim",
    "claim -> scorecard/readiness",
)
NODE_AUTHORITY_FIELDS = (
    "cas_ref",
    "runtime_event_ref",
    "diagnostic_event_ref",
    "schema_compatibility_ref",
    "effective_mode_ref",
    "same_input_closure_ref",
)
POLICY_DESIGN_RUNTIME_REF_KEYS = (
    "policy_intent_envelope_ref",
    "policy_design_capability_ledger_ref",
    "policy_design_case_ref",
)
DOMAIN_EVIDENCE_BLOCKERS: tuple[dict[str, str], ...] = (
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "lex",
        "record_family": "legal_authority_and_competence.v1",
        "owner": "team-domain-producers",
        "message": "Lex legal authority evidence is not implemented by the walking skeleton.",
    },
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "fabric",
        "record_family": "data_source_semantic_lineage.v1",
        "owner": "team-domain-producers",
        "message": (
            "Fabric/Data Forge source lineage evidence is not implemented by the "
            "walking skeleton."
        ),
    },
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "scholar",
        "record_family": "scholar_academic_evidence.v1",
        "owner": "team-domain-producers",
        "message": "Scholar literature evidence is not implemented by the walking skeleton.",
    },
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "foundry",
        "record_family": "method_validity_and_results.v1",
        "owner": "team-science-quality",
        "message": "Foundry method validity evidence is not implemented by the walking skeleton.",
    },
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "portfolio",
        "record_family": "evidence_portfolio_and_synthesis.v1",
        "owner": "team-science-quality",
        "message": (
            "Portfolio, independence, multiverse, and synthesis evidence is not "
            "implemented by the walking skeleton."
        ),
    },
    {
        "code": "policy_design_skeleton_missing_domain_evidence",
        "blocker_type": "missing_domain_evidence",
        "domain": "claim_compiler",
        "record_family": "claim_argument_evidence_case.v1",
        "owner": "team-claim-compiler",
        "message": (
            "Full claim argument, warrant, rebuttal, and reliability evidence is "
            "not implemented by the walking skeleton."
        ),
    },
)


def build_walking_skeleton_readiness_payload(
    *,
    repo_root: Path = REPO_ROOT,
    fixture_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    fixture = _resolve_path(repo_root, fixture_path or DEFAULT_FIXTURE)
    case = _load_wave6_case(fixture)
    profiles = {
        profile: _profile_readiness(case, profile=profile)
        for profile in PROFILE_ORDER
    }
    exit_fence = _exit_fence(profiles)
    status = "pass" if all(exit_fence.values()) else "fail"
    output = output_path if output_path is not None else repo_root / DEFAULT_OUTPUT
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "wave": "7",
        "source_fixture": str(fixture),
        "walking_skeleton_contract_id": POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
        "profiles": profiles,
        "exit_fence": exit_fence,
        "output": {"path": str(output), "format": "json"},
        "verification": {
            "acceptance_commands": [
                (
                    "uv run pytest "
                    "tests/repo_quality/tools/test_policy_design_case_walking_skeleton.py -q"
                ),
                (
                    "uv run python tools/quality/validation/"
                    "check_policy_design_case_walking_skeleton.py --repo-root ."
                ),
            ]
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _profile_readiness(case: Mapping[str, Any], *, profile: str) -> dict[str, Any]:
    profile_case = _case_for_profile(case, profile)
    validation_blockers = _validation_blockers(profile_case)
    scorecard = _scorecard_summary(profile_case, profile=profile)
    ref_path = _ref_path(profile_case)
    accepted_deficits = _accepted_deficits(profile_case)
    stub_families = _stub_record_families(profile_case)
    implemented_families = _implemented_domain_record_families(profile_case)
    blockers = [*validation_blockers]
    if profile in {"governed", "production"}:
        blockers.extend(copy.deepcopy(list(DOMAIN_EVIDENCE_BLOCKERS)))

    if blockers:
        outcome = "fail"
    elif accepted_deficits or scorecard["scorecard_status"] != "pass":
        outcome = "deficit"
    else:
        outcome = "pass"

    return {
        "profile": profile,
        "readiness_outcome": outcome,
        "scorecard_status": scorecard["scorecard_status"],
        "scorecard_blocking_codes": scorecard["blocking_codes"],
        "policy_design_case_gate_codes": scorecard["policy_design_case_gate_codes"],
        "all_refs_present": ref_path["status"] == "pass",
        "ref_path": ref_path,
        "accepted_deficits": accepted_deficits,
        "blockers": blockers,
        "stub_record_families": stub_families,
        "implemented_domain_record_families": implemented_families,
        "runtime_ref_keys": list(POLICY_DESIGN_RUNTIME_REF_KEYS),
    }


def _scorecard_summary(case: Mapping[str, Any], *, profile: str) -> dict[str, Any]:
    runtime_refs = _runtime_refs(case)
    job_payload = _job_payload(case, runtime_refs=runtime_refs)
    scorecard = build_quality_scorecard(
        canary_kind=profile,
        job_id=str(case.get("job_id") or ""),
        run_id=str(case.get("run_id") or ""),
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight=None,
        quality_evidence={"policy_design_case": dict(case)},
    )
    blocking_codes = sorted(
        {
            str(failure.get("code") or "")
            for failure in scorecard.get("blocking_quality_failures", [])
            if isinstance(failure, Mapping) and failure.get("code")
        }
    )
    policy_design_codes = sorted(
        {
            str(gate.get("code") or "")
            for gate in scorecard.get("quality_gates", [])
            if isinstance(gate, Mapping)
            and (
                str(gate.get("code") or "").startswith("policy_design")
                or str(gate.get("name") or "").startswith("policy_design_case")
            )
        }
    )
    return {
        "scorecard_status": str(scorecard.get("quality_status") or "fail"),
        "blocking_codes": blocking_codes,
        "policy_design_case_gate_codes": policy_design_codes,
    }


def _validation_blockers(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        validate_policy_design_case_profile(case)
    except PolicyDesignCaseAuthorityError as exc:
        return [
            {
                "code": exc.code,
                "blocker_type": "accepted_deficit_not_allowed",
                "owner": "team-runtime-quality",
                "message": str(exc),
                "next_action": (
                    "Replace the walking skeleton deficit with runtime-owned domain "
                    "evidence before governed or production authority."
                ),
            }
        ]
    return []


def _ref_path(case: Mapping[str, Any]) -> dict[str, Any]:
    nodes = _nodes_by_type(case)
    missing: list[str] = []
    for node_type in ("policy_intent", "concept_spine", "producer_evidence", "claim", "deficit"):
        if node_type not in nodes:
            missing.append(f"node:{node_type}")
    if missing:
        return {"status": "fail", "edges": [], "missing": missing}

    intent = nodes["policy_intent"]
    concept = nodes["concept_spine"]
    producer = nodes["producer_evidence"]
    claim = nodes["claim"]
    deficit = nodes["deficit"]

    checks = {
        "intent -> stub spine": concept.get("intent_ref") == intent.get("cas_ref"),
        "stub spine -> stub producer": (
            producer.get("concept_ref") == concept.get("concept_ref")
            and producer.get("jurisdiction_ref") == concept.get("jurisdiction_ref")
        ),
        "stub producer -> claim": producer.get("cas_ref")
        in set(_string_list(claim.get("producer_evidence_refs"))),
        "single_line_evidence_deficit -> claim": deficit.get("cas_ref")
        in set(_string_list(claim.get("accepted_deficit_refs"))),
        "claim -> scorecard/readiness": all(_runtime_refs(case).values()),
    }
    for node_type, node in nodes.items():
        for field_name in NODE_AUTHORITY_FIELDS:
            value = node.get(field_name)
            if not isinstance(value, str) or not value.strip():
                missing.append(f"{node_type}.{field_name}")
    failed_edges = [edge for edge, passed in checks.items() if not passed]
    return {
        "status": "pass" if not missing and not failed_edges else "fail",
        "edges": list(REF_PATH_EDGES),
        "failed_edges": failed_edges,
        "missing": missing,
        "refs": {
            node_type: {field: node.get(field) for field in NODE_AUTHORITY_FIELDS}
            for node_type, node in sorted(nodes.items())
        },
    }


def _exit_fence(profiles: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    research = profiles["research"]
    return {
        "intent_to_claim_to_scorecard_readiness_ref_path_proven": (
            research.get("all_refs_present") is True
            and research.get("readiness_outcome") in {"pass", "deficit"}
        ),
        "integration_failures_exposed_before_full_domain_implementation": all(
            _has_blocker_type(profiles[profile], "missing_domain_evidence")
            for profile in ("governed", "production")
        ),
        "no_real_domain_family_treated_as_implemented": all(
            not profiles[profile].get("implemented_domain_record_families")
            for profile in PROFILE_ORDER
        ),
    }


def _has_blocker_type(profile: Mapping[str, Any], blocker_type: str) -> bool:
    return any(
        isinstance(blocker, Mapping) and blocker.get("blocker_type") == blocker_type
        for blocker in profile.get("blockers", [])
    )


def _case_for_profile(case: Mapping[str, Any], profile: str) -> dict[str, Any]:
    profile_case = copy.deepcopy(dict(case))
    profile_case["effective_execution_profile"] = profile
    intent = profile_case.get("intent_envelope")
    if isinstance(intent, dict):
        intent["requested_authority_level"] = profile
    authority_profile = profile_case.get("authority_profile")
    if isinstance(authority_profile, dict):
        authority_profile["requested_authority_level"] = profile
        authority_profile["requested_execution_profile"] = profile
        authority_profile["effective_execution_profile"] = profile
    for node in profile_case.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node["requested_execution_profile"] = profile
        node["effective_execution_profile"] = profile
        envelope = node.get("runtime_authority_envelope")
        if isinstance(envelope, dict):
            envelope["requested_execution_profile"] = profile
            envelope["effective_execution_profile"] = profile
    return profile_case


def _load_wave6_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Wave 6 walking skeleton fixture must be a JSON object: {path}")
    return validate_policy_design_case_profile(payload)


def _runtime_refs(case: Mapping[str, Any]) -> dict[str, str]:
    contract = case.get("walking_skeleton_contract")
    capability_ledger = case.get("capability_ledger")
    authority = case.get("authority_chain") or case.get("runtime_authority")
    if not isinstance(contract, Mapping):
        contract = {}
    if not isinstance(capability_ledger, Mapping):
        capability_ledger = {}
    if not isinstance(authority, Mapping):
        authority = {}
    return {
        "policy_intent_envelope_ref": str(contract.get("intent_ref") or ""),
        "policy_design_capability_ledger_ref": str(capability_ledger.get("ledger_ref") or ""),
        "policy_design_case_ref": str(authority.get("cas_ref") or ""),
    }


def _job_payload(case: Mapping[str, Any], *, runtime_refs: Mapping[str, str]) -> dict[str, Any]:
    diagnostic_events = [
        {
            "event_id": f"evt-{ref_key}",
            "event_name": f"{ref_key}.persisted",
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
            "runtime_cas_ref": ref_value,
            "artifact_ref": ref_value,
        }
        for ref_key, ref_value in sorted(runtime_refs.items())
        if ref_value
    ]
    return {
        "job_id": str(case.get("job_id") or ""),
        "run_id": str(case.get("run_id") or ""),
        "state": "completed",
        "progress": {
            "details": {
                "runtime_quality_refs": dict(runtime_refs),
                "diagnostic_events": diagnostic_events,
            }
        },
    }


def _nodes_by_type(case: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("node_type")): dict(node)
        for node in case.get("nodes", [])
        if isinstance(node, Mapping) and node.get("node_type")
    }


def _accepted_deficits(case: Mapping[str, Any]) -> list[str]:
    deficits = []
    for node in case.get("nodes", []):
        if not isinstance(node, Mapping) or node.get("node_type") != "deficit":
            continue
        if node.get("status") == "accepted" and isinstance(node.get("deficit_kind"), str):
            deficits.append(str(node["deficit_kind"]))
    return sorted(set(deficits))


def _stub_record_families(case: Mapping[str, Any]) -> list[str]:
    families = {
        str(node.get("record_family"))
        for node in case.get("nodes", [])
        if isinstance(node, Mapping)
        and node.get("stub_record") is True
        and isinstance(node.get("record_family"), str)
    }
    return sorted(families)


def _implemented_domain_record_families(case: Mapping[str, Any]) -> list[str]:
    families = {
        str(node.get("record_family"))
        for node in case.get("nodes", [])
        if isinstance(node, Mapping)
        and node.get("real_domain_producer") is True
        and isinstance(node.get("record_family"), str)
    }
    return sorted(families)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _format_text(payload: Mapping[str, Any]) -> str:
    lines = [f"{TOOL_NAME}: {payload['status']}"]
    for profile in PROFILE_ORDER:
        result = payload["profiles"][profile]
        lines.append(
            f"{profile}: {result['readiness_outcome']} "
            f"(scorecard={result['scorecard_status']}, refs={result['all_refs_present']})"
        )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    output = _resolve_path(repo_root, args.output)
    payload = build_walking_skeleton_readiness_payload(
        repo_root=repo_root,
        fixture_path=args.fixture,
        output_path=output,
    )
    atomic_write_text(output, dump_json(payload))
    rendered = dump_json(payload) if args.output_format == "json" else _format_text(payload)
    sys.stdout.write(rendered)
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
