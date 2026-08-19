from __future__ import annotations

import copy
import importlib.util
from dataclasses import replace

import pytest

from polisyos.foundry.extensions.discovery import discover_foundry_method_components
from polisyos.foundry.extensions.registry import bootstrap_foundry_method_registry
from polisyos.foundry.methods.base import MethodMetadata
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog import snapshot as snapshot_module
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from polisyos.foundry.methods.catalog.snapshot import (
    MethodCatalogDiscoveryProvenanceError,
    build_method_capability_matrix,
    build_method_catalog_provenance_manifest,
    build_method_catalog_runtime_identity,
    build_method_catalog_snapshot,
    method_catalog_provenance_id,
)
from polisyos.foundry.methods.selection import reachable_value_method_fqns
from polisyos.foundry.methods.selection.registry import MethodRegistry, registry_scope

_Y0_INSTALLED = importlib.util.find_spec("y0") is not None


def test_governed_snapshot_consumes_supplied_builtin_provenance_without_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        monkeypatch.setattr(
            "polisyos.foundry.methods.catalog.snapshot.ensure_all_methods_registered",
            lambda _registry: pytest.fail("governed snapshot reran ambient discovery"),
        )

        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    assert report.discovery_manifest is not None
    assert report.discovery_manifest.is_bound is True
    assert tuple(entry.fqn for entry in snapshot.entries) == report.registry_fqns


def test_value_method_denominator_consumes_controlled_snapshot_without_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )
        monkeypatch.setattr(
            "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
            lambda _registry: pytest.fail("controlled denominator reran ambient discovery"),
        )

        methods = reachable_value_method_fqns(
            registry=registry,
            catalog_snapshot=snapshot,
        )

    assert methods
    assert set(methods) < set(report.registry_fqns)


def test_governed_snapshot_fails_closed_without_discovery_provenance() -> None:
    with (
        registry_scope() as registry,
        pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_discovery_provenance_missing",
        ),
    ):
        build_method_catalog_snapshot(
            registry=registry,
            require_bound_discovery=True,
        )


def test_governed_snapshot_rejects_registry_mutation_after_admission() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        registry.unregister(report.registry_fqns[0])

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_membership_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_governed_snapshot_rejects_same_fqn_override_after_admission() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        original = registry.get(report.registry_fqns[0])

        class AmbientOverride:
            signature = original.signature
            metadata = replace(
                original.metadata,
                description="ambient same-FQN override with markers intact",
            )

            @staticmethod
            def pure_step(state, params):
                return original.pure_step(state, params)

        registry.register(AmbientOverride, override=True)

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_content_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_governed_snapshot_rejects_same_fqn_override_during_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        target_fqn = report.registry_fqns[0]
        original = registry.get(target_fqn)
        from polisyos.foundry.methods.catalog import snapshot as snapshot_module

        real_available_backends = snapshot_module._available_execution_backends

        def _override_after_admission() -> set[str]:
            class MidBuildOverride:
                signature = original.signature
                metadata = replace(
                    original.metadata,
                    description="same-FQN override injected after admission",
                )

                @staticmethod
                def pure_step(state, params):
                    return original.pure_step(state, params)

            registry.register(MidBuildOverride, override=True)
            return real_available_backends()

        monkeypatch.setattr(
            snapshot_module,
            "_available_execution_backends",
            _override_after_admission,
        )

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_content_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_catalog_provenance_rejects_false_ambient_policy_and_binds_registry() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    assert report.discovery_manifest is not None
    with pytest.raises(
        MethodCatalogDiscoveryProvenanceError,
        match="catalog_ambient_source_policy_mismatch",
    ):
        build_method_catalog_provenance_manifest(
            snapshot,
            registry_report=report,
            ambient_manifest=report.discovery_manifest,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    provenance = build_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )

    assert provenance["governed_discovery"]["registry_binding_sha256"] == (
        report.registry_binding_sha256
    )
    assert provenance["provenance_id"] == method_catalog_provenance_id(provenance)


def test_governed_provenance_projection_keeps_ambient_custody_non_decisive() -> None:
    """Ambient observation drift must move raw custody but not governed identity."""

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    recorded = build_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )
    changed = copy.deepcopy(recorded)
    changed["ambient_discovery"]["manifest_id"] = "component_discovery_manifest_ambient_other"
    changed["ambient_discovery"]["component_count"] += 1
    changed["ambient_discovery"]["unbound_inputs"].append(
        "discovery_error:entry_point:example.weighted_average:ModuleNotFoundError"
    )
    changed["ambient_discovery"]["admission"]["status"] = "declared_not_admitted"
    membership = next(
        row
        for row in changed["predicate_provenance"]
        if row["predicate"] == "ambient.discovered_component_membership"
    )
    membership["classification"] = (
        "not_established"
        if membership["classification"] == "recomputed"
        else "recomputed"
    )
    changed["provenance_id"] = method_catalog_provenance_id(changed)

    assert recorded["provenance_id"] != changed["provenance_id"]
    assert (
        snapshot_module.method_catalog_governed_provenance_projection(recorded)
        == snapshot_module.method_catalog_governed_provenance_projection(changed)
    )
    assert snapshot_module.method_catalog_governed_provenance_id(
        recorded
    ) == snapshot_module.method_catalog_governed_provenance_id(changed)
    assert changed["ambient_discovery"]["unbound_inputs"]


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        ("missing_parent_admission", "catalog_ambient_input_not_quarantined"),
        ("governing_parent_admission", "catalog_ambient_input_not_quarantined"),
        ("contradictory_predicate_admission", "catalog_predicate_provenance_invalid"),
    ),
)
def test_governed_provenance_projection_fails_closed_on_invalid_admission(
    mutation: str,
    expected_error: str,
) -> None:
    """Only a complete structural quarantine may remove ambient observations."""

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    provenance = build_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )
    if mutation == "missing_parent_admission":
        provenance["ambient_discovery"].pop("admission")
    elif mutation == "governing_parent_admission":
        provenance["ambient_discovery"]["admission"][
            "included_in_governed_denominator"
        ] = True
    else:
        predicate = next(
            row
            for row in provenance["predicate_provenance"]
            if row["predicate"] == "ambient.discovered_component_membership"
        )
        predicate["decisive"] = True

    with pytest.raises(MethodCatalogDiscoveryProvenanceError, match=expected_error):
        snapshot_module.method_catalog_governed_provenance_projection(provenance)


def test_catalog_runtime_identity_names_packages_and_backend_fingerprints() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    identity = build_method_catalog_runtime_identity(snapshot)

    assert identity["schema_version"] == "policyos.method_catalog_runtime_identity.v1"
    assert identity["identity_id"].startswith("method_catalog_runtime_identity_")
    assert identity["entry_runtime_binding_count"] == len(snapshot.entries)
    assert identity["backend_fingerprints"]
    runtime_packages = {row["name"]: row for row in identity["runtime_packages"]}
    assert runtime_packages["python"]["version"]
    assert runtime_packages["policy-engine"]["version"]
    expected_fingerprints = {
        (
            str(entry.capability_matrix["runtime_posture"]["backend"]),
            str(entry.capability_matrix["runtime_posture"]["fingerprint"]),
        )
        for entry in snapshot.entries
    }
    assert {
        (str(row["backend"]), str(row["fingerprint"])) for row in identity["backend_fingerprints"]
    } == expected_fingerprints


def test_catalog_runtime_identity_fails_closed_without_policy_engine_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.snapshot.safe_version",
        lambda package_name: None if package_name == "policy-engine" else "test-version",
    )

    with pytest.raises(
        MethodCatalogDiscoveryProvenanceError,
        match="catalog_runtime_package_identity_missing:policy-engine",
    ):
        build_method_catalog_runtime_identity(snapshot)


def test_method_catalog_snapshot_contains_stable_entries() -> None:
    ensure_all_methods_registered()
    registered_fqns = tuple(
        sorted(entry.fqn for entry in MethodRegistry.get_instance().snapshot().entries())
    )
    first = build_method_catalog_snapshot(run_id="R_catalog")
    second = build_method_catalog_snapshot(run_id="R_catalog")

    first_fqns = [entry.fqn for entry in first.entries]
    second_fqns = [entry.fqn for entry in second.entries]

    assert first_fqns
    assert tuple(first_fqns) == registered_fqns
    assert first_fqns == second_fqns
    assert first.snapshot_id == second.snapshot_id
    assert first.schema_version == "2.0"
    first_value_capable = {
        entry.fqn
        for entry in first.entries
        if entry.capability_matrix.get("value_projection_contracts")
    }
    second_value_capable = {
        entry.fqn
        for entry in second.entries
        if entry.capability_matrix.get("value_projection_contracts")
    }
    assert len(first.entries) >= 382
    assert first_value_capable == second_value_capable
    assert len(first_value_capable) == 55


def test_value_projection_and_joint_simulation_output_axes_compose() -> None:
    class _ComposedOutputMethod:
        signature = replace(
            BayesianLinearRegressionEstimator.signature,
            name="composed_output_axes",
            namespace="tests.catalog",
        )
        metadata = MethodMetadata(
            description="Prove independent output-contract axes compose.",
            assumptions={
                "joint_simulation_output_shape": "time_series_trajectory",
                "joint_simulation_equilibrium_semantics": "dynamic_SCM",
            },
        )

        @staticmethod
        def pure_step(state, params):
            del params
            return state

    with registry_scope() as registry:
        registry.register(_ComposedOutputMethod)
        snapshot = build_method_catalog_snapshot(registry=registry)
        entry = next(
            item for item in snapshot.entries if item.fqn == _ComposedOutputMethod.signature.fqn
        )

    assert entry.capability_matrix["value_projection_contracts"]
    assert "joint_simulation_output_shape" in entry.assumptions
    assert "joint_simulation_equilibrium_semantics" in entry.assumptions
    assert (
        _ComposedOutputMethod.metadata.assumptions["joint_simulation_output_shape"]
        == "time_series_trajectory"
    )
    assert (
        _ComposedOutputMethod.metadata.assumptions["joint_simulation_equilibrium_semantics"]
        == "dynamic_SCM"
    )


@pytest.mark.skipif(
    _Y0_INSTALLED, reason="y0 is installed — symbolic_identify reports causal_available=True"
)
def test_method_catalog_snapshot_carries_causal_capability_posture() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    assert snapshot.causal_capability_hash
    assert snapshot.causal_runtime_posture

    symbolic_entry = next(
        entry for entry in snapshot.entries if "causal.transport.symbolic_identify@" in entry.fqn
    )
    assert symbolic_entry.causal_capability_requirements
    assert symbolic_entry.causal_available is False
    assert symbolic_entry.causal_disabled_reasons


def test_method_catalog_snapshot_includes_non_causal_families() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    fqns = {entry.fqn for entry in snapshot.entries}
    assert "econometrics.panel.fixed_effects@1.0.0" in fqns
    assert "econometrics.panel.difference_gmm@1.0.0" in fqns
    assert "econometrics.panel.system_gmm@1.0.0" in fqns
    assert "econometrics.timeseries.vecm@1.0.0" in fqns
    assert "optimization.linear.resource_lp@1.0.0" in fqns
    assert "optimization.integer.budget_milp@1.0.0" in fqns
    assert "optimization.io.leontief_io@1.0.0" in fqns
    assert "optimization.dynamic.dynamic_programming@1.0.0" in fqns
    assert "ml.regression.elastic_net@1.0.0" in fqns
    assert "ml.regression.gaussian_process@1.0.0" in fqns
    assert "ml.deep.tabular_transformer@1.0.0" in fqns
    assert "ml.deep.ft_transformer@1.0.0" in fqns
    assert "ml.deep.tabnet@1.0.0" in fqns
    assert "ml.graph.graph_conv@1.0.0" in fqns
    assert "ml.self_supervised.masked_autoencoder@1.0.0" in fqns
    assert "microsim.static.static_microsim@1.0.0" in fqns
    assert "microsim.policy.tax_benefit_calculator@1.0.0" in fqns
    assert "spatial.autocorrelation.moran_i@1.0.0" in fqns
    assert "network.community.community_detection@1.0.0" in fqns
    assert "bayesian.regression.linear_regression@1.0.0" in fqns
    assert "bayesian.timeseries.autoregression@1.0.0" in fqns
    assert "bayesian.regression.hierarchical@1.0.0" in fqns
    assert "bayesian.sampling.hmc@1.0.0" in fqns
    assert "bayesian.sampling.nuts@1.0.0" in fqns
    assert "bayesian.nonparametric.gaussian_mixture@1.0.0" in fqns
    assert "bayesian.nonparametric.dirichlet_process_mixture@1.0.0" in fqns
    assert "distributional.inequality.atkinson@1.0.0" in fqns
    assert "survey.weighting.horvitz_thompson@1.0.0" in fqns
    assert "forecasting.univariate.exponential_smoothing@1.0.0" in fqns
    assert "validation.probabilistic.normal_scores@1.0.0" in fqns
    assert "sensitivity.global.sobol_first_order@1.0.0" in fqns
    assert "spatial.interpolation.gaussian_process_kriging@1.0.0" in fqns
    assert "spatial.interpolation.idw@1.0.0" in fqns
    assert "spatial.panel.slx@1.0.0" in fqns
    assert "spatial.panel.sarar@1.0.0" in fqns
    assert "spatial.accessibility.two_step_fca@1.0.0" in fqns
    assert "spatial.microsim.smsm@1.0.0" in fqns
    assert "spatial.design.maup_profile@1.0.0" in fqns
    assert "spatial.design.zone_balance@1.0.0" in fqns
    assert "microsim.calibration.inverse_behavioral_calibration@1.0.0" in fqns

    # Phase 0: Policy domain
    assert "policy.welfare.cost_benefit_analysis@1.0.0" in fqns
    assert "policy.welfare.atkinson_swf@1.0.0" in fqns
    assert "policy.welfare.sufficient_statistics_welfare@1.0.0" in fqns
    assert "policy.mcda.topsis@1.0.0" in fqns
    assert "policy.mcda.rank_stability@1.0.0" in fqns
    assert "policy.mcda.robust_topsis@1.0.0" in fqns
    assert "policy.mcda.robust_ahp@1.0.0" in fqns
    assert "policy.mcda.robust_electre@1.0.0" in fqns
    assert "policy.evaluation.budget_impact@1.0.0" in fqns
    assert "policy.evaluation.foundation_model_policy_analysis@1.0.0" in fqns
    assert "policy.macro.fiscal_multiplier@1.0.0" in fqns
    assert "policy.macro.krusell_smith_lite@1.0.0" in fqns
    assert "policy.public_finance.optimal_linear_tax@1.0.0" in fqns
    assert "policy.agent_sim.mean_field_equilibrium@1.0.0" in fqns

    # Phase 1: Causal expansion
    assert "causal.treatment_effects.aipw@1.0.0" in fqns
    assert "causal.treatment_effects.tmle@1.0.0" in fqns
    assert "causal.treatment_effects.ipw@1.0.0" in fqns
    assert "causal.proximal.proximal_bridge@1.0.0" in fqns
    assert "causal.proximal.spatial_proximal_bridge@1.0.0" in fqns
    assert "causal.distributional.unconditional_qte@1.0.0" in fqns
    assert "causal.interference.network_cate@1.0.0" in fqns
    assert "causal.inference.did.callaway_santanna@1.0.0" in fqns
    assert "causal.inference.did.sun_abraham@1.0.0" in fqns
    assert "causal.bounds.manski@1.0.0" in fqns
    assert "causal.bounds.lee@1.0.0" in fqns
    assert "causal.mediation.causal_mediation@1.0.0" in fqns
    assert "causal.advanced.shift_share_iv@1.0.0" in fqns
    assert "causal.hte.dr_learner@1.0.0" in fqns

    # Phase 2: Econometrics expansion
    assert "econometrics.discrete_choice.logit@1.0.0" in fqns
    assert "econometrics.discrete_choice.probit@1.0.0" in fqns
    assert "econometrics.selection.heckman@1.0.0" in fqns
    assert "econometrics.count.poisson@1.0.0" in fqns
    assert "econometrics.semiparametric.robinson@1.0.0" in fqns
    assert "econometrics.high_dimensional.post_lasso@1.0.0" in fqns

    # Phase 3: Distributional expansion
    assert "distributional.inequality.theil@1.0.0" in fqns
    assert "distributional.inequality.palma_ratio@1.0.0" in fqns
    assert "distributional.mobility.transition_matrix@1.0.0" in fqns
    assert "distributional.mobility.transition_matrix_attrition_adjusted@1.0.0" in fqns
    assert "distributional.mobility.sequential_lifetime_transition_matrix@1.0.0" in fqns
    assert "distributional.mobility.refreshment_transition_matrix@1.0.0" in fqns
    assert "distributional.polarization.esteban_ray@1.0.0" in fqns

    # Phase 4: Sensitivity expansion
    assert "sensitivity.global.morris@1.0.0" in fqns
    assert "sensitivity.specification.specification_curve@1.0.0" in fqns
    assert "sensitivity.global.dependent_copula_sensitivity@1.0.0" in fqns

    # Phase 5: Survey expansion
    assert "survey.adaptive.adaptive_calibrated_ipw@1.0.0" in fqns
    assert "survey.adaptive.adaptive_augmented@1.0.0" in fqns
    assert "survey.estimation.causal_frontier_fay_herriot@1.0.0" in fqns
    assert "survey.estimation.fay_herriot@1.0.0" in fqns
    assert "survey.imputation.mice@1.0.0" in fqns
    assert "survey.design.complex_survey@1.0.0" in fqns
    assert "microsim.imputation.mnar_income_bounds@1.0.0" in fqns

    # Phase 6: Minor expansions
    assert "simulation.inference.bootstrap@1.0.0" in fqns
    assert "optimization.combinatorial.knapsack@1.0.0" in fqns
    assert "optimization.game_theory.nash_equilibrium@1.0.0" in fqns


def test_method_catalog_snapshot_exposes_v2_capability_matrix_fields() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item for item in snapshot.entries if item.fqn == "survey.weighting.horvitz_thompson@1.0.0"
    )

    assert entry.execution_backend == "numpy"
    assert entry.kind == "pure"
    assert entry.family == "survey.weighting"
    assert entry.variant == "horvitz_thompson"
    assert entry.fidelity_tier == "high"
    assert set(entry.data_modalities) == {"survey"}
    assert entry.runtime_stack == ["numpy"]
    assert entry.determinism_tier == "library_deterministic"
    assert entry.required_deps == ["numpy"]
    assert entry.optional_deps == []
    assert entry.fallback_policy == "none"
    assert entry.side_effect_profile == "none"
    assert entry.runnable is True
    assert entry.disabled_reasons == []
    assert entry.dependency_posture["all_required_available"] is True
    assert entry.capability_matrix["kind"] == "pure"
    assert entry.capability_matrix["execution_backend"] == "numpy"
    assert entry.capability_matrix["required_deps"] == ["numpy"]
    assert entry.capability_matrix["runnable"] is True
    assert entry.truthfulness_tier == "unverified"
    assert entry.implementation_depth_tier == "production_method"
    assert entry.effect_semantics["method_kind"] == "pure"
    assert entry.shape_semantics["input_arity"] >= 0
    assert entry.dependency_semantics["hard_requires"] == []
    assert entry.capability_matrix["declared_determinism_tier"] == "library_deterministic"
    assert entry.capability_matrix["runtime_determinism_tier"] == "library_deterministic"
    assert entry.capability_matrix["replay_semantics"]
    assert entry.capability_matrix["tolerance_budget"]["semantic_mode"] == "library_exact_cpu"
    assert entry.capability_matrix["runtime_posture"]["backend"] == "numpy"
    assert entry.capability_matrix["runtime_posture"]["available"] is True
    assert entry.capability_matrix["runtime_posture"]["fingerprint"]
    assert entry.capability_matrix["effective_truthfulness_tier"] == "unverified"
    assert entry.capability_matrix["implementation_depth_tier"] == "production_method"


def test_method_catalog_snapshot_uses_conservative_effective_determinism_tier() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item
        for item in snapshot.entries
        if item.fqn == "bayesian.regression.linear_regression@1.0.0"
    )

    assert entry.capability_matrix["declared_determinism_tier"] == "statistical"
    assert entry.capability_matrix["runtime_determinism_tier"] == "statistical"
    assert entry.determinism_tier == "statistical"
    assert entry.capability_matrix["replay_semantics"].startswith("Replay is seed-stable")


def test_method_catalog_snapshot_exposes_declared_truthfulness_scope_from_metadata() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item
        for item in snapshot.entries
        if item.fqn == "bayesian.regression.linear_regression@1.0.0"
    )

    assert entry.declared_truthfulness_tier == "asymptotic"
    assert entry.truthfulness_scope == "posterior"
    assert entry.truthfulness_tier == "asymptotic"
    assert entry.truthfulness_status == "catalog_only"


def test_method_catalog_snapshot_marks_hmc_and_nuts_as_catalog_only_asymptotic() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    for fqn in (
        "bayesian.sampling.hmc@1.0.0",
        "bayesian.sampling.nuts@1.0.0",
    ):
        entry = next(item for item in snapshot.entries if item.fqn == fqn)
        assert entry.declared_truthfulness_tier == "asymptotic"
        assert entry.truthfulness_scope == "posterior"
        assert entry.truthfulness_tier == "asymptotic"
        assert entry.truthfulness_status == "catalog_only"
        assert entry.capability_matrix["declared_truthfulness_tier"] == "asymptotic"
        assert entry.capability_matrix["truthfulness_tier"] == "asymptotic"
        assert entry.capability_matrix["truthfulness_status"] == "catalog_only"


def test_method_catalog_snapshot_marks_tabular_transformer_as_heuristic_baseline() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item for item in snapshot.entries if item.fqn == "ml.deep.tabular_transformer@1.0.0"
    )

    assert entry.truthfulness_tier == "unverified"
    assert entry.implementation_depth_tier == "heuristic_baseline"
    assert "baseline" in entry.implementation_depth_notes.lower()


def test_method_capability_matrix_exports_truthfulness_and_semantics() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    matrix = build_method_capability_matrix(snapshot, runnable_only=True)
    row = next(item for item in matrix if item["fqn"] == "survey.weighting.horvitz_thompson@1.0.0")

    assert row["truthfulness_tier"] == "unverified"
    assert row["implementation_depth_tier"] == "production_method"
    assert row["effect_semantics"]["method_kind"] == "pure"
    assert row["dependency_semantics"]["hard_requires"] == []
