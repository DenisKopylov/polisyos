"""Regression witnesses for SCM-02 factual abduction and attribution."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData, TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import (
    CausalContrastSpec,
    CausalQuery,
    CausalQueryResult,
    CausalRegime,
    InterventionSpec,
    InterventionType,
    QueryType,
    load_causal_query_result,
    persist_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalQueryResultRef
from polisyos.scientist.compute.job_spec import JobKey, JobResult
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import RunCausalEnsembleNode
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _linear_chain(
    *,
    noise_std: float = 1.0,
    coefficient: float = 1.0,
    root_intercept: float = 0.0,
) -> StructuralCausalModelSpec:
    """Build X -> Y with independent Gaussian structural noise."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": root_intercept,
                    "coefficients": {},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": coefficient},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _run_query(scm_spec: StructuralCausalModelSpec, query: dict[str, object]) -> dict[str, object]:
    """Run the public GCM query entrypoint with the optional comparison disabled."""
    payload = SCMQueryData(scm_spec=scm_spec, query=query)
    return GCMQuery.pure_step(
        payload,
        params={"__seed__": 117, "enable_dowhy_comparison": False},
    )


def _build_execution_context(tmp_path: Path, *, run_id: str) -> ExecutionContext:
    """Build the real node context used by producer/consumer witnesses."""
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _empirical_root_chain() -> StructuralCausalModelSpec:
    """Build the same chain with an empirical, non-Gaussian root carrier."""
    scm = _linear_chain()
    empirical_root = scm.mechanisms[0].model_copy(
        update={
            "family": MechanismFamily.EMPIRICAL,
            "family_params": {"mean": 0.0, "std": 1.0},
        }
    )
    return scm.model_copy(update={"mechanisms": [empirical_root, scm.mechanisms[1]]})


def _empirical_covariate_scm() -> StructuralCausalModelSpec:
    """Build X,Z -> Y with an empirical non-treatment root Z."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Z", "Y"],
        edges=[CausalEdge(src="X", dst="Y"), CausalEdge(src="Z", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.LINEAR,
                family_params={"intercept": 0.0, "coefficients": {}, "noise_std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Z",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={
                    "mean": 0.0,
                    "std": 1.0,
                    "observed_samples": [0.0, 1.0],
                    "observed_samples_source": "scm-02-fixture",
                    "observed_sample_alignment": "row-index",
                    "joint_sample_group": "scm-02-fixture",
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.0, "Z": 1.0},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def test_partial_gaussian_abduction_conditions_unobserved_parent() -> None:
    """Y=2 alone yields U_Y|Y=2 with mean 1 and variance 0.5 under do(X=0)."""
    output = _run_query(
        _linear_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"Y": 2.0},
            "n_samples": 2048,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(1.0, abs=0.08)
    assert result.result_std == pytest.approx(2.0**-0.5, abs=0.08)
    assert result.metadata["abduction_profile"] == "linear_gaussian_posterior"
    assert result.metadata["abduction_observed_nodes"] == ["Y"]
    assert result.metadata["abduction_noise_nodes"] == ["X", "Y"]
    assert result.metadata["abduction_gate_eligible"] is True
    assert output["envelope"].gate_eligible is False


def test_full_linear_factual_inputs_keep_exact_residual_control() -> None:
    """X=1,Y=2 fully observed keeps the exact residual Y(0)=1 control."""
    output = _run_query(
        _linear_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"X": 1.0, "Y": 2.0},
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(1.0)
    assert result.result_std == pytest.approx(0.0)


def test_full_observed_empirical_root_keeps_exact_residual_fallback() -> None:
    """A fully observed parent remains valid when Gaussian posterior is unavailable."""
    output = _run_query(
        _empirical_root_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"X": 1.0, "Y": 2.0},
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(1.0)
    assert result.result_std == pytest.approx(0.0)
    assert result.metadata["abduction_profile"] == "exact_residual_fallback"
    assert result.metadata["abduction_gate_eligible"] is True
    assert output["envelope"].gate_eligible is False


def test_attribution_uses_a_distinct_observational_baseline() -> None:
    """Y=1+3X with target do(X=2) has attribution contrast 6, not zero."""
    output = _run_query(
        _linear_chain(noise_std=0.0, coefficient=3.0),
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(6.0)
    assert result.result_std == pytest.approx(0.0)


def test_attribution_observational_comparator_requires_natural_root_evidence() -> None:
    """A natural comparator cannot gate on an undeclared treatment-root law."""
    complete_scm = _linear_chain(noise_std=0.0, coefficient=3.0)
    scm_without_treatment_root = complete_scm.model_copy(
        update={"mechanisms": [complete_scm.mechanisms[1]]}
    )

    def _run_contrast(comparator: dict[str, object]) -> dict[str, object]:
        return GCMQuery.pure_step(
            SCMQueryData(
                scm_spec=scm_without_treatment_root,
                query={
                    "query_type": "attribution",
                    "treatment_variable": "X",
                    "treatment_value": 2.0,
                    "outcome_variable": "Y",
                    "contrast": {
                        "target": {"type": "atomic", "value": 2.0},
                        "comparator": comparator,
                    },
                    "n_samples": 64,
                },
            ),
            params={
                "__seed__": 117,
                "enable_dowhy_comparison": False,
                "allow_declared_root_hypothesis": True,
            },
        )

    observational_output = _run_contrast({"kind": "observational"})
    observational_result = CausalQueryResult.model_validate(observational_output["query_result"])
    assert observational_result.metadata["declared_root_hypothesis"] == ["X"]
    assert observational_output["envelope"].gate_eligible is False
    assert any(
        "declared root hypothesis" in warning for warning in observational_output["warnings"]
    )

    explicit_output = _run_contrast(
        {
            "kind": "interventional",
            "intervention": {"type": "atomic", "value": 0.0},
        }
    )
    explicit_result = CausalQueryResult.model_validate(explicit_output["query_result"])
    assert explicit_result.metadata["declared_root_hypothesis"] == []
    assert explicit_output["envelope"].gate_eligible is False


def test_twin_partial_gaussian_abduction_reuses_conditioned_noise() -> None:
    """Twin worlds share draws from U|Y=2 instead of a fixed imputed residual."""
    payload = TwinNetworkQueryData(
        scm_spec=_linear_chain(),
        factual_condition={"Y": 2.0},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=0.0,
        outcome_variable="Y",
        n_samples=2048,
    )

    output = TwinNetworkQuery.pure_step(payload, params={"__seed__": 117})

    assert output["twin_network_result"].po_counter_mean == pytest.approx(1.0, abs=0.08)
    assert output["twin_network_result"].po_counter_std == pytest.approx(
        2.0**-0.5,
        abs=0.08,
    )
    assert output["twin_network_result"].ite_std == pytest.approx(0.0, abs=1.0e-10)
    assert output["twin_network_result"].po_correlation == pytest.approx(1.0, abs=1.0e-10)
    assert output["twin_network_result"].metadata["n_abduced_nodes"] == 2
    assert output["twin_network_result"].metadata["abduction_profile"] == (
        "linear_gaussian_posterior"
    )
    assert output["envelope"].gate_eligible is False


def test_partial_unsupported_abduction_is_limited_not_gate_eligible() -> None:
    """An empirical hidden parent cannot masquerade as Gaussian evidence."""
    output = _run_query(
        _empirical_root_chain(),
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"Y": 2.0},
            "n_samples": 128,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.metadata["abduction_profile"] == "limited_imputed_fallback"
    assert result.metadata["abduction_observed_nodes"] == ["Y"]
    assert result.metadata["abduction_gate_eligible"] is False
    assert "abduction_limitation" in result.metadata
    assert output["envelope"].gate_eligible is False
    assert any("limited abduction" in str(item) for item in output["warnings"])


def test_twin_empirical_factual_root_is_not_claimed_exact() -> None:
    """Twin prediction must not gate an observed root it cannot pin."""
    payload = TwinNetworkQueryData(
        scm_spec=_empirical_covariate_scm(),
        factual_condition={"X": 1.0, "Z": 50.0, "Y": 51.0},
        treatment_variable="X",
        factual_treatment_value=1.0,
        counterfactual_treatment_value=0.0,
        outcome_variable="Y",
        n_samples=128,
    )

    output = TwinNetworkQuery.pure_step(payload, params={"__seed__": 117})

    result = output["twin_network_result"]
    assert result.metadata["abduction_profile"] == "limited_unpinned_empirical_root"
    assert result.metadata["abduction_gate_eligible"] is False
    assert "cannot pin observed empirical root" in result.metadata["abduction_limitation"]
    assert output["envelope"].gate_eligible is False


def test_contrast_regime_requires_a_matching_intervention_payload() -> None:
    """Regime tags must agree with the typed intervention payload."""
    atomic = InterventionSpec(type=InterventionType.ATOMIC, value=0.0)
    with pytest.raises(ValueError, match="intervention is required"):
        CausalRegime(kind="interventional")
    with pytest.raises(ValueError, match="must not carry an intervention"):
        CausalRegime(kind="observational", intervention=atomic)


def test_attribution_target_must_be_interventional() -> None:
    """An attribution target cannot silently become an observational contrast."""
    with pytest.raises(ValueError, match="target regime must be interventional"):
        CausalContrastSpec(
            target={"kind": "observational"},
            comparator=CausalRegime(kind="observational"),
        )


def test_legacy_attribution_is_normalized_to_explicit_observational_comparator() -> None:
    """Legacy ATTRIBUTION requests retain an explicit, non-do comparator arm."""
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )

    assert query.contrast is not None
    assert query.contrast.target.type is InterventionType.ATOMIC
    assert query.contrast.target.value == pytest.approx(2.0)
    assert query.contrast.comparator.kind == "observational"
    assert query.contrast.comparator.intervention is None


def test_attribution_contrast_roundtrip_preserves_both_arms() -> None:
    """Serialized contrast requests preserve target/comparator semantics."""
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        contrast=CausalContrastSpec(
            target=InterventionSpec(type=InterventionType.ATOMIC, value=2.0),
            comparator=CausalRegime(
                kind="interventional",
                intervention=InterventionSpec(type=InterventionType.ATOMIC, value=0.0),
            ),
        ),
    )

    restored = CausalQuery.model_validate(query.model_dump(mode="json"))

    assert restored.contrast == query.contrast
    assert restored.contrast is not None
    assert restored.contrast.target.value == pytest.approx(2.0)
    assert restored.contrast.comparator.intervention is not None
    assert restored.contrast.comparator.intervention.value == pytest.approx(0.0)


def test_explicit_do_zero_is_not_observational_attribution_baseline() -> None:
    """An explicit do(X=0) comparator remains distinct from the legacy baseline."""
    output = _run_query(
        _linear_chain(noise_std=0.0, coefficient=3.0, root_intercept=4.0),
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "contrast": {
                "target": {
                    "type": "atomic",
                    "value": 2.0,
                },
                "comparator": {
                    "kind": "interventional",
                    "intervention": {"type": "atomic", "value": 0.0},
                },
            },
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(6.0)
    assert result.metadata["contrast_target"]["type"] == "atomic"
    assert result.metadata["contrast_comparator"]["intervention"]["value"] == pytest.approx(0.0)
    assert output["envelope"].metadata["contrast_comparator"]["kind"] == "interventional"


def test_explicit_identical_target_and_comparator_have_zero_contrast() -> None:
    """Identical explicit do-arms must cancel, even with a nonzero natural root."""
    output = _run_query(
        _linear_chain(noise_std=0.0, coefficient=3.0, root_intercept=4.0),
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "contrast": {
                "target": {"type": "atomic", "value": 2.0},
                "comparator": {
                    "kind": "interventional",
                    "intervention": {"type": "atomic", "value": 2.0},
                },
            },
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_mean == pytest.approx(0.0)
    assert result.result_std == pytest.approx(0.0)
    assert result.result_ci == pytest.approx((0.0, 0.0))
    assert result.metadata["contrast_target"] == {
        "type": "atomic",
        "value": 2.0,
        "distribution": None,
        "bounds": None,
        "shift": None,
        "legal_constraint_id": None,
    }
    assert (
        result.metadata["contrast_comparator"]["intervention"] == result.metadata["contrast_target"]
    )


def test_stochastic_policy_comparison_executes_and_preserves_distinct_arms() -> None:
    """Two non-overlapping stochastic policies contribute to the contrast."""
    output = _run_query(
        _linear_chain(noise_std=0.0, coefficient=3.0, root_intercept=4.0),
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "contrast": {
                "target": {
                    "type": "stochastic",
                    "distribution": "uniform(1,2)",
                },
                "comparator": {
                    "kind": "interventional",
                    "intervention": {
                        "type": "stochastic",
                        "distribution": "uniform(3,4)",
                    },
                },
            },
            "n_samples": 64,
        },
    )

    result = CausalQueryResult.model_validate(output["query_result"])
    assert result.result_distribution is not None
    assert len(result.result_distribution) == 64
    assert result.result_std > 0.0
    assert all(-9.0 <= value <= -3.0 for value in result.result_distribution)
    assert result.metadata["contrast_target"]["type"] == "stochastic"
    assert result.metadata["contrast_target"]["distribution"] == "uniform(1,2)"
    assert result.metadata["contrast_comparator"]["intervention"]["type"] == "stochastic"
    assert result.metadata["contrast_comparator"]["intervention"]["distribution"] == "uniform(3,4)"


def test_legacy_v1_result_loads_and_writes_matching_v1_1_cas_manifest(tmp_path: Path) -> None:
    """A v1.0 CAS payload is read with provenance and re-emitted as v1.1."""
    store = FileSystemCAS(tmp_path / "cas")
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )
    result = CausalQueryResult(
        query=query,
        result_mean=6.0,
        result_std=0.0,
        result_ci=(6.0, 6.0),
        metadata={"legacy_fixture": True},
    )
    legacy_payload = result.model_dump(mode="json")
    legacy_payload["schema_version"] = "1.0"
    legacy_ref = store.put_json(
        legacy_payload,
        PutOptions(
            kind="ir.causal_query_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_query_result", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_legacy_ref = CausalQueryResultRef.model_validate(legacy_ref.model_dump(mode="json"))

    loaded = load_causal_query_result(_ensure_ir_artifact_store(store), typed_legacy_ref)
    assert loaded.schema_version == "1.2"
    assert loaded.metadata["source_schema_version"] == "1.0"
    assert loaded.metadata["legacy_fixture"] is True

    current_ref = persist_causal_query_result(_ensure_ir_artifact_store(store), loaded)
    manifest = store.get_manifest(current_ref.artifact_id)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "1.2"
    assert store.get_bytes(current_ref.artifact_id)


def test_legacy_result_rejects_self_attested_provenance_conflict(tmp_path: Path) -> None:
    """A legacy payload cannot override the CAS manifest's source provenance."""
    store = FileSystemCAS(tmp_path / "cas")
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )
    result = CausalQueryResult(
        query=query,
        result_mean=6.0,
        result_std=0.0,
        result_ci=(6.0, 6.0),
        metadata={
            "source_schema_version": "9.9",
            "source_schema_name": "attacker.claimed.schema",
        },
    )
    legacy_payload = result.model_dump(mode="json")
    legacy_payload["schema_version"] = "1.0"
    legacy_ref = store.put_json(
        legacy_payload,
        PutOptions(
            kind="ir.causal_query_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_query_result", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_legacy_ref = CausalQueryResultRef.model_validate(legacy_ref.model_dump(mode="json"))

    with pytest.raises(ValueError, match=r"provenance|manifest"):
        load_causal_query_result(_ensure_ir_artifact_store(store), typed_legacy_ref)


def test_raw_legacy_result_rejects_self_attested_provenance_without_cas() -> None:
    """Raw legacy DTO validation cannot bless provenance without a CAS manifest."""
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )
    result = CausalQueryResult(
        query=query,
        result_mean=6.0,
        result_std=0.0,
        result_ci=(6.0, 6.0),
    )
    legacy_payload = result.model_dump(mode="json")
    legacy_payload["schema_version"] = "1.0"
    legacy_payload["metadata"] = {
        "source_schema_version": "9.9",
        "source_schema_name": "attacker.claimed.schema",
    }

    with pytest.raises(ValueError, match=r"provenance|manifest"):
        CausalQueryResult.model_validate(legacy_payload)


def test_legacy_provenance_is_manifest_bound_across_result_versions(tmp_path: Path) -> None:
    """Raw DTOs stay unbound while CAS reconciliation rejects v1.1 claims."""
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )
    result = CausalQueryResult(
        query=query,
        result_mean=6.0,
        result_std=0.0,
        result_ci=(6.0, 6.0),
    )
    raw_legacy_payload = result.model_dump(mode="json")
    raw_legacy_payload["schema_version"] = "1.0"
    unbound = CausalQueryResult.model_validate(raw_legacy_payload)
    assert unbound.schema_version == "1.2"
    assert "source_schema_version" not in unbound.metadata

    claimed_legacy_payload = dict(raw_legacy_payload)
    claimed_legacy_payload["metadata"] = {
        "source_schema_version": "1.0",
        "source_schema_name": "plausible.but.unbound",
    }
    with pytest.raises(ValueError, match=r"provenance|manifest"):
        CausalQueryResult.model_validate(claimed_legacy_payload)

    store = FileSystemCAS(tmp_path / "cas")
    v11_payload = result.model_dump(mode="json")
    v11_payload["metadata"] = {
        "source_schema_version": "9.9",
        "source_schema_name": "attacker.claimed.schema",
    }
    v11_ref = store.put_json(
        v11_payload,
        PutOptions(
            kind="ir.causal_query_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.causal_query_result", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_v11_ref = CausalQueryResultRef.model_validate(v11_ref.model_dump(mode="json"))
    with pytest.raises(ValueError, match=r"provenance|manifest"):
        load_causal_query_result(_ensure_ir_artifact_store(store), typed_v11_ref)


def test_causal_result_loader_requires_manifest_schema(tmp_path: Path) -> None:
    """A CAS artifact without schema metadata cannot promote payload self-attestation."""
    store = FileSystemCAS(tmp_path / "cas")
    query = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
    )
    result_payload = CausalQueryResult(
        query=query,
        result_mean=6.0,
        result_std=0.0,
        result_ci=(6.0, 6.0),
    ).model_dump(mode="json")
    result_payload["schema_version"] = "1.0"
    ref = store.put_json(
        result_payload,
        PutOptions(kind="ir.causal_query_result", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    with pytest.raises(ValueError, match=r"manifest|schema"):
        load_causal_query_result(
            _ensure_ir_artifact_store(store),
            CausalQueryResultRef.model_validate(ref.model_dump(mode="json")),
        )


def test_causal_query_producer_reconciles_envelope_with_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted envelope arms/status are derived from the typed result, not output text."""
    ctx = _build_execution_context(tmp_path, run_id="R_scm02_envelope_reconcile")
    scm_ref = persist_structural_causal_model_spec(
        _ensure_ir_artifact_store(ctx.store), _linear_chain()
    )

    def _fake_run_job(*args: object, **kwargs: object) -> JobResult:
        del args
        method_state = kwargs["method_state"]
        query = method_state.query
        result = CausalQueryResult(
            query=query,
            result_mean=6.0,
            result_std=0.0,
            result_ci=(6.0, 6.0),
            result_distribution=[6.0],
        )
        mismatched_envelope = result.to_uncertainty_envelope().model_dump(mode="json")
        mismatched_envelope["gate_eligible"] = False
        mismatched_envelope["metadata"]["contrast_comparator"] = {
            "kind": "interventional",
            "intervention": {"type": "atomic", "value": 0.0},
        }
        payload = {
            "causal_query_result": result.model_dump(mode="json"),
            "query_result": result.model_dump(mode="json"),
            "envelope": mismatched_envelope,
        }
        method_ref = ctx.store.put_json(
            payload,
            PutOptions(
                kind="scientist.method_result.causal.structural",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
                inputs=[InputRef(artifact_id=scm_ref.artifact_id, role="input:scm_spec")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return JobResult(
            job_key=JobKey(value="job:test:scm02-envelope-reconcile"),
            method_result_ref=method_ref,
            final_state=payload,
            issues=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_scm02_envelope_reconcile",
        params={
            "causal_query": {
                "query_type": "attribution",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "contrast": {
                    "target": {"type": "atomic", "value": 2.0},
                    "comparator": {"kind": "observational"},
                },
                "n_samples": 64,
            },
            "structural_causal_model_ref": scm_ref.model_dump(mode="json"),
        },
    )

    outcome = RunCausalQueriesNode().execute(ctx, state)

    assert outcome.status == "ok"
    envelope_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF]
    persisted = load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), envelope_ref)
    assert persisted.gate_eligible is False
    assert persisted.metadata["contrast_comparator"]["kind"] == "observational"


def test_attribution_comparator_is_typed_and_legacy_atomic_value_is_preserved() -> None:
    """Comparator omissions fail closed while legacy target mapping remains compatible."""
    base_payload = {
        "query_type": "attribution",
        "treatment_variable": "X",
        "treatment_value": 2.0,
        "outcome_variable": "Y",
        "contrast": {
            "target": {"type": "atomic", "value": 2.0},
        },
    }
    with pytest.raises(ValueError, match="value is required"):
        CausalQuery.model_validate(
            {
                **base_payload,
                "contrast": {
                    **base_payload["contrast"],
                    "comparator": {
                        "kind": "interventional",
                        "intervention": {"type": "atomic"},
                    },
                },
            }
        )
    with pytest.raises(ValueError, match="distribution is required"):
        CausalQuery.model_validate(
            {
                **base_payload,
                "contrast": {
                    **base_payload["contrast"],
                    "comparator": {
                        "kind": "interventional",
                        "intervention": {"type": "stochastic"},
                    },
                },
            }
        )

    legacy = CausalQuery.model_validate(
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "intervention_spec": {"type": "atomic"},
        }
    )
    assert legacy.intervention_spec is not None
    assert legacy.intervention_spec.value == pytest.approx(2.0)
    assert legacy.contrast is not None
    assert legacy.contrast.target.value == pytest.approx(2.0)
    assert legacy.contrast.comparator.kind == "observational"

    legacy_instance = CausalQuery.model_validate(
        {
            "query_type": "attribution",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "intervention_spec": InterventionSpec(type=InterventionType.ATOMIC),
        }
    )
    assert legacy_instance.intervention_spec is not None
    assert legacy_instance.intervention_spec.value == pytest.approx(2.0)
    assert legacy_instance.contrast is not None
    assert legacy_instance.contrast.target.value == pytest.approx(2.0)


def test_causal_query_producer_persists_typed_contrast_and_v1_1_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real query node carries both arms through producer persistence."""
    ctx = _build_execution_context(tmp_path, run_id="R_scm02_producer")
    scm_ref = persist_structural_causal_model_spec(
        _ensure_ir_artifact_store(ctx.store), _linear_chain()
    )

    def _fake_run_job(*args: object, **kwargs: object) -> JobResult:
        del args
        method_state = kwargs["method_state"]
        query = method_state.query
        result = CausalQueryResult(
            query=query,
            result_mean=6.0,
            result_std=0.0,
            result_ci=(6.0, 6.0),
            result_distribution=[6.0],
        )
        payload = {
            "causal_query_result": result.model_dump(mode="json"),
            "query_result": result.model_dump(mode="json"),
            "envelope": result.to_uncertainty_envelope().model_dump(mode="json"),
        }
        method_ref = ctx.store.put_json(
            payload,
            PutOptions(
                kind="scientist.method_result.causal.structural",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
                inputs=[InputRef(artifact_id=scm_ref.artifact_id, role="input:scm_spec")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return JobResult(
            job_key=JobKey(value="job:test:scm02-producer"),
            method_result_ref=method_ref,
            final_state=payload,
            issues=[],
        )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.ensure_causal_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.run_job",
        _fake_run_job,
    )

    state = ExperimentState(
        run_id="R_scm02_producer",
        params={
            "causal_query": {
                "query_type": "attribution",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "contrast": {
                    "target": {"type": "atomic", "value": 2.0},
                    "comparator": {"kind": "observational"},
                },
                "n_samples": 64,
            },
            "structural_causal_model_ref": scm_ref.model_dump(mode="json"),
        },
    )

    outcome = RunCausalQueriesNode().execute(ctx, state)

    assert outcome.status == "ok"
    result_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF]
    manifest = ctx.store.get_manifest(result_ref.artifact_id)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "1.2"
    loaded = load_causal_query_result(
        _ensure_ir_artifact_store(ctx.store),
        CausalQueryResultRef.model_validate(result_ref.model_dump(mode="json")),
    )
    assert loaded.query.contrast is not None
    assert loaded.query.contrast.comparator.kind == "observational"
    assert loaded.metadata["contrast_target"]["value"] == pytest.approx(2.0)


def test_causal_ensemble_rejects_mixed_canonical_contrast_before_persisting(
    tmp_path: Path,
) -> None:
    """A mixed-member target/comparator set fails before ensemble aggregation."""
    ctx = _build_execution_context(tmp_path, run_id="R_scm02_mixed_ensemble")
    scm_ref = persist_structural_causal_model_spec(
        _ensure_ir_artifact_store(ctx.store), _linear_chain()
    )
    graph_ref = persist_causal_graph_model(
        _ensure_ir_artifact_store(ctx.store), _linear_chain().graph
    )
    target = InterventionSpec(type=InterventionType.ATOMIC, value=2.0)
    observational = CausalQuery(
        query_type=QueryType.ATTRIBUTION,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        contrast=CausalContrastSpec(
            target=target,
            comparator=CausalRegime(kind="observational"),
        ),
    )
    explicit_zero = observational.model_copy(
        update={
            "contrast": CausalContrastSpec(
                target=target,
                comparator=CausalRegime(
                    kind="interventional",
                    intervention=InterventionSpec(type=InterventionType.ATOMIC, value=0.0),
                ),
            )
        }
    )
    result_refs = [
        persist_causal_query_result(
            _ensure_ir_artifact_store(ctx.store),
            CausalQueryResult(
                query=query,
                result_mean=6.0,
                result_std=0.0,
                result_ci=(6.0, 6.0),
                result_distribution=[6.0],
            ),
        )
        for query in (observational, explicit_zero)
    ]
    state = ExperimentState(
        run_id="R_scm02_mixed_ensemble",
        params={
            "causal_ensemble_enabled": True,
            "causal_ensemble_members": [
                {
                    "structural_causal_model_spec_ref": scm_ref.model_dump(mode="json"),
                    "graph_ref": graph_ref.model_dump(mode="json"),
                    "causal_query_result_ref": ref.model_dump(mode="json"),
                }
                for ref in result_refs
            ],
        },
    )

    outcome = RunCausalEnsembleNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "mismatched canonical" in outcome.error.message
    assert ARTIFACT_CAUSAL_ENSEMBLE_REF not in outcome.state.artifacts_index
