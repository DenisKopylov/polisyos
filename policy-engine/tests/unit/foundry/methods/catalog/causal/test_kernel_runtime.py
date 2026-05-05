from __future__ import annotations

import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand
from polisyos.foundry.methods.catalog.causal.kernel_lowering import build_kernel_estimator_spec
from polisyos.foundry.methods.catalog.causal.kernel_methods import KernelCMEPluginEstimator
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus, ProofBundle
from polisyos.ir.analytics.estimand import make_backdoor_estimand
from polisyos.ir.passes import KernelLoweringPass, PassContext


def _synthetic_state(seed: int = 7, n_obs: int = 160) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_obs, 2))
    logits = 0.8 * x[:, 0] - 0.3 * x[:, 1]
    probs = 1.0 / (1.0 + np.exp(-logits))
    treatment = rng.binomial(1, probs).astype(float)
    outcome = 0.9 * treatment + 0.5 * x[:, 0] + 0.2 * x[:, 1] + rng.normal(scale=0.35, size=n_obs)
    return {
        "covariates": x,
        "treatment": treatment,
        "outcome": outcome,
    }


def test_kernel_lowering_pass_emits_ready_spec() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )
    context = (
        PassContext()
        .with_surface("estimand_ast", ast)
        .with_surface(
            "kernel_lowering_metadata",
            {
                "kernel_lowering_requested": True,
                "kernel_template": "backdoor_cme",
                "distributional_query_kind": "interventional_law",
            },
        )
    )

    result = KernelLoweringPass().run(context)
    spec = result.analysis_updates["kernel_estimator_spec"]

    assert spec.template.value == "backdoor_cme"
    assert spec.lowering_disposition.value == "ready"
    assert spec.variable_roles["treatment"] == ("T",)
    assert spec.variable_roles["outcome"] == ("Y",)


def test_kernel_methods_register_under_kernel_namespaces() -> None:
    MethodRegistry.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()

    kernel_names = {sig.name for sig in registry.query(namespace="causal.kernel")}
    nuisance_names = {sig.name for sig in registry.query(namespace="causal.kernel.nuisance")}

    assert {
        "cme_plugin",
        "frontdoor_cme",
        "transport_cme",
        "dr_cme",
        "kiv",
        "proximal_minimax",
        "kernel_semantics_diagnostics",
        "regularization_diagnostics",
        "effect_test",
        "refusal",
    }.issubset(kernel_names)
    assert {
        "fit_cme_y_given_xz",
        "fit_cme_m_given_x",
        "fit_cme_y_given_mx",
        "fit_density_ratio",
        "fit_propensity",
        "fit_kiv_first_stage",
        "fit_kiv_second_stage",
        "solve_proximal_bridge",
    }.issubset(nuisance_names)


def test_kernel_cme_plugin_returns_successful_distributional_report() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )
    state = _synthetic_state()
    spec = build_kernel_estimator_spec(
        ast,
        shape="backdoor",
        identification_metadata={
            "kernel_lowering_requested": True,
            "distributional_query_kind": "interventional_law",
            "variable_roles": {"treatment": ("treatment",), "outcome": ("outcome",)},
        },
    )

    output = KernelCMEPluginEstimator.pure_step(
        state,
        {"kernel_spec": spec.model_dump(mode="json"), "__seed__": 11},
    )

    report = output["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert output["kernel_report"]["effect_norm"] > 0.0
    assert output["result"]["characteristic"] is True


def test_kernel_compile_execute_and_audit_persists_kernel_spec(tmp_path) -> None:
    MethodRegistry.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    store = FileSystemCAS(tmp_path / "cas")
    engine = CausalEngine(registry=registry, artifact_store=store)

    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )
    recommendation, executor_graph = compile_estimand(
        ast,
        run_id="kernel-stage14",
        n_obs=160,
        identification_metadata={
            "kernel_lowering_requested": True,
            "kernel_template": "dr_cme",
            "distributional_query_kind": "interventional_law",
            "binary_treatment": True,
            "variable_roles": {"treatment": ("treatment",), "outcome": ("outcome",)},
        },
    )
    report, node_outputs = engine.estimate(executor_graph, _synthetic_state())

    assert recommendation.strategy.value == "dr_cme"
    assert report is not None
    assert report.status is EstimationStatus.SUCCESS

    bundle = engine.audit(
        None,
        report,
        run_id="kernel-stage14",
        executor_graph=executor_graph,
        node_outputs=node_outputs,
        proof_bundle=ProofBundle(
            proof_status="identified",
            proof_stratum="A0_trusted",
            theorem_family="id_algorithm",
            completeness_regime="complete",
            implementation_coverage="stage14.1",
            estimand_ast=ast.model_dump(mode="json"),
        ),
    )

    assert bundle.kernel_estimator_spec_ref is not None
    assert bundle.method_config["kernel_template"] == "dr_cme"
    assert bundle.diagnostic_scores["kernel_effect_norm"] > 0.0
    assert bundle.diagnostic_scores["kernel_characteristic"] == 1.0
