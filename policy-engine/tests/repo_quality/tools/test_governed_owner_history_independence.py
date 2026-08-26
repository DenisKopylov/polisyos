from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = POLICY_ENGINE_ROOT.parent
_WORKER_RESULT_PREFIX = "POLISYOS_GOVERNED_HISTORY_WITNESS="


@dataclass(frozen=True)
class _ProducerCase:
    producer_id: str
    worker_timeout_seconds: int
    expected_receipt_count: int
    minimum_lineage_count: int


_PRODUCER_CASES = (
    _ProducerCase(
        producer_id="n9-promotion",
        worker_timeout_seconds=300,
        expected_receipt_count=3,
        minimum_lineage_count=3,
    ),
    _ProducerCase(
        producer_id="n6-generation-cycle",
        worker_timeout_seconds=300,
        expected_receipt_count=2,
        minimum_lineage_count=2,
    ),
    _ProducerCase(
        producer_id="n10a-second-domain",
        worker_timeout_seconds=600,
        expected_receipt_count=4,
        minimum_lineage_count=5,
    ),
    _ProducerCase(
        producer_id="depth-n",
        worker_timeout_seconds=600,
        expected_receipt_count=3,
        minimum_lineage_count=1,
    ),
    _ProducerCase(
        producer_id="n11-confidence-ledger",
        worker_timeout_seconds=600,
        expected_receipt_count=4,
        minimum_lineage_count=3,
    ),
)


def _tree_digest(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest(), len(files)


def _first_json_differences(left: object, right: object) -> list[str]:
    differences: list[str] = []

    def walk(left_value: object, right_value: object, path: tuple[str, ...]) -> None:
        if len(differences) >= 12:
            return
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            for key in sorted(set(left_value) | set(right_value)):
                if key not in left_value or key not in right_value:
                    differences.append("/" + "/".join((*path, key)) + ":key_presence")
                else:
                    walk(left_value[key], right_value[key], (*path, key))
            return
        if isinstance(left_value, list) and isinstance(right_value, list):
            if len(left_value) != len(right_value):
                differences.append("/" + "/".join(path) + ":length")
                return
            for index, (left_item, right_item) in enumerate(
                zip(left_value, right_value, strict=True)
            ):
                walk(left_item, right_item, (*path, str(index)))
            return
        if left_value != right_value:
            pointer = "/" + "/".join(path)
            differences.append(
                f"{pointer}:{left_value!r}!={right_value!r}"[:500]
            )

    walk(left, right, ())
    return differences


def _history_scope() -> Any:
    from polisyos.runtime.quality.confidence_ledger import ConfidenceRiskBudgetScope

    return ConfidenceRiskBudgetScope(
        scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
        authority_purpose="n9_promotion",
        owner_scope_key="design-problem:governed-owner-history-witness",
        owner_projection_hash="sha256:" + "1" * 64,
        epoch_ref=None,
        model_ref=None,
        rule_ref="policyos.layer3.gy.n9.v1",
        schema_ref="policyos.runtime.design_problem.v1",
    )


def _install_durable_history(product_root: Path, history_kind: str) -> str:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.confidence_ledger import (
        ConfidenceLedgerError,
        ConfidenceLedgerSession,
        load_confidence_ledger_registry,
    )

    scope = _history_scope()
    if history_kind == "fresh":
        session = ConfidenceLedgerSession.from_repo(product_root, risk_scope=scope)
        receipt = session.receipt()
        assert receipt.events == ()
        assert receipt.checks == ()
        return "fresh_authority_empty_history"

    if history_kind != "registry-binding-incompatible":
        raise AssertionError(f"unknown_history_kind:{history_kind}")

    registry = load_confidence_ledger_registry(
        product_root / "architecture/production_quality/confidence_ledger.toml"
    )
    registry_source = registry.source_payload()
    current_profile = registry_source["policy"]["default_schedule_profile_id"]
    alternate_profile = next(
        row["profile_id"]
        for row in registry_source["schedule_profiles"]
        if row["profile_id"] != current_profile
    )
    registry_source["policy"]["default_schedule_profile_id"] = alternate_profile
    incompatible = ConfidenceLedgerSession._for_verification(
        product_root,
        risk_scope=scope,
        artifact_store=FileSystemCAS(product_root / ".polisyos/cas"),
        state_root=product_root / ".polisyos/runtime/confidence_ledger",
        registry_source=registry_source,
    )
    incompatible_receipt = incompatible.receipt()
    assert incompatible_receipt.events == ()
    assert incompatible_receipt.checks == ()
    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_binding_mismatch"):
        ConfidenceLedgerSession.from_repo(product_root, risk_scope=scope)
    return "ledger_scope_binding_mismatch"


def _validated_promotion_receipt_counts(
    raw_receipts: tuple[dict[str, Any], ...],
) -> tuple[int, int, int]:
    from polisyos.runtime.quality.promotion_sequence import CanonicalPromotionReceipt

    verification_count = 0
    non_promotable_count = 0
    lineage_count = 0
    for raw in raw_receipts:
        receipt = CanonicalPromotionReceipt.model_validate(raw)
        assert receipt.confidence_ledger_projection.authority_provenance == "verification"
        assert receipt.consumer_promotable is False
        assert receipt.non_promotable_reason == "verification_only_replay"
        semantic = receipt.confidence_ledger_semantic_projection
        assert semantic is not None
        assert semantic.authority_provenance == "verification"
        verification_count += 1
        non_promotable_count += 1
        lineage_count += 1
    return verification_count, non_promotable_count, lineage_count


def _run_n9_owner(product_root: Path) -> tuple[bytes, int, int, int]:
    from tools.quality.validation import check_layer3_gy_promotion_contract as owner

    output = owner.build_contract_json_for_write(product_root).encode("utf-8")
    payload = json.loads(output)
    assert owner.validate_payload(payload) == {"status": "pass", "issues": []}
    receipts = tuple(
        payload[key]
        for key in (
            "contract_lane_anytime_refusal",
            "production_honest_shadow",
            "non_promotable_contract_stamp",
        )
    )
    verification, non_promotable, lineage = _validated_promotion_receipt_counts(receipts)
    return output, verification, non_promotable, lineage


def _run_n6_owner(product_root: Path) -> tuple[bytes, int, int, int]:
    from tools.quality.validation import check_layer3_gy_generation_cycle_contract as owner

    output = owner.build_contract_json_for_write(product_root).encode("utf-8")
    payload = json.loads(output)
    assert owner.validate_payload(payload) == {"status": "pass", "issues": []}
    receipts = tuple(payload["generation_cycle_run"]["promotion_port"]["receipts"])
    verification, non_promotable, lineage = _validated_promotion_receipt_counts(receipts)
    return output, verification, non_promotable, lineage


def _run_n10a_owner(product_root: Path) -> tuple[bytes, int, int, int]:
    from polisyos.runtime.quality.design_problem import DesignProblem
    from tools.quality.validation import check_layer3_gy_second_domain_pack as owner

    owner._CYCLE_TRACE_CACHE.clear()
    frozen = owner._load_frozen_bundle(product_root)
    trace = owner._build_cycle_trace(product_root, frozen["smoke_problem"])
    reconciled = {"cycle_trace": trace}
    owner._preserve_frozen_operational_metrics(reconciled, product_root)
    trace = reconciled["cycle_trace"]

    problem = DesignProblem.model_validate(frozen["smoke_problem"]["design_problem"])
    capture = trace["n4_owner_capture"]
    assert capture["recording_source"] == (
        "historical_capture_raw_responses_replayed_through_current_n4_owner"
    )
    assert owner._historical_n4_replay_receipt_issues(capture, problem=problem) == []
    replay_receipt = capture["historical_replay_receipt"]
    assert replay_receipt["schema_version"] == (
        "policyos.policy_design_case.gy_n10.n4_replay_receipt.v1"
    )

    promotion = trace["generation_cycle_run"]["promotion_port"]
    assert promotion["status"] == "not_promoted"
    assert promotion["reason"] == "verification_n9_sequence_non_consumer"
    receipts = tuple(promotion["receipts"])
    verification, non_promotable, receipt_lineage = (
        _validated_promotion_receipt_counts(receipts)
    )
    assert isinstance(replay_receipt["call_rebindings"], list)
    comparison_plan = owner._cycle_trace_plan_from_manifest(trace)
    assert trace["comparison_content_hash"] == owner._cycle_trace_comparison_content_hash(
        trace,
        comparison_plan,
    )
    output = (
        owner._canonical_json(comparison_plan.project(trace)) + "\n"
    ).encode("utf-8")
    return output, verification, non_promotable, receipt_lineage + 1


def _run_depth_n_owner(product_root: Path) -> tuple[bytes, int, int, int]:
    import asyncio

    from polisyos.pdc import build_gy_comparison_projection_plan
    from tools.quality.validation import (
        check_layer3_gy_depth_n_universality_contract as owner,
    )

    frozen = json.loads((product_root / owner.OUTPUT_PATH).read_text(encoding="utf-8"))
    role = "unseen"
    domain_run, recording, admissions = asyncio.run(
        owner._domain_run_and_normalized_recording(
            product_root,
            role=role,
            recording=frozen["proof_recordings"][role],
            historical_domain_run=frozen["domain_runs"][role],
        )
    )
    assert owner._authority_source_migration_receipt_issues(
        recording,
        replayed_domain_run=domain_run,
    ) == ()
    migration = recording["authority_source_migration_receipt"]
    assert migration["schema_version"] == (
        "policyos.layer3.gy.n10.authority_source_migration_receipt.v1"
    )
    assert migration["migration_reason"] == (
        "ambient_canonical_repo_to_isolated_verification"
    )
    assert migration["consumer_effect"] == "non_authorizing_verification_only"
    assert migration["predicate_provenance"] == (
        owner._authority_source_predicate_provenance()
    )

    promotion = domain_run["stage_trace"]["promotion"]
    assert promotion["authority_provenance"] == ["verification"]
    assert promotion["reason"] == "verification_n9_sequence_non_consumer"
    assert promotion["all_receipts_non_consumer"] is True
    assert promotion["certified_candidate_ids"] == []
    receipt_count = int(promotion["receipt_count"])
    owner_output = {
        "domain_runs": {role: domain_run},
        "proof_recordings": {role: recording},
    }
    comparison_plan = build_gy_comparison_projection_plan(
        owner_output,
        admissions=admissions,
    )
    output = (
        owner._canonical_json(comparison_plan.project(owner_output)) + "\n"
    ).encode("utf-8")
    return output, receipt_count, receipt_count, 1


def _run_n11_owner(product_root: Path) -> tuple[bytes, int, int, int]:
    from tools.quality.validation import check_layer3_gy_confidence_ledger as owner
    from tools.quality.validation import (
        check_layer3_gy_depth_n_universality_contract as depth_n,
    )
    from tools.quality.validation import layer3_gy_confidence_ledger_contract as adapter
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        DEFAULT_N13B_CONTRACT,
        N13bAcquisitionExecutorContract,
    )

    capstone = json.loads(
        (product_root / adapter.DEFAULT_N10_CAPSTONE).read_text(encoding="utf-8")
    )
    assert depth_n.validate_payload(capstone)["status"] == "pass"
    lineage_count = 0
    for role, recording in capstone["proof_recordings"].items():
        assert depth_n._authority_source_migration_receipt_issues(
            recording,
            replayed_domain_run=capstone["domain_runs"][role],
        ) == ()
        lineage_count += 1

    n13b = N13bAcquisitionExecutorContract.model_validate_json(
        (product_root / DEFAULT_N13B_CONTRACT).read_bytes()
    )
    catalog_path = (
        product_root
        / "production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb"
    )
    l5_path = (
        product_root
        / "production_data/canonical/local_data_20260501/"
        "ukraine_server_support_20260410/runtime_calibration_internals/"
        "calibration/d2/measurement_registry.json"
    )
    original_n10 = adapter._recompute_n10_capstone
    original_n13b = adapter._recompute_n13b_contract
    original_bundle_loader = owner.load_owner_bundle
    try:
        adapter._recompute_n10_capstone = lambda _root: capstone
        adapter._recompute_n13b_contract = (
            lambda _root, *, catalog_path, l5_path: n13b
        )
        adapter.clear_owner_bundle_cache()
        bundle = adapter.load_owner_bundle(
            product_root,
            catalog_path=catalog_path,
            l5_path=l5_path,
        )
        owner.load_owner_bundle = lambda *_args, **_kwargs: bundle
        contract = owner.build_live_contract(
            product_root,
            catalog_path=catalog_path,
            l5_path=l5_path,
        )
    finally:
        owner.load_owner_bundle = original_bundle_loader
        adapter._recompute_n13b_contract = original_n13b
        adapter._recompute_n10_capstone = original_n10
        adapter.clear_owner_bundle_cache()

    assert owner.validate_payload(contract, expected=contract)["status"] == "pass"
    projections = (
        contract.real_ledger_projection,
        contract.conformance_ledger_projection,
        contract.n9_promotion_projection,
        contract.n12_epoch_reference_projection,
    )
    assert {projection.authority_provenance for projection in projections} == {
        "verification"
    }
    checks = (
        tuple(contract.real_ledger_projection.checks)
        + tuple(contract.conformance_ledger_projection.checks)
        + tuple(contract.n9_promotion_projection.promotion_rows)
    )
    assert checks
    assert all(check.eligible_for_promotion is False for check in checks)
    output = owner.contract_bytes(contract)
    return output, len(checks), len(checks), lineage_count


def _run_owner(product_root: Path, producer_id: str) -> tuple[bytes, int, int, int]:
    runners = {
        "n9-promotion": _run_n9_owner,
        "n6-generation-cycle": _run_n6_owner,
        "n10a-second-domain": _run_n10a_owner,
        "depth-n": _run_depth_n_owner,
        "n11-confidence-ledger": _run_n11_owner,
    }
    return runners[producer_id](product_root)


def _worker_main(producer_id: str, history_kind: str, product_root: Path) -> int:
    started = time.monotonic()
    history_terminal = _install_durable_history(product_root, history_kind)
    authority_root = product_root / ".polisyos"
    digest_before, history_file_count = _tree_digest(authority_root)

    from polisyos.runtime.quality.confidence_ledger import ConfidenceLedgerSession

    from_repo_code = ConfidenceLedgerSession.from_repo.__func__.__code__
    from_repo_calls: list[str] = []
    monitoring_tool = sys.monitoring.PROFILER_ID
    if sys.monitoring.get_tool(monitoring_tool) is not None:
        raise AssertionError("Python profiler monitoring slot is already in use")

    def observe_from_repo(_code: object, _instruction_offset: int) -> None:
        from_repo_calls.append(f"{producer_id}:{history_kind}")

    sys.monitoring.use_tool_id(monitoring_tool, "gy-def9-from-repo-observer")
    sys.monitoring.register_callback(
        monitoring_tool,
        sys.monitoring.events.PY_START,
        observe_from_repo,
    )
    sys.monitoring.set_local_events(
        monitoring_tool,
        from_repo_code,
        sys.monitoring.events.PY_START,
    )
    try:
        output, verification_count, non_promotable_count, lineage_count = _run_owner(
            product_root,
            producer_id,
        )
    finally:
        sys.monitoring.set_local_events(monitoring_tool, from_repo_code, 0)
        sys.monitoring.register_callback(
            monitoring_tool,
            sys.monitoring.events.PY_START,
            None,
        )
        sys.monitoring.free_tool_id(monitoring_tool)

    digest_after, final_file_count = _tree_digest(authority_root)
    result = {
        "producer_id": producer_id,
        "history_kind": history_kind,
        "history_terminal": history_terminal,
        "history_digest_before": digest_before,
        "history_digest_after": digest_after,
        "history_file_count": history_file_count,
        "final_history_file_count": final_file_count,
        "from_repo_calls": from_repo_calls,
        "output_base64": base64.b64encode(output).decode("ascii"),
        "output_byte_count": len(output),
        "verification_receipt_count": verification_count,
        "non_promotable_receipt_count": non_promotable_count,
        "typed_lineage_count": lineage_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    print(_WORKER_RESULT_PREFIX + json.dumps(result, sort_keys=True))
    return 0


def _clone_for_history(clone_root: Path, head: str) -> Path:
    clone = subprocess.run(
        (
            "git",
            "clone",
            "--quiet",
            "--shared",
            "--no-hardlinks",
            "--no-checkout",
            REPOSITORY_ROOT.as_posix(),
            clone_root.as_posix(),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert clone.returncode == 0, clone.stderr
    checkout = subprocess.run(
        ("git", "checkout", "--quiet", "--detach", head),
        cwd=clone_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert checkout.returncode == 0, checkout.stderr
    product_root = clone_root / "policy-engine"
    production_data = POLICY_ENGINE_ROOT / "production_data"
    assert production_data.exists()
    (product_root / "production_data").symlink_to(
        production_data.resolve(),
        target_is_directory=True,
    )
    (product_root / ".venv").symlink_to(
        (POLICY_ENGINE_ROOT / ".venv").resolve(),
        target_is_directory=True,
    )
    return product_root


def _run_history_case(
    case: _ProducerCase,
    history_kind: str,
    *,
    product_root: Path,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (
            (product_root / "src").as_posix(),
            product_root.as_posix(),
        )
    )
    try:
        completed = subprocess.run(
            (
                sys.executable,
                Path(__file__).resolve().as_posix(),
                "--worker",
                case.producer_id,
                history_kind,
                product_root.as_posix(),
            ),
            cwd=product_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=case.worker_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"{case.producer_id}:{history_kind} exceeded "
            f"{case.worker_timeout_seconds}s; stdout={exc.stdout!r}; stderr={exc.stderr!r}"
        )
    if completed.returncode != 0:
        pytest.fail(
            f"{case.producer_id}:{history_kind} worker failed with "
            f"{completed.returncode}; stdout={completed.stdout[-8000:]!r}; "
            f"stderr={completed.stderr[-8000:]!r}"
        )
    marker_rows = [
        line.removeprefix(_WORKER_RESULT_PREFIX)
        for line in completed.stdout.splitlines()
        if line.startswith(_WORKER_RESULT_PREFIX)
    ]
    assert len(marker_rows) == 1, completed.stdout[-8000:]
    result = json.loads(marker_rows[0])
    result["worker_stdout"] = completed.stdout
    result["worker_stderr"] = completed.stderr
    return result


@pytest.mark.parametrize(
    "case",
    _PRODUCER_CASES,
    ids=lambda case: case.producer_id,
)
def test_real_governed_owner_bytes_ignore_incompatible_durable_history(
    case: _ProducerCase,
    tmp_path: Path,
) -> None:
    """Recompute one governed owner over both authority-history terminals."""

    head = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    product_root = _clone_for_history(tmp_path / "checkout", head)
    fresh = _run_history_case(
        case,
        "fresh",
        product_root=product_root,
    )
    fresh_history = tmp_path / "fresh-authority-history"
    (product_root / ".polisyos").rename(fresh_history)
    assert _tree_digest(fresh_history) == (
        fresh["history_digest_after"],
        fresh["final_history_file_count"],
    )
    incompatible = _run_history_case(
        case,
        "registry-binding-incompatible",
        product_root=product_root,
    )

    assert fresh["history_terminal"] == "fresh_authority_empty_history"
    assert incompatible["history_terminal"] == "ledger_scope_binding_mismatch"
    assert fresh["history_file_count"] > 0
    assert incompatible["history_file_count"] > 0
    assert fresh["history_digest_before"] != incompatible["history_digest_before"]
    for observed in (fresh, incompatible):
        assert observed["producer_id"] == case.producer_id
        assert observed["from_repo_calls"] == []
        assert observed["history_digest_before"] == observed["history_digest_after"]
        assert observed["history_file_count"] == observed["final_history_file_count"]
        assert observed["output_byte_count"] > 0
        assert observed["verification_receipt_count"] == case.expected_receipt_count
        assert observed["non_promotable_receipt_count"] == case.expected_receipt_count
        assert observed["typed_lineage_count"] >= case.minimum_lineage_count
    fresh_output = base64.b64decode(fresh["output_base64"])
    incompatible_output = base64.b64decode(incompatible["output_base64"])
    assert fresh_output == incompatible_output, _first_json_differences(
        json.loads(fresh_output),
        json.loads(incompatible_output),
    )


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "--worker":
        raise SystemExit("usage: test_file --worker PRODUCER HISTORY PRODUCT_ROOT")
    raise SystemExit(_worker_main(sys.argv[2], sys.argv[3], Path(sys.argv[4])))
