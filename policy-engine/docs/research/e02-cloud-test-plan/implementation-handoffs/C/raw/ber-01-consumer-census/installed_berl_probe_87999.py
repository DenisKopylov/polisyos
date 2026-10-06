from __future__ import annotations

import copy
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any, NoReturn

from polisyos.core.artifacts import FileSystemCAS, ProducerInfo, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
import polisyos
import polisyos.berl
import polisyos.runtime.quality.explanation_reliability as reliability

SCRATCH = pathlib.Path(__file__).resolve().parent
CAS_ROOT = SCRATCH / "cas-runtime-87999"
SITE = next(pathlib.Path(item).resolve() for item in sys.path if item.endswith("site-packages"))


def origin(module: object) -> str | None:
    value = getattr(module, "__file__", None)
    return str(pathlib.Path(value).resolve()) if value else None


def in_site(path: str | None) -> bool:
    return bool(path) and pathlib.Path(path).resolve().is_relative_to(SITE)


modules = {
    "polisyos": origin(polisyos),
    "polisyos.berl": origin(polisyos.berl),
    "polisyos.runtime.quality.explanation_reliability": origin(reliability),
    "polisyos.core.artifacts": origin(sys.modules["polisyos.core.artifacts"]),
    "polisyos.core.canon": origin(sys.modules["polisyos.core.canon"]),
}
assert all(in_site(path) for path in modules.values()), modules
assert importlib.util.find_spec("pytest") is None, "base-only runtime unexpectedly contains test dependency"
wheel = metadata.distribution("policy-engine")
assert wheel.version == "0.1.0"

sha = lambda char: "sha256:" + char * 64


def _bundle(*, schema_version: str, upper_bound: float = 0.03) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "bundle_id": f"berl-bundle-{schema_version}",
        "created_at": datetime(2026, 5, 18, tzinfo=UTC).isoformat(),
        "faithfulness_claim": "bounded",
        "display_policy": "limited",
        "model": {
            "model_id": "policy_model",
            "model_hash": sha("m"),
            "model_class": "gradient_boosted_trees",
            "training_data_hash": sha("d"),
        },
        "prediction": {
            "prediction_id": "prediction-1",
            "row_id": "synthetic-case-only",
            "output_name": "claim_acceptance",
            "output_scale": "probability",
            "raw_score": 0.72,
            "display_score": 0.72,
            "decision_threshold": 0.65,
        },
        "feature_context": {
            "feature_values_ref": sha("f"),
            "feature_schema_version": "2026-05",
            "constraints_ref": sha("c"),
        },
        "assumptions": {
            "perturbation_distribution": {
                "name": "conditional_empirical_local",
                "radius": 0.2,
                "categorical_policy": "observed_support_only",
                "continuous_policy": "local_empirical_resampling",
                "support_constraints": sha("c"),
            },
            "feature_dependence_policy": {
                "primary": "marginal_interventional",
                "alternatives_tested": ["conditional_observational"],
                "causal_claim_made": False,
            },
            "background_data": {
                "dataset_ref": sha("b"),
                "n": 120,
                "sampling_policy": "fixed_fixture_sample",
            },
        },
        "redundancy": {"clusters": []},
        "methods": [
            {
                "method_id": "kernel_shap_marginal",
                "library": "berl-fixture",
                "library_version": "1.0.0",
                "params": {"coalition_samples": 64},
                "assumptions": {"feature_removal": "marginal_interventional"},
                "attributions": [{"feature": "employment_rate", "value": 0.18}],
                "infidelity": {
                    "point_estimate": 0.01,
                    "upper_bound": upper_bound,
                    "confidence": 0.95,
                    "n_eval_perturbations": 64,
                    "residual_cap": 1.0,
                    "bound_type": "empirical_bernstein_heldout",
                    "evaluation_split": "heldout",
                },
            }
        ],
        "disagreement": {
            "methods_compared": ["kernel_shap_marginal"],
            "top_k": 1,
            "top_k_jaccard_median": 1.0,
            "kendall_tau_median": 1.0,
            "sign_conflict_features": [],
            "flags": [],
        },
        "validity": {
            "support_check": {
                "ood_rate_eval_perturbations": 0.01,
                "constraint_violation_rate": 0.0,
            },
            "use_restrictions": ["Local to declared perturbation support."],
        },
        "audit": {
            "code_version": "berl-fixture@sha256:code",
            "random_seeds": [7],
            "artifact_refs": [sha("r")],
        },
    }


class EchoVerifier:
    calls = 0

    def verify(self, bundle: object, method: object, evidence: object) -> NoReturn:
        del bundle, method, evidence
        self.calls += 1
        raise AssertionError("unadmitted conditional verifier must not be invoked")


cas = FileSystemCAS(CAS_ROOT)
canon = CanonSpec(forbid_floats=False)
producer = ProducerInfo(component="installed-public-builder-probe", version="1.0.0")


def persist_bundle(payload: dict[str, Any]) -> tuple[Any, str]:
    ref = cas.put_json(
        payload,
        PutOptions(
            kind="scientist.explanation_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.berl.explanation_bundle", version=payload["schema_version"]),
            producer=producer,
        ),
        canon_spec=canon,
    )
    raw = cas.get_bytes(ref)
    readback = from_canonical_bytes(raw)
    assert isinstance(readback, dict)
    assert readback == payload
    return ref, hashlib.sha256(raw).hexdigest()


def exercise(label: str, payload: dict[str, Any], *, verifier: EchoVerifier | None = None,
             expected_violation: str | None = None) -> dict[str, Any]:
    bundle_ref, bundle_sha = persist_bundle(payload)
    record = reliability.build_berl_warrant_reliability_record(
        reliability_id=f"reliability-{label}",
        claim_id="claim-synthetic-only",
        explanation_bundle_ref=str(bundle_ref.artifact_id),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.1},
        explanation_bundle=payload,
        evidence_ref=f"synthetic-evidence://{label}",
        warrant_id=f"warrant-{label}",
        conditional_evidence_verifier=verifier,
    )
    # The accepted behavior under audit is lossless retention by the public builder.
    assert record["explanation_bundle"] == payload
    assert record["explanation_bundle"]["created_at"] == payload["created_at"]
    raw_record = cas.put_json(
        record,
        PutOptions(kind="runtime.berl_warrant_reliability", media_type="application/json"),
        canon_spec=canon,
    )
    stored_bytes = cas.get_bytes(raw_record)
    stored_record = from_canonical_bytes(stored_bytes)
    assert isinstance(stored_record, dict)
    assert stored_record == record
    assert stored_record["explanation_bundle"] == payload
    result = reliability.evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [stored_record]},
        {
            "warrant_id": f"warrant-{label}",
            "claim_id": "claim-synthetic-only",
            "berl_reliability_refs": [f"reliability-{label}"],
        },
        claim_id="claim-synthetic-only",
        conditional_evidence_verifier=verifier,
    )
    assert len(result.records) == 1, result
    normalized = result.records[0]
    decision = normalized["threshold_decision"]
    violations = list(decision.get("violations", []))
    if expected_violation is None:
        assert not result.issues, [issue.message for issue in result.issues]
        assert decision["status"] == "pass", decision
        assert normalized["explanation_bundle"]["schema_version"] == payload["schema_version"]
        assert not violations, violations
    else:
        assert decision["status"] == "fail", decision
        assert expected_violation in violations, violations
    return {
        "bundle_artifact_id": str(bundle_ref.artifact_id),
        "bundle_payload_sha256": bundle_sha,
        "builder_record_artifact_id": str(raw_record.artifact_id),
        "builder_record_sha256": hashlib.sha256(stored_bytes).hexdigest(),
        "builder_preserved_full_bundle_before_cas": record["explanation_bundle"] == payload,
        "cas_readback_preserved_full_bundle": stored_record["explanation_bundle"] == payload,
        "consumer_status": decision["status"],
        "consumer_violations": violations,
        "consumer_issue_codes": [issue.code for issue in result.issues],
        "consumer_issue_messages": [issue.message for issue in result.issues],
        "consumer_schema_version": normalized.get("explanation_bundle", {}).get("schema_version"),
    }


profiles: dict[str, Any] = {}
for version in ("1.1.0", "1.0.0"):
    payload = _bundle(schema_version=version)
    profiles[version] = exercise(f"profile-{version}", payload)

conditional = _bundle(schema_version="1.1.0")
conditional["assumptions"]["feature_dependence_policy"]["primary"] = "conditional_observational"
method = conditional["methods"][0]
method["method_id"] = "kernel_shap_conditional"
method["conditional_evidence"] = {
    "profile_id": "gaussian_linear_exact",
    "authority_purpose": "prediction_attribution",
    "law_ref": "law://unresolved/not-present",
    "law_content_digest": "sha256:unresolved-law-bytes",
    "model_hash": conditional["model"]["model_hash"],
    "model_profile_ref": "model-profile://unresolved/not-present",
    "model_profile_digest": "sha256:unresolved-model-bytes",
    "model_verifier_ref": "verifier://unresolved/model",
    "population_ref": "population://fixture",
    "cohort_ref": "cohort://fixture",
    "observation_window_ref": "window://fixture",
    "feature_schema_version": conditional["feature_context"]["feature_schema_version"],
    "model_epoch": "epoch://fixture",
    "feature_order": ["employment_rate"],
    "support_ref": "support://fixture",
    "provenance_ref": "provenance://fixture",
    "verifier_ref": "verifier://unresolved/law",
    "precision_status": "exact",
}
conditional["audit"]["artifact_refs"].append("law://unresolved/not-present")
echo = EchoVerifier()
conditional_result = exercise(
    "conditional-unresolved",
    conditional,
    verifier=echo,
    expected_violation="conditional_law_authority_not_admitted:kernel_shap_conditional",
)
markers_only = copy.deepcopy(conditional)
markers_only["methods"][0].pop("conditional_evidence")
markers_only_result = exercise(
    "conditional-markers-only",
    markers_only,
    verifier=echo,
    expected_violation="conditional_law_evidence_missing:kernel_shap_conditional",
)
assert echo.calls == 0, f"unadmitted conditional verifier was invoked {echo.calls} times"

receipt = {
    "candidate_commit": "87999f69c5f99d69ee2622ef00cd7f4e04d7d572",
    "candidate_tree": "0280403e6837c5b220ac748a7674f4e5830ba0ab",
    "wheel_sha256": "27f15cec628f5b8ab9c1e48dcb9ddf9c6d363ea6e4c413be2a0239832b0a7e2e",
    "sdist_sha256": "222c2a0d724b883c769070a4af093186f753ac7deaf032579e969a1d5eabe549",
    "runtime_environment": {
        "python": sys.version,
        "isolated_flag": sys.flags.isolated,
        "site_packages": str(SITE),
        "pytest_present": importlib.util.find_spec("pytest") is not None,
        "distribution_version": wheel.version,
        "module_origins": modules,
    },
    "installed_builder_cas_consumer_profiles": profiles,
    "conditional_unresolved": conditional_result,
    "conditional_evidence_removed": markers_only_result,
    "echo_verifier_calls": echo.calls,
    "fixture_scope": "Synthetic schema/consumer fixture only; no scientific precision assertion, production model, or external evidence was run or admitted.",
}
receipt_path = SCRATCH / "installed-berl-runtime-87999.json"
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2, sort_keys=True))
