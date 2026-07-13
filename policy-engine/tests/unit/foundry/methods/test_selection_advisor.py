from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace

import numpy as np
import pytest
from pydantic import ValidationError

import polisyos.foundry.methods.components.value_evidence as value_evidence
import polisyos.foundry.methods.selection as method_selection
import polisyos.foundry.methods.selection.advisor as advisor_module
from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot
from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.components.consensus import (
    ConsensusTarget,
    EstimandSpec,
    run_cross_method_consensus,
)
from polisyos.foundry.methods.exceptions import FoundryMethodError
from polisyos.foundry.methods.selection import (
    AdvisorValuePolicy,
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodSelectionCriteria,
    MethodSelectionReceipt,
    advise_methods,
    advise_methods_for_analyst,
    build_advisor_execution_context,
    pareto_advise_methods,
    select_value_method_for_problem,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.foundry.methods.selection_history import MethodExecutionRecord, SelectionHistoryStore
from polisyos.ir.analytics.uncertainty import (
    NativeValueEstimandBinding,
    value_uncertainty_output_contract,
)


def test_reachable_value_denominator_fails_closed_on_catalog_error(monkeypatch) -> None:
    ensure_all_methods_registered()

    def _catalog_failure(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(advisor_module, "build_method_catalog_snapshot", _catalog_failure)

    with pytest.raises(FoundryMethodError) as exc_info:
        advisor_module.reachable_value_method_fqns()

    assert exc_info.value.code == "value_method_catalog_unavailable"


class _WaterQualityNativeInterval:
    """Third-domain native interval contract used to prove owner-driven discovery."""

    contract_id = "test.water_quality.native_interval.v1"
    output_contract_declaration = value_uncertainty_output_contract(contract_id)

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> None:
        del estimand, projection_binding
        return None


class _WaterQualityValueMethod:
    """Pack-shaped U2 witness with no engine family or FQN registration."""

    signature = MethodSignature(
        name="water_quality_interval",
        namespace="environment.water_quality",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit("water_quality_interval", "json"),
                    output_contract=_WaterQualityNativeInterval,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
    )


def _entry(
    fqn: str,
    *,
    family: str,
    variant: str,
    execution_backend: str = "numpy",
    runnable: bool = True,
    truthfulness_tier: str = "exact",
    implementation_depth_tier: str = "production_method",
    declared_truthfulness_tier: str | None = None,
    data_modalities: list[str] | None = None,
    advisor_cost: dict[str, object] | None = None,
    advisor_accuracy: dict[str, object] | None = None,
) -> MethodCatalogEntry:
    namespace_name, version = fqn.split("@", 1)
    namespace, name = namespace_name.rsplit(".", 1)
    data_modalities = data_modalities or ["cross-section"]
    capability_matrix = {
        "kind": "pure",
        "execution_backend": execution_backend,
        "runtime_stack": [execution_backend],
        "truthfulness_tier": truthfulness_tier,
        "implementation_depth_tier": implementation_depth_tier,
        "declared_truthfulness_tier": declared_truthfulness_tier,
        "effective_truthfulness_tier": truthfulness_tier,
        "backend_available": runnable,
        "runnable": runnable,
    }
    if advisor_cost is not None:
        capability_matrix["advisor_cost"] = advisor_cost
    if advisor_accuracy is not None:
        capability_matrix["advisor_accuracy"] = advisor_accuracy
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
        runnable=runnable,
        capability_matrix=capability_matrix,
        truthfulness_tier=truthfulness_tier,
        implementation_depth_tier=implementation_depth_tier,
        implementation_depth_notes=f"{implementation_depth_tier} note",
        declared_truthfulness_tier=declared_truthfulness_tier,
        effective_truthfulness_tier=truthfulness_tier,
        truthfulness_status="catalog_only" if declared_truthfulness_tier else "runtime_only",
        truthfulness_notes=f"{truthfulness_tier} note",
        effect_semantics={"method_kind": "pure"},
        shape_semantics={"input_arity": 1},
        dependency_semantics={"hard_requires": []},
        typical_min_obs=500,
    )


def _consensus_estimand(*, time_horizon: str | None = None) -> EstimandSpec:
    return EstimandSpec(
        query_id="q-cross-method",
        estimand_id="ate",
        outcome="outcome",
        treatment_or_exposure="treatment",
        covariates_or_conditioning=("x1", "x2"),
        adjustment_set=("x1", "x2"),
        population="analysis_population",
        time_horizon=time_horizon,
        unit="points",
        target_role="causal",
    )


def _consensus_target(
    result_id: str,
    *,
    family: str,
    point: float,
    se: float = 0.1,
    estimand: EstimandSpec | None = None,
) -> ConsensusTarget:
    return ConsensusTarget(
        result_id=result_id,
        method_family=family,
        method_name=result_id,
        estimand=estimand or _consensus_estimand(),
        target_kind="causal_effect",
        point=np.asarray([point], dtype=float),
        covariance=np.asarray([[se * se]], dtype=float),
    )


def test_method_advisor_returns_ranked_payload_and_capability_matrix() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
                truthfulness_tier="exact",
                implementation_depth_tier="production_method",
            ),
            _entry(
                "causal.treatment_effects.proxy_score@1.0.0",
                family="causal.treatment_effects",
                variant="proxy_score",
                truthfulness_tier="unverified",
                implementation_depth_tier="heuristic_baseline",
            ),
            _entry(
                "survey.weighting.horvitz_thompson@1.0.0",
                family="survey.weighting",
                variant="horvitz_thompson",
                data_modalities=["survey"],
            ),
        ],
    )

    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(
            preferred_family="causal.treatment_effects",
            preferred_variant="tmle",
            minimum_fidelity_tier="high",
            required_data_modalities=("cross-section",),
        ),
        data=DataCharacteristics(n_obs=2_000),
        limit=2,
    )

    result = advise_methods(snapshot, query)

    assert [entry.fqn for entry in result.recommended] == [
        "causal.treatment_effects.tmle@1.0.0",
        "causal.treatment_effects.proxy_score@1.0.0",
    ]
    assert [row["fqn"] for row in result.payload] == [entry.fqn for entry in result.recommended]
    assert [row["fqn"] for row in result.capability_matrix] == [
        entry.fqn for entry in result.recommended
    ]
    assert result.capability_matrix[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["implementation_depth_tier"] == "production_method"
    assert result.payload[0]["advisor_score"] > result.payload[1]["advisor_score"]
    assert (
        result.payload[0]["truthfulness_depth_score"]
        > result.payload[1]["truthfulness_depth_score"]
    )
    assert [item.fqn for item in result.score_trace] == [
        "causal.treatment_effects.tmle@1.0.0",
        "causal.treatment_effects.proxy_score@1.0.0",
    ]

    assert result.calibrated_regret_certificate is not None
    assert result.calibrated_regret_certificate.loss_profile_id == "balanced"
    assert result.calibrated_regret_certificate.tier_source == "static_catalog"
    assert result.calibrated_regret_certificate.status == "INSUFFICIENT_LOGGING"
    assert result.family_summary == (
        {
            "family": "causal.treatment_effects",
            "count": 2,
            "truthfulness_tiers": ["exact", "unverified"],
            "deepest_truthfulness_tier": "exact",
            "truthfulness_depth_score": 3,
            "implementation_depth_tiers": ["heuristic_baseline", "production_method"],
            "deepest_implementation_depth_tier": "production_method",
            "catalog_depth_score": 3,
            "frontier_method_count": 0,
        },
    )


def test_value_advisor_trace_is_filtered_to_the_value_denominator() -> None:
    result = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_value_denominator",
            "diversity_key": ("posterior", "tabular", "effect"),
        },
        problem={
            "design_problem_id": "problem_value_denominator",
            "problem_statement": "Estimate an uncertainty-bounded causal effect.",
            "domain": "generic_policy",
            "runtime_hints": {
                "value_data_characteristics": {
                    "n_obs": 64,
                    "n_units": 16,
                    "n_periods": 4,
                    "is_panel": False,
                    "treatment_is_binary": True,
                    "outcome_is_continuous": True,
                }
            },
        },
    )

    assert result["status"] == "selected"
    denominator = set(result["denominator"])
    assert denominator
    assert set(result["score_trace"]) <= denominator
    assert result["ranked_alternatives"]
    assert all(
        row["method_fqn"] in denominator
        for row in result["ranked_alternatives"]
    )
    assert sum(
        row["method_fqn"] == result["selected_method_fqn"]
        for row in result["ranked_alternatives"]
    ) == 1


def test_value_denominator_excludes_diagnostics_without_native_projection() -> None:
    """A diagnostic name/tag cannot substitute for an owner-native value contract."""

    result = select_value_method_for_problem(
        candidate={
            "candidate_id": "education_candidate_unbound",
            "diversity_key": ("tabular", "cross-section", "education"),
        },
        problem={
            "design_problem_id": "education_value_denominator",
            "problem_statement": "Estimate tertiary enrollment effects.",
            "domain": "education",
            "runtime_hints": {
                "value_data_characteristics": {
                    "n_obs": 3,
                    "n_units": 3,
                    "n_periods": 1,
                    "is_panel": False,
                    "treatment_is_binary": None,
                    "outcome_is_continuous": True,
                },
                "value_required_data_modalities": ("tabular",),
            },
        },
    )

    assert result["status"] == "selected"
    assert "econometrics.diagnostics.hausman_test@1.0.0" not in result["denominator"]
    assert all("diagnostic" not in fqn for fqn in result["denominator"])


def test_value_denominator_rejects_catalog_capability_without_method_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shaped catalog row cannot make a diagnostic method value-capable."""

    registry = MethodRegistry.get_instance()
    ensure_all_methods_registered(registry)
    live_catalog = build_method_catalog_snapshot(registry=registry)
    hausman = next(
        entry
        for entry in live_catalog.entries
        if entry.fqn == "econometrics.diagnostics.hausman_test@1.0.0"
    )
    slot_name = str(hausman.output_slots[0]["name"])
    owner_ref = (
        f"{_WaterQualityNativeInterval.__module__}:"
        f"{_WaterQualityNativeInterval.__qualname__}"
    )
    forged_capability = value_evidence.NativeValueProjectionCapability(
        output_slot=slot_name,
        contract_id=_WaterQualityNativeInterval.contract_id,
        owner_module=_WaterQualityNativeInterval.__module__,
        owner_qualname=_WaterQualityNativeInterval.__qualname__,
    )
    forged = hausman.model_copy(
        update={
            "capability_matrix": {
                **hausman.capability_matrix,
                "value_projection_contracts": [
                    forged_capability.model_dump(mode="json")
                ],
            },
            "output_slots": [
                {
                    **hausman.output_slots[0],
                    "contract_id": _WaterQualityNativeInterval.contract_id,
                    "contract_capabilities": ["value_uncertainty_projection"],
                    "contract_owner": owner_ref,
                }
            ],
        }
    )
    forged_catalog = live_catalog.model_copy(update={"entries": [forged]})
    monkeypatch.setattr(
        advisor_module,
        "build_method_catalog_snapshot",
        lambda *, registry=None: forged_catalog,
    )

    result = select_value_method_for_problem(
        registry=registry,
        candidate={"candidate_id": "catalog-shape-attack"},
        problem={
            "design_problem_id": "catalog-shape-attack",
            "problem_statement": "Estimate an outcome.",
            "domain": "generic",
        },
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ("value_method_registry_empty",)


def test_value_projection_capability_is_discovered_from_third_contract_owner() -> None:
    """A new native contract flows without a method-family/FQN branch in the advisor."""

    resolver = value_evidence.resolve_method_value_projection_capabilities

    capabilities = resolver(
        method_cls=_WaterQualityValueMethod,
        method_signature=_WaterQualityValueMethod.signature,
    )

    assert len(capabilities) == 1
    assert capabilities[0].output_slot == "result"
    assert capabilities[0].contract_id == _WaterQualityNativeInterval.contract_id
    assert capabilities[0].projector == "to_value_uncertainty"
    assert capabilities[0].owner_qualname.endswith("_WaterQualityNativeInterval")


def test_value_advisor_builds_content_bound_selection_receipt_from_real_trace() -> None:
    result = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_selection_receipt",
            "diversity_key": ("posterior", "tabular", "effect"),
        },
        problem={
            "design_problem_id": "problem_selection_receipt",
            "problem_statement": "Estimate an uncertainty-bounded causal effect.",
            "domain": "generic_policy",
            "runtime_hints": {
                "value_data_characteristics": {
                    "n_obs": 64,
                    "n_units": 16,
                    "n_periods": 4,
                    "is_panel": False,
                    "treatment_is_binary": True,
                    "outcome_is_continuous": True,
                }
            },
        },
    )

    receipt = MethodSelectionReceipt.model_validate(result["selection_receipt"])

    assert receipt.selection_authority == "foundry_registry_advisor"
    assert receipt.denominator == tuple(sorted(set(receipt.denominator)))
    assert len(receipt.denominator) > 1
    assert receipt.selected_method_fqn == result["selected_method_fqn"]
    assert tuple(row.method_fqn for row in receipt.ranked_alternatives) == tuple(
        result["score_trace"]
    )
    assert sum(row.selected for row in receipt.ranked_alternatives) == 1


def test_method_selection_context_hash_uses_exact_canonical_selector_payload() -> None:
    profile_hash = "sha256:" + "a" * 64
    candidate = {
        "candidate_id": "candidate_selection_context",
        "diversity_key": ("posterior", "tabular", "effect"),
    }
    problem = {
        "design_problem_id": "problem_selection_context",
        "problem_statement": "Estimate a bounded effect.",
        "domain": "generic_policy",
        "runtime_hints": {
            "value_data_characteristics": {
                "n_obs": 64,
                "n_units": 16,
                "n_periods": 4,
                "is_panel": True,
                "treatment_is_binary": True,
                "outcome_is_continuous": True,
            },
            "value_data_profile_content_hash": profile_hash,
            "value_required_data_modalities": ("tabular", "panel"),
        },
    }
    manifest = (
        {"contract_target": "tabular"},
        {"data_modality": "panel"},
        {"contract_target": "tabular"},
    )
    ensure_all_methods_registered()
    catalog_snapshot_id = build_method_catalog_snapshot().snapshot_id
    expected_payload = {
        "schema_version": "policyos.foundry.method_selection_context.v2",
        "catalog_snapshot_id": catalog_snapshot_id,
        "candidate_signal": "candidate_selection_context posterior tabular effect",
        "problem_signal": (
            "problem_selection_context Estimate a bounded effect. generic_policy"
        ),
        "value_data_profile_content_hash": profile_hash,
        "effective_query": {
            "criteria": {
                "preferred_kind": None,
                "preferred_family": None,
                "preferred_variant": None,
                "family_prefixes": ("bayesian",),
                "preferred_execution_backends": (),
                "required_data_modalities": ("tabular", "panel"),
                "preferred_data_modalities": (),
                "preferred_determinism_tier": None,
                "minimum_fidelity_tier": None,
                "runnable_only": True,
                "exclude_fqns": (),
            },
            "data": {
                "n_obs": 64,
                "n_units": 16,
                "n_periods": 4,
                "has_instrument": False,
                "has_running_variable": False,
                "is_panel": True,
                "treatment_is_binary": True,
                "outcome_is_continuous": True,
            },
            "runtime_budget_ms": 25.0,
            "limit": 8,
            "runnable_only": True,
            "loss_profile_id": "balanced",
            "coverage_floor": None,
            "confidence_level": 0.95,
            "cost_policy": "ignore",
            "cost_budget": None,
            "risk_delta": 0.05,
            "return_certificate": False,
            "dominance_mode": "point",
            "allow_heuristic_cost_estimate": True,
            "require_declared_accuracy_estimate": False,
            "require_cross_method_consensus": False,
            "minimum_consensus_methods": 2,
        },
        "requested_method_fqn": None,
        "manifest_targets": ("panel", "tabular"),
        "runtime_budget_ms": 25.0,
    }
    expected_hash = "sha256:" + hashlib.sha256(
        json.dumps(
            expected_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()

    actual_hash = method_selection.method_selection_context_hash(
        candidate=candidate,
        problem=problem,
        observation_to_contract_manifest=manifest,
        runtime_budget_ms=25.0,
    )

    assert actual_hash == expected_hash
    assert actual_hash == method_selection.method_selection_context_hash(
        candidate=candidate,
        problem=problem,
        observation_to_contract_manifest=manifest,
        runtime_budget_ms=25.0,
    )


def test_advisor_receipt_rejects_replay_across_owner_profile_contexts() -> None:
    candidate = {
        "candidate_id": "candidate_advisor_context_replay",
        "diversity_key": ("posterior", "tabular", "effect"),
    }

    def _problem(profile_digest: str) -> dict[str, object]:
        return {
            "design_problem_id": "problem_advisor_context_replay",
            "problem_statement": "Estimate a bounded effect.",
            "domain": "generic_policy",
            "runtime_hints": {
                "value_data_characteristics": {
                    "n_obs": 64,
                    "n_units": 16,
                    "n_periods": 4,
                    "is_panel": True,
                    "treatment_is_binary": True,
                    "outcome_is_continuous": True,
                },
                "value_data_profile_content_hash": profile_digest,
                "value_required_data_modalities": ("tabular",),
            },
        }

    first_problem = _problem("sha256:" + "d" * 64)
    second_problem = _problem("sha256:" + "e" * 64)
    first_selection = select_value_method_for_problem(candidate=candidate, problem=first_problem)
    second_selection = select_value_method_for_problem(candidate=candidate, problem=second_problem)
    first_receipt = MethodSelectionReceipt.model_validate(first_selection["selection_receipt"])
    second_receipt = MethodSelectionReceipt.model_validate(second_selection["selection_receipt"])

    assert first_selection["selected_method_fqn"] == second_selection["selected_method_fqn"]
    assert first_selection["denominator"] == second_selection["denominator"]
    assert first_selection["score_trace"] == second_selection["score_trace"]
    assert first_receipt.selection_context_hash != second_receipt.selection_context_hash
    assert first_receipt.content_hash != second_receipt.content_hash
    assert first_receipt.verify_selection_context(
        method_selection.method_selection_context_hash(
            candidate=candidate,
            problem=first_problem,
        )
    ) is first_receipt
    with pytest.raises(ValueError, match="value_method_selection_context_hash_mismatch"):
        first_receipt.verify_selection_context(second_receipt.selection_context_hash)


@pytest.mark.parametrize("requested", [False, True])
def test_value_selection_receipt_rejects_replay_across_catalog_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    requested: bool,
) -> None:
    base_catalog = build_method_catalog_snapshot()
    active_catalog = {"snapshot": base_catalog}
    monkeypatch.setattr(
        "polisyos.foundry.methods.selection.advisor.build_method_catalog_snapshot",
        lambda **_kwargs: active_catalog["snapshot"],
    )
    candidate = {"candidate_id": "candidate_catalog_context"}
    problem = {
        "design_problem_id": "problem_catalog_context",
        "problem_statement": "Choose a registered value method.",
        "domain": "generic_policy",
        "runtime_hints": {
            "value_data_profile_content_hash": "sha256:" + "c" * 64,
        },
    }
    preliminary = select_value_method_for_problem(candidate=candidate, problem=problem)
    requested_fqn = str(preliminary["selected_method_fqn"]) if requested else None
    first = select_value_method_for_problem(
        candidate=candidate,
        problem=problem,
        requested_method_fqn=requested_fqn,
    )
    first_receipt = MethodSelectionReceipt.model_validate(first["selection_receipt"])
    removed_fqn = next(
        fqn
        for fqn in reversed(first_receipt.denominator)
        if fqn != first_receipt.selected_method_fqn
    )
    active_catalog["snapshot"] = base_catalog.model_copy(
        update={
            "snapshot_id": f"{base_catalog.snapshot_id}-changed",
            "entries": [
                entry for entry in base_catalog.entries if entry.fqn != removed_fqn
            ],
        }
    )
    second = select_value_method_for_problem(
        candidate=candidate,
        problem=problem,
        requested_method_fqn=requested_fqn,
    )
    second_receipt = MethodSelectionReceipt.model_validate(second["selection_receipt"])

    assert first_receipt.selected_method_fqn == second_receipt.selected_method_fqn
    assert first_receipt.selection_context_hash != second_receipt.selection_context_hash
    with pytest.raises(ValueError, match="value_method_selection_context_hash_mismatch"):
        first_receipt.verify_selection_context(
            method_selection.method_selection_context_hash(
                candidate=candidate,
                problem=problem,
                requested_method_fqn=requested_fqn,
            )
        )


def test_requested_value_method_builds_receipt_from_verified_registry_entry() -> None:
    advisor_selection = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_registry_request_source",
            "diversity_key": ("posterior", "tabular", "effect"),
        },
        problem={
            "design_problem_id": "problem_registry_request_source",
            "problem_statement": "Estimate an uncertainty-bounded causal effect.",
            "domain": "generic_policy",
        },
    )
    requested_fqn = advisor_selection["selected_method_fqn"]

    requested_selection = select_value_method_for_problem(
        candidate={"candidate_id": "candidate_registry_request"},
        problem={
            "design_problem_id": "problem_registry_request",
            "problem_statement": "Use the explicitly requested registered method.",
            "domain": "generic_policy",
        },
        requested_method_fqn=requested_fqn,
    )
    receipt = MethodSelectionReceipt.model_validate(requested_selection["selection_receipt"])

    assert receipt.selection_authority == "requested_registry_method"
    assert receipt.selected_method_fqn == requested_fqn
    assert receipt.denominator == tuple(sorted(set(receipt.denominator)))
    assert len(receipt.ranked_alternatives) == 1
    assert receipt.ranked_alternatives[0].method_fqn == requested_fqn
    assert receipt.ranked_alternatives[0].selected is True
    assert receipt.ranked_alternatives[0].advisor_score is None
    assert receipt.ranked_alternatives[0].loss_reasons == ("explicit_registry_request",)


def test_requested_registry_receipt_is_bound_to_its_owner_profile_context() -> None:
    candidate = {"candidate_id": "candidate_requested_context_replay"}
    first_problem = {
        "design_problem_id": "problem_requested_context_replay",
        "problem_statement": "Use the requested registered method.",
        "domain": "generic_policy",
        "runtime_hints": {
            "value_data_profile_content_hash": "sha256:" + "f" * 64,
        },
    }
    advisor_selection = select_value_method_for_problem(candidate=candidate, problem=first_problem)
    advisor_receipt = MethodSelectionReceipt.model_validate(advisor_selection["selection_receipt"])
    requested_fqn = str(advisor_selection["selected_method_fqn"])
    second_problem = {
        **first_problem,
        "runtime_hints": {
            "value_data_profile_content_hash": "sha256:" + "0" * 64,
        },
    }

    first_selection = select_value_method_for_problem(
        candidate=candidate,
        problem=first_problem,
        requested_method_fqn=requested_fqn,
    )
    second_selection = select_value_method_for_problem(
        candidate=candidate,
        problem=second_problem,
        requested_method_fqn=requested_fqn,
    )
    first_receipt = MethodSelectionReceipt.model_validate(first_selection["selection_receipt"])
    second_receipt = MethodSelectionReceipt.model_validate(second_selection["selection_receipt"])

    assert first_receipt.selection_authority == "requested_registry_method"
    assert first_receipt.selected_method_fqn == second_receipt.selected_method_fqn
    assert first_receipt.denominator == second_receipt.denominator
    assert first_receipt.selection_context_hash != advisor_receipt.selection_context_hash
    assert first_receipt.selection_context_hash != second_receipt.selection_context_hash
    assert first_receipt.content_hash != second_receipt.content_hash
    assert first_receipt.verify_selection_context(
        method_selection.method_selection_context_hash(
            candidate=candidate,
            problem=first_problem,
            requested_method_fqn=requested_fqn,
        )
    ) is first_receipt
    with pytest.raises(ValueError, match="value_method_selection_context_hash_mismatch"):
        first_receipt.verify_selection_context(second_receipt.selection_context_hash)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda payload: payload.update(selection_authority="caller_asserted_advisor"),
            "selection_authority",
        ),
        (
            lambda payload: payload.update(denominator=tuple(reversed(payload["denominator"]))),
            "value_method_selection_denominator_not_canonical",
        ),
        (
            lambda payload: payload["ranked_alternatives"][0].update(
                method_fqn="out.of.denominator@1.0.0"
            ),
            "value_method_selection_trace_outside_denominator",
        ),
        (
            lambda payload: payload.update(
                ranked_alternatives=[
                    {**row, "selected": False} for row in payload["ranked_alternatives"]
                ]
            ),
            "value_method_selection_receipt_incoherent",
        ),
        (
            lambda payload: payload.update(denominator=(payload["selected_method_fqn"],)),
            "value_method_selection_fixed_default",
        ),
        (
            lambda payload: payload.update(content_hash="sha256:" + "0" * 64),
            "value_method_selection_receipt_content_hash_mismatch",
        ),
        (
            lambda payload: payload.update(selection_context_hash="sha256:" + "0" * 64),
            "value_method_selection_receipt_content_hash_mismatch",
        ),
        (
            lambda payload: payload.update(unexpected_authority_hint="trusted"),
            "extra_forbidden",
        ),
    ],
)
def test_value_method_selection_receipt_rejects_self_attested_or_incoherent_payloads(
    mutation: object,
    reason: str,
) -> None:
    selection = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_selection_receipt_negative",
            "diversity_key": ("posterior", "tabular", "effect"),
        },
        problem={
            "design_problem_id": "problem_selection_receipt_negative",
            "problem_statement": "Estimate an uncertainty-bounded causal effect.",
            "domain": "generic_policy",
            "runtime_hints": {
                "value_data_characteristics": {
                    "n_obs": 64,
                    "n_units": 16,
                    "n_periods": 4,
                    "is_panel": False,
                    "treatment_is_binary": True,
                    "outcome_is_continuous": True,
                }
            },
        },
    )
    payload = selection["selection_receipt"]
    mutation(payload)  # type: ignore[operator]

    with pytest.raises(ValidationError, match=reason):
        MethodSelectionReceipt.model_validate(payload)


def test_method_advisor_strict_phase5_blocks_missing_consensus() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
            )
        ],
    )
    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(preferred_family="causal.treatment_effects"),
        require_cross_method_consensus=True,
    )

    result = advise_methods(snapshot, query)

    assert result.recommended == ()
    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "not_enough_methods"
    assert result.cross_method_consensus.recommendation_allowed is False


def test_method_advisor_prefers_production_depth_over_heuristic_baseline() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.evaluation.rigorous@1.0.0",
                family="policy.evaluation",
                variant="rigorous",
                truthfulness_tier="exact",
                implementation_depth_tier="production_method",
            ),
            _entry(
                "policy.evaluation.quick_proxy@1.0.0",
                family="policy.evaluation",
                variant="quick_proxy",
                truthfulness_tier="approximate_calibrated",
                implementation_depth_tier="heuristic_baseline",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.evaluation",
                minimum_fidelity_tier="high",
                required_data_modalities=("cross-section",),
            ),
            data=DataCharacteristics(n_obs=2_000),
            limit=2,
        ),
    )

    assert [entry.fqn for entry in result.recommended] == [
        "policy.evaluation.rigorous@1.0.0",
        "policy.evaluation.quick_proxy@1.0.0",
    ]
    assert result.family_summary == (
        {
            "family": "policy.evaluation",
            "count": 2,
            "truthfulness_tiers": ["approximate_calibrated", "exact"],
            "deepest_truthfulness_tier": "exact",
            "truthfulness_depth_score": 3,
            "implementation_depth_tiers": ["heuristic_baseline", "production_method"],
            "deepest_implementation_depth_tier": "production_method",
            "catalog_depth_score": 3,
            "frontier_method_count": 0,
        },
    )


def test_method_advisor_certificate_marks_ambiguous_rank_when_gap_crosses_zero() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.choice.primary@1.0.0",
                family="policy.choice",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.choice.runner_up@1.0.0",
                family="policy.choice",
                variant="runner_up",
                truthfulness_tier="exact",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(4):
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.choice.primary@1.0.0",
                timestamp=now + idx,
                latency_ms=40.0,
                success=True,
                candidate_fqns=(
                    "policy.choice.primary@1.0.0",
                    "policy.choice.runner_up@1.0.0",
                ),
                selected_rank=1,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.40, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.choice.runner_up@1.0.0": 0.15},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.choice.runner_up@1.0.0",
                timestamp=now + 100 + idx,
                latency_ms=45.0,
                success=True,
                candidate_fqns=(
                    "policy.choice.primary@1.0.0",
                    "policy.choice.runner_up@1.0.0",
                ),
                selected_rank=2,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.41, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.choice.primary@1.0.0": 0.14},
            )
        )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.choice"),
            limit=2,
        ),
        history=history,
    )

    cert = result.calibrated_regret_certificate
    assert cert is not None
    assert cert.status == "AMBIGUOUS_RANK"
    assert cert.ope_estimator == "shadow_replay"
    assert cert.top1_vs_top2_gap_cs is not None
    assert cert.top1_vs_top2_gap_cs.lower <= 0.0 <= cert.top1_vs_top2_gap_cs.upper


def test_method_advisor_applies_runtime_truthfulness_downgrade_from_history() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.runtime.posterior@1.0.0",
                family="policy.runtime",
                variant="posterior",
                truthfulness_tier="asymptotic",
                declared_truthfulness_tier="asymptotic",
            ),
            _entry(
                "policy.runtime.calibrated@1.0.0",
                family="policy.runtime",
                variant="calibrated",
                truthfulness_tier="approximate_calibrated",
                declared_truthfulness_tier="approximate_calibrated",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    history.record(
        MethodExecutionRecord(
            method_fqn="policy.runtime.posterior@1.0.0",
            timestamp=now,
            latency_ms=50.0,
            success=True,
            runtime_truthfulness_tier="unverified",
            effective_truthfulness_tier="unverified",
            truthfulness_status="runtime_downgraded",
            truthfulness_scope="posterior",
            truthfulness_evidence_ref="cas://truthfulness/posterior",
        )
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.runtime"),
            limit=2,
        ),
        history=history,
    )

    assert [entry.fqn for entry in result.recommended] == [
        "policy.runtime.calibrated@1.0.0",
        "policy.runtime.posterior@1.0.0",
    ]
    assert result.payload[1]["truthfulness_tier"] == "unverified"
    assert result.payload[1]["runtime_truthfulness_tier"] == "unverified"
    assert result.payload[1]["truthfulness_status"] == "runtime_downgraded"
    assert result.capability_matrix[1]["truthfulness_tier"] == "unverified"
    assert result.calibrated_regret_certificate is not None
    assert result.calibrated_regret_certificate.tier_source == "runtime_validated"


def test_method_advisor_uses_declared_hmc_and_nuts_truthfulness_before_runtime_history() -> None:
    ensure_all_methods_registered()
    full_snapshot = build_method_catalog_snapshot(run_id="R_phase0_truthfulness")
    snapshot = MethodCatalogSnapshot(
        snapshot_id="phase0-truthfulness",
        entries=tuple(
            entry
            for entry in full_snapshot.entries
            if entry.fqn
            in {
                "bayesian.sampling.hmc@1.0.0",
                "bayesian.sampling.nuts@1.0.0",
            }
        ),
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(runnable_only=False),
            data=DataCharacteristics(n_obs=1_000),
            limit=2,
            runnable_only=False,
        ),
    )

    assert {entry.fqn for entry in result.recommended} == {
        "bayesian.sampling.hmc@1.0.0",
        "bayesian.sampling.nuts@1.0.0",
    }
    for row in result.payload:
        assert row["truthfulness_tier"] == "asymptotic"
        assert row["declared_truthfulness_tier"] == "asymptotic"
        assert row["truthfulness_status"] == "catalog_only"


def test_method_advisor_builds_execution_context_with_full_candidate_slate() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.telemetry.primary@1.0.0",
                family="policy.telemetry",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.telemetry.alt@1.0.0",
                family="policy.telemetry",
                variant="alt",
                truthfulness_tier="approximate_calibrated",
            ),
            _entry(
                "policy.telemetry.fallback@1.0.0",
                family="policy.telemetry",
                variant="fallback",
                truthfulness_tier="unverified",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.telemetry"),
            limit=2,
        ),
    )

    context = build_advisor_execution_context(
        result,
        selection_propensity=0.25,
        shadow_loss_estimates={"policy.telemetry.alt@1.0.0": 0.2},
    )

    assert context is not None
    assert context.loss_profile_id == "balanced"
    assert context.candidate_fqns == (
        "policy.telemetry.primary@1.0.0",
        "policy.telemetry.alt@1.0.0",
        "policy.telemetry.fallback@1.0.0",
    )
    assert context.selected_rank == 1
    assert context.selection_propensity == pytest.approx(0.25)
    assert set(context.advisor_score_vector) == set(context.candidate_fqns)
    assert context.shadow_loss_estimates["policy.telemetry.alt@1.0.0"] == pytest.approx(0.2)


def test_method_advisor_certificate_validates_separated_top1_rank() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.rank.safe@1.0.0",
                family="policy.rank",
                variant="safe",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.rank.risky@1.0.0",
                family="policy.rank",
                variant="risky",
                truthfulness_tier="exact",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(32):
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.rank.safe@1.0.0",
                timestamp=now + idx,
                latency_ms=30.0,
                success=True,
                candidate_fqns=(
                    "policy.rank.safe@1.0.0",
                    "policy.rank.risky@1.0.0",
                ),
                selected_rank=1,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.05, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.rank.risky@1.0.0": 0.65},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.rank.risky@1.0.0",
                timestamp=now + 100 + idx,
                latency_ms=90.0,
                success=False,
                candidate_fqns=(
                    "policy.rank.safe@1.0.0",
                    "policy.rank.risky@1.0.0",
                ),
                selected_rank=2,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.80, "failure_penalty": 1.0},
                shadow_loss_estimates={"policy.rank.safe@1.0.0": 0.05},
            )
        )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.rank"),
            limit=2,
            loss_profile_id="coverage_strict",
        ),
        history=history,
    )

    cert = result.calibrated_regret_certificate
    assert cert is not None
    assert cert.loss_profile_id == "coverage_strict"
    assert cert.status == "VALID"
    assert cert.observed_regret_cs is not None
    assert cert.certified_regret_upper is not None
    assert cert.observed_regret_cs.upper <= cert.certified_regret_upper
    assert cert.top1_vs_top2_gap_cs is not None
    assert cert.top1_vs_top2_gap_cs.lower > 0.0


def test_method_advisor_cost_filter_excludes_over_budget_high_value_method() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="cost-filter",
        entries=[
            _entry(
                "policy.cost.expensive@1.0.0",
                family="policy.cost",
                variant="expensive",
                advisor_cost={
                    "estimated_total_ms": 160.0,
                    "upper_ms": 160.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.cost.feasible@1.0.0",
                family="policy.cost",
                variant="feasible",
                advisor_cost={
                    "estimated_total_ms": 40.0,
                    "upper_ms": 40.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.cost",
                preferred_variant="expensive",
            ),
            cost_policy="filter",
            cost_budget={"max_total_ms": 100.0},
            limit=2,
        ),
    )

    assert [entry.fqn for entry in result.recommended] == ["policy.cost.feasible@1.0.0"]
    assert result.advisor_optimization is not None
    assert result.advisor_optimization.status == "FILTERED"
    assert result.advisor_optimization.certificate is not None
    assert result.advisor_optimization.certificate.infeasible_method_ids == (
        "policy.cost.expensive@1.0.0",
    )
    assert result.payload[0]["cost_estimate"]["feasible"] is True


def test_pareto_advisor_returns_nondominated_budget_feasible_frontier() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="pareto",
        entries=[
            _entry(
                "policy.pareto.accurate@1.0.0",
                family="policy.pareto",
                variant="accurate",
                advisor_cost={
                    "estimated_total_ms": 50.0,
                    "upper_ms": 50.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.pareto.dominated@1.0.0",
                family="policy.pareto",
                variant="dominated",
                advisor_cost={
                    "estimated_total_ms": 80.0,
                    "upper_ms": 80.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.pareto.cheap@1.0.0",
                family="policy.pareto",
                variant="cheap",
                advisor_cost={
                    "estimated_total_ms": 10.0,
                    "upper_ms": 10.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.pareto",
                preferred_variant="accurate",
            ),
            cost_budget={"max_total_ms": 100.0},
            limit=3,
        ),
        value_policy=AdvisorValuePolicy(accuracy_weight=1.0),
    )

    assert optimization.success is True
    assert optimization.status == "PARETO_OPTIMAL"
    assert optimization.x == "policy.pareto.accurate@1.0.0"
    assert {score.method_id for score in optimization.pareto_front} == {
        "policy.pareto.accurate@1.0.0",
        "policy.pareto.cheap@1.0.0",
    }
    assert "policy.pareto.dominated@1.0.0" not in {
        score.method_id for score in optimization.pareto_front
    }
    assert all(score.spend_upper <= 100.0 for score in optimization.pareto_front)


def test_pareto_advisor_budget_certificate_records_exact_feasibility() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="certificate",
        entries=[
            _entry(
                "policy.cert.safe@1.0.0",
                family="policy.cert",
                variant="safe",
                advisor_cost={
                    "estimated_total_ms": 25.0,
                    "upper_ms": 30.0,
                    "bound_type": "EXACT_BOUND",
                    "estimator_version": "test-cost.v1",
                },
            ),
            _entry(
                "policy.cert.over@1.0.0",
                family="policy.cert",
                variant="over",
                advisor_cost={
                    "estimated_total_ms": 95.0,
                    "upper_ms": 120.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.cert",
                preferred_variant="safe",
            ),
            cost_budget={"max_total_ms": 100.0},
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.feasible is True
    assert certificate.selected_method_id == "policy.cert.safe@1.0.0"
    assert certificate.estimated_cost_upper == pytest.approx(30.0)
    assert certificate.slack_lower_bound == pytest.approx(70.0)
    assert certificate.bound_type == "EXACT_BOUND"
    assert certificate.confidence == pytest.approx(1.0)
    assert certificate.cost_model_version == "test-cost.v1"


def test_pareto_advisor_heuristic_cost_estimate_downgrades_certificate() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="heuristic",
        entries=[
            _entry(
                "causal.dml.heuristic@1.0.0",
                family="causal.dml",
                variant="heuristic",
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="causal.dml"),
            data=DataCharacteristics(n_obs=100),
            cost_budget={"max_total_ms": 1_000_000.0},
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.bound_type == "HEURISTIC_POINT_ESTIMATE"
    assert certificate.confidence is None
    assert any("heuristic" in obligation for obligation in certificate.proof_obligations)


def test_cost_policy_ignore_preserves_legacy_advisor_ordering() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="ignore-compat",
        entries=[
            _entry("policy.compat.a@1.0.0", family="policy.compat", variant="a"),
            _entry("policy.compat.b@1.0.0", family="policy.compat", variant="b"),
        ],
    )
    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(
            preferred_family="policy.compat",
            preferred_variant="b",
        ),
        limit=2,
    )

    legacy = advise_methods(snapshot, query)
    explicit_ignore = advise_methods(snapshot, replace(query, cost_policy="ignore"))

    assert [entry.fqn for entry in legacy.recommended] == [
        entry.fqn for entry in explicit_ignore.recommended
    ]
    assert legacy.advisor_optimization is None
    assert explicit_ignore.advisor_optimization is None


def test_pareto_advisor_infeasible_budget_reports_relaxations() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="infeasible",
        entries=[
            _entry(
                "policy.infeasible.cheaper@1.0.0",
                family="policy.infeasible",
                variant="cheaper",
                advisor_cost={
                    "estimated_total_ms": 80.0,
                    "upper_ms": 90.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.infeasible.accurate@1.0.0",
                family="policy.infeasible",
                variant="accurate",
                advisor_cost={
                    "estimated_total_ms": 120.0,
                    "upper_ms": 140.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.infeasible",
                preferred_variant="accurate",
            ),
            cost_policy="pareto",
            cost_budget={"max_total_ms": 50.0},
        ),
    )

    optimization = result.advisor_optimization
    assert optimization is not None
    assert optimization.success is False
    assert optimization.status == "INFEASIBLE_BUDGET"
    assert result.recommended == ()
    assert optimization.diagnostics["min_required_budget_point"] == pytest.approx(80.0)
    assert optimization.diagnostics["min_required_budget_upper"] == pytest.approx(90.0)
    assert optimization.diagnostics["cheapest_candidate"] == "policy.infeasible.cheaper@1.0.0"
    assert optimization.diagnostics["highest_accuracy_over_budget_candidate"] == (
        "policy.infeasible.accurate@1.0.0"
    )
    relaxations = optimization.diagnostics["closest_feasible_relaxations"]
    assert relaxations[0]["method_id"] == "policy.infeasible.cheaper@1.0.0"
    assert relaxations[0]["required_budget"]["ms_limit"] == pytest.approx(90.0)


def test_pareto_advisor_multi_resource_budget_blocks_memory_overrun() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="multi-resource",
        entries=[
            _entry(
                "policy.resource.memory_hungry@1.0.0",
                family="policy.resource",
                variant="memory_hungry",
                advisor_cost={
                    "estimated_total_ms": 20.0,
                    "upper_ms": 20.0,
                    "estimated_memory_mb": 512.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.resource.small@1.0.0",
                family="policy.resource",
                variant="small",
                advisor_cost={
                    "estimated_total_ms": 30.0,
                    "upper_ms": 30.0,
                    "estimated_memory_mb": 64.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.resource",
                preferred_variant="memory_hungry",
            ),
            cost_policy="filter",
            cost_budget={"max_total_ms": 100.0, "max_memory_mb": 128.0},
            limit=2,
        ),
    )

    optimization = result.advisor_optimization
    assert optimization is not None
    assert [entry.fqn for entry in result.recommended] == ["policy.resource.small@1.0.0"]
    hungry = next(
        score
        for score in optimization.candidates
        if score.method_id == "policy.resource.memory_hungry@1.0.0"
    )
    assert hungry.feasible is False
    assert "memory_limit" in hungry.violations


def test_pareto_advisor_calibrated_probabilistic_certificate_confidence() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="calibrated-cost",
        entries=[
            _entry(
                "policy.calibrated.safe@1.0.0",
                family="policy.calibrated",
                variant="safe",
                advisor_cost={
                    "estimated_total_ms": 70.0,
                    "upper_ms": 85.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                    "coverage_confidence": 0.95,
                    "calibration_scope": "unit-test",
                },
            )
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.calibrated"),
            cost_budget={"max_total_ms": 100.0},
            risk_delta=0.05,
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.bound_type == "CALIBRATED_PROBABILISTIC_BOUND"
    assert certificate.confidence == pytest.approx(0.95)
    assert certificate.delta == pytest.approx(0.05)
    assert certificate.calibration_scope == "unit-test"


def test_robust_pareto_keeps_candidate_when_uncertainty_overlaps() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="robust-frontier",
        entries=[
            _entry(
                "policy.robust.nominal_winner@1.0.0",
                family="policy.robust",
                variant="nominal_winner",
                advisor_cost={
                    "estimated_total_ms": 40.0,
                    "lower_ms": 35.0,
                    "upper_ms": 45.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                },
                advisor_accuracy={
                    "accuracy": 0.80,
                    "accuracy_lower": 0.70,
                    "accuracy_upper": 0.90,
                },
            ),
            _entry(
                "policy.robust.uncertain_alt@1.0.0",
                family="policy.robust",
                variant="uncertain_alt",
                advisor_cost={
                    "estimated_total_ms": 42.0,
                    "lower_ms": 39.0,
                    "upper_ms": 50.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                },
                advisor_accuracy={
                    "accuracy": 0.78,
                    "accuracy_lower": 0.72,
                    "accuracy_upper": 0.88,
                },
            ),
        ],
    )

    point = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.robust"),
            cost_budget={"max_total_ms": 100.0},
            dominance_mode="point",
        ),
    )
    robust = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.robust"),
            cost_budget={"max_total_ms": 100.0},
            dominance_mode="robust",
        ),
    )

    assert {score.method_id for score in point.pareto_front} == {
        "policy.robust.nominal_winner@1.0.0"
    }
    assert {score.method_id for score in robust.pareto_front} == {
        "policy.robust.nominal_winner@1.0.0",
        "policy.robust.uncertain_alt@1.0.0",
    }


def test_pareto_advisor_no_cost_model_when_heuristics_disabled() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="no-cost-model",
        entries=[
            _entry("policy.no_cost.a@1.0.0", family="policy.no_cost", variant="a"),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.no_cost"),
            cost_budget={"max_total_ms": 100.0},
            allow_heuristic_cost_estimate=False,
        ),
    )

    assert optimization.success is False
    assert optimization.status == "NO_COST_MODEL"


def test_pareto_advisor_requires_declared_accuracy_when_requested() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="no-accuracy",
        entries=[
            _entry(
                "policy.no_accuracy.a@1.0.0",
                family="policy.no_accuracy",
                variant="a",
                advisor_cost={
                    "estimated_total_ms": 10.0,
                    "upper_ms": 10.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.no_accuracy"),
            cost_budget={"max_total_ms": 100.0},
            require_declared_accuracy_estimate=True,
        ),
    )

    assert optimization.success is False
    assert optimization.status == "NO_ACCURACY_ESTIMATE"


def test_cross_method_consensus_passes_when_methods_agree() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("regression_adjusted", family="regression", point=0.20),
            _consensus_target("dml", family="double_ml", point=0.22),
        ),
    )

    assert consensus.status == "pass"
    assert consensus.recommendation_allowed is True
    assert consensus.global_cmd_score < 1.0
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.metric == "z_score"


def test_cross_method_consensus_refuses_and_classifies_isolated_family() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("regression_adjusted", family="regression", point=0.00),
            _consensus_target("dml", family="double_ml", point=0.02),
            _consensus_target("iv_2sls", family="iv", point=0.46),
        ),
    )

    assert consensus.status in {"refuse", "hard_refuse"}
    assert consensus.recommendation_allowed is False
    assert consensus.user_message == "Methods disagree, no recommendation."
    assert consensus.global_cmd_score > 1.0
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.adjusted_q_value is not None
    assert consensus.worst_pair.adjusted_q_value <= 0.01
    assert consensus.likely_misspecification.status == "likely_misspecified_family"
    assert consensus.likely_misspecification.likely_family == "iv"
    assert consensus.consensus_set == ("dml", "regression_adjusted")


def test_cross_method_consensus_marks_estimand_mismatch_not_disagreement() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target(
                "one_week",
                family="prediction",
                point=0.10,
                estimand=_consensus_estimand(time_horizon="one_week"),
            ),
            _consensus_target(
                "one_month",
                family="prediction",
                point=0.40,
                estimand=_consensus_estimand(time_horizon="one_month"),
            ),
        ),
    )

    assert consensus.status == "not_comparable"
    assert consensus.recommendation_allowed is True
    assert consensus.likely_misspecification.status == "estimand_mismatch"
    assert consensus.global_cmd_score == 0.0


def test_cross_method_consensus_transforms_log_scale_before_comparing() -> None:
    identity_estimand = _consensus_estimand()
    log_estimand = replace(identity_estimand, scale="log")

    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "scale": "identity"},
        (
            _consensus_target(
                "identity_scale",
                family="regression",
                point=2.0,
                se=0.2,
                estimand=identity_estimand,
            ),
            ConsensusTarget(
                result_id="log_scale",
                method_family="bayesian",
                method_name="log_scale",
                estimand=log_estimand,
                target_kind="causal_effect",
                point=np.asarray([np.log(2.0)], dtype=float),
                covariance=np.asarray([[0.1 * 0.1]], dtype=float),
            ),
        ),
    )

    assert consensus.status == "pass"
    assert consensus.noncomparable_method_ids == ()
    assert all(
        check.estimand is not None and check.estimand.scale == "identity"
        for check in consensus.pairwise
        if check.comparable
    )
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.point_j == pytest.approx((2.0,))


def test_cross_method_consensus_warns_when_disagreement_is_not_decision_relevant() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("positive_a", family="regression", point=0.20, se=0.01),
            _consensus_target("positive_b", family="double_ml", point=0.50, se=0.01),
        ),
    )

    assert consensus.status == "warn"
    assert consensus.recommendation_allowed is True
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.adjusted_q_value is not None
    assert consensus.worst_pair.adjusted_q_value <= 0.01
    assert consensus.worst_pair.decision_relevant is False


def test_cross_method_consensus_refuses_statistical_conflict_in_strict_mode() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "strict_consensus_validation": True},
        (
            _consensus_target("positive_a", family="regression", point=0.20, se=0.01),
            _consensus_target("positive_b", family="double_ml", point=0.50, se=0.01),
        ),
    )

    assert consensus.status in {"refuse", "hard_refuse"}
    assert consensus.recommendation_allowed is False
    assert consensus.user_message == "Methods disagree, no recommendation."
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.decision_relevant is True


def test_cross_method_consensus_runs_distributional_diagnostics() -> None:
    central = np.linspace(-1.0, 1.0, 80, dtype=float).reshape(-1, 1)
    split_tail = np.concatenate(
        [
            np.linspace(-4.0, -3.0, 40, dtype=float),
            np.linspace(3.0, 4.0, 40, dtype=float),
        ]
    ).reshape(-1, 1)

    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "strict_consensus_validation": True},
        (
            ConsensusTarget(
                result_id="central_predictive",
                method_family="prediction",
                method_name="central_predictive",
                estimand=_consensus_estimand(),
                target_kind="causal_effect",
                point=np.asarray([0.0], dtype=float),
                covariance=np.asarray([[1.0]], dtype=float),
                samples=central,
            ),
            ConsensusTarget(
                result_id="tail_predictive",
                method_family="prediction",
                method_name="tail_predictive",
                estimand=_consensus_estimand(),
                target_kind="causal_effect",
                point=np.asarray([0.0], dtype=float),
                covariance=np.asarray([[1.0]], dtype=float),
                samples=split_tail,
            ),
        ),
        distribution_permutations=399,
    )

    distribution_checks = [
        check for check in consensus.pairwise if check.projection == "distribution"
    ]
    assert distribution_checks
    assert distribution_checks[0].metric == "energy_distance"
    assert distribution_checks[0].adjusted_q_value is not None
    assert distribution_checks[0].adjusted_q_value <= 0.01
    assert consensus.status == "refuse"
    assert consensus.recommendation_allowed is False


def test_method_advisor_suppresses_recommendations_when_consensus_refuses() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.consensus.primary@1.0.0",
                family="policy.consensus",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.consensus.alt@1.0.0",
                family="policy.consensus",
                variant="alt",
                truthfulness_tier="exact",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.consensus"),
            limit=2,
        ),
        consensus_results=(
            _consensus_target("primary_output", family="regression", point=0.0),
            _consensus_target("alt_output", family="iv", point=0.40),
        ),
    )

    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "refuse"
    assert result.recommended == ()
    assert result.payload == ()
    assert [item.fqn for item in result.score_trace] == [
        "policy.consensus.alt@1.0.0",
        "policy.consensus.primary@1.0.0",
    ]


def test_analyst_advisor_requires_strict_cross_method_consensus() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry("policy.strict.primary@1.0.0", family="policy.strict", variant="primary"),
            _entry("policy.strict.alt@1.0.0", family="policy.strict", variant="alt"),
        ],
    )

    result = advise_methods_for_analyst(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.strict"),
            limit=2,
        ),
        consensus_results=(_consensus_target("primary_output", family="regression", point=0.0),),
    )

    assert result.query.require_cross_method_consensus is True
    assert result.query.cost_policy == "annotate"
    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "not_enough_methods"
    assert result.cross_method_consensus.recommendation_allowed is False
    assert result.recommended == ()
