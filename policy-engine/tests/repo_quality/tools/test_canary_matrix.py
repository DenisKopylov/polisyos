from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.ops_runners.runtime import (
    canary_matrix,
    local_production_canary,
    run_canary_matrix,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent


def test_canary_matrix_declares_full_phase_0_4_dimensions() -> None:
    payload = canary_matrix.build_matrix_payload()

    assert payload["schema_version"] == "policyos.canary_matrix.v1"
    assert payload["dimensions"] == {
        "profile": ["dev", "research", "governed", "production"],
        "provider": ["simulated", "live_gonka_proxy"],
        "data": ["fixture", "canonical_production"],
        "scenario": ["public_golden", "negative", "adversarial", "hidden_quarantined"],
        "ui": ["api_only", "dashboard_smoke"],
    }
    assert len(payload["lanes"]) == 128

    lane_ids = [lane["lane_id"] for lane in payload["lanes"]]
    assert lane_ids == sorted(lane_ids)
    assert len(lane_ids) == len(set(lane_ids))


def test_canary_matrix_keeps_ci_lanes_deterministic_and_live_lanes_quarantined() -> None:
    lanes = {lane["lane_id"]: lane for lane in canary_matrix.build_canary_lanes()}

    ci_lane = lanes[
        "profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only"
    ]
    assert ci_lane["status"] == "ready"
    assert ci_lane["ci_safe"] is True
    assert ci_lane["quarantine"] is None
    assert ci_lane["runner"]["module"] == "tools.ops_runners.runtime.local_production_canary"
    assert "--mode=simulated" in ci_lane["runner"]["argv"]
    assert (
        "--production-data-root=tests/_data/data_forge/ukraine_shadow"
        in ci_lane["runner"]["argv"]
    )
    assert "--execution-profile=dev" in ci_lane["runner"]["argv"]
    assert "--canary-kind=dev" in ci_lane["runner"]["argv"]

    live_lane = lanes[
        "profile-production__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only"
    ]
    assert live_lane["status"] == "quarantined"
    assert live_lane["ci_safe"] is False
    assert live_lane["quarantine"]["reason"] == "requires live Gonka-compatible LLM proxy"
    assert "--mode=real" in live_lane["runner"]["argv"]
    assert "--production-data-root=production_data" in live_lane["runner"]["argv"]
    assert "--execution-profile=production" in live_lane["runner"]["argv"]
    assert "--canary-kind=production" in live_lane["runner"]["argv"]


def test_canary_matrix_every_lane_declares_required_evidence_files_and_missing_lanes() -> None:
    lanes = canary_matrix.build_canary_lanes()
    common_files = {
        "bundle.json",
        "request.sanitized.json",
        "env.sanitized.json",
        "artifacts.json",
        "job.json",
        "quality_evidence/quality_scorecard.json",
        "quality_evidence/golden_scenario_contract.json",
    }
    deferred = [lane for lane in lanes if lane["status"] == "deferred"]
    skipped = [lane for lane in lanes if lane["status"] == "skipped"]

    assert deferred
    assert skipped
    assert any(lane["scenario"] == "negative" for lane in deferred)
    assert any(lane["scenario"] == "hidden_quarantined" for lane in skipped)

    live_negative_lane = next(
        lane
        for lane in lanes
        if lane["provider"] == "live_gonka_proxy"
        and lane["scenario"] == "negative"
        and lane["ui"] == "api_only"
    )
    assert live_negative_lane["status"] == "quarantined"
    assert any(
        gap["status"] == "deferred"
        and gap["dimension"] == "scenario"
        and gap["value"] == "negative"
        for gap in live_negative_lane["coverage"]["missing_or_deferred_gaps"]
    )

    for lane in lanes:
        files = set(lane["required_evidence_files"])
        assert common_files <= files
        assert lane["coverage"]["status"] == lane["status"]
        assert lane["coverage"]["missing_or_deferred_reason"]

    dashboard_lane = next(lane for lane in lanes if lane["ui"] == "dashboard_smoke")
    assert "dashboard.json" in dashboard_lane["required_evidence_files"]

    production_data_lane = next(
        lane for lane in lanes if lane["data"] == "canonical_production"
    )
    assert "production_data_evidence.json" in production_data_lane["required_evidence_files"]


def test_canary_matrix_types_governed_and_production_backing_service_gaps() -> None:
    lanes = {lane["lane_id"]: lane for lane in canary_matrix.build_canary_lanes()}
    lane = lanes[
        "profile-production__provider-simulated__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    ]

    assert lane["status"] != "ready"
    assert lane["setup_error"]["type"] == "local_backing_service_unavailable"
    assert lane["setup_error"]["readiness_state"] == "not_ready"
    assert lane["setup_error"]["code"] == "canary_postgresql_state_store_unavailable"
    assert lane["setup_error"]["service"] == "postgresql_control_state_store"
    assert lane["setup_error"]["required_backend"] == "postgresql"
    assert lane["setup_error"]["owner"] == "runtime-platform"
    assert lane["coverage"]["setup_error"] == lane["setup_error"]


def test_local_canary_runner_accepts_profile_specific_matrix_args() -> None:
    args = local_production_canary._build_parser().parse_args(
        [
            "--mode=simulated",
            "--execution-profile=production",
            "--canary-kind=production",
            "--production-data-root=tests/_data/data_forge/ukraine_shadow",
        ]
    )

    request = local_production_canary._build_canary_request(
        model="model",
        production_data_root=Path("tests/_data/data_forge/ukraine_shadow"),
        max_iterations=1,
        run_budget_usd=0.05,
        execution_profile=args.execution_profile,
    )

    assert args.execution_profile == "production"
    assert args.canary_kind == "production"
    assert request["execution_profile"] == "production"


def test_simulated_serious_lane_embeds_deterministic_evidence_as_runtime_owned() -> None:
    scenario = local_production_canary.load_quality_scenario_contract(
        "ukraine_msme_wartime_credit_support",
        scenarios_file=REPO_ROOT / "tools/ops_runners/runtime/golden_quality_scenarios.json",
    )
    job_payload = {
        "job_id": "job-deterministic-closeout",
        "run_id": "R_deterministic_closeout",
        "state": "completed",
        "progress": {
            "details": {
                "runtime_quality_refs": {
                    "normative_applicability_report_ref": "sha256:" + "1" * 64,
                    "fabric_retrieval_trace_ref": "sha256:" + "2" * 64,
                    "foundry_method_report_ref": "sha256:" + "3" * 64,
                    "policy_grounding_matrix_ref": "sha256:" + "4" * 64,
                    "conflict_check_ref": "sha256:" + "5" * 64,
                    "policy_design_case_ref": "sha256:" + "6" * 64,
                    "policy_intent_envelope_ref": "sha256:" + "7" * 64,
                    "policy_design_capability_ledger_ref": "sha256:" + "8" * 64,
                },
                "data_snapshot_ref": "sha256:" + "9" * 64,
                "input_bindings_ref": "sha256:" + "a" * 64,
                "registry_bundle_ref": "sha256:" + "b" * 64,
                "quality_report_ref": "sha256:" + "c" * 64,
            }
        },
    }

    evidence = local_production_canary._deterministic_quality_evidence_from_scenario(
        scenario,
        job_payload=job_payload,
        run_payload=None,
    )
    embedded = local_production_canary._with_embedded_runtime_quality_evidence(
        job_payload,
        evidence,
    )
    runtime_evidence = embedded["progress"]["details"]["runtime_quality_evidence"]

    assert runtime_evidence["normative_evidence"]["status"] == "pass"
    assert runtime_evidence["normative_evidence"]["legal_corpus_snapshot"]
    assert runtime_evidence["fabric_retrieval_trace"]["candidate_sources"][0]["source_rights"]
    assert runtime_evidence["foundry_method_report"]["selected_methods"][0][
        "identification_requirements"
    ]
    assert runtime_evidence["scholar_evidence"]["status"] == "pass"
    assert runtime_evidence["policy_design_case"]["pass1b_tenant_cas_approval_governance"][
        "status"
    ] == "pass"
    claim_registry = runtime_evidence["policy_design_case"]["claim_registry"]
    claim_row = claim_registry["claims"][0]
    assert claim_row["claim_id"] == "rec_1"
    assert claim_row["assurance_node_id"]
    assert claim_row["claim_ref"].startswith("sha256:")
    assert claim_row["runtime_event_ref"].startswith("event://")
    assert claim_row["authority_role"] == "producer_authority"
    assert claim_row["provenance_kind"] == "runtime_emitted"
    assert claim_row["selected_producer_refs"]["lex"]
    assert claim_row["selected_producer_refs"]["fabric"]
    assert claim_row["selected_producer_refs"]["data_forge"]
    assert claim_row["selected_producer_refs"]["scholar"]
    assert claim_row["selected_producer_refs"]["foundry"]
    assert claim_row["selected_producer_refs"]["options_objectives"]


def test_canary_matrix_cli_writes_stable_json(tmp_path) -> None:
    output = tmp_path / "canary_matrix.json"

    assert canary_matrix.main(["--list", "--json-output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == canary_matrix.build_matrix_payload()
    assert payload["summary"]["total_lanes"] == 128
    assert payload["summary"]["ready"] > 0
    assert payload["summary"]["quarantined"] > 0
    assert payload["summary"]["deferred"] > 0
    assert payload["summary"]["skipped"] > 0


def test_canary_matrix_reference_doc_records_coverage_and_evidence() -> None:
    doc = REPO_ROOT / "docs/reference/runtime/production-canary-matrix.md"
    text = doc.read_text(encoding="utf-8")

    assert "policyos.canary_matrix.v1" in text
    assert "`profile`" in text
    assert "`live_gonka_proxy`" in text
    assert "`quality_evidence/quality_scorecard.json`" in text
    assert "Missing lanes are represented as `deferred` or `skipped`" in text


def _write_fake_lane_bundle(
    bundle_dir: Path,
    *,
    status: str = "pass",
    write_required: bool = True,
    omit_required: set[str] | None = None,
) -> None:
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "status": "completed",
                "quality_status": status,
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": str(bundle_dir),
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps({"schema_version": "policyos.quality_scorecard.v1", "quality_status": status}),
        encoding="utf-8",
    )
    if not write_required:
        return
    lanes = {
        str(lane["lane_id"]): lane
        for lane in canary_matrix.build_canary_lanes()
    }
    lane = lanes.get(bundle_dir.name)
    if lane is None:
        return
    omitted = omit_required or set()
    for rel_path in lane["required_evidence_files"]:
        if rel_path in omitted:
            continue
        path = bundle_dir / rel_path
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema_version": "test.fake_canary_evidence.v1"}),
            encoding="utf-8",
        )


def _lane_by_id(lane_id: str) -> dict[str, object]:
    lanes = {str(lane["lane_id"]): lane for lane in canary_matrix.build_canary_lanes()}
    return dict(lanes[lane_id])


def _run_one_ready_lane_with_missing_evidence(
    tmp_path: Path,
    monkeypatch,
    *,
    lane: dict[str, object],
    missing_file: str,
    scorecard_status: str = "pass",
) -> dict[str, object]:
    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(
            bundle_dir,
            status=scorecard_status,
            omit_required={missing_file},
        )
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)
    results = run_canary_matrix.run_matrix(
        lanes=[lane],
        output_root=tmp_path / "evidence",
        run_root=tmp_path / "runs",
        allow_live_provider=False,
        cwd=REPO_ROOT,
        timeout_s=30,
    )
    return results[0]


def test_real_canary_matrix_runs_deterministic_subset_and_writes_lane_summaries(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "matrix_result.json"
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        argv = list(command)
        calls.append(argv)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    deterministic_lanes = [
        lane for lane in canary_matrix.build_canary_lanes() if lane["closeout_required"]
    ]

    assert payload["schema_version"] == "policyos.canary_matrix_run.v1"
    assert payload["summary"]["selected_lanes"] == len(deterministic_lanes)
    assert payload["summary"]["executed"] == len(deterministic_lanes)
    assert payload["summary"]["passed"] == len(deterministic_lanes)
    assert payload["summary"]["failed"] == 0
    assert len(calls) == len(deterministic_lanes)
    for lane_result in payload["lanes"]:
        assert lane_result["status"] == "passed"
        assert lane_result["bundle_path"]
        assert lane_result["scorecard_status"] == "pass"
        assert lane_result["failure_envelope"] is None


def test_real_canary_matrix_fails_lane_when_scorecard_fails(tmp_path, monkeypatch) -> None:
    output = tmp_path / "matrix_result.json"

    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir, status="fail")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 2
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    lane = payload["lanes"][0]
    assert lane["status"] == "failed"
    assert lane["scorecard_status"] == "fail"
    assert lane["failure_envelope"]["code"] == "canary_scorecard_failed"
    assert payload["summary"]["failure_envelope"]["code"] == "canary_matrix_has_failures"


def test_real_canary_matrix_rejects_bundle_scorecard_runtime_scorecard_conflict(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "matrix_result.json"

    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir, status="pass")
        (bundle_dir / "quality_evidence" / "quality_scorecard.json").write_text(
            json.dumps(
                {
                    "schema_version": "policyos.quality_scorecard.v1",
                    "quality_status": "pass",
                    "quality_scorecard_ref": "sha256:" + "a" * 64,
                    "evidence_refs": {"quality_scorecard": "sha256:" + "a" * 64},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 2
    )

    lane = json.loads(output.read_text(encoding="utf-8"))["lanes"][0]
    assert lane["status"] == "failed"
    assert lane["failure_envelope"]["code"] == "source_truth_conflict"
    conflict = lane["failure_envelope"]["source_truth_conflicts"][0]
    assert conflict["field_family"] == "scorecard_identity_and_gates"
    assert conflict["failure_code"] == "hds_scorecard_identity_conflict"


def test_real_canary_matrix_rejects_warn_scorecard_outside_ci_smoke(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "matrix_result.json"

    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir, status="warn")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--lane-id",
                "profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 2
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["lanes"][0]["failure_envelope"]["code"] == "canary_scorecard_failed"

    assert (
        run_canary_matrix.main(
            [
                "--ci-smoke",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["lanes"][0]["status"] == "passed"
    assert payload["lanes"][0]["scorecard_status"] == "warn"


def test_real_canary_matrix_rejects_warn_scorecard_for_deterministic_closeout(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "matrix_result.json"

    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir, status="warn")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 2
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["lanes"][0]["failure_envelope"]["code"] == "canary_scorecard_failed"
    assert payload["lanes"][0]["scorecard_status"] == "warn"


def test_real_canary_matrix_fails_lane_when_required_evidence_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "matrix_result.json"

    def fake_run(command, **_kwargs):
        argv = list(command)
        lane_id = next(value for value in argv if value.startswith("--matrix-lane-id=")).split(
            "=", 1
        )[1]
        bundle_dir = tmp_path / "bundles" / lane_id
        _write_fake_lane_bundle(bundle_dir, write_required=False)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--output-root",
                str(tmp_path / "evidence"),
                "--run-root",
                str(tmp_path / "runs"),
                "--json-output",
                str(output),
            ]
        )
        == 2
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    failure = payload["lanes"][0]["failure_envelope"]
    assert failure["code"] == "canary_required_evidence_missing"
    assert "quality_evidence/provider_model_quality_ledger.json" in (
        failure["missing_required_evidence"]
    )


def test_real_canary_matrix_fails_missing_provider_ledger_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    lane = _lane_by_id(
        "profile-research__provider-simulated__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )

    result = _run_one_ready_lane_with_missing_evidence(
        tmp_path,
        monkeypatch,
        lane=lane,
        missing_file="quality_evidence/provider_model_quality_ledger.json",
    )

    failure = result["failure_envelope"]
    assert result["status"] == "failed"
    assert failure["code"] == "canary_required_evidence_missing"
    assert failure["missing_required_evidence"] == [
        "quality_evidence/provider_model_quality_ledger.json"
    ]


def test_real_canary_matrix_fails_missing_performance_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    lane = _lane_by_id(
        "profile-research__provider-simulated__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )

    result = _run_one_ready_lane_with_missing_evidence(
        tmp_path,
        monkeypatch,
        lane=lane,
        missing_file="performance.json",
    )

    failure = result["failure_envelope"]
    assert result["status"] == "failed"
    assert failure["code"] == "canary_required_evidence_missing"
    assert failure["missing_required_evidence"] == ["performance.json"]


def test_real_canary_matrix_fails_missing_dashboard_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    lane = _lane_by_id(
        "profile-research__provider-simulated__data-canonical_production"
        "__scenario-public_golden__ui-dashboard_smoke"
    )
    lane["status"] = "ready"
    lane["closeout_required"] = True

    result = _run_one_ready_lane_with_missing_evidence(
        tmp_path,
        monkeypatch,
        lane=lane,
        missing_file="dashboard.json",
    )

    failure = result["failure_envelope"]
    assert result["status"] == "failed"
    assert failure["code"] == "canary_required_evidence_missing"
    assert failure["missing_required_evidence"] == ["dashboard.json"]


def test_real_canary_matrix_can_select_one_lane_or_one_scenario() -> None:
    lane_id = (
        "profile-dev__provider-simulated__data-fixture"
        "__scenario-public_golden__ui-api_only"
    )

    by_lane = run_canary_matrix.select_lanes(
        canary_matrix.build_canary_lanes(),
        lane_id=lane_id,
    )
    by_scenario = run_canary_matrix.select_lanes(
        canary_matrix.build_canary_lanes(),
        scenario="public_golden",
    )
    ci_smoke = run_canary_matrix.select_lanes(
        canary_matrix.build_canary_lanes(),
        ci_smoke=True,
    )

    assert [lane["lane_id"] for lane in by_lane] == [lane_id]
    assert by_scenario
    assert all(lane["closeout_required"] for lane in by_scenario)
    assert {lane["scenario"] for lane in by_scenario} == {"public_golden"}
    assert ci_smoke
    assert all(lane["ci_safe"] for lane in ci_smoke)


def test_deterministic_selection_excludes_live_ready_closeout_even_when_allowed() -> None:
    lanes = [
        {
            "lane_id": "research-closeout",
            "status": "ready",
            "provider": "simulated",
            "closeout_required": True,
        },
        {
            "lane_id": "live-closeout",
            "status": "ready",
            "provider": "live_gonka_proxy",
            "closeout_required": True,
        },
        {
            "lane_id": "dev-smoke",
            "status": "ready",
            "provider": "simulated",
            "ci_safe": True,
            "closeout_required": False,
        },
    ]

    selected = run_canary_matrix.select_lanes(
        lanes,
        deterministic=True,
        include_live_provider=True,
    )

    assert [lane["lane_id"] for lane in selected] == ["research-closeout"]


def test_local_canary_runner_collects_runtime_hot_path_observations() -> None:
    calls: list[object] = []

    class _RunIndex:
        def refresh(self, *, force: bool = False) -> None:
            calls.append(("refresh", force))

        def list_runs(self, **kwargs):
            calls.append(("list_runs", kwargs))
            return [], {"count": 0}

    class _RuntimeCtx:
        run_index = _RunIndex()

    class _State:
        runtime_api_ctx = _RuntimeCtx()

    class _App:
        state = _State()

    class _Response:
        status_code = 200

        def json(self):
            return {"ok": True}

    class _Client:
        def get(self, path: str):
            calls.append(("get", path))
            return _Response()

    observations = local_production_canary._collect_runtime_hot_path_observations(
        _App(),
        _Client(),
        run_id="R_runtime_hot_paths",
        tenant_id="tenant-a",
    )

    assert set(observations) == {
        "run_index_refresh_ms",
        "run_index_list_ms",
        "timeline_api_ms",
        "lineage_api_ms",
    }
    assert all(value >= 0 for value in observations.values())
    assert ("refresh", True) in calls
    assert ("get", "/api/v1/runs/R_runtime_hot_paths/timeline") in calls
    assert ("get", "/api/v1/runs/R_runtime_hot_paths/lineage") in calls


def test_canary_matrix_workflow_wires_ci_and_quarantined_nightly_jobs() -> None:
    workflow = WORKSPACE_ROOT / ".github/workflows/policyos-canary-matrix.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "run_canary_matrix.py --deterministic" in text
    assert "--allow-live-provider" in text
    assert "POLISYOS_LLM_GATEWAY_API_KEY" in text
    assert "schedule:" in text


def test_live_provider_lane_requires_credentials_and_explicit_flag(tmp_path, monkeypatch) -> None:
    lane_id = (
        "profile-production__provider-live_gonka_proxy__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )
    output = tmp_path / "live_result.json"
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        argv = list(command)
        calls.append(argv)
        lane_id_from_command = next(
            value for value in argv if value.startswith("--matrix-lane-id=")
        ).split("=", 1)[1]
        bundle_dir = tmp_path / "bundles" / lane_id_from_command
        _write_fake_lane_bundle(bundle_dir)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)
    monkeypatch.delenv("POLISYOS_LLM_GATEWAY_API_KEY", raising=False)

    assert (
        run_canary_matrix.main(["--lane-id", lane_id, "--json-output", str(output)])
        == 2
    )
    blocked_payload = json.loads(output.read_text(encoding="utf-8"))
    failure = blocked_payload["lanes"][0]["failure_envelope"]
    assert calls == []
    assert blocked_payload["lanes"][0]["status"] == "blocked"
    assert failure["type"] == "live_provider_unavailable"
    assert failure["readiness_state"] == "not_ready"
    assert failure["phase"] == "setup"
    assert failure["service"] == "gonka_proxy_llm_gateway"
    assert failure["code"] == "live_provider_not_enabled"
    assert failure["owner"] == "runtime-quality"

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "secret")
    assert (
        run_canary_matrix.main(
            [
                "--lane-id",
                lane_id,
                "--allow-live-provider",
                "--json-output",
                str(output),
            ]
        )
        == 0
    )
    allowed_payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert allowed_payload["lanes"][0]["status"] == "passed"


def test_deterministic_only_lane_runs_cloud_live_lane_with_credentials(
    tmp_path,
    monkeypatch,
) -> None:
    lane_id = (
        "profile-research__provider-live_gonka_proxy__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )
    output = tmp_path / "live_result.json"
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        argv = list(command)
        calls.append(argv)
        lane_id_from_command = next(
            value for value in argv if value.startswith("--matrix-lane-id=")
        ).split("=", 1)[1]
        bundle_dir = tmp_path / "bundles" / lane_id_from_command
        _write_fake_lane_bundle(bundle_dir)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f"Evidence bundle: {bundle_dir}\n",
            stderr="",
        )

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "secret")
    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--only-lane",
                lane_id,
                "--json-output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["selection"]["deterministic"] is True
    assert payload["selection"]["only_lane"] == lane_id
    assert payload["selected_lane_ids"] == [lane_id]
    assert payload["summary"]["selected_lanes"] == 1
    assert len(calls) == 1
    assert payload["lanes"][0]["status"] == "passed"


def test_deterministic_only_lane_blocks_cloud_live_lane_without_credentials(
    tmp_path,
    monkeypatch,
) -> None:
    lane_id = (
        "profile-research__provider-live_gonka_proxy__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )
    output = tmp_path / "live_result.json"
    calls: list[list[str]] = []

    monkeypatch.delenv("POLISYOS_LLM_GATEWAY_API_KEY", raising=False)
    monkeypatch.setattr(
        run_canary_matrix,
        "_run_lane_command",
        lambda command, **_kwargs: calls.append(list(command)),
    )

    assert (
        run_canary_matrix.main(
            [
                "--deterministic",
                "--only-lane",
                lane_id,
                "--json-output",
                str(output),
            ]
        )
        == 2
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    failure = payload["lanes"][0]["failure_envelope"]
    assert calls == []
    assert payload["lanes"][0]["status"] == "blocked"
    assert failure["code"] == "live_provider_not_enabled"
    assert failure["missing"] == ["POLISYOS_LLM_GATEWAY_API_KEY"]


def test_governed_production_lane_selection_surfaces_typed_setup_error(
    tmp_path,
    monkeypatch,
) -> None:
    lane_id = (
        "profile-production__provider-simulated__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )
    output = tmp_path / "production_result.json"
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(run_canary_matrix, "_run_lane_command", fake_run)

    assert (
        run_canary_matrix.main(["--lane-id", lane_id, "--json-output", str(output)])
        == 2
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    result = payload["lanes"][0]
    assert calls == []
    assert result["status"] == "blocked"
    assert result["failure_envelope"]["type"] == "local_backing_service_unavailable"
    assert result["failure_envelope"]["readiness_state"] == "not_ready"
    assert result["failure_envelope"]["code"] == "canary_postgresql_state_store_unavailable"
