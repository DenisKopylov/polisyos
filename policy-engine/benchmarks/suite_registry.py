"""Declarative benchmark suite registry shared by all runners."""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections import OrderedDict
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class SuiteSpec:
    suite_id: str
    label: str
    script_relpath: str
    aliases: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ("air-m2", "extended")
    claim_profiles: tuple[str, ...] = ()
    proof_class: str = "standard"
    headline: bool = False
    stress_only: bool = False

    @property
    def script_path(self) -> Path:
        return Path(__file__).resolve().parent / self.script_relpath


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
    ),
    SuiteSpec(
        suite_id="estimation_lbidd",
        label="Circuit 2b: Estimation — LBIDD benchmark",
        script_relpath="estimation/lbidd_benchmark.py",
        aliases=("estimation", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
    ),
    SuiteSpec(
        suite_id="estimation_realcause",
        label="Circuit 2c: Estimation — RealCause benchmark",
        script_relpath="estimation/realcause_benchmark.py",
        aliases=("estimation", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
    ),
    SuiteSpec(
        suite_id="hte_interpretable",
        label="Circuit 2d: HTE — Interpretable HTE benchmark",
        script_relpath="hte/interpretable_hte_benchmark.py",
        aliases=("hte", "core", "publication_core"),
        claim_profiles=("full_stack_publication_claim",),
        proof_class="publication_benchmark",
        headline=True,
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


def suites_for_profile(profile: str) -> list[SuiteSpec]:
    normalized = profile.strip().lower()
    if normalized not in {"air-m2", "extended"}:
        raise ValueError(f"Unknown benchmark profile: {profile!r}")
    return [spec for spec in _SUITES if normalized in spec.profiles]


def canonical_suite_id(suite_id: str) -> str:
    return _LEGACY_ID_ALIASES.get(suite_id, suite_id)


def spec_by_suite_id(suite_id: str) -> SuiteSpec | None:
    normalized = canonical_suite_id(suite_id)
    for spec in _SUITES:
        if spec.suite_id == normalized:
            return spec
    return None


def alias_targets(alias: str, *, profile: str | None = None) -> list[SuiteSpec]:
    normalized = canonical_suite_id(alias)
    candidates = suites_for_profile(profile) if profile else list(_SUITES)
    return [
        spec
        for spec in candidates
        if normalized == spec.suite_id or normalized in spec.aliases
    ]


def emit_registry_tsv(*, profile: str | None = None) -> str:
    candidates = suites_for_profile(profile) if profile else list(_SUITES)
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


def suites_for_claim_profile(claim_profile: str, *, profile: str | None = None) -> list[SuiteSpec]:
    candidates = suites_for_profile(profile) if profile else list(_SUITES)
    return [spec for spec in candidates if claim_profile in spec.claim_profiles]


__all__ = [
    "SuiteSpec",
    "alias_targets",
    "all_suite_specs",
    "canonical_suite_id",
    "emit_registry_tsv",
    "spec_by_suite_id",
    "suites_for_claim_profile",
    "suites_for_profile",
]


def _main() -> int:
    parser = argparse.ArgumentParser(description="Print benchmark suite registry.")
    parser.add_argument("--profile", choices=("air-m2", "extended"))
    parser.add_argument("--format", choices=("tsv", "json"), default="tsv")
    parser.add_argument("--alias")
    parser.add_argument("--claim-profile")
    args = parser.parse_args()

    if args.alias and args.claim_profile:
        parser.error("--alias and --claim-profile are mutually exclusive")

    if args.alias:
        specs = alias_targets(args.alias, profile=args.profile)
    elif args.claim_profile:
        specs = suites_for_claim_profile(args.claim_profile, profile=args.profile)
    else:
        specs = suites_for_profile(args.profile) if args.profile else list(_SUITES)
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
            }
            for spec in specs
        ]
        print(json.dumps(payload, indent=2))
        return 0

    print(emit_registry_tsv(profile=args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
