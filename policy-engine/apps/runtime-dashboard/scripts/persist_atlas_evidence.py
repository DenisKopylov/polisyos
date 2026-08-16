"""Persist one Atlas verification payload and its content-bound receipt in Core CAS."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactManifest,
        ArtifactStore,
        ProducerInfo,
        VerificationReport,
    )
    from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo
    from polisyos.core.canon import CanonSpec


OPERATION = "persist_atlas_evidence"
RAW_REPORT_KIND = "atlas_evidence_raw_runner_report"
RAW_REPORT_INPUT_ROLE = "runner_report"
PAYLOAD_KIND = "atlas_evidence_verification_payload"
PAYLOAD_SCHEMA = {
    "id": "polisyos.atlas.evidence-verification-payload",
    "version": "1.0.0",
}
RECONCILIATION_PAYLOAD_SCHEMA = {
    "id": "polisyos.atlas.evidence-verification-payload",
    "version": "1.1.0",
}
RECEIPT_KIND = "atlas_evidence_receipt"
RECEIPT_SCHEMA = {
    "id": "polisyos.atlas.evidence-receipt",
    "version": "1.0.0",
}
RECONCILIATION_RECEIPT_SCHEMA = {
    "id": "polisyos.atlas.evidence-receipt",
    "version": "1.1.0",
}
RECEIPT_INPUT_ROLE = "verification_payload"
PRODUCER_COMPONENT = "polisyos.atlas.evidence_persistence@1.0.0"
PRODUCER_VERSION = "1.0.0"
IMPLEMENTATION_PATHS = (
    "apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
    "apps/runtime-dashboard/src/test/evidence/captureAtlasEvidence.ts",
    "apps/runtime-dashboard/scripts/capture_atlas_evidence.mjs",
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
)
C10_IMPLEMENTATION_PATHS = (
    "apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts",
    "apps/runtime-dashboard/src/app/routes/routes.tsx",
    "apps/runtime-dashboard/src/app/routes/routes.test.tsx",
    "apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs",
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
)
C10_SOURCE_ARTIFACT_PATHS = (
    "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
    "architecture/atlas_surfaces/adoption-ledger.schema.json",
    "architecture/atlas_surfaces/live-application-readiness-ledger.json",
    "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
    "apps/runtime-dashboard/src/app/routes/routes.tsx",
    "apps/runtime-dashboard/src/app/routes/routes.test.tsx",
)
C10_EVIDENCE_KIND = "automated_reconciliation"
C10_SUBJECT = {
    "kind": "surface",
    "subject_id": "atlas-surface-readiness",
    "state_id": "ledger-reconciliation",
}
C10_RULE = {
    "rule_id": "atlas.surface-readiness-reconciliation",
    "rule_version": "1.0.0",
}
C10_AUTHORITY = {
    "authoritative_for": ["atlas_surface_readiness_reconciliation"],
    "may_not_use_for": [
        "component_maturity",
        "design_authority",
        "policy_authority",
        "promotion",
        "publication",
        "runtime_authority",
        "stable",
    ],
}
C10_PRODUCER = {
    "producer_id": "atlas-surface-readiness-reconciliation-producer",
    "producer_version": "1.0.0",
}
C10_VERIFIER = {
    "verifier_id": "atlas-surface-readiness-reconciliation-verifier",
    "verifier_version": "1.0.0",
}
C10_COMMAND_ARGV = ["node", "scripts/reconcile_atlas_surface_readiness.mjs"]
C10_FIELD_PROVENANCE = {
    "adoption_denominator": "recomputed",
    "readiness_denominator": "recomputed",
    "stable_claims": "recomputed",
    "implemented_claims": "recomputed",
    "redirect_route_identity": "independently_reconciled",
    "redirect_behavioral_matrix": "independently_reconciled",
    "route_test_receipt": "independently_reconciled",
    "route_test_process_exit": "independently_reconciled",
    "route_test_report_sha256": "recomputed",
    "raw_report_sha256": "recomputed",
    "canonical_source_artifacts": "recomputed",
    "capture_implementation": "independently_reconciled",
}
C10_ROUTE_TEST_RECEIPT_SCHEMA = {
    "id": "polisyos.atlas.c10-route-test-receipt",
    "version": "1.0.0",
}
C10_ROUTE_TEST_FILE = "src/app/routes/routes.test.tsx"
C10_ROUTE_TEST_ASSERTIONS = (
    "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/launch'",
    "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/sources'",
    "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/data'",
    "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/lex'",
    "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/health'",
)
C10_RUNTIME_FACTS_COMMAND = (
    "node",
    "apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs",
    "--canonical-facts",
)
C10_RECONCILIATION_KEYS = {
    "adoption_entries",
    "adoption_stable",
    "adoption_stable_ids",
    "readiness_entries",
    "readiness_stable",
    "readiness_stable_ids",
    "readiness_implemented",
    "implemented_surface_ids",
    "nondeprecated_implemented_ids",
    "verified_deprecated_redirects",
}
DENIED_USES = [
    "component_maturity",
    "design_authority",
    "policy_authority",
    "promotion",
    "publication",
    "runtime_authority",
    "stable",
]
BOUND_FIELDS = ("evidence_kind", "subject", "rule", "provenance", "times", "result")


class AtlasEvidencePersistenceError(ValueError):
    """Report a fail-closed Atlas evidence persistence contract violation."""


def _policy_engine_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_worktree_import_root() -> None:
    source_root = str(_policy_engine_root() / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AtlasEvidencePersistenceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_json_constant(value: str) -> NoReturn:
    raise AtlasEvidencePersistenceError(f"non-JSON numeric constant: {value}")


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise AtlasEvidencePersistenceError("stdin must contain one JSON request")
    try:
        request = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise AtlasEvidencePersistenceError(f"stdin is not valid JSON: {exc.msg}") from exc
    if not isinstance(request, dict):
        raise AtlasEvidencePersistenceError("request must be a JSON object")
    expected = {"operation", "payload", "raw_report_base64", "receipt"}
    actual = set(request)
    if actual != expected:
        raise AtlasEvidencePersistenceError(
            f"request keys must be exactly {sorted(expected)}; got {sorted(actual)}"
        )
    if request["operation"] != OPERATION:
        raise AtlasEvidencePersistenceError(f"operation must equal {OPERATION!r}")
    if not isinstance(request["raw_report_base64"], str) or not request["raw_report_base64"]:
        raise AtlasEvidencePersistenceError("raw_report_base64 must be a non-empty string")
    if not isinstance(request["payload"], dict):
        raise AtlasEvidencePersistenceError("payload must be a JSON object")
    if not isinstance(request["receipt"], dict):
        raise AtlasEvidencePersistenceError("receipt must be a JSON object")
    return request


def _parse_raw_report(raw_report: bytes) -> dict[str, Any]:
    """Decode strict raw JSON once so C10 can content-bind it before CAS."""
    try:
        parsed = json.loads(
            raw_report.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasEvidencePersistenceError("raw runner report must be valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise AtlasEvidencePersistenceError("raw runner report must be a JSON object")
    return parsed


def _decode_raw_report(value: str) -> bytes:
    try:
        raw_report = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AtlasEvidencePersistenceError("raw_report_base64 is not canonical base64") from exc
    if not raw_report:
        raise AtlasEvidencePersistenceError("raw runner report must not be empty")
    _parse_raw_report(raw_report)
    return raw_report


def _require_exact_mapping(value: object, expected: Mapping[str, object], *, field: str) -> None:
    if value != dict(expected):
        raise AtlasEvidencePersistenceError(f"{field} must equal the C07 contract")


def _run_git(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed executable; arguments are module-owned.
        ["/usr/bin/git", *args],
        cwd=_policy_engine_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AtlasEvidencePersistenceError(
            f"capture implementation git provenance failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _capture_implementation_provenance(
    implementation_paths: tuple[str, ...],
) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    aggregate = hashlib.sha256()
    for relative_path in implementation_paths:
        file_sha256 = hashlib.sha256(
            (_policy_engine_root() / relative_path).read_bytes()
        ).hexdigest()
        files.append({"path": relative_path, "sha256": file_sha256})
        aggregate.update(f"{relative_path}\0{file_sha256}\n".encode())
    repository_revision = _run_git("rev-parse", "HEAD").strip()
    dirty = bool(_run_git("status", "--porcelain=v1").strip())
    return {
        "implementation_sha256": aggregate.hexdigest(),
        "files": files,
        "repository_revision": repository_revision,
        "dirty": dirty,
    }


def _capture_c10_source_artifacts() -> dict[str, Any]:
    """Hash the fixed canonical owner artifacts C10 is allowed to reconcile."""
    files: list[dict[str, str]] = []
    aggregate = hashlib.sha256()
    for relative_path in C10_SOURCE_ARTIFACT_PATHS:
        file_sha256 = hashlib.sha256(
            (_policy_engine_root() / relative_path).read_bytes()
        ).hexdigest()
        files.append({"path": relative_path, "sha256": file_sha256})
        aggregate.update(f"{relative_path}\0{file_sha256}\n".encode())
    return {"source_set_sha256": aggregate.hexdigest(), "files": files}


def _read_c10_canonical_json(relative_path: str) -> dict[str, Any]:
    """Read one fixed canonical C10 JSON owner with strict JSON decoding."""
    return _parse_raw_report((_policy_engine_root() / relative_path).read_bytes())


def _c10_entries(
    ledger: dict[str, Any],
    *,
    label: str,
    identity_field: str,
    requires_readiness_state: bool,
) -> list[dict[str, Any]]:
    """Return one owner ledger population after its C10-relevant invariants."""
    entries = ledger.get("entries")
    if not isinstance(entries, list) or not entries:
        raise AtlasEvidencePersistenceError(f"C10 {label} ledger entries must be a non-empty list")
    identities: set[str] = set()
    parsed: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise AtlasEvidencePersistenceError(f"C10 {label} ledger entry must be a JSON object")
        identity = entry.get(identity_field)
        maturity = entry.get("maturity")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in identities
            or maturity not in {"experimental", "beta", "stable", "deprecated"}
        ):
            raise AtlasEvidencePersistenceError(
                f"C10 {label} ledger does not satisfy its canonical identity vocabulary"
            )
        if requires_readiness_state and entry.get("readiness_state") not in {
            "contract_only",
            "producer_missing",
            "bridge_missing",
            "consumer_missing",
            "verification_missing",
            "surface_missing",
            "semantic_test_missing",
            "implemented",
        }:
            raise AtlasEvidencePersistenceError(
                "C10 readiness ledger does not satisfy its canonical readiness vocabulary"
            )
        identities.add(identity)
        parsed.append(entry)
    return parsed


def _c10_runtime_redirects() -> list[dict[str, str]]:
    """Derive the exact deprecated routes through the real APP_ROUTES runtime owner."""
    result = subprocess.run(  # noqa: S603 - module-owned fixed command tuple.
        C10_RUNTIME_FACTS_COMMAND,
        cwd=_policy_engine_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AtlasEvidencePersistenceError(
            "C10 runtime redirect derivation failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        facts = json.loads(
            result.stdout,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise AtlasEvidencePersistenceError(
            "C10 runtime redirect facts are not valid JSON"
        ) from exc
    if not isinstance(facts, dict) or set(facts) != {"redirects"}:
        raise AtlasEvidencePersistenceError(
            "C10 runtime redirect facts must contain only redirects"
        )
    redirects = facts.get("redirects")
    if not isinstance(redirects, list) or len(redirects) != 5:
        raise AtlasEvidencePersistenceError(
            "C10 runtime redirect facts must contain exactly five rows"
        )
    identities: set[str] = set()
    parsed: list[dict[str, str]] = []
    for redirect in redirects:
        if not isinstance(redirect, dict) or set(redirect) != {"surface_id", "from", "to"}:
            raise AtlasEvidencePersistenceError("C10 runtime redirect row shape mismatch")
        surface_id = redirect.get("surface_id")
        source = redirect.get("from")
        target = redirect.get("to")
        if (
            not isinstance(surface_id, str)
            or not surface_id
            or surface_id in identities
            or not isinstance(source, str)
            or not source.startswith("/")
            or not isinstance(target, str)
            or not target.startswith("/")
        ):
            raise AtlasEvidencePersistenceError("C10 runtime redirect row values mismatch")
        identities.add(surface_id)
        parsed.append({"surface_id": surface_id, "from": source, "to": target})
    return parsed


def _derive_c10_route_test_receipt(
    raw_report: dict[str, Any], raw_report_bytes: bytes, process_exit_code: int
) -> dict[str, Any]:
    """Derive C10's behavioral receipt from the exact Vitest JSON bytes."""
    test_results = raw_report.get("testResults")
    results = test_results if isinstance(test_results, list) else []
    matching_results = [
        result
        for result in results
        if isinstance(result, dict)
        and isinstance(result.get("name"), str)
        and result["name"].replace("\\", "/").endswith(f"/{C10_ROUTE_TEST_FILE}")
    ]
    test_result = matching_results[0] if len(matching_results) == 1 else None
    assertions = (
        test_result.get("assertionResults")
        if isinstance(test_result, dict) and isinstance(test_result.get("assertionResults"), list)
        else []
    )
    required_assertions: list[dict[str, str]] = []
    for expected_name in C10_ROUTE_TEST_ASSERTIONS:
        matching_assertions = [
            assertion
            for assertion in assertions
            if isinstance(assertion, dict) and assertion.get("fullName") == expected_name
        ]
        status = (
            "pass"
            if len(matching_assertions) == 1
            and matching_assertions[0].get("status") == "passed"
            else "missing"
            if not matching_assertions
            else "fail"
        )
        required_assertions.append({"full_name": expected_name, "status": status})
    receipt: dict[str, Any] = {
        "receipt_schema": C10_ROUTE_TEST_RECEIPT_SCHEMA,
        "test_file": C10_ROUTE_TEST_FILE,
        "report_sha256": hashlib.sha256(raw_report_bytes).hexdigest(),
        "process_exit_code": process_exit_code,
        "outcome": "fail",
        "required_assertions": required_assertions,
        "failure_code": "redirect_test_receipt_invalid",
    }
    passed = (
        process_exit_code == 0
        and raw_report.get("success") is True
        and isinstance(test_result, dict)
        and test_result.get("status") == "passed"
        and all(assertion["status"] == "pass" for assertion in required_assertions)
    )
    if passed:
        receipt.pop("failure_code")
        receipt["outcome"] = "pass"
    return receipt


def _c10_canonical_reconciliation(
    route_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute the only C10 result that may reach the CAS write boundary."""
    adoption_entries = _c10_entries(
        _read_c10_canonical_json("architecture/atlas_surfaces/atlas-v15-adoption-ledger.json"),
        label="adoption",
        identity_field="id",
        requires_readiness_state=False,
    )
    readiness_entries = _c10_entries(
        _read_c10_canonical_json(
            "architecture/atlas_surfaces/live-application-readiness-ledger.json"
        ),
        label="readiness",
        identity_field="surface_id",
        requires_readiness_state=True,
    )
    adoption_stable = [entry for entry in adoption_entries if entry["maturity"] == "stable"]
    readiness_stable = [entry for entry in readiness_entries if entry["maturity"] == "stable"]
    implemented = [
        entry for entry in readiness_entries if entry["readiness_state"] == "implemented"
    ]
    nondeprecated_implemented = [
        entry for entry in implemented if entry["maturity"] != "deprecated"
    ]
    redirects = _c10_runtime_redirects()
    deprecated_implemented_ids = [
        entry["surface_id"]
        for entry in implemented
        if entry["maturity"] == "deprecated"
    ]
    exact_deprecated_set = len(deprecated_implemented_ids) == len(redirects) and all(
        redirect["surface_id"] in deprecated_implemented_ids for redirect in redirects
    )
    findings: list[dict[str, str]] = []
    for entry in adoption_stable:
        findings.append(
            {
                "code": "stable_evidence_reference_unresolved",
                "detail": (
                    f"stable adoption entry {entry['id']} has no typed subject-bound Core evidence"
                ),
            }
        )
    for entry in readiness_stable:
        findings.append(
            {
                "code": "stable_evidence_reference_unresolved",
                "detail": (
                    "stable readiness entry "
                    f"{entry['surface_id']} has no typed subject-bound Core evidence"
                ),
            }
        )
    for entry in nondeprecated_implemented:
        findings.extend(
            [
                {
                    "code": "implemented_negative_test_missing",
                    "detail": (
                        f"implemented entry {entry['surface_id']} "
                        "lacks typed negative-test evidence"
                    ),
                },
                {
                    "code": "implemented_semantic_test_missing",
                    "detail": (
                        f"implemented entry {entry['surface_id']} "
                        "lacks typed semantic-test evidence"
                    ),
                },
            ]
        )
    if not exact_deprecated_set:
        findings.append(
            {
                "code": "implemented_deprecated_redirect_unverified",
                "detail": (
                    "deprecated implemented ledger identities do not equal the exact runtime "
                    "redirect set"
                ),
            }
        )
    if route_receipt["outcome"] != "pass":
        findings.append(
            {
                "code": "redirect_test_receipt_invalid",
                "detail": (
                    "the launcher did not receive five exact passing runtime redirect assertions"
                ),
            }
        )
    reconciliation = {
        "adoption_entries": len(adoption_entries),
        "adoption_stable": len(adoption_stable),
        "adoption_stable_ids": [entry["id"] for entry in adoption_stable],
        "readiness_entries": len(readiness_entries),
        "readiness_stable": len(readiness_stable),
        "readiness_stable_ids": [entry["surface_id"] for entry in readiness_stable],
        "readiness_implemented": len(implemented),
        "implemented_surface_ids": [entry["surface_id"] for entry in implemented],
        "nondeprecated_implemented_ids": [
            entry["surface_id"] for entry in nondeprecated_implemented
        ],
        "verified_deprecated_redirects": redirects if exact_deprecated_set else [],
    }
    return reconciliation, {"outcome": "pass" if not findings else "fail", "findings": findings}


def _contract_for(
    payload: Mapping[str, object], receipt: Mapping[str, object]
) -> tuple[dict[str, str], dict[str, str], set[str], dict[str, list[str]], tuple[str, ...]]:
    payload_schema = payload.get("payload_schema")
    receipt_schema = receipt.get("receipt_schema")
    if payload_schema == PAYLOAD_SCHEMA and receipt_schema == RECEIPT_SCHEMA:
        return (
            PAYLOAD_SCHEMA,
            RECEIPT_SCHEMA,
            {"automated_browser", "automated_keyboard", "manual_at"},
            {
                "authoritative_for": ["atlas_evidence_capture"],
                "may_not_use_for": DENIED_USES,
            },
            IMPLEMENTATION_PATHS,
        )
    if (
        payload_schema == RECONCILIATION_PAYLOAD_SCHEMA
        and receipt_schema == RECONCILIATION_RECEIPT_SCHEMA
    ):
        return (
            RECONCILIATION_PAYLOAD_SCHEMA,
            RECONCILIATION_RECEIPT_SCHEMA,
            {C10_EVIDENCE_KIND},
            C10_AUTHORITY,
            C10_IMPLEMENTATION_PATHS,
        )
    raise AtlasEvidencePersistenceError(
        "payload_schema and receipt_schema must form one supported C07/C10 versioned contract"
    )


def _is_lower_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_c10_route_test_receipt(value: object) -> None:
    """Require the launcher-owned exact behavioral redirect matrix receipt."""
    if not isinstance(value, dict):
        raise AtlasEvidencePersistenceError("C10 route-test receipt must be a JSON object")
    expected_keys = {
        "receipt_schema",
        "test_file",
        "report_sha256",
        "process_exit_code",
        "outcome",
        "required_assertions",
    }
    if value.get("outcome") == "fail":
        expected_keys.add("failure_code")
    if set(value) != expected_keys:
        raise AtlasEvidencePersistenceError("C10 route-test receipt keys are not exact")
    _require_exact_mapping(
        value.get("receipt_schema"),
        C10_ROUTE_TEST_RECEIPT_SCHEMA,
        field="C10 route-test receipt schema",
    )
    if value.get("test_file") != C10_ROUTE_TEST_FILE:
        raise AtlasEvidencePersistenceError("C10 route-test receipt test file mismatch")
    if not _is_lower_sha256(value.get("report_sha256")):
        raise AtlasEvidencePersistenceError("C10 route-test receipt digest must be SHA-256")
    process_exit_code = value.get("process_exit_code")
    if type(process_exit_code) is not int or process_exit_code < 0:
        raise AtlasEvidencePersistenceError("C10 route-test receipt process exit code mismatch")
    if value.get("outcome") not in {"pass", "fail"}:
        raise AtlasEvidencePersistenceError("C10 route-test receipt outcome must be pass or fail")
    assertions = value.get("required_assertions")
    if not isinstance(assertions, list) or len(assertions) != len(C10_ROUTE_TEST_ASSERTIONS):
        raise AtlasEvidencePersistenceError("C10 route-test receipt must contain five assertions")
    assertion_statuses: list[str] = []
    for expected_name, assertion in zip(C10_ROUTE_TEST_ASSERTIONS, assertions, strict=True):
        if not isinstance(assertion, dict) or set(assertion) != {"full_name", "status"}:
            raise AtlasEvidencePersistenceError("C10 route-test assertion shape mismatch")
        if assertion.get("full_name") != expected_name:
            raise AtlasEvidencePersistenceError("C10 route-test assertion identity mismatch")
        status = assertion.get("status")
        if status not in {"pass", "fail", "missing"}:
            raise AtlasEvidencePersistenceError("C10 route-test assertion status mismatch")
        assertion_statuses.append(status)
    all_passed = all(status == "pass" for status in assertion_statuses)
    if value["outcome"] == "pass" and (
        process_exit_code != 0 or not all_passed or "failure_code" in value
    ):
        raise AtlasEvidencePersistenceError(
            "C10 passing route-test receipt is not behaviorally complete"
        )
    if value["outcome"] == "fail" and value.get("failure_code") != "redirect_test_receipt_invalid":
        raise AtlasEvidencePersistenceError("C10 failed route-test receipt needs its named code")


def _validate_c10_contract(
    payload: dict[str, Any],
    receipt: dict[str, Any],
    *,
    implementation_provenance: Mapping[str, object],
) -> None:
    """Fail closed unless this is exactly the C10 reconciliation observation."""
    if payload.get("evidence_kind") != C10_EVIDENCE_KIND:
        raise AtlasEvidencePersistenceError("C10 evidence kind mismatch")
    _require_exact_mapping(payload.get("subject"), C10_SUBJECT, field="C10 payload subject")
    _require_exact_mapping(payload.get("rule"), C10_RULE, field="C10 payload rule")
    _require_exact_mapping(receipt.get("authority"), C10_AUTHORITY, field="C10 receipt authority")
    _require_exact_mapping(receipt.get("subject"), C10_SUBJECT, field="C10 receipt subject")
    _require_exact_mapping(receipt.get("rule"), C10_RULE, field="C10 receipt rule")
    for label, provenance in (
        ("payload", payload.get("provenance")),
        ("receipt", receipt.get("provenance")),
    ):
        if not isinstance(provenance, dict):
            raise AtlasEvidencePersistenceError(f"C10 {label} provenance must be a JSON object")
        if provenance.get("producer") != C10_PRODUCER:
            raise AtlasEvidencePersistenceError(f"C10 {label} producer identity mismatch")
        if provenance.get("verifier") != C10_VERIFIER:
            raise AtlasEvidencePersistenceError(f"C10 {label} verifier identity mismatch")
        if provenance.get("command_argv") != C10_COMMAND_ARGV:
            raise AtlasEvidencePersistenceError(f"C10 {label} command identity mismatch")
        if provenance.get("predicate_provenance") != "independently_reconciled":
            raise AtlasEvidencePersistenceError(
                f"C10 {label} predicate provenance must be independently_reconciled"
            )
        if provenance.get("repository_revision") != implementation_provenance[
            "repository_revision"
        ]:
            raise AtlasEvidencePersistenceError(
                f"C10 {label} repository revision does not bind implementation provenance"
            )
    details = payload.get("details")
    if not isinstance(details, dict):
        raise AtlasEvidencePersistenceError("C10 details must be a JSON object")
    expected_detail_keys = {
        "reconciliation",
        "route_test_receipt",
        "route_test_report_sha256",
        "raw_report_sha256",
        "source_artifacts",
        "capture_implementation",
        "field_provenance",
    }
    if set(details) != expected_detail_keys:
        raise AtlasEvidencePersistenceError("C10 details keys must bind the exact basis")
    _require_exact_mapping(
        details.get("field_provenance"),
        C10_FIELD_PROVENANCE,
        field="C10 field provenance",
    )
    if not _is_lower_sha256(details.get("raw_report_sha256")):
        raise AtlasEvidencePersistenceError("C10 raw report digest must be SHA-256")
    if not _is_lower_sha256(details.get("route_test_report_sha256")):
        raise AtlasEvidencePersistenceError("C10 route-test digest must be SHA-256")
    _validate_c10_route_test_receipt(details.get("route_test_receipt"))
    route_receipt = details["route_test_receipt"]
    if details["route_test_report_sha256"] != route_receipt["report_sha256"]:
        raise AtlasEvidencePersistenceError("C10 route-test digest does not bind its receipt")
    source_artifacts = details.get("source_artifacts")
    if not isinstance(source_artifacts, dict) or set(source_artifacts) != {
        "source_set_sha256",
        "files",
    }:
        raise AtlasEvidencePersistenceError("C10 canonical source-artifact shape mismatch")
    if not _is_lower_sha256(source_artifacts.get("source_set_sha256")):
        raise AtlasEvidencePersistenceError("C10 canonical source-set digest must be SHA-256")
    source_files = source_artifacts.get("files")
    if not isinstance(source_files, list) or len(source_files) != len(C10_SOURCE_ARTIFACT_PATHS):
        raise AtlasEvidencePersistenceError("C10 canonical source-artifact population mismatch")
    for expected_path, source_file in zip(C10_SOURCE_ARTIFACT_PATHS, source_files, strict=True):
        if (
            not isinstance(source_file, dict)
            or set(source_file) != {"path", "sha256"}
            or source_file.get("path") != expected_path
            or not _is_lower_sha256(source_file.get("sha256"))
        ):
            raise AtlasEvidencePersistenceError("C10 canonical source-artifact binding mismatch")
    reconciliation = details.get("reconciliation")
    if not isinstance(reconciliation, dict) or set(reconciliation) != C10_RECONCILIATION_KEYS:
        raise AtlasEvidencePersistenceError("C10 reconciliation shape mismatch")
    if any(
        type(reconciliation[key]) is not int or reconciliation[key] < 0
        for key in (
            "adoption_entries",
            "adoption_stable",
            "readiness_entries",
            "readiness_stable",
            "readiness_implemented",
        )
    ) or not isinstance(reconciliation["verified_deprecated_redirects"], list):
        raise AtlasEvidencePersistenceError("C10 reconciliation values mismatch")
    for field, count_field in (
        ("adoption_stable_ids", "adoption_stable"),
        ("readiness_stable_ids", "readiness_stable"),
        ("implemented_surface_ids", "readiness_implemented"),
        ("nondeprecated_implemented_ids", None),
    ):
        identities = reconciliation[field]
        if (
            not isinstance(identities, list)
            or not all(isinstance(identity, str) and identity for identity in identities)
            or len(set(identities)) != len(identities)
            or (count_field is not None and len(identities) != reconciliation[count_field])
        ):
            raise AtlasEvidencePersistenceError("C10 reconciliation identity population mismatch")


def _validate_c10_raw_binding(raw_report: bytes, payload: dict[str, Any]) -> None:
    """Content-bind exact Vitest bytes and recomputed C10 facts before CAS."""
    raw = _parse_raw_report(raw_report)
    details = payload["details"]
    route_receipt = details["route_test_receipt"]
    _validate_c10_route_test_receipt(route_receipt)
    raw_sha256 = hashlib.sha256(raw_report).hexdigest()
    if (
        details["raw_report_sha256"] != raw_sha256
        or details["route_test_report_sha256"] != raw_sha256
        or route_receipt["report_sha256"] != raw_sha256
    ):
        raise AtlasEvidencePersistenceError("C10 exact Vitest raw digest does not bind details")
    derived_route_receipt = _derive_c10_route_test_receipt(
        raw,
        raw_report,
        route_receipt["process_exit_code"],
    )
    if derived_route_receipt != route_receipt:
        raise AtlasEvidencePersistenceError(
            "C10 route-test receipt does not equal exact Vitest JSON derivation"
        )
    if details["source_artifacts"] != _capture_c10_source_artifacts():
        raise AtlasEvidencePersistenceError(
            "C10 canonical source artifacts do not bind the current tree"
        )
    expected_reconciliation, expected_result = _c10_canonical_reconciliation(
        derived_route_receipt
    )
    if details["reconciliation"] != expected_reconciliation:
        raise AtlasEvidencePersistenceError(
            "C10 reconciliation does not equal independently recomputed canonical facts"
        )
    if payload["result"] != expected_result:
        raise AtlasEvidencePersistenceError(
            "C10 result does not equal independently recomputed canonical facts"
        )


def _validate_transport_contract(
    payload: dict[str, Any],
    receipt: dict[str, Any],
    *,
    implementation_provenance: Mapping[str, object],
) -> None:
    expected_payload_keys = {
        "payload_schema",
        "evidence_kind",
        "subject",
        "rule",
        "provenance",
        "times",
        "result",
        "details",
    }
    if set(payload) != expected_payload_keys:
        raise AtlasEvidencePersistenceError(
            "payload keys must equal the C07 verification-payload envelope"
        )
    expected_receipt_keys = {
        "receipt_schema",
        "authority",
        "evidence_kind",
        "subject",
        "rule",
        "provenance",
        "audiences",
        "times",
        "result",
        "retention",
    }
    if set(receipt) != expected_receipt_keys:
        raise AtlasEvidencePersistenceError(
            "receipt transport keys must equal the C07 receipt without evidence_payload_ref"
        )
    (
        expected_payload_schema,
        expected_receipt_schema,
        allowed_evidence_kinds,
        expected_authority,
        expected_implementation_paths,
    ) = _contract_for(payload, receipt)
    _require_exact_mapping(
        payload.get("payload_schema"), expected_payload_schema, field="payload_schema"
    )
    _require_exact_mapping(
        receipt.get("receipt_schema"), expected_receipt_schema, field="receipt_schema"
    )
    if payload.get("evidence_kind") not in allowed_evidence_kinds:
        raise AtlasEvidencePersistenceError("payload evidence_kind is outside the C07 closed set")
    if receipt.get("evidence_kind") != payload.get("evidence_kind"):
        raise AtlasEvidencePersistenceError("receipt evidence_kind does not bind the payload")
    if not isinstance(payload.get("details"), dict) or not payload["details"]:
        raise AtlasEvidencePersistenceError("payload details must be a non-empty JSON object")
    raw_report_sha256 = payload["details"].get("raw_report_sha256")
    if not _is_lower_sha256(raw_report_sha256):
        raise AtlasEvidencePersistenceError("payload raw_report_sha256 must be lowercase SHA-256")
    if payload["details"].get("capture_implementation") != dict(implementation_provenance):
        raise AtlasEvidencePersistenceError("capture implementation provenance mismatch")
    if tuple(
        item.get("path") for item in payload["details"]["capture_implementation"].get("files", [])
        if isinstance(item, dict)
    ) != expected_implementation_paths:
        raise AtlasEvidencePersistenceError(
            "capture implementation paths do not bind this contract"
        )

    _require_exact_mapping(receipt.get("authority"), expected_authority, field="receipt authority")
    retention = receipt.get("retention")
    if not isinstance(retention, dict):
        raise AtlasEvidencePersistenceError("receipt retention must be a JSON object")
    if retention.get("retention_class") != "content_addressed_runtime_artifacts":
        raise AtlasEvidencePersistenceError("receipt retention_class does not match C07")
    if retention.get("retention_days") != 365:
        raise AtlasEvidencePersistenceError("receipt retention_days does not match C07")
    if retention.get("cleanup_policy") != "manual_approval_only":
        raise AtlasEvidencePersistenceError("receipt cleanup_policy does not match C07")

    for field in BOUND_FIELDS:
        if field not in payload or field not in receipt:
            raise AtlasEvidencePersistenceError(f"missing semantic binding field: {field}")
        if payload[field] != receipt[field]:
            raise AtlasEvidencePersistenceError(
                f"receipt does not bind verification payload field: {field}"
            )
    if expected_payload_schema == RECONCILIATION_PAYLOAD_SCHEMA:
        _validate_c10_contract(
            payload,
            receipt,
            implementation_provenance=implementation_provenance,
        )


def _canon_spec() -> CanonSpec:
    from polisyos.core.canon import CanonSpec

    return CanonSpec(
        name="polisyos.canon.json",
        version="0.2.0",
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=True,
        max_depth=128,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _governance() -> ArtifactGovernanceInfo:
    from polisyos.core.artifacts.manifest import (
        ArtifactEncryptionPolicyInfo,
        ArtifactGovernanceInfo,
        ArtifactRetentionPolicyInfo,
    )

    return ArtifactGovernanceInfo(
        classification="internal",
        retention=ArtifactRetentionPolicyInfo(
            scope="cas",
            retention_days=365,
            delete_on_expiry=False,
        ),
        encryption=ArtifactEncryptionPolicyInfo(
            mode="none",
            enforced=False,
            verified=False,
        ),
    )


def _producer(implementation_provenance: Mapping[str, object]) -> ProducerInfo:
    from polisyos.core.artifacts import GitInfo, ProducerInfo

    return ProducerInfo(
        component=PRODUCER_COMPONENT,
        version=PRODUCER_VERSION,
        git=GitInfo(
            commit=str(implementation_provenance["repository_revision"]),
            dirty=bool(implementation_provenance["dirty"]),
        ),
    )


def _build_store() -> ArtifactStore:
    from polisyos.core.artifacts.backends.config import (
        ArtifactStoreConfig,
        build_artifact_store,
    )

    return build_artifact_store(ArtifactStoreConfig.from_env())


def _assert_verification(report: VerificationReport, *, label: str) -> None:
    if not report.ok:
        detail = report.error or "unknown integrity error"
        raise AtlasEvidencePersistenceError(f"{label} CAS integrity verification failed: {detail}")


def _assert_manifest(
    manifest: ArtifactManifest,
    *,
    kind: str,
    schema_name: str | None,
    schema_version: str | None,
    expected_inputs: list[tuple[str, str]],
    expected_producer: ProducerInfo,
    expect_canon: bool = True,
) -> None:
    if manifest.kind != kind:
        raise AtlasEvidencePersistenceError(f"{kind} manifest kind mismatch")
    if manifest.media_type != "application/json":
        raise AtlasEvidencePersistenceError(f"{kind} manifest media_type mismatch")

    schema = manifest.artifact_schema
    if schema_name is None:
        if schema is not None:
            raise AtlasEvidencePersistenceError(f"{kind} manifest must not invent a schema")
    elif schema is None or schema.name != schema_name or schema.version != schema_version:
        raise AtlasEvidencePersistenceError(f"{kind} manifest schema identity mismatch")

    from polisyos.core.artifacts import CanonInfo

    canon = manifest.canon
    if expect_canon:
        if canon != CanonInfo.from_spec(_canon_spec()):
            raise AtlasEvidencePersistenceError(f"{kind} manifest canon metadata mismatch")
    elif canon is not None:
        raise AtlasEvidencePersistenceError(f"{kind} raw bytes must not claim JSON canon metadata")

    producer = manifest.producer
    if producer != expected_producer:
        raise AtlasEvidencePersistenceError(f"{kind} manifest producer mismatch")
    if manifest.governance != _governance():
        raise AtlasEvidencePersistenceError(f"{kind} manifest governance mismatch")

    actual_inputs = [(str(input_ref.artifact_id), input_ref.role) for input_ref in manifest.inputs]
    if actual_inputs != expected_inputs:
        raise AtlasEvidencePersistenceError(
            f"{kind} manifest inputs mismatch: expected {expected_inputs!r}, got {actual_inputs!r}"
        )


def _resolve_json(store: ArtifactStore, artifact_id: ArtifactID, *, label: str) -> object:
    from polisyos.core.canon import from_canonical_bytes

    value = from_canonical_bytes(store.get_bytes(artifact_id))
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AtlasEvidencePersistenceError(
            f"{label} canonical payload did not decode to plain finite JSON"
        ) from exc
    return value


def persist_atlas_evidence(
    raw_report: bytes,
    payload: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Persist, verify, resolve, and lineage-check one C07 evidence pair.

    Args:
        raw_report: Exact UTF-8 JSON bytes emitted by the declared runner.
        payload: Strict C07 verification payload already validated by the TypeScript owner.
        receipt: Strict C07 receipt fields except the circular ``evidence_payload_ref``.

    Returns:
        A JSON-serializable result containing both CAS refs, verification reports,
        resolved objects, and the receipt's verified payload-lineage edge.

    Raises:
        AtlasEvidencePersistenceError: If storage, integrity, lineage, or binding
            does not satisfy the C07 contract.
    """
    (
        payload_schema,
        receipt_schema,
        _allowed_evidence_kinds,
        _expected_authority,
        implementation_paths,
    ) = _contract_for(payload, receipt)
    implementation_provenance = _capture_implementation_provenance(implementation_paths)
    _validate_transport_contract(
        payload,
        receipt,
        implementation_provenance=implementation_provenance,
    )
    _ensure_worktree_import_root()

    from polisyos.core.artifacts import InputRef, PutOptions, SchemaInfo

    store = _build_store()
    canon_spec = _canon_spec()
    producer = _producer(implementation_provenance)
    raw_report_digest = hashlib.sha256(raw_report).hexdigest()
    if raw_report_digest != payload["details"]["raw_report_sha256"]:
        raise AtlasEvidencePersistenceError("raw runner report does not bind payload digest")
    if payload_schema == RECONCILIATION_PAYLOAD_SCHEMA:
        _validate_c10_raw_binding(raw_report, payload)
    raw_report_ref = store.put_bytes(
        raw_report,
        PutOptions(
            kind=RAW_REPORT_KIND,
            media_type="application/json",
            producer=producer,
            inputs=[],
            governance=_governance(),
        ),
    )
    raw_report_verification = store.verify(raw_report_ref.artifact_id)
    _assert_verification(raw_report_verification, label="raw runner report")
    raw_report_manifest = store.get_manifest(raw_report_ref.artifact_id)
    _assert_manifest(
        raw_report_manifest,
        kind=RAW_REPORT_KIND,
        schema_name=None,
        schema_version=None,
        expected_inputs=[],
        expected_producer=producer,
        expect_canon=False,
    )
    if store.get_bytes(raw_report_ref.artifact_id) != raw_report:
        raise AtlasEvidencePersistenceError("resolved raw runner report differs from input")

    payload_ref = store.put_json(
        payload,
        PutOptions(
            kind=PAYLOAD_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=payload_schema["id"], version=payload_schema["version"]),
            producer=producer,
            inputs=[
                InputRef(
                    artifact_id=raw_report_ref.artifact_id,
                    role=RAW_REPORT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=canon_spec,
    )
    payload_report = store.verify(payload_ref.artifact_id)
    _assert_verification(payload_report, label="verification payload")
    payload_manifest = store.get_manifest(payload_ref.artifact_id)
    _assert_manifest(
        payload_manifest,
        kind=PAYLOAD_KIND,
        schema_name=payload_schema["id"],
        schema_version=payload_schema["version"],
        expected_inputs=[(str(raw_report_ref.artifact_id), RAW_REPORT_INPUT_ROLE)],
        expected_producer=producer,
    )
    resolved_payload = _resolve_json(
        store,
        payload_ref.artifact_id,
        label="verification payload",
    )
    if resolved_payload != payload:
        raise AtlasEvidencePersistenceError("resolved verification payload differs from input")
    if not isinstance(resolved_payload, dict):
        raise AtlasEvidencePersistenceError("resolved verification payload must be a JSON object")

    stored_receipt = dict(receipt)
    stored_receipt["evidence_payload_ref"] = {
        "artifact_id": str(payload_ref.artifact_id),
        "kind": PAYLOAD_KIND,
        "media_type": "application/json",
        "schema_id": payload_schema["id"],
        "schema_version": payload_schema["version"],
    }
    receipt_ref = store.put_json(
        stored_receipt,
        PutOptions(
            kind=RECEIPT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=receipt_schema["id"], version=receipt_schema["version"]),
            producer=producer,
            inputs=[
                InputRef(
                    artifact_id=payload_ref.artifact_id,
                    role=RECEIPT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=canon_spec,
    )
    receipt_report = store.verify(receipt_ref.artifact_id)
    _assert_verification(receipt_report, label="evidence receipt")
    receipt_manifest = store.get_manifest(receipt_ref.artifact_id)
    expected_lineage = [(str(payload_ref.artifact_id), RECEIPT_INPUT_ROLE)]
    _assert_manifest(
        receipt_manifest,
        kind=RECEIPT_KIND,
        schema_name=receipt_schema["id"],
        schema_version=receipt_schema["version"],
        expected_inputs=expected_lineage,
        expected_producer=producer,
    )
    resolved_receipt = _resolve_json(store, receipt_ref.artifact_id, label="evidence receipt")
    if resolved_receipt != stored_receipt:
        raise AtlasEvidencePersistenceError("resolved evidence receipt differs from stored input")
    if not isinstance(resolved_receipt, dict):
        raise AtlasEvidencePersistenceError("resolved evidence receipt must be a JSON object")
    _validate_transport_contract(
        resolved_payload,
        {key: value for key, value in resolved_receipt.items() if key != "evidence_payload_ref"},
        implementation_provenance=implementation_provenance,
    )
    resolved_payload_ref = resolved_receipt.get("evidence_payload_ref")
    expected_payload_ref = stored_receipt["evidence_payload_ref"]
    if resolved_payload_ref != expected_payload_ref:
        raise AtlasEvidencePersistenceError("resolved receipt payload reference mismatch")

    return {
        "ok": True,
        "operation": OPERATION,
        "raw_report_ref": raw_report_ref.model_dump(mode="json"),
        "payload_ref": payload_ref.model_dump(mode="json"),
        "receipt_ref": receipt_ref.model_dump(mode="json"),
        "raw_report_verification": raw_report_verification.model_dump(mode="json"),
        "payload_verification": payload_report.model_dump(mode="json"),
        "receipt_verification": receipt_report.model_dump(mode="json"),
        "payload_manifest_input": {
            "artifact_id": str(raw_report_ref.artifact_id),
            "role": RAW_REPORT_INPUT_ROLE,
        },
        "receipt_manifest_input": {
            "artifact_id": expected_lineage[0][0],
            "role": expected_lineage[0][1],
        },
        "resolved_payload": {
            "artifact_id": str(payload_ref.artifact_id),
            "payload": resolved_payload,
        },
        "resolved_receipt": {
            "artifact_id": str(receipt_ref.artifact_id),
            "receipt": resolved_receipt,
        },
    }


def _emit(value: object) -> None:
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def _fail(exc: Exception) -> NoReturn:
    _emit(
        {
            "ok": False,
            "operation": OPERATION,
            "error": {
                "code": "atlas_evidence_persistence_failed",
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    )
    raise SystemExit(1)


def main() -> None:
    """Read one strict JSON request and emit one strict JSON result."""
    try:
        request = _read_request()
        raw_report = _decode_raw_report(request["raw_report_base64"])
        result = persist_atlas_evidence(raw_report, request["payload"], request["receipt"])
    except Exception as exc:  # The process boundary must always return structured JSON.
        _fail(exc)
    _emit(result)


if __name__ == "__main__":
    main()
