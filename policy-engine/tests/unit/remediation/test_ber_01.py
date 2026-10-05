"""BER-01 characterization and RED tests for BERL explanation profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from polisyos.berl.adapters.protocol import (
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UnavailableAdapter,
)
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from polisyos.berl.adapters.shap_tree import TreeSHAPAdapter
from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
from polisyos.berl.contracts.schema import (
    generated_explanation_bundle_schema,
    validate_persisted_explanation_bundle,
    write_explanation_bundle_schema,
)
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
PERSISTED_SCHEMA_PATH = (
    POLICY_ENGINE_ROOT
    / "src"
    / "polisyos"
    / "berl"
    / "contracts"
    / "explanation_bundle.schema.json"
)


def _persisted_validator() -> Draft202012Validator:
    schema = json.loads(PERSISTED_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _full_payload(*, schema_version: str = "1.0.0") -> dict[str, Any]:
    """Return one complete payload suitable for both schema profiles."""

    return {
        "schema_version": schema_version,
        "bundle_id": "bundle-ber-01",
        "created_at": "2026-09-21T00:00:00Z",
        "faithfulness_claim": "bounded",
        "display_policy": "limited",
        "model": {
            "model_id": "fake-model",
            "model_hash": "sha256:fake-model",
            "model_class": "in-memory-two-feature",
            "training_data_hash": "sha256:training",
            "calibration_ref": "calibration://fixture",
        },
        "prediction": {
            "prediction_id": "prediction-ber-01",
            "row_id": "row-1",
            "output_name": "score",
            "output_scale": "score",
            "raw_score": 8.0,
            "display_score": 0.8,
            "decision_threshold": 0.5,
        },
        "feature_context": {
            "feature_values_ref": "inline://features/row-1",
            "feature_schema_version": "features-1",
            "constraints_ref": "constraints://none",
            "missingness_policy": "model_native",
        },
        "assumptions": {
            "explanation_question": "local_prediction_drivers",
            "perturbation_distribution": {
                "name": "empirical",
                "radius": 0.5,
                "categorical_policy": "preserve",
                "continuous_policy": "uniform",
                "support_constraints": "none",
            },
            "feature_dependence_policy": {
                "primary": "marginal",
                "alternatives_tested": ["conditional"],
                "causal_claim_made": False,
            },
            "background_data": {
                "dataset_ref": "inline://background",
                "n": 2,
                "sampling_policy": "fixture",
            },
        },
        "redundancy": {"clusters": []},
        "methods": [
            {
                "method_id": "kernel_shap",
                "library": "polisyos",
                "library_version": "test",
                "scope": "local",
                "params": {"background_n": 2},
                "assumptions": {"causal_claim_made": False},
                "attributions": [
                    {"feature": "x1", "value": 2.0},
                    {"feature": "x2", "value": 6.0},
                ],
                "group_attributions": [],
                "infidelity": {
                    "loss": "squared_reconstruction_error",
                    "point_estimate": 0.0,
                    "upper_bound": 0.0,
                    "confidence": 0.95,
                    "n_eval_perturbations": 1,
                    "residual_cap": 1.0,
                    "bound_type": "empirical",
                    "evaluation_split": "heldout",
                },
                "stability": {
                    "bootstrap_runs": 0,
                    "seed_policy": "fixed",
                    "max_rank_shift_top5": 0,
                },
            }
        ],
        "disagreement": {
            "methods_compared": ["kernel_shap"],
            "top_k": 5,
            "top_k_jaccard_median": 1.0,
            "kendall_tau_median": 1.0,
            "magnitude_l1_median": 0.0,
            "sign_conflict_features": [],
            "redundancy_adjusted_conflicts": [],
            "uncertainty_summary": "none",
            "flags": [],
        },
        "validity": {
            "support_check": {
                "ood_rate_eval_perturbations": 0.0,
                "constraint_violation_rate": 0.0,
            },
            "use_restrictions": [],
        },
        "audit": {
            "code_version": "ber-01-test",
            "random_seeds": [7],
            "artifact_refs": ["artifact://ber-01"],
        },
    }


def _minimal_input_payload() -> dict[str, Any]:
    """Return the construction-input form with supported defaults omitted."""

    return {
        "bundle_id": "bundle-ber-01-input",
        "created_at": "2026-09-21T00:00:00Z",
        "model": {
            "model_id": "fake-model",
            "model_hash": "sha256:fake-model",
            "model_class": "in-memory-two-feature",
        },
        "prediction": {
            "prediction_id": "prediction-input",
            "row_id": "row-1",
            "output_name": "score",
            "output_scale": "score",
            "raw_score": 8.0,
        },
        "feature_context": {
            "feature_values_ref": "inline://features/row-1",
            "feature_schema_version": "features-1",
        },
        "assumptions": {
            "perturbation_distribution": {"name": "empirical"},
            "feature_dependence_policy": {"primary": "marginal"},
        },
        "audit": {"code_version": "ber-01-test"},
    }


def _context(
    *,
    feature_names: tuple[str, ...] = ("x1", "x2"),
    background_rows: list[dict[str, float]] | None = None,
    max_exact_features: int | None = None,
) -> ExplanationContext:
    params: dict[str, object] = {}
    if background_rows is not None:
        params["background_rows"] = background_rows
    if max_exact_features is not None:
        params["max_exact_shap_features"] = max_exact_features
    return ExplanationContext(
        feature_names=feature_names,
        output_scale="score",
        perturbation_distribution="empirical",
        feature_dependence_policy="marginal",
        confidence=0.95,
        random_seed=7,
        params=params,
    )


def _linear_model(*, x1_weight: float = 2.0, x2_weight: float = 3.0):
    def predict(features: dict[str, float]) -> float:
        return x1_weight * features["x1"] + x2_weight * features["x2"]

    return predict


def _request(
    *,
    methods: tuple[str, ...],
    feature_dependence_policy: str = "conditional_observational",
    background_rows: tuple[dict[str, float], ...] = (
        {"x1": 0.0, "x2": 0.0},
        {"x1": 1.0, "x2": 1.0},
    ),
    adapter_params: dict[str, object] | None = None,
) -> ExplanationRequest:
    return ExplanationRequest(
        x={"x1": 1.0, "x2": 2.0},
        feature_names=("x1", "x2"),
        methods=methods,
        feature_dependence_policy=feature_dependence_policy,
        model_id="fake-model",
        model_hash="sha256:fake-model",
        model_class="in-memory-two-feature",
        prediction_id="prediction-ber-01",
        row_id="row-1",
        background_rows=background_rows,
        n_eval_perturbations=1,
        random_seed=7,
        include_redundancy=False,
        adapter_params=adapter_params or {"max_exact_shap_features": 2},
    )


@dataclass
class _CountingModel:
    """Two-feature in-memory model that records every real invocation."""

    x1_weight: float = 2.0
    x2_weight: float = 3.0
    calls: list[dict[str, float]] = field(default_factory=list)

    def __call__(self, features: dict[str, float]) -> float:
        row = {name: float(value) for name, value in features.items()}
        self.calls.append(row)
        return self.x1_weight * row["x1"] + self.x2_weight * row["x2"]


@dataclass(frozen=True, slots=True)
class _IdentityMismatchAdapter(KernelSHAPAdapter):
    """Run the real kernel while returning a forged execution identity."""

    report_identity_in_params: bool = False

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        raw = super().explain(model, x, context)
        params = dict(raw.params)
        params["effective_method_id"] = (
            "kernel_shap" if self.report_identity_in_params else "tree_shap"
        )
        return replace(
            raw,
            effective_method_id=("tree_shap" if self.report_identity_in_params else "kernel_shap"),
            params=params,
        )


def test_full_bundle_is_accepted_by_both_input_and_persisted_profiles() -> None:
    payload = _full_payload()

    bundle = ExplanationBundle.model_validate(payload)
    _persisted_validator().validate(bundle.model_dump(mode="json"))


def test_orchestrator_bundle_round_trips_as_persisted_artifact(tmp_path: Path) -> None:
    bundle = ExplanationOrchestrator().explain(
        _CountingModel(),
        _request(methods=("kernel_shap",)),
    )
    artifact_path = tmp_path / "explanation-bundle.json"
    artifact_path.write_text(bundle.model_dump_json() + "\n", encoding="utf-8")
    serialized = artifact_path.read_text(encoding="utf-8")

    _persisted_validator().validate(json.loads(serialized))
    loaded = ExplanationBundle.model_validate_json(serialized)

    assert loaded == bundle
    assert validate_persisted_explanation_bundle(json.loads(serialized)) == bundle
    assert loaded.methods[0].requested_method_id == "kernel_shap"
    assert loaded.methods[0].effective_method_id == "kernel_shap"


def test_construction_input_profile_keeps_supported_defaults_explicitly_distinct() -> None:
    payload = _minimal_input_payload()

    bundle = ExplanationBundle.model_validate(payload)

    assert bundle.schema_version == "1.0.0"
    assert bundle.methods == []
    with pytest.raises(JsonSchemaValidationError):
        _persisted_validator().validate(payload)


def test_generated_schema_matches_persisted_schema_content() -> None:
    persisted = json.loads(PERSISTED_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert generated_explanation_bundle_schema() == persisted


def test_schema_writer_reproduces_persisted_schema_bytes(tmp_path: Path) -> None:
    generated_path = tmp_path / "explanation_bundle.schema.json"

    write_explanation_bundle_schema(generated_path)

    assert generated_path.read_bytes() == PERSISTED_SCHEMA_PATH.read_bytes()


def test_nested_empty_objects_are_rejected_by_both_profiles() -> None:
    payload = _full_payload()
    payload["model"] = {}

    with pytest.raises(PydanticValidationError):
        ExplanationBundle.model_validate(payload)
    with pytest.raises(JsonSchemaValidationError):
        _persisted_validator().validate(payload)


def test_nested_extra_fields_are_rejected_by_both_profiles() -> None:
    payload = _full_payload()
    payload["model"]["unclaimed"] = "must be rejected"

    with pytest.raises(PydanticValidationError):
        ExplanationBundle.model_validate(payload)
    with pytest.raises(JsonSchemaValidationError):
        _persisted_validator().validate(payload)


def test_unknown_version_is_rejected_by_persisted_profile_only() -> None:
    payload = _full_payload(schema_version="9.9.9")

    bundle = ExplanationBundle.model_validate(payload)

    assert bundle.schema_version == "9.9.9"
    with pytest.raises(JsonSchemaValidationError):
        _persisted_validator().validate(payload)


def test_effective_request_changes_keep_model_and_background_distinct() -> None:
    adapter = KernelSHAPAdapter()
    x = {"x1": 1.0, "x2": 2.0}
    zero_background = [{"x1": 0.0, "x2": 0.0}]
    unit_background = [{"x1": 1.0, "x2": 1.0}]

    zero_result = adapter.explain(
        _linear_model(),
        x,
        _context(background_rows=zero_background, max_exact_features=2),
    )
    unit_result = adapter.explain(
        _linear_model(),
        x,
        _context(background_rows=unit_background, max_exact_features=2),
    )
    changed_model_result = adapter.explain(
        _linear_model(x1_weight=4.0),
        x,
        _context(background_rows=zero_background, max_exact_features=2),
    )

    assert zero_result.attributions != unit_result.attributions
    assert zero_result.attributions != changed_model_result.attributions


def test_orchestrator_cache_key_includes_model_background_and_adapter_parameters() -> None:
    orchestrator = ExplanationOrchestrator()
    base_request = _request(methods=("kernel_shap",))
    base_model = _CountingModel()
    base_bundle = orchestrator.explain(base_model, base_request)
    base_method = base_bundle.methods[0]
    base_attributions = base_method.attributions
    base_baseline_values = base_method.params["baseline_values"]

    changed_model_bundle = orchestrator.explain(
        _CountingModel(x1_weight=4.0),
        replace(
            base_request,
            model_id="fake-model-changed",
            model_hash="sha256:fake-model-changed",
        ),
    )
    changed_model_method = changed_model_bundle.methods[0]

    changed_background_request = replace(
        base_request,
        background_rows=(
            {"x1": 10.0, "x2": 10.0},
            {"x1": 11.0, "x2": 11.0},
        ),
    )
    changed_background_bundle = orchestrator.explain(base_model, changed_background_request)
    changed_background_method = changed_background_bundle.methods[0]

    changed_parameter_bundle = orchestrator.explain(
        base_model,
        replace(
            base_request,
            adapter_params={"max_exact_shap_features": 1},
        ),
    )
    changed_parameter_method = changed_parameter_bundle.methods[0]

    assert changed_model_bundle.model.model_hash == "sha256:fake-model-changed"
    assert changed_model_method.attributions != base_attributions
    assert changed_background_method.params["baseline_values"] != base_baseline_values
    assert changed_background_method.attributions != base_attributions
    assert changed_parameter_method.scope == "diagnostic"
    assert "exponential" in str(changed_parameter_method.params["diagnostic"])


def test_kernel_shap_preserves_feature_count_and_empty_background_guards() -> None:
    adapter = KernelSHAPAdapter()
    with pytest.raises(ValueError, match="exponential"):
        adapter.explain(
            _linear_model(),
            {"x1": 1.0, "x2": 2.0, "x3": 3.0},
            _context(
                feature_names=("x1", "x2", "x3"),
                background_rows=[{"x1": 0.0, "x2": 0.0, "x3": 0.0}],
                max_exact_features=2,
            ),
        )

    with pytest.raises(ValueError, match="must not be empty"):
        adapter.explain(
            _linear_model(),
            {"x1": 1.0, "x2": 2.0},
            _context(background_rows=[], max_exact_features=2),
        )


def test_kernel_shap_does_not_mutate_input_or_persisted_background_rows() -> None:
    adapter = KernelSHAPAdapter()
    x = {"x1": 1.0, "x2": 2.0}
    background_rows = [{"x1": 0.0, "x2": 0.0}, {"x1": 1.0, "x2": 1.0}]
    original_x = deepcopy(x)
    original_background_rows = deepcopy(background_rows)

    adapter.explain(
        _linear_model(),
        x,
        _context(background_rows=background_rows, max_exact_features=2),
    )

    assert x == original_x
    assert background_rows == original_background_rows


def test_aliases_preserve_requested_ids_and_share_effective_identity() -> None:
    model = _CountingModel()
    request = _request(
        methods=("kernel_shap", "kernel_shap_marginal"),
        feature_dependence_policy="marginal",
    )

    bundle = ExplanationOrchestrator().explain(model, request)
    by_requested_id = {method.method_id: method.model_dump() for method in bundle.methods}

    assert by_requested_id["kernel_shap"]["requested_method_id"] == "kernel_shap"
    assert by_requested_id["kernel_shap_marginal"]["requested_method_id"] == "kernel_shap_marginal"
    assert by_requested_id["kernel_shap"]["effective_method_id"] == "kernel_shap"
    assert by_requested_id["kernel_shap_marginal"]["effective_method_id"] == "kernel_shap"


def test_aliases_share_one_raw_calculation_and_are_not_disagreement_methods() -> None:
    one_alias_model = _CountingModel()
    one_alias_bundle = ExplanationOrchestrator().explain(
        one_alias_model,
        _request(methods=("kernel_shap",), feature_dependence_policy="marginal"),
    )

    two_alias_model = _CountingModel()
    two_alias_bundle = ExplanationOrchestrator().explain(
        two_alias_model,
        _request(
            methods=("kernel_shap", "kernel_shap_marginal"),
            feature_dependence_policy="marginal",
        ),
    )

    assert len(two_alias_model.calls) == len(one_alias_model.calls)
    assert two_alias_bundle.disagreement is None
    assert one_alias_bundle.methods[0].method_id == "kernel_shap"


def test_alias_dedup_preserves_requested_claim_confidence_and_validation_posture() -> None:
    one_claim_request = replace(
        _request(methods=("kernel_shap",), feature_dependence_policy="marginal"),
        n_eval_perturbations=5,
        residual_cap=0.019,
    )
    two_claim_request = replace(
        _request(
            methods=("kernel_shap", "kernel_shap_marginal"),
            feature_dependence_policy="marginal",
        ),
        n_eval_perturbations=5,
        residual_cap=0.019,
    )

    one_claim_bundle = ExplanationOrchestrator().explain(
        _CountingModel(),
        one_claim_request,
    )
    two_claim_bundle = ExplanationOrchestrator().explain(
        _CountingModel(),
        two_claim_request,
    )

    base_confidence = 0.95
    one_claim_confidence = base_confidence
    two_claim_confidence = 1.0 - ((1.0 - base_confidence) / 2)
    one_claim_method = one_claim_bundle.methods[0]

    assert one_claim_request.confidence == base_confidence
    assert two_claim_request.confidence == base_confidence
    assert one_claim_method.infidelity is not None
    assert one_claim_method.infidelity.confidence == pytest.approx(one_claim_confidence)
    assert all(method.infidelity is not None for method in two_claim_bundle.methods)
    assert all(
        method.infidelity is not None
        and method.infidelity.confidence == pytest.approx(two_claim_confidence)
        for method in two_claim_bundle.methods
    )
    assert one_claim_bundle.faithfulness_claim == "bounded"
    assert one_claim_bundle.display_policy == "analyst_display"
    assert two_claim_bundle.faithfulness_claim == "unbounded"
    assert two_claim_bundle.display_policy == "diagnostic_only"


def test_unsupported_backend_keeps_requested_id_and_existing_diagnostic() -> None:
    unavailable = UnavailableAdapter(
        method_id="kernel_shap_conditional",
        diagnostic="conditional backend unavailable",
    )

    bundle = ExplanationOrchestrator(adapters={"kernel_shap_conditional": unavailable}).explain(
        _CountingModel(),
        _request(methods=("kernel_shap_conditional",)),
    )

    method = bundle.methods[0]
    assert method.method_id == "kernel_shap_conditional"
    assert method.scope == "diagnostic"
    assert method.params["diagnostic"] == "conditional backend unavailable"


def test_conditional_kernel_request_is_not_registered_as_marginal_kernel() -> None:
    bundle = ExplanationOrchestrator().explain(
        _CountingModel(),
        _request(methods=("kernel_shap_conditional",)),
    )

    method = bundle.methods[0]

    assert method.method_id == "kernel_shap_conditional"
    assert method.requested_method_id == "kernel_shap_conditional"
    assert method.scope == "diagnostic"
    assert method.effective_method_id == "kernel_shap_conditional"
    assert method.attributions == []
    assert "conditional" in str(method.params["diagnostic"]).lower()


@pytest.mark.parametrize("report_identity_in_params", [False, True])
def test_orchestrator_rejects_adapter_reported_identity_not_bound_to_registry(
    report_identity_in_params: bool,
) -> None:
    adapter = _IdentityMismatchAdapter(
        method_id="forged_method",
        report_identity_in_params=report_identity_in_params,
    )
    bundle = ExplanationOrchestrator(adapters={"forged_method": adapter}).explain(
        _CountingModel(),
        _request(methods=("forged_method",)),
    )

    method = bundle.methods[0]

    assert method.method_id == "forged_method"
    assert method.requested_method_id == "forged_method"
    assert method.scope == "diagnostic"
    assert method.effective_method_id == "kernel_shap"
    assert method.attributions == []
    assert "identity" in str(method.params["diagnostic"]).lower()


def test_tree_shap_fallback_is_explicit_and_does_not_claim_tree_exactness() -> None:
    raw = TreeSHAPAdapter().explain(
        _linear_model(),
        {"x1": 1.0, "x2": 2.0},
        _context(
            background_rows=[{"x1": 0.0, "x2": 0.0}],
            max_exact_features=2,
        ),
    )

    assert raw.params.get("requested_method_id") == "tree_shap"
    assert raw.params.get("effective_method_id") == "kernel_shap"
    assert raw.params.get("fallback") is True
    assert "empirical" in str(raw.params.get("fallback_reason", "")).lower()
    assert raw.assumptions["causal_claim_made"] is False
