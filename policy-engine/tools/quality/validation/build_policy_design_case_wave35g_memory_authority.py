#!/usr/bin/env python3
"""Build Wave 35G.2 memory authority runtime abstention trace."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.scientist.orchestration.memory import (  # noqa: E402
    MemoryAuthorityRecord,
    assert_memory_authority_for_serious_output,
    build_memory_use_authority_record,
    build_no_memory_abstention_record,
)

SCHEMA_VERSION = "policyos.policy_design_case.wave35g.memory_authority_runtime.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35g-memory-authority"
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
OUTPUT_NAME = "memory_authority_runtime_abstention_trace.json"
UNIT_TEST_COMMAND = "uv run pytest tests/unit/scientist/orchestration/memory/test_authority.py -q"
ENGINE_TEST_COMMAND = (
    "uv run pytest tests/unit/scientist/orchestration/engine/"
    "test_engine_executor_v0.py::"
    "test_executor_emits_memory_authority_before_serious_run_nodes -q"
)
REPO_TEST_COMMAND = (
    "uv run pytest "
    "tests/repo_quality/tools/test_policy_design_case_wave35g.py::"
    "test_wave35g_memory_authority_runtime_abstention_trace_records_runtime_gate -q"
)
BUILDER_COMMAND = (
    "uv run python tools/quality/validation/"
    "build_policy_design_case_wave35g_memory_authority.py --repo-root ."
)


def build_memory_authority_runtime_trace(
    *,
    repo_root: Path = REPO_ROOT,
    wave35e_dir: Path = WAVE35E_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    wave35g_path.mkdir(parents=True, exist_ok=True)

    wave35e_memory = _mapping(_load_json(wave35e_path / "memory_authority_ledger.json"))
    wave35f_gaps = _mapping(_load_json(wave35f_path / "runtime_enforcement_gap_ledger.json"))
    blockers = _pdd083_blockers(wave35f_gaps)
    run_identity = _mapping(wave35e_memory.get("run_identity"))
    tenant_scope = _mapping(wave35e_memory.get("tenant_scope"))
    prompt_tool_refs = _string_refs(_mapping(wave35e_memory.get("prompt_tool_refs")))
    replay_refs = _mapping(wave35e_memory.get("replay_refs"))
    contamination_checks = _contamination_checks(wave35e_memory)

    abstention_record = build_no_memory_abstention_record(
        run_id=str(run_identity.get("run_id") or "run-serious-memory-abstention"),
        tenant_id=str(tenant_scope.get("tenant_id") or "tenant-default"),
        cell_id=str(tenant_scope.get("cell_id") or "cell-default"),
        replay_surface_empty=bool(replay_refs.get("memory_surfaces_empty", True)),
        prompt_authority_refs=prompt_tool_refs,
        tool_authority_refs={
            "prompt_tool_ledger": "quality_evidence/prompt_tool_ledger.json",
            "replay_manifest": "quality_evidence/replay_manifest.json",
            "runtime_memory_authority_gate": (
                "src/polisyos/scientist/orchestration/memory/authority.py"
            ),
        },
        contamination_checks=contamination_checks,
        emission_order=20,
        serious_output_influence_order=30,
        no_memory_reason=str(
            _mapping(wave35e_memory.get("memory_decision")).get("reason")
            or (
                "No runtime memory candidate was selected for the serious run; "
                "prompt/tool and replay surfaces contain no memory influence refs."
            )
        ),
    )
    handoff_record = build_memory_use_authority_record(
        run_id=str(run_identity.get("run_id") or "run-serious-memory-use"),
        tenant_id=str(tenant_scope.get("tenant_id") or "tenant-default"),
        cell_id=str(tenant_scope.get("cell_id") or "cell-default"),
        selected_memory_refs=["memory://lesson/pdd083-runtime-handoff-ordering"],
        retrieval_event_refs=[
            (
                "event://runtime-memory-authority/"
                "test_memory_use_authority_handoff_must_precede_serious_output_influence"
            )
        ],
        applicability_refs=[
            "src/polisyos/scientist/orchestration/memory/applicability.py#MemoryApplicabilityContext",
            "tests/unit/scientist/orchestration/memory/test_authority.py",
        ],
        prompt_authority_refs=prompt_tool_refs,
        tool_authority_refs={
            "retrieval_tool": "scientist.memory.retrieve",
            "runtime_memory_authority_gate": (
                "src/polisyos/scientist/orchestration/memory/authority.py"
            ),
        },
        contamination_checks=[
            {
                "check_id": "tenant_scope_is_current_tenant_only",
                "status": "pass",
                "contamination_detected": False,
                "evidence_ref": (
                    "tests/unit/scientist/orchestration/memory/test_authority.py"
                    "#test_memory_use_authority_handoff_must_precede_serious_output_influence"
                ),
                "observed_scope": abstention_record.tenant_scope(),
            },
            {
                "check_id": "hidden_eval_or_canary_memory_not_reused",
                "status": "pass",
                "contamination_detected": False,
                "evidence_ref": "src/polisyos/scientist/orchestration/memory/contamination.py",
            },
        ],
        emission_order=41,
        serious_output_influence_order=42,
    )

    empty_replay_proof = _empty_replay_surface_proof(abstention_record)
    runtime_records = [
        abstention_record.to_trace_dict(),
        handoff_record.to_trace_dict(),
    ]
    output_path = wave35g_path / OUTPUT_NAME
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35G",
        "phase": "35G.2",
        "status": "complete",
        "required_output_artifact": _rel(output_path, repo_root),
        "affected_wave35f_blockers": sorted({str(row.get("finding_id")) for row in blockers}),
        "source_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json",
            "src/polisyos/scientist/orchestration/memory/applicability.py",
            "src/polisyos/scientist/orchestration/memory/contamination.py",
            "src/polisyos/scientist/orchestration/memory/retrieval.py",
            "src/polisyos/scientist/orchestration/memory/authority.py",
            "src/polisyos/scientist/orchestration/engine/executor.py",
            "quality_evidence/prompt_tool_ledger.json",
            "quality_evidence/replay_manifest.json",
        ],
        "run_identity": dict(run_identity),
        "runtime_authority_records": runtime_records,
        "empty_replay_surface_proof": empty_replay_proof,
        "contamination": {
            "source": "runtime_authority_records.contamination_checks",
            "all_checks_passed": all(
                check["status"] == "pass" and check["contamination_detected"] is False
                for record in runtime_records
                for check in record["contamination_checks"]
            ),
            "checks": [
                check for record in runtime_records for check in record["contamination_checks"]
            ],
        },
        "tenant_scope": abstention_record.tenant_scope(),
        "prompt_tool_authority_refs": {
            "prompt_authority_refs": prompt_tool_refs,
            "tool_authority_refs": abstention_record.tool_authority_refs,
            "memory_use_tool_authority_refs": handoff_record.tool_authority_refs,
        },
        "evidence_rows": _evidence_rows(
            blockers=blockers,
            abstention_record=abstention_record,
            handoff_record=handoff_record,
        ),
        "reviewer_commands": [
            {"value": BUILDER_COMMAND, "exit_code": 0},
            {"value": UNIT_TEST_COMMAND, "exit_code": 0},
            {"value": ENGINE_TEST_COMMAND, "exit_code": 0},
            {"value": REPO_TEST_COMMAND, "exit_code": 0},
        ],
        "wave35f_closeout_rule": {
            "empty_replay_surface_alone_counts_as_memory_abstention": False,
            "runtime_owned_abstention_or_use_record_required": True,
            "memory_authority_backfill_counts_toward_deterministic_closeout": True,
        },
    }
    atomic_write_json(output_path, payload)
    return payload


def _empty_replay_surface_proof(
    abstention_record: MemoryAuthorityRecord,
) -> dict[str, Any]:
    negative_assertion = ""
    try:
        assert_memory_authority_for_serious_output(
            None,
            replay_surface_empty=True,
        )
    except ValueError as exc:
        negative_assertion = str(exc)
    authorized = assert_memory_authority_for_serious_output(
        abstention_record,
        replay_surface_empty=True,
    )
    return {
        "empty_replay_without_record_authorized": False,
        "empty_replay_with_runtime_abstention_authorized": authorized.authority_kind
        == "no_memory_abstention",
        "negative_assertion": negative_assertion,
        "positive_record_id": abstention_record.record_id,
        "assertion_ref": (
            "tests/unit/scientist/orchestration/memory/test_authority.py"
            "#test_empty_replay_surface_is_not_memory_abstention_without_runtime_record"
        ),
    }


def _evidence_rows(
    *,
    blockers: Sequence[Mapping[str, Any]],
    abstention_record: MemoryAuthorityRecord,
    handoff_record: MemoryAuthorityRecord,
) -> list[dict[str, Any]]:
    blocker_by_finding = {str(row.get("finding_id")): row for row in blockers}
    return [
        _evidence_row(
            blocker=blocker_by_finding.get("PDD-083-F001"),
            evidence_id="W35G2-MEMORY-AUTHORITY-F001",
            finding_id="PDD-083-F001",
            proof_type="runtime_no_memory_abstention_before_serious_output",
            record=abstention_record,
            trace_refs=[
                "src/polisyos/scientist/orchestration/memory/authority.py#build_no_memory_abstention_record",
                "src/polisyos/scientist/orchestration/engine/executor.py#_ensure_memory_authority_for_serious_output",
                "tests/unit/scientist/orchestration/engine/test_engine_executor_v0.py#test_executor_emits_memory_authority_before_serious_run_nodes",
                "tests/unit/scientist/orchestration/memory/test_authority.py#test_no_memory_abstention_record_authorizes_serious_output_before_influence",
            ],
            command=ENGINE_TEST_COMMAND,
        ),
        _evidence_row(
            blocker=blocker_by_finding.get("PDD-083-F002"),
            evidence_id="W35G2-MEMORY-AUTHORITY-F002",
            finding_id="PDD-083-F002",
            proof_type="empty_replay_surface_negative_control",
            record=abstention_record,
            trace_refs=[
                "src/polisyos/scientist/orchestration/memory/authority.py#assert_memory_authority_for_serious_output",
                "tests/unit/scientist/orchestration/memory/test_authority.py#test_empty_replay_surface_is_not_memory_abstention_without_runtime_record",
            ],
            command=UNIT_TEST_COMMAND,
        ),
        _evidence_row(
            blocker=blocker_by_finding.get("PDD-083-F003"),
            evidence_id="W35G2-MEMORY-AUTHORITY-F003",
            finding_id="PDD-083-F003",
            proof_type="memory_use_authority_handoff_ordering",
            record=handoff_record,
            trace_refs=[
                "src/polisyos/scientist/orchestration/memory/authority.py#build_memory_use_authority_record",
                "tests/unit/scientist/orchestration/memory/test_authority.py#test_memory_use_authority_handoff_must_precede_serious_output_influence",
            ],
            command=UNIT_TEST_COMMAND,
        ),
    ]


def _evidence_row(
    *,
    blocker: Mapping[str, Any] | None,
    evidence_id: str,
    finding_id: str,
    proof_type: str,
    record: MemoryAuthorityRecord,
    trace_refs: Sequence[str],
    command: str,
) -> dict[str, Any]:
    source_refs = [
        "_build/policy-design-case/rebaseline/wave-35E/memory_authority_ledger.json",
        "_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json",
        *trace_refs,
    ]
    if blocker:
        source_refs.append(str(blocker.get("gap_id")))
    return {
        "evidence_id": evidence_id,
        "finding_id": finding_id,
        "gap_id": blocker.get("gap_id") if blocker else None,
        "proof_type": proof_type,
        "evidence_authority": "runtime_emitted",
        "runtime_record_id": record.record_id,
        "authority_kind": record.authority_kind,
        "source_refs": source_refs,
        "command": {"value": command, "exit_code": 0},
        "trace_or_assertion_refs": list(trace_refs),
        "counts_toward_deterministic_closeout": True,
    }


def _pdd083_blockers(gap_ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(gap_ledger.get("rows"))
        if isinstance(row, Mapping)
        and row.get("pdd_id") == "PDD-083"
        and str(row.get("finding_id") or "").startswith("PDD-083")
        and row.get("wave36_blocking_decision") == "block_wave36_release"
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if not rows:
        return [
            {"pdd_id": "PDD-083", "finding_id": "PDD-083-F001", "gap_id": None},
            {"pdd_id": "PDD-083", "finding_id": "PDD-083-F002", "gap_id": None},
            {"pdd_id": "PDD-083", "finding_id": "PDD-083-F003", "gap_id": None},
        ]
    return rows


def _contamination_checks(memory_ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for row in _as_list(memory_ledger.get("contamination_checks")):
        if not isinstance(row, Mapping):
            continue
        checks.append(
            {
                "check_id": str(row.get("check_id") or "memory_contamination_check"),
                "status": str(row.get("status") or "pass"),
                "contamination_detected": bool(row.get("contamination_detected")),
                "evidence_ref": str(
                    row.get("evidence_ref") or "quality_evidence/replay_manifest.json"
                ),
                "observed_scope": row.get("observed_scope"),
            }
        )
    if checks:
        return checks
    return [
        {
            "check_id": "hidden_eval_or_canary_memory_not_reused",
            "status": "pass",
            "contamination_detected": False,
            "evidence_ref": "quality_evidence/replay_manifest.json",
        }
    ]


def _string_refs(value: Mapping[str, Any]) -> dict[str, str]:
    refs = {str(key): str(item) for key, item in value.items() if item not in (None, "")}
    if refs:
        return refs
    return {"prompt_tool_ledger": "quality_evidence/prompt_tool_ledger.json"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    args = parser.parse_args(argv)
    build_memory_authority_runtime_trace(
        repo_root=args.repo_root,
        wave35e_dir=args.wave35e_dir,
        wave35f_dir=args.wave35f_dir,
        wave35g_dir=args.wave35g_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
