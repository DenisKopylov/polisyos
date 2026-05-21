from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.replay import (
    build_replay_manifest,
    explain_replay_drift,
    persist_drift_explanation,
    persist_replay_manifest,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _manifest() -> dict[str, object]:
    return build_replay_manifest(
        request_payload={
            "question": "Should wartime MSME credit support be expanded?",
            "authorization": "Bearer live-secret",
        },
        git_sha="abc123",
        dependency_fingerprints={
            "uv.lock": _sha("1"),
            "pyproject.toml": _sha("2"),
        },
        feature_flags={"scientist_v2": True, "swarm": False},
        provider_model_metadata={
            "provider": "gonka_proxy",
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            "temperature": 0,
        },
        prompt_template_fingerprints={
            "formalizer": _sha("3"),
            "critic": _sha("4"),
        },
        data_refs={"production_snapshot": _sha("5")},
        source_refs={"fabric_trace": _sha("6")},
        norm_refs={"ua_credit_normpack": _sha("7")},
        cas_refs={"policy_output": _sha("8")},
        random_seeds={"python": 1729, "numpy": 31415},
        run_params={
            "max_iterations": 1,
            "llm_gateway_api_key": "sk-live-secret",
            "run_budget_usd": 0.05,
        },
        quality_scorecard_ref="quality_evidence/quality_scorecard.json",
        execution_summary={
            "status": "completed",
            "run_id": "R_replay",
            "policy_output_ref": _sha("9"),
        },
        quality_summary={
            "quality_status": "pass",
            "overall_score": 1.0,
            "blocking_quality_failures": [],
        },
    )


def test_replay_manifest_records_sanitized_deterministic_refs_and_persists(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest = _manifest()

    assert manifest["schema_version"] == "policyos.replay_manifest.v1"
    assert manifest["request_fingerprint"].startswith("sha256:")
    assert manifest["git_sha"] == "abc123"
    assert manifest["dependency_fingerprints"]["uv.lock"] == _sha("1")
    assert manifest["feature_flags"] == {"scientist_v2": True, "swarm": False}
    assert manifest["provider_model_metadata"]["provider"] == "gonka_proxy"
    assert manifest["prompt_template_fingerprints"]["formalizer"] == _sha("3")
    assert manifest["data_refs"]["production_snapshot"] == _sha("5")
    assert manifest["source_refs"]["fabric_trace"] == _sha("6")
    assert manifest["norm_refs"]["ua_credit_normpack"] == _sha("7")
    assert manifest["cas_refs"]["policy_output"] == _sha("8")
    assert manifest["random_seeds"] == {"numpy": 31415, "python": 1729}
    assert manifest["run_params"]["llm_gateway_api_key"]["present"] is True
    assert manifest["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert manifest["execution_summary"]["status"] == "completed"
    assert manifest["quality_summary"]["quality_status"] == "pass"

    rendered = json.dumps(manifest, sort_keys=True)
    assert "live-secret" not in rendered
    assert "sk-live-secret" not in rendered

    ref = persist_replay_manifest(manifest, store=store)
    stored = from_canonical_bytes(store.get_bytes(ref.artifact_id))

    assert str(ref.artifact_id).startswith("sha256:")
    assert stored == manifest


def test_replay_manifest_includes_runtime_ledgers_and_registry_versions() -> None:
    manifest = build_replay_manifest(
        request_payload={"question": "Can this serious run be replayed?"},
        runtime_event_log={
            "runtime_event_log_ref": _sha("e"),
            "event_count": 7,
        },
        authority_envelopes=[
            {
                "evidence_id": "evidence-runtime-replay",
                "artifact_kind": "drift_explanation",
                "cas_ref": _sha("f"),
            }
        ],
        schema_compatibility_decisions={
            "scorecard": {"decision": "compatible", "registry_version": "2026.05"}
        },
        effective_mode_ledger={
            "mode_ledger_id": "mode-ledger-1",
            "effective_execution_profile": "production",
        },
        degradation_ledger={
            "degradation_ledger_ref": _sha("d"),
            "blocking_record_count": 0,
        },
        semantic_binding_ledger={
            "semantic_binding_ledger_ref": _sha("c"),
            "status": "pass",
        },
        prompt_tool_parser_ledger={
            "prompt_tool_ledger_ref": _sha("p"),
            "status": "pass",
        },
        assurance_case={
            "assurance_case_ref": _sha("q"),
            "claim": {"status": "supported"},
        },
        registry_refs={
            "invariant_registry": {"version": "2026.05", "ref": _sha("i")},
            "schema_compatibility_registry": {"version": "2026.05", "ref": _sha("s")},
            "source_truth_lattice": {"version": "2026.05", "ref": _sha("t")},
            "mode_fallback_policy": {"version": "2026.05", "ref": _sha("m")},
            "event_type_registry": {"version": "2026.05", "ref": _sha("v")},
        },
    )

    assert manifest["runtime_event_log"]["runtime_event_log_ref"] == _sha("e")
    assert manifest["authority_envelopes"][0]["cas_ref"] == _sha("f")
    assert manifest["schema_compatibility_decisions"]["scorecard"]["decision"] == (
        "compatible"
    )
    assert manifest["effective_mode_ledger"]["effective_execution_profile"] == (
        "production"
    )
    assert manifest["degradation_ledger"]["degradation_ledger_ref"] == _sha("d")
    assert manifest["semantic_binding_ledger"]["status"] == "pass"
    assert manifest["prompt_tool_parser_ledger"]["status"] == "pass"
    assert manifest["assurance_case"]["claim"]["status"] == "supported"
    assert manifest["registry_refs"]["invariant_registry"]["ref"] == _sha("i")


def test_identical_deterministic_refs_match_execution_and_quality_summaries(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest = _manifest()
    explanation = explain_replay_drift(
        baseline_manifest=manifest,
        replay_manifest=dict(manifest),
    )
    ref = persist_drift_explanation(explanation, store=store)

    assert explanation["schema_version"] == "policyos.drift_explanation.v1"
    assert explanation["status"] == "match"
    assert explanation["production_readiness"] == "pass"
    assert explanation["execution_summary_match"] is True
    assert explanation["quality_summary_match"] is True
    assert explanation["differences"] == []
    assert from_canonical_bytes(store.get_bytes(ref.artifact_id)) == explanation


@pytest.mark.parametrize(
    ("mutator", "expected_path", "expected_source"),
    [
        (
            lambda replay: replay["norm_refs"].__setitem__(
                "ua_credit_normpack", _sha("a")
            ),
            "$.norm_refs.ua_credit_normpack",
            "norm",
        ),
        (
            lambda replay: replay["data_refs"].__setitem__(
                "production_snapshot", _sha("b")
            ),
            "$.data_refs.production_snapshot",
            "data",
        ),
        (
            lambda replay: replay["prompt_template_fingerprints"].__setitem__(
                "formalizer", _sha("c")
            ),
            "$.prompt_template_fingerprints.formalizer",
            "prompt",
        ),
        (
            lambda replay: replay["provider_model_metadata"].__setitem__(
                "provider", "new-provider"
            ),
            "$.provider_model_metadata.provider",
            "provider",
        ),
        (
            lambda replay: replay["provider_model_metadata"].__setitem__(
                "model_fingerprint", _sha("d")
            ),
            "$.provider_model_metadata.model_fingerprint",
            "model",
        ),
    ],
)
def test_replay_explains_substituted_norms_data_prompts_and_provider_variants(
    mutator,
    expected_path: str,
    expected_source: str,
) -> None:
    baseline = _manifest()
    replay = _manifest()
    mutator(replay)

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert explanation["status"] == "unexplained_drift"
    assert explanation["production_readiness"] == "fail"
    assert len(explanation["differences"]) == 1
    difference = explanation["differences"][0]
    assert difference["path"] == expected_path
    assert difference["drift_source"] == expected_source
    assert difference["impact"] == "low"
    assert difference["status"] == "unexplained"
    assert difference["baseline_fingerprint"].startswith("sha256:")
    assert difference["replay_fingerprint"].startswith("sha256:")
    assert difference["baseline_fingerprint"] != difference["replay_fingerprint"]


@pytest.mark.parametrize(
    "registry_key",
    [
        "invariant_registry",
        "schema_compatibility_registry",
        "source_truth_lattice",
        "mode_fallback_policy",
        "event_type_registry",
    ],
)
def test_replay_explains_substituted_runtime_registry_versions(registry_key: str) -> None:
    baseline = build_replay_manifest(
        request_payload={"question": "Baseline"},
        registry_refs={registry_key: {"version": "2026.05", "ref": _sha("1")}},
    )
    replay = build_replay_manifest(
        request_payload={"question": "Baseline"},
        registry_refs={registry_key: {"version": "2026.06", "ref": _sha("2")}},
    )

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert explanation["status"] == "unexplained_drift"
    assert explanation["production_readiness"] == "fail"
    assert explanation["summary"]["drift_sources"] == ["registry"]
    assert {
        difference["path"] for difference in explanation["differences"]
    } == {
        f"$.registry_refs.{registry_key}.ref",
        f"$.registry_refs.{registry_key}.version",
    }
    assert {difference["impact"] for difference in explanation["differences"]} == {
        "high"
    }


def test_accepted_difference_requires_typed_source_and_bounded_impact() -> None:
    baseline = _manifest()
    replay = _manifest()
    replay["data_refs"] = {"production_snapshot": _sha("a")}

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
        accepted_differences=[
            {
                "path": "$.data_refs.production_snapshot",
                "drift_source": "data",
                "impact": "low",
                "reason": "Approved refresh of the production data snapshot.",
            }
        ],
    )

    assert explanation["status"] == "accepted_drift"
    assert explanation["production_readiness"] == "pass"
    assert explanation["execution_summary_match"] is True
    assert explanation["quality_summary_match"] is True
    assert explanation["summary"]["accepted_difference_count"] == 1
    assert explanation["differences"] == [
        {
            "path": "$.data_refs.production_snapshot",
            "drift_source": "data",
            "impact": "low",
            "status": "accepted",
            "baseline_fingerprint": _sha("5"),
            "replay_fingerprint": _sha("a"),
            "reason": "Approved refresh of the production data snapshot.",
        }
    ]


def test_accepted_high_impact_registry_drift_is_typed_non_ready() -> None:
    baseline = build_replay_manifest(
        request_payload={"question": "Baseline"},
        registry_refs={"invariant_registry": {"version": "2026.05", "ref": _sha("1")}},
    )
    replay = build_replay_manifest(
        request_payload={"question": "Baseline"},
        registry_refs={"invariant_registry": {"version": "2026.06", "ref": _sha("2")}},
    )

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
        accepted_differences=[
            {
                "path_prefix": "$.registry_refs.invariant_registry",
                "drift_source": "registry",
                "impact": "high",
                "reason": "Operator accepted a registry refresh.",
            }
        ],
    )

    assert explanation["status"] == "accepted_drift_non_ready"
    assert explanation["production_readiness"] == "fail"
    assert explanation["summary"]["max_impact"] == "high"
    assert explanation["blocking_failure"]["code"] == "authority_replay_drift_unbounded"
    assert {
        difference["status"] for difference in explanation["differences"]
    } == {"accepted_non_ready"}


def test_unexplained_drift_fails_production_readiness() -> None:
    baseline = _manifest()
    replay = _manifest()
    replay["quality_summary"] = {
        "quality_status": "fail",
        "overall_score": 0.4,
        "blocking_quality_failures": [{"gate": "fabric_retrieval_trace_present"}],
    }

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert explanation["status"] == "unexplained_drift"
    assert explanation["production_readiness"] == "fail"
    assert explanation["quality_summary_match"] is False
    assert explanation["summary"]["unexplained_difference_count"] == 3
    assert {difference["status"] for difference in explanation["differences"]} == {
        "unexplained"
    }
    assert {
        difference["drift_source"] for difference in explanation["differences"]
    } == {"nondeterminism"}
