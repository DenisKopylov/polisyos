from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from tools.ops_runners.runtime import replay_canary_bundle

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_fake_bundle(
    bundle_dir: Path,
    *,
    quality_status: str = "pass",
    overall_score: float = 1.0,
) -> None:
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True)
    _write_json(
        bundle_dir / "bundle.json",
        {
            "schema_version": "policyos.canary_evidence.v1",
            "git_sha": "abc123",
            "canary_kind": "production",
            "job_id": "job-replay",
            "run_id": "R_replay",
            "status": "completed",
            "execution_status": "completed",
            "quality_status": quality_status,
            "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
            "quality_evidence_bundle_path": str(bundle_dir),
            "command": {
                "argv": ["local_production_canary", "--mode=real"],
                "run_params": {"max_iterations": 1, "random_seed": 1729},
            },
            "files": {
                "request": "request.sanitized.json",
                "env": "env.sanitized.json",
                "artifacts": "artifacts.json",
                "quality_evidence": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json",
                },
            },
        },
    )
    _write_json(
        bundle_dir / "request.sanitized.json",
        {
            "question": "Should wartime MSME credit support be expanded?",
            "api_key": {
                "present": True,
                "env_var": "POLISYOS_LLM_GATEWAY_API_KEY",
                "fingerprint": _sha("1"),
            },
        },
    )
    _write_json(
        bundle_dir / "env.sanitized.json",
        {
            "POLISYOS_EXECUTION_PROFILE": "production",
            "POLISYOS_LLM_GATEWAY_API_KEY": {
                "present": True,
                "env_var": "POLISYOS_LLM_GATEWAY_API_KEY",
                "fingerprint": _sha("2"),
            },
            "POLISYOS_SCIENTIST_V2_ENABLED": "1",
            "POLISYOS_LLM_GATEWAY_PROVIDER": "gonka_proxy",
        },
    )
    _write_json(
        bundle_dir / "artifacts.json",
        {
            "refs": [
                {
                    "source": "job",
                    "path": "$.progress.details.data_snapshot_ref",
                    "value": _sha("3"),
                },
                {
                    "source": "job",
                    "path": "$.progress.details.registry_bundle_ref",
                    "value": _sha("4"),
                },
                {
                    "source": "job",
                    "path": "$.progress.details.prompt_template_ref",
                    "value": _sha("5"),
                },
                {
                    "source": "run",
                    "path": "$.source_refs.production_msme_panel",
                    "value": _sha("6"),
                },
                {
                    "source": "lineage",
                    "path": "$.norm_refs.ua_credit_normpack",
                    "value": _sha("7"),
                },
                {
                    "source": "run",
                    "path": "$.artifacts.policy_output_ref",
                    "value": _sha("8"),
                },
            ],
            "quality_ref_resolution": {
                "status": "complete",
                "refs": {
                    "fabric_retrieval_trace_ref": _sha("9"),
                    "normative_applicability_report_ref": _sha("a"),
                },
            },
        },
    )
    _write_json(
        quality_dir / "quality_scorecard.json",
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "execution_status": "completed",
            "quality_status": quality_status,
            "overall_score": overall_score,
            "stage_scores": {"llm": overall_score},
            "blocking_quality_failures": (
                [] if quality_status == "pass" else [{"gate": "fabric_retrieval_trace_present"}]
            ),
            "evidence_refs": {
                "provider_preflight": "provider_preflight.json",
                "quality_scorecard": "quality_evidence/quality_scorecard.json",
            },
        },
    )


def test_replay_canary_bundle_builds_sanitized_replay_refs_without_secret_reuse(
    tmp_path,
) -> None:
    bundle_dir = tmp_path / "bundle"
    cas_root = tmp_path / "cas"
    _write_fake_bundle(bundle_dir)

    result = replay_canary_bundle.replay_canary_bundle(
        bundle_dir,
        cas_root=cas_root,
    )

    assert result["schema_version"] == "policyos.replay_canary_bundle.v1"
    assert result["status"] == "match"
    assert result["production_readiness"] == "pass"
    assert result["replay_manifest_ref"].startswith("sha256:")
    assert result["drift_explanation_ref"].startswith("sha256:")
    assert result["files"]["replay_result"] == "replay.json"
    assert (bundle_dir / "replay.json").exists()

    store = FileSystemCAS(cas_root)
    manifest = from_canonical_bytes(store.get_bytes(result["replay_manifest_ref"]))
    explanation = from_canonical_bytes(store.get_bytes(result["drift_explanation_ref"]))

    assert manifest["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert manifest["request_fingerprint"].startswith("sha256:")
    assert manifest["feature_flags"]["POLISYOS_SCIENTIST_V2_ENABLED"] == "1"
    assert manifest["provider_model_metadata"]["provider"] == "gonka_proxy"
    assert manifest["prompt_template_fingerprints"]["prompt_template_ref"] == _sha("5")
    assert manifest["data_refs"]["data_snapshot_ref"] == _sha("3")
    assert manifest["source_refs"]["production_msme_panel"] == _sha("6")
    assert manifest["norm_refs"]["ua_credit_normpack"] == _sha("7")
    assert manifest["cas_refs"]["policy_output_ref"] == _sha("8")
    assert manifest["random_seeds"] == {"random_seed": 1729}
    assert explanation["production_readiness"] == "pass"

    rendered = json.dumps({"result": result, "manifest": manifest, "explanation": explanation})
    assert "live-secret" not in rendered
    assert "POLISYOS_LLM_GATEWAY_API_KEY=secret" not in rendered


def test_replay_canary_bundle_fails_when_replay_has_unexplained_drift(tmp_path) -> None:
    baseline_bundle = tmp_path / "baseline"
    replay_bundle = tmp_path / "replay"
    cas_root = tmp_path / "cas"
    output = tmp_path / "replay_output.json"
    _write_fake_bundle(baseline_bundle)
    _write_fake_bundle(replay_bundle, quality_status="fail", overall_score=0.4)

    baseline = replay_canary_bundle.replay_canary_bundle(
        baseline_bundle,
        cas_root=cas_root,
    )

    exit_code = replay_canary_bundle.main(
        [
            "--bundle",
            str(replay_bundle),
            "--cas-root",
            str(cas_root),
            "--baseline-manifest-ref",
            baseline["replay_manifest_ref"],
            "--json-output",
            str(output),
        ]
    )

    assert exit_code == 2
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "unexplained_drift"
    assert result["production_readiness"] == "fail"
    assert result["summary"]["unexplained_difference_count"] > 0
    assert result["drift_explanation_ref"].startswith("sha256:")


def test_deterministic_replay_reference_doc_records_contract() -> None:
    doc = REPO_ROOT / "docs/reference/runtime/deterministic-replay.md"
    text = doc.read_text(encoding="utf-8")

    assert "policyos.replay_manifest.v1" in text
    assert "policyos.drift_explanation.v1" in text
    assert "`replay_manifest_ref`" in text
    assert "`drift_explanation_ref`" in text
    assert "Unexplained drift fails production readiness" in text
    assert "must not contain raw secrets" in text
