from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.local_independence import (
    CensoringInterventionSpec,
    EliminabilityCheck,
    EliminabilityStep,
    IndependentCensoringCheck,
    IntensityModelRequirement,
    LocalIndependenceEdge,
    LocalIndependenceGraphicalChecks,
    LocalIndependenceGraphSpec,
    LocalIndependenceIdentificationSpec,
    LocalIndependenceRuntimeRequirements,
    LocalIndependenceTarget,
    LocalIndependenceWeightingCertificate,
    TreatmentIntensityInterventionSpec,
    load_local_independence_weighting_certificate,
    persist_local_independence_weighting_certificate,
)


def _certificate() -> LocalIndependenceWeightingCertificate:
    return LocalIndependenceWeightingCertificate(
        verification_status="identified",
        theorem_family="local_independence_weighting_v1",
        target=LocalIndependenceTarget(
            functional="cumulative_incidence_difference",
            outcome_process="Y",
            horizon_start=0.0,
            horizon_end=365.0,
            time_scale="days",
        ),
        graph=LocalIndependenceGraphSpec(
            process_family="counting_process",
            representation="LIG_or_muDMG",
            separation_criterion="mu",
            graph_ref="sha256:test-graph",
            nodes=("X", "Y", "C", "L"),
            edges=(LocalIndependenceEdge(src="X", dst="Y"),),
            latent_nodes=("U",),
        ),
        treatment_intervention=TreatmentIntensityInterventionSpec(
            node="X",
            predictable_wrt=("L_history", "X_history"),
            lambda_pi_ref="artifact://lambda-pi",
        ),
        censoring_intervention=CensoringInterventionSpec(
            node="C",
            mode="prevent",
            value=0.0,
        ),
        identification=LocalIndependenceIdentificationSpec(
            theorem_reference=("Røysland–Ryalen–Nygård–Didelez (2024/2025), Theorem 2",),
            weight_components=("W_treatment", "W_censoring"),
            marginalize_over=("U",),
        ),
        graphical_checks=LocalIndependenceGraphicalChecks(
            independent_censoring=IndependentCensoringCheck(
                checked=True,
                criterion="mu_separation",
                statement="C is mu-separated from the target given declared history.",
                conditioning_set=("L",),
                blocked_trails=("C<-L->Y",),
            ),
            eliminability=EliminabilityCheck(
                checked=True,
                target_node="X",
                eliminate_set=("U",),
                elimination_sequence=(
                    EliminabilityStep(
                        step=1,
                        removed=("U",),
                        justification_kind="mu_separation",
                        witness="blocked after conditioning on L",
                    ),
                ),
            ),
        ),
        runtime_requirements=LocalIndependenceRuntimeRequirements(
            needed_intensity_models=(
                IntensityModelRequirement(
                    process="X",
                    conditioning=("L", "X_history"),
                    estimation="aalen",
                ),
                IntensityModelRequirement(
                    process="C",
                    conditioning=("L",),
                    estimation="censoring_model",
                ),
            ),
            data_contract="event_log_or_counting_process_panel",
            positivity_assumed=True,
            diagnostics_required=True,
        ),
        assumptions=(
            "causal_validity_intensity_replacement",
            "independent_censoring_local",
            "eliminable_latent_processes",
            "bounded_likelihood_ratio",
        ),
        proof_trace=(
            "LI_CAUSAL_VALIDITY",
            "LI_IC_CENSORING",
            "LI_ELIMINABILITY_STEP:1:U",
            "LI_WEIGHTING_IDENTIFY",
        ),
    )


def test_local_independence_certificate_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = _certificate()

    ref = persist_local_independence_weighting_certificate(store, certificate)
    loaded = load_local_independence_weighting_certificate(store, ref)

    assert loaded == certificate
    assert loaded.graph.process_family == "counting_process"
    assert loaded.identification.weight_components == ("W_treatment", "W_censoring")
    assert loaded.graphical_checks.eliminability.checked is True


def test_local_independence_certificate_summary_is_proofbundle_friendly() -> None:
    summary = _certificate().to_summary_dict()

    assert summary["verification_status"] == "identified"
    assert summary["theorem_family"] == "local_independence_weighting_v1"
    assert summary["graph"]["process_family"] == "counting_process"
    assert summary["graphical_checks"]["independent_censoring_checked"] is True
    assert "bounded_likelihood_ratio" in summary["assumptions"]
