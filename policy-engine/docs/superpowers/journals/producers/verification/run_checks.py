"""Run one explicitly named verification gate per invocation and retain its full output."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
CLAIM = "tests/unit/scientist/governance/continuous/test_owner_event_producer.py::"
CLAIM_HTTP = "tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::"
CASE = "tests/unit/runtime/quality/test_global_case_index.py::"
ATLAS = "tests/unit/runtime/http/test_public_decision_verification_routes.py::"
BROWSER_NODE = (
    "real verification service authenticates a report and rejects the same record "
    "after signature removal$"
)

TESTS = {
    "atlas": [
        ATLAS + "test_owned_run_packet_is_redacted_issued_and_publicly_verified",
        ATLAS + "test_public_export_refusal_prevents_record_and_link_issuance",
        ATLAS + "test_legacy_browser_token_receives_public_verifier_refusal",
        "tests/unit/runtime/http/test_public_decision_verification.py::"
        "test_persisted_index_survives_new_service_and_reads_never_resign",
        "tests/unit/runtime/http/test_public_decision_verification_configuration.py::"
        "test_configured_keys_issue_and_reverify_persisted_report",
    ],
    "case": [
        "tests/unit/runtime/http/test_capability_discovery_api.py::"
        "test_case_provider_is_backed_by_canonical_global_index",
        "tests/unit/runtime/http/test_capability_discovery_api.py::"
        "test_case_provider_refuses_invalid_persisted_binding",
        CASE + "test_real_s2_producer_emits_persisted_content_bound_case_index",
        CASE + "test_case_field_names_do_not_identify_the_canonical_vocabulary",
        CASE + "test_linked_content_identity_must_match_binding[changed0]",
        CASE + "test_linked_content_identity_must_match_binding[changed1]",
        CASE + "test_linked_content_identity_must_match_binding[changed2]",
        CASE + "test_canonical_kind_with_unverified_provenance_refuses_the_inventory[producer]",
        CASE + "test_canonical_kind_with_unverified_provenance_refuses_the_inventory[schema]",
        CASE + "test_missing_family_vocabulary_cannot_be_replaced_with_case_identity[families0]",
        CASE + "test_missing_family_vocabulary_cannot_be_replaced_with_case_identity[families1]",
        CASE + "test_mutated_linked_bytes_refuse_even_after_a_successful_read",
        CASE + "test_new_bindings_join_the_next_complete_snapshot",
        CASE + "test_tenant_and_cell_views_never_reuse_another_scopes_cases",
        CASE + "test_missing_scope_cannot_emit_an_unscoped_inventory",
    ],
    "claim": [
        CLAIM_HTTP + "test_monitor_event_persists_claim_supersession_without_in_place_edit",
        CLAIM_HTTP + "test_default_http_supersession_request_preserves_unappointed_owner_limit",
        CLAIM_HTTP
        + "test_http_supersession_rejects_unresolved_monitor_before_owner_effect[absent]",
        CLAIM_HTTP
        + "test_http_supersession_rejects_unresolved_monitor_before_owner_effect[wrong_vocabulary]",
        CLAIM + "test_monitor_metadata_cannot_advance_current_claim_head",
        CLAIM + "test_unsigned_candidate_reaches_consumer_with_empty_appointment",
        CLAIM + "test_current_head_replay_cannot_substitute_a_new_matching_appointment",
        CLAIM + "test_owner_event_verification_rejects_present_but_unproven_evidence[unsigned]",
        CLAIM + "test_owner_event_verification_rejects_present_but_unproven_evidence[wrong_scope]",
        CLAIM + "test_owner_event_verification_rejects_present_but_unproven_evidence[revoked]",
        CLAIM
        + "test_owner_event_verification_rejects_present_but_unproven_evidence[fake_successor]",
        CLAIM
        + "test_owner_event_verification_rejects_present_but_unproven_evidence[wrong_vocabulary]",
        "tests/unit/runtime/http/test_decision_validity_api.py::"
        "test_live_monitor_ref_reloads_bytes_and_persists_lifecycle_and_epoch_bindings",
    ],
    "foundry": [
        "tests/unit/foundry/methods/test_dependency_profile.py::"
        "test_no_runtime_cutoff_preflight_blocks_before_sync_or_candidate_generation",
        "tests/unit/foundry/methods/test_dependency_profile.py::"
        "test_barriered_write_after_second_post_fstat_preserves_equal_candidate_manifests",
        "tests/unit/foundry/methods/test_dependency_profile.py::"
        "test_public_builders_reject_caller_constructed_positive_profile",
        "tests/unit/runtime/quality/test_value_gate.py::"
        "test_n8_dependency_discriminant_matching_supplied_fail_is_ambient_only",
        "tests/unit/runtime/quality/test_value_gate.py::"
        "test_n8_dependency_discriminant_supplied_pass_requires_current_recomputation",
        "tests/unit/runtime/http/test_governed_projection_validation_worker.py::"
        "test_value_gate_worker_diagnostic_exception_cannot_change_governing_status",
    ],
}
COMMANDS = {name: ["uv", "run", "pytest", *nodes, "-q", "-rA"] for name, nodes in TESTS.items()}
COMMANDS.update(
    {
        "atlas-browser": [
            "corepack",
            "pnpm",
            "exec",
            "playwright",
            "test",
            "e2e/public-decision-verification.browser.ts",
            "--config",
            "e2e/playwright.public-verification.config.ts",
            "--grep",
            BROWSER_NODE,
        ],
        "atlas-removal": ["uv", "run", "python", str(HERE / "atlas_probe.py")],
        "case-removal": ["uv", "run", "python", str(HERE / "case_probe.py")],
        "foundry-removal": ["uv", "run", "python", str(HERE / "foundry_probe.py")],
        **{
            f"claim-{probe}-removal": [
                "uv",
                "run",
                "python",
                str(HERE / "claim_probes.py"),
                "--probe",
                probe,
            ]
            for probe in ("binding", "caller", "append")
        },
        "collection": [
            "uv",
            "run",
            "pytest",
            *(node for nodes in TESTS.values() for node in nodes),
            "--collect-only",
            "-q",
        ],
        "guardrails": ["uv", "run", "polisyos-tools", "architecture", "guardrails", "check"],
        "lint": [
            ".venv/bin/python",
            "-m",
            "ruff",
            "check",
            "tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py",
            "tests/unit/scientist/governance/continuous/test_owner_event_producer.py",
            "tests/unit/runtime/http/test_capability_discovery_api.py",
            "tests/unit/runtime/http/test_runtime_api_authz.py",
            str(HERE / "atlas_probe.py"),
            str(HERE / "case_probe.py"),
            str(HERE / "claim_probes.py"),
            str(HERE / "foundry_probe.py"),
            str(HERE / "run_checks.py"),
        ],
    }
)
# Baseline full source audit completed in ~6 minutes; targeted cold HTTP startup
# completed within 2 minutes. Leave ample measured margin without an implicit kill.
TIMEOUTS = {**dict.fromkeys(COMMANDS, 600), "guardrails": 1800}


def main() -> int:
    """Select one gate, retain complete stdout/stderr and return its actual exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=sorted(COMMANDS), nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.list:
        sys.stdout.write(json.dumps(COMMANDS, indent=2) + "\n")
        return 0
    if args.gate is None:
        parser.error("choose one gate or --list")
    tag = args.tag or f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{args.gate}"
    if not tag or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in tag
    ):
        parser.error("tag must contain only letters, digits, hyphens and underscores")
    raw = HERE / "raw"
    raw.mkdir(exist_ok=True)
    log_path, result_path = raw / f"{tag}.log", raw / f"{tag}.json"
    if log_path.exists() or result_path.exists():
        parser.error("receipt already exists; choose a fresh tag")
    cwd = PRODUCT_ROOT / "apps/runtime-dashboard" if args.gate == "atlas-browser" else PRODUCT_ROOT
    command = COMMANDS[args.gate]
    started = time.monotonic()
    timed_out = False
    with log_path.open("xb") as output:
        try:
            # Commands come exclusively from the fixed local allowlist above.
            result = subprocess.run(  # noqa: S603
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUTS[args.gate],
                check=False,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    receipt = {
        "gate": args.gate,
        "command": command,
        "cwd": str(cwd),
        "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timed_out": timed_out,
        "output": str(log_path.relative_to(PRODUCT_ROOT)),
        "output_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "expected_exit_code": 1 if args.gate.endswith("-removal") else 0,
    }
    result_path.write_text(json.dumps(receipt, indent=2) + "\n")
    sys.stdout.write(json.dumps(receipt, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
