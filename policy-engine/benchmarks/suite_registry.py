"""Declarative benchmark suite registry shared by all runners."""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections import OrderedDict
from pathlib import Path
from tools._lib.imports import repo_root_from


VALIDATION_CONTOURS = ("legacy", "production", "academic")
VISIBILITY_LANES = ("public", "hidden_release", "prod_shadow")
GATE_CLASSES = ("legacy_floor", "prod_blocker", "academic_claim", "shadow_only")


@dataclasses.dataclass(frozen=True)
class SuiteSpec:
    suite_id: str
    label: str
    script_relpath: str
    aliases: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ("air-m2", "extended")
    claim_profiles: tuple[str, ...] = ()
    proof_class: str = "standard"
    default_timeout_s: float = 0.0
    headline: bool = False
    stress_only: bool = False
    validation_contours: tuple[str, ...] = ("legacy",)
    visibility: str = "public"
    family: str | None = None
    gate_class: str = "legacy_floor"
    required_comparators: tuple[str, ...] = ()
    primary_metrics: tuple[str, ...] = ()
    supports_shadow: bool = False
    memory_gib_hint: float = 2.0

    @property
    def script_path(self) -> Path:
        return repo_root_from(__file__) / "benchmarks" / self.script_relpath


_SUITES: tuple[SuiteSpec, ...] = (
    SuiteSpec(
        suite_id="symbolic",
        label="Circuit 1: Symbolic Identification (ID algorithm gold suite)",
        script_relpath="symbolic/run_symbolic_benchmark.py",
        aliases=("symbolic", "core", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="estimation_acic",
        label="Circuit 2a: Estimation — ACIC benchmark",
        script_relpath="estimation/acic_benchmark.py",
        aliases=("estimation", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
        memory_gib_hint=14.0,
    ),
    SuiteSpec(
        suite_id="estimation_lbidd",
        label="Circuit 2b: Estimation — LBIDD benchmark",
        script_relpath="estimation/lbidd_benchmark.py",
        aliases=("estimation", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
        memory_gib_hint=13.0,
    ),
    SuiteSpec(
        suite_id="estimation_realcause",
        label="Circuit 2c: Estimation — RealCause benchmark",
        script_relpath="estimation/realcause_benchmark.py",
        aliases=("estimation", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
        memory_gib_hint=14.0,
    ),
    SuiteSpec(
        suite_id="hte_interpretable",
        label="Circuit 2d: HTE — Interpretable HTE benchmark",
        script_relpath="hte/interpretable_hte_benchmark.py",
        aliases=("hte", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
        memory_gib_hint=8.0,
    ),
    SuiteSpec(
        suite_id="discovery_sachs",
        label="Circuit 3a: Discovery — Sachs protein signalling (11-node PC)",
        script_relpath="discovery/sachs_benchmark.py",
        aliases=("discovery", "core"),
        proof_class="supplementary_benchmark",
    ),
    SuiteSpec(
        suite_id="discovery_tuebingen",
        label="Circuit 3b: Discovery — Tübingen ANM cause-effect pairs",
        script_relpath="discovery/tuebingen_benchmark.py",
        aliases=("discovery", "core"),
        proof_class="supplementary_benchmark",
    ),
    SuiteSpec(
        suite_id="discovery_causeme",
        label="Circuit 3c: Discovery — CauseMe VAR(1) Granger benchmark",
        script_relpath="discovery/causeme_benchmark.py",
        aliases=("discovery", "core"),
        profiles=("extended",),
        proof_class="supplementary_benchmark",
    ),
    SuiteSpec(
        suite_id="discovery_causalbench",
        label="Circuit 3d: Discovery — CausalBench perturbational (8-node)",
        script_relpath="discovery/causalbench_benchmark.py",
        aliases=("discovery", "core"),
        profiles=("extended",),
        proof_class="supplementary_benchmark",
    ),
    SuiteSpec(
        suite_id="missing_mgraph",
        label="Circuit 4a: Missing — M-graph recoverability (Mohan-Pearl 2021)",
        script_relpath="missing/mgraph_benchmark.py",
        aliases=("missing", "core", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="transport_core",
        label="Circuit 4b: Transport — Transportability (ID/TR/mZ-ID/CTF)",
        script_relpath="transport/transport_benchmark.py",
        aliases=("transport", "core", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="policy_natural_experiments",
        label="Circuit 4c: Policy — Natural experiments / quasi-experimental benchmark",
        script_relpath="natural_experiments/policy_natural_experiments.py",
        aliases=("policy", "natural", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
    ),
    SuiteSpec(
        suite_id="policy_did_interference",
        label="Circuit 4d: Policy — DID with interference / spillover benchmark",
        script_relpath="interference/policy_did_interference.py",
        aliases=("policy", "interference", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
    ),
    SuiteSpec(
        suite_id="temporal_gold",
        label="Circuit 4f: Temporal — Continuous-time gold benchmark",
        script_relpath="temporal/temporal_gold_benchmark.py",
        aliases=("temporal", "core", "publication_core"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="publication_benchmark",
        headline=True,
    ),
    SuiteSpec(
        suite_id="temporal_hidden",
        label="Circuit 4g: Temporal — Hidden temporal stress benchmark",
        script_relpath="temporal/temporal_hidden_benchmark.py",
        aliases=("temporal", "stress", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="stress_evidence",
        headline=False,
        stress_only=True,
    ),
    SuiteSpec(
        suite_id="adversarial_symbolic_stress",
        label="Circuit 4e: Stress — Adversarial symbolic generator benchmark",
        script_relpath="adversarial/adversarial_symbolic_stress.py",
        aliases=("stress", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="stress_evidence",
        headline=False,
        stress_only=True,
    ),
    SuiteSpec(
        suite_id="capability_multi_source",
        label="Circuit 5a: Capability — Multi-source mZ-ID transport demo",
        script_relpath="capability_wins/demo_multi_source_transport.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_fusion_missingness",
        label="Circuit 5b: Capability — Fusion + missingness demo",
        script_relpath="capability_wins/demo_fusion_plus_missingness.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_symbolic_nonid",
        label="Circuit 5c: Capability — Symbolic NegativeCertificate demo",
        script_relpath="capability_wins/demo_symbolic_non_id_certificate.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_ctf_transportability",
        label="Circuit 5d: Capability — CTF transportability demo",
        script_relpath="capability_wins/demo_ctf_transportability.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_compiled_audit",
        label="Circuit 5e: Capability — Compiled pipeline audit demo",
        script_relpath="capability_wins/demo_compiled_pipeline_audit.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_cyclic_feedback",
        label="Circuit 5f: Capability — Cyclic policy feedback demo",
        script_relpath="capability_wins/demo_cyclic_policy_feedback.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_surrogate_experiments",
        label="Circuit 5g: Capability — Arbitrary surrogate experiments demo",
        script_relpath="capability_wins/capability_surrogate_experiments.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_nested_surrogate_ctf",
        label="Circuit 5h: Capability — Nested counterfactual surrogates demo",
        script_relpath="capability_wins/capability_nested_surrogate_ctf.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_multiple_incomplete_sources",
        label="Circuit 5i: Capability — Multiple incomplete sources demo",
        script_relpath="capability_wins/capability_multiple_incomplete_sources.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_did_with_interference",
        label="Circuit 5j: Capability — DID with interference demo",
        script_relpath="capability_wins/capability_did_with_interference.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="capability_compositional_causality",
        label="Circuit 5l: Capability — Compositional causality stitching benchmark",
        script_relpath="composition/compositional_causality_benchmark.py",
        aliases=("composition", "capability", "capability_demos"),
        proof_class="supplementary_benchmark",
        headline=False,
    ),
    SuiteSpec(
        suite_id="capability_nontransportability_bounds",
        label="Circuit 5k: Capability — Non-transportability bounds demo",
        script_relpath="capability_wins/capability_nontransportability_bounds.py",
        aliases=("capability", "capability_demos", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="capability_gap",
        headline=True,
    ),
    SuiteSpec(
        suite_id="reproducibility_deterministic",
        label="Circuit 6a: Reproducibility — Deterministic symbolic outputs",
        script_relpath="reproducibility/test_deterministic_symbolic.py",
        aliases=("repro", "reproducibility", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="reproducibility_regression",
        label="Circuit 6b: Reproducibility — 3× repeat no-flaky",
        script_relpath="reproducibility/test_regression_no_flaky.py",
        aliases=("repro", "reproducibility", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="reproducibility_audit",
        label="Circuit 6c: Reproducibility — Audit trail completeness",
        script_relpath="reproducibility/test_audit_trail_complete.py",
        aliases=("repro", "reproducibility", "publication_core", "frontier"),
        claim_profiles=("frontier_frontier_claim", "full_stack_publication_claim"),
        proof_class="frontier_correctness",
        headline=True,
    ),
    SuiteSpec(
        suite_id="proof_closure_prod",
        label="Production contour — Proof closure benchmark",
        script_relpath="proof_closure/proof_closure_prod.py",
        aliases=("proof_closure", "production_grade"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="proof_closure",
        gate_class="prod_blocker",
        required_comparators=("y0", "ananke"),
        primary_metrics=(
            "routing_accuracy",
            "bare_dead_end_rate",
            "proof_replay_success_rate",
            "bounds_validity_rate",
            "abstention_calibration",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="readiness_governance",
        label="Production contour — Readiness governance benchmark",
        script_relpath="governance/readiness_governance.py",
        aliases=("readiness_governance", "production_grade", "governance"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="readiness_governance",
        gate_class="prod_blocker",
        primary_metrics=(
            "false_pass_rate",
            "false_block_rate",
            "decision_calibration",
            "diagnostic_presence_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="cold_start_import",
        label="Production contour — Cold-start import benchmark",
        script_relpath="ops/cold_start_import.py",
        aliases=("ops", "production_grade", "cold_start"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="cold_start_import",
        gate_class="prod_blocker",
        primary_metrics=("cold_start_success_rate", "bootstrap_success_rate"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="replay_lineage",
        label="Production contour — Replay and lineage benchmark",
        script_relpath="ops/replay_lineage.py",
        aliases=("ops", "production_grade", "replay_lineage"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="replay_lineage",
        gate_class="prod_blocker",
        primary_metrics=("replay_success_rate", "hash_stability_rate", "lineage_completeness_rate"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="fault_injection",
        label="Production contour — Fault injection benchmark",
        script_relpath="ops/fault_injection.py",
        aliases=("ops", "production_grade", "fault_injection"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="fault_injection",
        gate_class="prod_blocker",
        primary_metrics=("safe_failure_rate", "diagnostic_capture_rate"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="budgeted_execution",
        label="Production contour — Budgeted execution benchmark",
        script_relpath="ops/budgeted_execution.py",
        aliases=("ops", "production_grade", "budgeted_execution"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="budgeted_execution",
        gate_class="prod_blocker",
        primary_metrics=("p50_latency_s", "p95_latency_s", "peak_rss_mb", "quality_under_budget"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="schema_drift",
        label="Production contour — Schema drift benchmark",
        script_relpath="ops/schema_drift.py",
        aliases=("ops", "production_grade", "schema_drift"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="schema_drift",
        gate_class="prod_blocker",
        primary_metrics=("drift_detection_rate", "unsafe_pass_rate"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="concurrency_determinism",
        label="Production contour — Concurrency determinism benchmark",
        script_relpath="ops/concurrency_determinism.py",
        aliases=("ops", "production_grade", "concurrency"),
        profiles=("extended",),
        validation_contours=("production",),
        visibility="public",
        family="concurrency_determinism",
        gate_class="prod_blocker",
        primary_metrics=("determinism_rate", "idempotence_rate"),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="proof_closure_public",
        label="Academic contour — Proof closure public benchmark",
        script_relpath="proof_closure/proof_closure_public.py",
        aliases=("proof_closure", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="proof_closure",
        gate_class="academic_claim",
        required_comparators=("y0", "ananke"),
        primary_metrics=(
            "routing_accuracy",
            "bare_dead_end_rate",
            "proof_replay_success_rate",
            "bounds_validity_rate",
            "abstention_calibration",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="proof_closure_hidden_release",
        label="Academic contour — Proof closure hidden release benchmark",
        script_relpath="proof_closure/proof_closure_hidden_release.py",
        aliases=("proof_closure", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="proof_closure",
        gate_class="academic_claim",
        required_comparators=("y0", "ananke"),
        primary_metrics=(
            "routing_accuracy",
            "bare_dead_end_rate",
            "proof_replay_success_rate",
            "bounds_validity_rate",
            "abstention_calibration",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="composition_alignment_public",
        label="Academic contour — Composition and alignment public benchmark",
        script_relpath="composition/composition_alignment_public.py",
        aliases=("composition_alignment", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="composition_alignment",
        gate_class="academic_claim",
        primary_metrics=(
            "invalid_stitch_recall",
            "valid_stitch_precision",
            "preservation_status_accuracy",
            "assumption_injection_correctness",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="composition_alignment_hidden_release",
        label="Academic contour — Composition and alignment hidden release benchmark",
        script_relpath="composition/composition_alignment_hidden_release.py",
        aliases=("composition_alignment", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="composition_alignment",
        gate_class="academic_claim",
        primary_metrics=(
            "invalid_stitch_recall",
            "valid_stitch_precision",
            "preservation_status_accuracy",
            "assumption_injection_correctness",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="temporal_paths_public",
        label="Academic contour — Temporal paths public benchmark",
        script_relpath="temporal/temporal_paths_public.py",
        aliases=("temporal_paths", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="temporal_paths",
        gate_class="academic_claim",
        required_comparators=("pygformula", "tigramite", "econml"),
        primary_metrics=(
            "path_rmse",
            "integral_error",
            "band_coverage",
            "diagnostic_presence_rate",
            "bundle_reload_success_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="temporal_paths_hidden_release",
        label="Academic contour — Temporal paths hidden release benchmark",
        script_relpath="temporal/temporal_paths_hidden_release.py",
        aliases=("temporal_paths", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="temporal_paths",
        gate_class="academic_claim",
        required_comparators=("pygformula", "tigramite", "econml"),
        primary_metrics=(
            "path_rmse",
            "integral_error",
            "band_coverage",
            "diagnostic_presence_rate",
            "bundle_reload_success_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="distributional_public",
        label="Academic contour — Distributional public benchmark",
        script_relpath="distributional/distributional_public.py",
        aliases=("distributional", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="distributional",
        gate_class="academic_claim",
        required_comparators=("pot",),
        primary_metrics=(
            "wasserstein_error",
            "quantile_error",
            "tail_risk_error",
            "mass_conservation_rate",
            "subgroup_monotonicity_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="distributional_hidden_release",
        label="Academic contour — Distributional hidden release benchmark",
        script_relpath="distributional/distributional_hidden_release.py",
        aliases=("distributional", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="distributional",
        gate_class="academic_claim",
        required_comparators=("pot",),
        primary_metrics=(
            "wasserstein_error",
            "quantile_error",
            "tail_risk_error",
            "mass_conservation_rate",
            "subgroup_monotonicity_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="strategic_solver_public",
        label="Academic contour — Strategic solver public benchmark",
        script_relpath="strategic/strategic_solver_public.py",
        aliases=("strategic_solver", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="strategic_solver",
        gate_class="academic_claim",
        required_comparators=("openspiel", "nashpy"),
        primary_metrics=(
            "leader_value_error",
            "best_response_gap",
            "exploitability_proxy",
            "budget_enforcement_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="strategic_solver_hidden_release",
        label="Academic contour — Strategic solver hidden release benchmark",
        script_relpath="strategic/strategic_solver_hidden_release.py",
        aliases=("strategic_solver", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="strategic_solver",
        gate_class="academic_claim",
        required_comparators=("openspiel", "nashpy"),
        primary_metrics=(
            "leader_value_error",
            "best_response_gap",
            "exploitability_proxy",
            "budget_enforcement_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="abstraction_exactness_public",
        label="Academic contour — Abstraction exactness public benchmark",
        script_relpath="abstraction/abstraction_exactness_public.py",
        aliases=("abstraction_exactness", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="abstraction_exactness",
        gate_class="academic_claim",
        primary_metrics=(
            "micro_macro_exact_match_rate",
            "certificate_validity_rate",
            "leakage_detection_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="abstraction_exactness_hidden_release",
        label="Academic contour — Abstraction exactness hidden release benchmark",
        script_relpath="abstraction/abstraction_exactness_hidden_release.py",
        aliases=("abstraction_exactness", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="abstraction_exactness",
        gate_class="academic_claim",
        primary_metrics=(
            "micro_macro_exact_match_rate",
            "certificate_validity_rate",
            "leakage_detection_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="discovery_governance_public",
        label="Academic contour — Discovery governance public benchmark",
        script_relpath="governance/discovery_governance_public.py",
        aliases=("discovery_governance", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="discovery_governance",
        gate_class="academic_claim",
        required_comparators=("causal-learn", "pgmpy", "tigramite"),
        primary_metrics=(
            "constraint_precision",
            "constraint_recall",
            "disputed_edge_calibration",
            "ranking_utility_correlation",
            "cap_violation_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="discovery_governance_hidden_release",
        label="Academic contour — Discovery governance hidden release benchmark",
        script_relpath="governance/discovery_governance_hidden_release.py",
        aliases=("discovery_governance", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="discovery_governance",
        gate_class="academic_claim",
        required_comparators=("causal-learn", "pgmpy", "tigramite"),
        primary_metrics=(
            "constraint_precision",
            "constraint_recall",
            "disputed_edge_calibration",
            "ranking_utility_correlation",
            "cap_violation_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="interaction_contracts_public",
        label="Academic contour — Interaction contracts public benchmark",
        script_relpath="interaction/interaction_contracts_public.py",
        aliases=("interaction_contracts", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="public",
        family="interaction_contracts",
        gate_class="academic_claim",
        primary_metrics=(
            "certificate_completeness_rate",
            "unsupported_failure_correctness",
            "interference_regression_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="interaction_contracts_hidden_release",
        label="Academic contour — Interaction contracts hidden release benchmark",
        script_relpath="interaction/interaction_contracts_hidden_release.py",
        aliases=("interaction_contracts", "academic_grade"),
        profiles=("extended",),
        validation_contours=("academic",),
        visibility="hidden_release",
        family="interaction_contracts",
        gate_class="academic_claim",
        primary_metrics=(
            "certificate_completeness_rate",
            "unsupported_failure_correctness",
            "interference_regression_rate",
        ),
        supports_shadow=True,
    ),
    SuiteSpec(
        suite_id="honest_comparison",
        label="Honest head-to-head: PolicyOS vs raw open-source causal inference",
        script_relpath="honest_comparison/run_honest_benchmark.py",
        aliases=("honest", "head_to_head"),
        profiles=("extended",),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
        validation_contours=("academic",),
        visibility="public",
        family="estimation",
        gate_class="academic_claim",
        required_comparators=("econml", "zepid", "dowhy"),
        primary_metrics=(
            "ate_rmse",
            "ci_coverage",
            "pehe",
            "failure_rate",
        ),
    ),
)


_LEGACY_ID_ALIASES: dict[str, str] = {
    "capability_non_id_cert": "capability_symbolic_nonid",
    "capability_ctf_transport": "capability_ctf_transportability",
    "capability_pipeline_audit": "capability_compiled_audit",
    "capability_cyclic": "capability_cyclic_feedback",
    "repro_deterministic": "reproducibility_deterministic",
    "repro_no_flaky": "reproducibility_regression",
    "repro_audit_trail": "reproducibility_audit",
}


def all_suite_specs() -> tuple[SuiteSpec, ...]:
    return _SUITES


def _filtered_specs(
    *,
    profile: str | None = None,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> list[SuiteSpec]:
    candidates = list(_SUITES)
    if profile is not None:
        normalized_profile = profile.strip().lower()
        if normalized_profile not in {"air-m2", "extended"}:
            raise ValueError(f"Unknown benchmark profile: {profile!r}")
        candidates = [spec for spec in candidates if normalized_profile in spec.profiles]
    if validation_contour is not None:
        normalized_contour = validation_contour.strip().lower()
        if normalized_contour not in VALIDATION_CONTOURS:
            raise ValueError(f"Unknown validation contour: {validation_contour!r}")
        candidates = [
            spec for spec in candidates
            if normalized_contour in spec.validation_contours
        ]
    if visibility is not None:
        normalized_visibility = visibility.strip().lower()
        if normalized_visibility not in VISIBILITY_LANES:
            raise ValueError(f"Unknown visibility lane: {visibility!r}")
        if normalized_visibility == "prod_shadow":
            candidates = [spec for spec in candidates if spec.supports_shadow]
        else:
            candidates = [spec for spec in candidates if spec.visibility == normalized_visibility]
    return candidates


def suites_for_profile(
    profile: str,
    *,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> list[SuiteSpec]:
    normalized = profile.strip().lower()
    if normalized not in {"air-m2", "extended"}:
        raise ValueError(f"Unknown benchmark profile: {profile!r}")
    return _filtered_specs(
        profile=normalized,
        validation_contour=validation_contour,
        visibility=visibility,
    )


def filtered_suite_specs(
    *,
    profile: str | None = None,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> list[SuiteSpec]:
    return _filtered_specs(
        profile=profile,
        validation_contour=validation_contour,
        visibility=visibility,
    )


def canonical_suite_id(suite_id: str) -> str:
    return _LEGACY_ID_ALIASES.get(suite_id, suite_id)


def spec_by_suite_id(suite_id: str) -> SuiteSpec | None:
    normalized = canonical_suite_id(suite_id)
    for spec in _SUITES:
        if spec.suite_id == normalized:
            return spec
    return None


def alias_targets(
    alias: str,
    *,
    profile: str | None = None,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> list[SuiteSpec]:
    normalized = canonical_suite_id(alias)
    candidates = _filtered_specs(
        profile=profile,
        validation_contour=validation_contour,
        visibility=visibility,
    )
    return [
        spec
        for spec in candidates
        if normalized == spec.suite_id or normalized in spec.aliases
    ]


def emit_registry_tsv(
    *,
    profile: str | None = None,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> str:
    candidates = _filtered_specs(
        profile=profile,
        validation_contour=validation_contour,
        visibility=visibility,
    )
    lines = []
    for spec in candidates:
        aliases = ",".join(OrderedDict.fromkeys((spec.suite_id, *spec.aliases)).keys())
        profiles = ",".join(spec.profiles)
        lines.append(
            "\t".join(
                [
                    spec.suite_id,
                    spec.label,
                    str(spec.script_path),
                    aliases,
                    profiles,
                ]
            )
        )
    return "\n".join(lines)


def suites_for_claim_profile(
    claim_profile: str,
    *,
    profile: str | None = None,
    validation_contour: str | None = None,
    visibility: str | None = None,
) -> list[SuiteSpec]:
    candidates = _filtered_specs(
        profile=profile,
        validation_contour=validation_contour,
        visibility=visibility,
    )
    return [spec for spec in candidates if claim_profile in spec.claim_profiles]


__all__ = [
    "SuiteSpec",
    "alias_targets",
    "all_suite_specs",
    "canonical_suite_id",
    "emit_registry_tsv",
    "filtered_suite_specs",
    "spec_by_suite_id",
    "suites_for_claim_profile",
    "suites_for_profile",
    "VALIDATION_CONTOURS",
    "VISIBILITY_LANES",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print benchmark suite registry.")
    parser.add_argument("--profile", choices=("air-m2", "extended"))
    parser.add_argument("--format", choices=("tsv", "json"), default="tsv")
    parser.add_argument("--alias")
    parser.add_argument("--claim-profile")
    parser.add_argument("--validation-contour", choices=VALIDATION_CONTOURS)
    parser.add_argument("--visibility", choices=VISIBILITY_LANES)
    args = parser.parse_args(argv)

    if args.alias and args.claim_profile:
        parser.error("--alias and --claim-profile are mutually exclusive")

    if args.alias:
        specs = alias_targets(
            args.alias,
            profile=args.profile,
            validation_contour=args.validation_contour,
            visibility=args.visibility,
        )
    elif args.claim_profile:
        specs = suites_for_claim_profile(
            args.claim_profile,
            profile=args.profile,
            validation_contour=args.validation_contour,
            visibility=args.visibility,
        )
    else:
        specs = _filtered_specs(
            profile=args.profile,
            validation_contour=args.validation_contour,
            visibility=args.visibility,
        )
    if args.format == "json":
        payload = [
            {
                "suite_id": spec.suite_id,
                "label": spec.label,
                "script_path": str(spec.script_path),
                "aliases": [spec.suite_id, *spec.aliases],
                "profiles": list(spec.profiles),
                "claim_profiles": list(spec.claim_profiles),
                "proof_class": spec.proof_class,
                "headline": spec.headline,
                "stress_only": spec.stress_only,
                "validation_contours": list(spec.validation_contours),
                "visibility": spec.visibility,
                "family": spec.family,
                "gate_class": spec.gate_class,
                "required_comparators": list(spec.required_comparators),
                "primary_metrics": list(spec.primary_metrics),
                "supports_shadow": spec.supports_shadow,
                "memory_gib_hint": spec.memory_gib_hint,
            }
            for spec in specs
        ]
        print(json.dumps(payload, indent=2))
        return 0

    print(
        emit_registry_tsv(
            profile=args.profile,
            validation_contour=args.validation_contour,
            visibility=args.visibility,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
