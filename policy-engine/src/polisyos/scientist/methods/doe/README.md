# DoE (`polisyos.scientist.methods.doe`)

`doe` covers Scientist's design-of-experiments and stress-analysis work:
sensitivity, ablation, and adversarial plans, sample-set generation, and
post-analysis of vulnerabilities.

## Role in the system

- **Depends on:** numerical sampling/analysis utilities and Scientist evaluation contracts
- **Used by:** `scientist.search.adversarial` and CLI stress/sensitivity commands
- The package creates controlled experiment plans for testing robustness and parameter sensitivity.

## Key concepts

- **SensitivityPlan** — parameterized sensitivity design with a failure policy.
- **AdversarialPlan** — scenario-based stress test for policy candidates.
- **Sampling** — generation of sensitivity/adversarial samples.
- **Analysis** — aggregation of results and vulnerabilities after execution.
- **Sensitivity uncertainty** — calibrated CI payloads, rank uncertainty, and retained row blocks.
- **Coverage benchmarks** — analytic truth suites, empirical coverage metrics, and approval profiles.
- **StressTestReport** — the final publication format for robustness issues. The `run_stress_test`
  result also exposes its exact selected CAS report reference through the transient
  `cas_artifact_ref` property; that caller handle is excluded from the persisted payload. A
  finite score also requires the current candidate to be a selected `PolicyCandidateSchema`
  artifact; the legacy `scientist.policy_candidate_schema` kind remains candidate-only and is
  not relabeled by the runtime bridge.

## Bounded distribution contract (DOE-02)

`ParameterSpec.lower_bound` and `upper_bound` are always physical support.  The
legacy uniform form remains unchanged.  A non-uniform parameter must carry an
explicit versioned `DistributionSpecV1`:

- `NORMAL` requires finite `mean` and positive finite `std`; the pinned SALib
  mapping is `truncnorm` with `[lower, upper, mean, std]`.
- `TRIANGULAR` requires `mode_fraction` in the physical support; the mapping
  is `triang` with `[lower, upper, mode_fraction]`.
- `LOGNORMAL` and legacy non-uniform parameters without a typed specification
  fail closed until a bounded adapter is admitted.  Bounds are never silently
  reinterpreted as log-space or distribution moments, and values are not
  clipped to manufacture support.

Sampling and analysis use the same versioned mapping and expose its fingerprint
in analysis metadata.  A fingerprint identifies the mapping and backend, while
the plan seed remains a separate request input.  Seeded Morris/Sobol streams
are isolated; seeded FAST remains `compatibility_pending` because SALib 1.5.2
mutates process-global NumPy state.

## Adaptive execution accounting

`AdaptiveSampler` preserves the caller's large-run permission and admits each
expanded design before invoking the evaluator. Its additive `attempts` history
distinguishes generation, evaluation, analysis, and completed rounds. Counts
describe only observed work: an evaluator exception has an unknown completed
row count rather than inheriting the planned design size. Malformed sample and
output shapes fail inside their owning phase boundary. After at least one valid
round, a later failure returns that last completed scientific result without an
extra evaluation; a first-round failure is propagated.

These in-memory attempt records are operational observations, not USD charges,
durable provenance, independent replicas, or evidence that the design is
scientifically sufficient. Monetary settlement requires an admitted typed
bridge to the orchestration budget owner; none is inferred from row counts.

Focused coordinator-fault tests may explicitly inject synthetic collaborators.
Real-backend verification must separately run the locked SALib sampler and
analyzer; an unavailable backend is a missing verification profile, not a pass.

## Morris trajectory admission

Point analysis, PCA component analysis, and elementary-effect uncertainty admit
only complete ungrouped trajectories: every step changes one parameter, every
parameter changes once, and the step and coordinates match the declared grid.
The check uses unit coordinates from the admitted uniform, truncated-normal,
or triangular sampling law. Finite values and divisible row counts alone are
insufficient. Whole valid blocks may be reordered or bootstrapped; individual
row resampling cannot preserve this design. `RankingStabilityChecker` therefore
resamples whole Morris trajectories. Its Sobol/FAST resampling is outside this
bounded repair. It validates the original Morris design before resampling and
refuses failed original runs; ranking stability under dropped or imputed runs
has no admitted selection or recovery contract.

The uniform elementary-effect helper requires explicit physical bounds and
`num_levels`; point and uncertainty effects share normalized units. Nonuniform
uncertainty remains unavailable until its coordinate contract is admitted.
Geometry does not authenticate original trajectory provenance or establish
statistical sufficiency or absence of failure-selection bias.

## Public API

- `SensitivityPlan`, `ScenarioSweep`, `AblationPlan`
- `AdversarialPlan`, `AdversarialStrategy`
- `generate_sensitivity_samples(...)`, `generate_adversarial_samples(...)`
- `analyze_sensitivity(...)`
- `SensitivityUncertaintyConfig`, `SensitivityUncertaintyBundle`
- `analyze_sobol_paired_bootstrap(...)`, `analyze_sobol_asymptotic_delta(...)`
- `analyze_morris_trajectory_bootstrap(...)`, `analyze_rqmc_replicate_ci(...)`
- `analyze_hierarchical_replicate_bootstrap(...)`
- `sobol_storage_from_blocks(...)`, `morris_storage_from_elementary_effects(...)`
- `SensitivityCoverageProfile`, `run_sobol_linear_coverage_benchmark(...)`
- `default_sobol_benchmark_cases(...)`, `default_morris_benchmark_cases(...)`
- `run_sobol_iid_coverage_benchmark(...)`, `run_morris_effect_coverage_benchmark(...)`
- `default_sensitivity_truth_suite(...)`, `sobol_sparse_interaction_truth(...)`
- `resolve_sensitivity_uncertainty_method(...)`, `apply_calibrated_multiplier(...)`
- `StressTestReport`, `Vulnerability`, `VulnerabilityType`

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-31
- Python modules: 12
- Exports: 82
- README reflects that `doe` remains upstream for search/stress flows.

## Selected experiment replay

`SensitivityBridge.analyze_search_space` uses the existing seeded sampler and
plan admission rather than a separate raw SALib route. Supplying `store` writes
one complete exploratory experiment as `doe_sensitivity_analysis` schema 1.0,
returns its full selected CAS reference, and requires an explicit seed. Persisted
Sobol experiments also require a declared independent experimental input law;
that declaration is not evidence of the population law. Native callable sources
and the current pinned SALib profile are reconciled at this boundary. Supported
sampler/analyzer options are passed explicitly and stored in the identity;
mutable package defaults cannot silently change the design or effect scale.

The artifact keeps the original ordered float64 experiment rows, including failed
observations, plan and run denominator, declared units, deterministic identities,
and the numerical result. Whole Morris trajectories or complete Saltelli blocks
may be reordered together with their outcomes; altered roles or multiplicities
are refused. Fresh readers resolve the exact kind/schema/selected canonical
profile, reconcile the complete seeded design and backend source context, and
rerun the analysis before the search adapter uses its ranking. Byte integrity,
a retained ranking string or a shape-correct matrix alone cannot admit it.

`SensitivityAwareCandidateGenerator.from_artifact` exposes the selected reference
and experiment identities in the existing `_sensitivity` candidate metadata.
Its default bounded reader admits at most 16 MiB / one million JSON elements;
a caller may supply explicit `CoreJsonReadLimits` for a different resource
profile. These limits do not establish scientific sufficiency.

Legacy unseeded in-process analysis and direct candidate construction remain
available as exploratory inputs. Neither route establishes evaluator provenance,
transitive environment authenticity, a population law, ranking/promotion rights
or publication authority. The stored experiment is a numerical replay source,
not a production provenance or independent-evidence receipt.

All materializing plan consumers reconstruct the current complete request before
work, including nested mutable fields and actual pre-filter Morris row counts.
An explicit large-run override admits a declared larger plan, not undeclared
additional trajectories or completed-work estimates.
