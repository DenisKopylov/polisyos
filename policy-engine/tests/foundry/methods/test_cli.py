from __future__ import annotations

import json
import importlib
import sys
import types

from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot
from polisyos.foundry.methods import cli


def _entry(
    fqn: str,
    *,
    family: str,
    variant: str,
    execution_backend: str = "numpy",
    runnable: bool = True,
    truthfulness_tier: str = "production_method",
    data_modalities: list[str] | None = None,
) -> MethodCatalogEntry:
    namespace_name, version = fqn.split("@", 1)
    namespace, name = namespace_name.rsplit(".", 1)
    data_modalities = data_modalities or ["cross-section"]
    capability_matrix = {
        "kind": "pure",
        "execution_backend": execution_backend,
        "runtime_stack": [execution_backend],
        "determinism_tier": "library_deterministic",
        "truthfulness_tier": truthfulness_tier,
        "backend_available": runnable,
        "runnable": runnable,
        "runtime_posture": {
            "backend": execution_backend,
            "available": runnable,
            "determinism_tier": "library_deterministic",
            "replay_semantics": "Replay must match exactly within the same CPU/library stack; cross-ISA uses tolerance budget.",
            "tolerance_budget": {"semantic_mode": "library_exact_cpu"},
            "fingerprint": "fp123",
        },
        "replay_semantics": "Replay must match exactly within the same CPU/library stack; cross-ISA uses tolerance budget.",
        "tolerance_budget": {"semantic_mode": "library_exact_cpu"},
    }
    return MethodCatalogEntry(
        fqn=fqn,
        namespace=namespace,
        name=name,
        version=version,
        backend=execution_backend,
        execution_backend=execution_backend,
        kind="pure",
        family=family,
        variant=variant,
        fidelity_tier="high",
        data_modalities=data_modalities,
        runtime_stack=[execution_backend],
        determinism_tier="library_deterministic",
        runnable=runnable,
        capability_matrix=capability_matrix,
        truthfulness_tier=truthfulness_tier,
        truthfulness_notes=f"{truthfulness_tier} note",
        effect_semantics={"method_kind": "pure"},
        shape_semantics={"input_arity": 1},
        dependency_semantics={"hard_requires": []},
        typical_min_obs=500,
    )


def _snapshot() -> MethodCatalogSnapshot:
    return MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
                truthfulness_tier="production_method",
            ),
            _entry(
                "causal.treatment_effects.proxy_score@1.0.0",
                family="causal.treatment_effects",
                variant="proxy_score",
                truthfulness_tier="heuristic_baseline",
            ),
            _entry(
                "survey.weighting.horvitz_thompson@1.0.0",
                family="survey.weighting",
                variant="horvitz_thompson",
                data_modalities=["survey"],
            ),
        ],
    )


def test_capabilities_command_emits_runtime_posture_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("polisyos.foundry.methods.cli._load_catalog_snapshot", _snapshot)

    rc = cli.main(["capabilities", "--family", "survey", "--json"])
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert payload["snapshot_id"] == "snapshot"
    row = payload["capability_matrix"][0]
    assert row["family"] == "survey.weighting"
    assert row["runtime_posture"]["backend"] == "numpy"
    assert row["tolerance_budget"]["semantic_mode"] == "library_exact_cpu"


def test_advisor_command_emits_ranked_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("polisyos.foundry.methods.cli._load_catalog_snapshot", _snapshot)

    rc = cli.main(
        [
            "advisor",
            "--family",
            "causal.treatment_effects",
            "--variant",
            "tmle",
            "--required-modality",
            "cross-section",
            "--n-obs",
            "2000",
            "--limit",
            "2",
            "--json",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert [item["fqn"] for item in payload["recommended"]] == [
        "causal.treatment_effects.tmle@1.0.0",
        "causal.treatment_effects.proxy_score@1.0.0",
    ]
    assert payload["capability_matrix"][0]["truthfulness_tier"] == "production_method"
    assert payload["family_summary"][0]["family"] == "causal.treatment_effects"


def test_evidence_command_emits_operator_summary_json(monkeypatch, capsys) -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="evidence-snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
                truthfulness_tier="production_method",
            ),
            _entry(
                "causal.treatment_effects.proxy_score@1.0.0",
                family="causal.treatment_effects",
                variant="proxy_score",
                truthfulness_tier="heuristic_baseline",
                runnable=False,
                execution_backend="bayesian",
            ),
        ],
    )
    monkeypatch.setattr("polisyos.foundry.methods.cli._load_catalog_snapshot", lambda: snapshot)

    rc = cli.main(["evidence", "--family", "causal", "--json"])
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert payload["snapshot_id"] == "evidence-snapshot"
    assert payload["method_count"] == 2
    assert payload["runnable_count"] == 1
    assert payload["blocked_count"] == 1
    assert payload["backend_summary"][0]["value"] in {"bayesian", "numpy"}
    assert any(item["determinism_tier"] == "library_deterministic" for item in payload["replay_contracts"])


def test_release_acceptance_command_emits_report_json(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    manifest_path = tmp_path / "release_manifest.json"
    runtime_bundle_dir = tmp_path / "runtime_bundle"
    method_contract_bundle_dir = tmp_path / "method_contract_bundle"
    store_root = tmp_path / "acceptance_cas"
    calls: dict[str, object] = {}

    class _FakeRunner:
        def __init__(self, store) -> None:
            calls["store_root"] = store.root

        def run(self, **kwargs):
            calls["kwargs"] = kwargs
            return type(
                "_FakeReport",
                (),
                {
                    "passed": True,
                    "model_dump": staticmethod(
                        lambda mode="json": {
                            "passed": True,
                            "manifest_path": str(kwargs["release_manifest_path"]),
                            "release_bundle_root": str(kwargs["release_manifest_path"].parent),
                            "packet_ref": "packet-123",
                            "governance_verdict": "approve",
                            "steps": [
                                {"step_id": "compile_exec_plan", "status": "passed"},
                                {"step_id": "verify_replay_roundtrip", "status": "passed"},
                            ],
                        }
                    ),
                },
            )

    monkeypatch.setitem(
        sys.modules,
        "polisyos.foundry.release_acceptance",
        types.SimpleNamespace(ReleaseAcceptanceRunner=_FakeRunner),
    )

    rc = cli.main(
        [
            "release-acceptance",
            "--manifest-path",
            str(manifest_path),
            "--runtime-bundle-dir",
            str(runtime_bundle_dir),
            "--method-contract-bundle-dir",
            str(method_contract_bundle_dir),
            "--store-root",
            str(store_root),
            "--json",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert payload["passed"] is True
    assert payload["packet_ref"] == "packet-123"
    assert payload["governance_verdict"] == "approve"
    assert [step["step_id"] for step in payload["steps"]] == [
        "compile_exec_plan",
        "verify_replay_roundtrip",
    ]
    assert calls["store_root"] == store_root
    assert calls["kwargs"] == {
        "release_manifest_path": manifest_path,
        "runtime_bundle_dir": runtime_bundle_dir,
        "method_contract_bundle_dir": method_contract_bundle_dir,
    }


def test_release_acceptance_module_imports_without_ukraine_cycle() -> None:
    module = importlib.import_module("polisyos.foundry.release_acceptance")

    assert hasattr(module, "ReleaseAcceptanceRunner")
