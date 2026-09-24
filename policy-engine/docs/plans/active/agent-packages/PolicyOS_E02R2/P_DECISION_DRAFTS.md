# E02-R2 P-b principal decision drafts

Status: all 16 drafts await Denis’s decision. No option is selected by this document. Costs are qualitative engineering, runtime compute, compatibility, and maintenance costs; none is a measured currency or person-week estimate. Each JSON row with bucket `b` has a `principal_decision_draft_ref` pointing to its section and a structured `principal_decision_draft` copy.

Every draft names its premise, at least two options and their costs, residual, falsifying revisit trigger, and the seam where the decision binds. The decision concerns the listed finding only; separate E02 package residuals remain explicit.

## B122 — Near-zero plateau and non-finite score policy

**Question.** Which metric-owned tolerance and non-finite policy determines a meaningful plateau near zero?

**Premise.** The controller uses minimization. A zero historical minimum followed by a positive recent value is regression, while a negative value can be genuine improvement; one global machine epsilon cannot define semantic improvement across differently scaled objectives.

**Options and costs.**

1. **Metric-owned signed tolerance.** Normalize objective direction, compute signed gain, then apply configured absolute tolerance near zero and relative tolerance away from zero. A non-finite/unknown score is not scientific convergence; the separate resource ceiling may still stop execution. Cost: Medium: metric profiles and serialized rule versions must carry direction and tolerances; avoids scale confusion.

2. **Single optimizer-wide absolute threshold.** Keep one configured absolute threshold for all objectives and treat non-finite values under a common explicit stop/unknown rule. Cost: Low initial migration; high semantic risk and repeated tuning because income, rates, and normalized losses have different scales.

**Residual.** Neither option normalizes every maximize/minimize objective or establishes that a resource stop is scientific convergence; the selected policy must state both separately.

**Revisit falsifier.** Reopen if a unit conversion or sign reversal for the same objective changes plateau disposition without changing the underlying improvement, or if a non-finite run is recorded as scientific convergence.

**Binding seam.** ImprovementPlateau.check plus the objective/metric contract and its persisted rule version.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B122`
**JSON cross-reference.** `partial_triage.json`, finding_id `B122`, `principal_decision_draft_ref: #b122`.

## B116 — Comparability required before technical champion promotion

**Question.** How should a champion remain comparable when suite, split, loop, or data basis changes?

**Premise.** Candidate and evaluation must bind to each other and to an applicable benchmark basis; equal metric names/numbers do not establish comparable evidence.

**Options and costs.**

1. **Re-evaluate the current champion on each new basis.** Reject mismatched candidate/evaluation bindings. When suite, split, metric method, or data basis changes, evaluate the current champion on the new basis before comparing candidates. Cost: High compute and latency for expensive benchmarks; preserves one continuously comparable champion.

2. **Maintain a champion per immutable comparison cohort.** Key champion records by suite/version, split, metric method, and data basis; never compare or promote across cohorts without a new bridge evaluation. Cost: Medium storage and API complexity; avoids mandatory reruns but fragments the notion of one global champion.

**Residual.** This establishes technical comparability only; it does not prove evaluator quality or grant any institutional promotion authority.

**Revisit falsifier.** Reopen if a candidate from another candidate_ref/loop/split or an incompatible suite can alter the pointer, or if an admitted conversion between two suites is shown equivalent but cannot be represented.

**Binding seam.** ChampionRegistry.consider_promotion, BenchmarkEvaluation binding, SearchLoopRunner caller, and the persisted comparison-cohort identity.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B116`
**JSON cross-reference.** `partial_triage.json`, finding_id `B116`, `principal_decision_draft_ref: #b116`.

## B117 — Atomic comparison and conditional champion publication

**Question.** Which concurrency envelope must the champion read–compare–publish operation support?

**Premise.** Atomic replacement of one pointer does not serialize the predecessor comparison. A stale writer can overwrite a stronger result; the repository card does not establish production multi-process demand.

**Options and costs.**

1. **Conditional publish through the store owner.** Publish only if the predecessor version/digest still matches, then re-read and re-compare on conflict. Keep expensive evaluation outside the transaction. Cost: Medium to high: requires a conditional-write primitive from the actual store and explicit conflict handling; supports concurrent writers.

2. **One serialized publication owner.** Route all compare-and-publish operations through one existing writer/lock owner; reject or queue other publishers. Cost: Medium: simpler storage contract, but adds throughput and availability limits and must prove every writer uses the owner.

**Residual.** Crash durability and multi-host behavior remain unclaimed unless the selected store primitive and deployment mode establish them.

**Revisit falsifier.** Reopen if a controlled B(score 2)/C(score 3) schedule leaves score 2 current, or if a second process can bypass the chosen serialization owner.

**Binding seam.** ChampionRegistry predecessor read, comparison, and pointer publication as one owned conditional transition.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B117`
**JSON cross-reference.** `partial_triage.json`, finding_id `B117`, `principal_decision_draft_ref: #b117`.

## B133 — Run identity versus mutable alias for history cache

**Question.** Does run_id name an immutable completed run or a mutable alias to the latest versioned artifact?

**Premise.** Warm and cold managers must replay the same referenced history. The current cache is keyed only by run_id, while registration can replace the history under that id.

**Options and costs.**

1. **Immutable run identity.** Treat a completed run_id as immutable and reject a conflicting re-registration; address the cached history by its immutable ArtifactRef/digest. Cost: Low to medium: simple replay semantics, but callers must allocate a new run id for revised history and retain old records.

2. **Versioned mutable alias.** Allow a run_id alias to move only by publishing a new versioned ArtifactRef; key cache entries by the referenced digest/version and keep old refs replayable. Cost: Medium: supports updates but needs alias history, cache invalidation, and version-aware readers.

**Residual.** Memory eviction policy and the separate TRN-02 live-metadata/distributed-atomicity residuals are not decided here.

**Revisit falsifier.** Reopen if a warm reader sees stale/new bytes differently from a cold reader for the same immutable ref, or if a legitimate caller must repoint run_id without a versioned ref.

**Binding seam.** register_run, _eval_cache keying, history loader, and the immutable artifact reference persisted with each run.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B133`
**JSON cross-reference.** `partial_triage.json`, finding_id `B133`, `principal_decision_draft_ref: #b133`.

**Scope distinction.** The source card B133 concerns mutable run_id/cache identity. The Appendix C TRN-02 residual also groups live metadata and distributed atomicity; those are separate residuals, not this decision.

## LA-053 — Retirement policy for the old Scientist calibration_curve address

**Question.** Should the old Scientist import address remain a supported compatibility facade, or retire after consumers move to the public calibration owner?

**Premise.** The original card finds the old address re-exports the shared calibration owner; ordinary tests still use the old path. A full external compatibility contract/caller census is not established.

**Options and costs.**

1. **Retain a time-bounded compatibility facade.** Keep the old re-export while internal and documented external consumers migrate; publish a compatibility window and preserve equivalent types/exceptions. Cost: Low immediate breakage; ongoing alias, docs, import-surface, and maintenance cost until retirement.

2. **Retire after caller and contract census.** Move ordinary tests/imports to polisyos.calibration, keep only a necessary compatibility test during the declared window, then remove the alias if no supported external consumer remains. Cost: Medium migration and release coordination; possible breaking change if the external contract census is incomplete.

**Residual.** The E02 PCL-01 note also names mixed valid/empty and skipped-level identity; that package residual is not settled by choosing this import-address lifetime.

**Revisit falsifier.** Reopen retirement if a supported external import/config reference is observed after the census, or reopen retention if the declared window ends and no supported caller remains.

**Binding seam.** Scientist backtesting calibration_curve import/FQN, root exports, package docs, and the release compatibility contract.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-053`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-053`, `principal_decision_draft_ref: #la-053`.

**Scope distinction.** The source card is a calibration_curve address migration. The Appendix C PCL-01 residual uses different mixed/identity wording; retain that as a separate residual.

## B169 — When a scalar or one interval may represent a forecast trajectory

**Question.** May an aggregate scalar/single interval be projected across a time horizon, and under what producer declaration?

**Premise.** The adapter currently repeats scalar metrics and one interval across the horizon, but the measurement could be a mean effect, period aggregate, constant forecast, or diagnostic. Those meanings are not interchangeable.

**Options and costs.**

1. **Require horizon-aligned values by default.** Require each time point to bind estimand, units, baseline, origin/cutoff, temporal coordinate, and interval semantics. Permit repetition only from a producer explicitly declaring a stationary constant forecast. Cost: Medium: richer producer DTOs and some existing scalar outputs become limited/refused until their meaning is supplied.

2. **Retain scalar as an explicitly aggregate profile.** Allow scalar output only as a typed horizon aggregate or explicitly constant profile; prevent it from being scored as an unqualified temporal trajectory. Cost: Medium: preserves simple producers but adds profile/consumer branches and limits cross-profile comparisons.

**Residual.** Production metric and uncertainty-envelope semantics remain unestablished; draws or time-varying variance must not be invented.

**Revisit falsifier.** Reopen if an admitted production producer declares a scalar as a horizon aggregate yet the chosen profile either rejects it or scores it as pointwise forecasts, or if one-point intervals are treated as predictive intervals without matching outcomes.

**Binding seam.** Forecast input DTO and the Scientist adapter in HistoricalValidationPlan/_predict_with_scientist, before scoring or publication.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B169`
**JSON cross-reference.** `partial_triage.json`, finding_id `B169`, `principal_decision_draft_ref: #b169`.

## B170 — Meaning and execution cost of n_simulation_runs

**Question.** Does n_simulation_runs mean independent executions, internal draws, bootstrap replicas, or something else?

**Premise.** The plan validates the count, but the current scenario dispatch makes one Scientist call for n=1 and n=7 alike. A cache hit is not an independent replica.

**Options and costs.**

1. **Implement independent outer executions.** Define n as independently seeded runs, pass an explicit seed plan to the existing execution owner, and persist requested/started/completed/failed counts plus sufficient distribution statistics. Cost: High and roughly proportional to n in compute, storage, and failure handling; honest support for repeated validation.

2. **Support n=1 until the owner implements repetitions.** Accept one run; return typed unsupported/limited for n>1 rather than silently dispatching once. Preserve an explicit PROVIDED-replicates path only when real completed replicates are supplied. Cost: Low initial compute/implementation; users lose multi-run support until the owner path exists.

**Residual.** The existing workflow’s internal Monte Carlo draws are not established, and the selected policy does not claim them.

**Revisit falsifier.** Reopen if plans with different n still produce indistinguishable execution manifests, or if a purported replica is only a cache hit or repeated scalar.

**Binding seam.** HistoricalValidationPlan validation, _run_single_scenario/_predict_with_scientist dispatch, seed ownership, and pre-execution budget admission.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B170`
**JSON cross-reference.** `partial_triage.json`, finding_id `B170`, `principal_decision_draft_ref: #b170`.

## B171 — Stable meaning for aggregate errors across scenario partitioning

**Question.** Should overall error weight every observation equally or every named scenario equally?

**Premise.** A technical repartition of the same residuals changes equal-scenario macro RMSE/MAE and can reverse candidate order; micro-RMSE can be reconstructed from pooled sufficient statistics.

**Options and costs.**

1. **Publish micro and macro as distinct metrics.** Make pooled sufficient-statistic micro error the default overall metric; retain equal-scenario macro under an explicit name and stable scenario identity. Cost: Medium: schema, serialization, and consumers must carry counts/weighted sums and both metric names.

2. **Keep equal-scenario macro as the only overall metric.** Require stable substantive scenario IDs and explicitly name the result macro error; do not call it partition-invariant overall error. Cost: Low numerical implementation cost, but requires scenario identity discipline and leaves observation-weighted performance unavailable.

**Residual.** Comparability of units and weights across different metrics or jurisdictions remains a separate contract.

**Revisit falsifier.** Reopen if merely sharding one named scenario changes the published micro result, or if a supposedly equal-scenario aggregate changes after technical split/merge without a declared scenario change.

**Binding seam.** Scenario aggregator _aggregate, serialized summary sufficient statistics, and the metric name/weighting contract.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B171`
**JSON cross-reference.** `partial_triage.json`, finding_id `B171`, `principal_decision_draft_ref: #b171`.

## B106 — Completeness and denominator for empirical robustness

**Question.** May robustness be claimed over the full declared scenario set, or only over a named sampled/early-stopped subset?

**Premise.** Presentation dedupe/top-k truncation must not alter counts of tested scenarios, observed violations, or non-results; adaptive stopping does not automatically estimate the entire space.

**Options and costs.**

1. **Require complete declared-set accounting.** Stream occurrence, tested-scenario, missing/non-numeric, and completeness counts before display cap; mark early-stopped or incomplete runs unknown/limited. Cost: Medium compute and schema work; may delay a result until the declared set finishes.

2. **Allow a named sampled estimate.** Keep bounded/adaptive execution but report the sampling design, inspected denominator, uncertainty, and sampled-score label; never call it full-population robustness. Cost: Lower compute and faster feedback; weaker claim and added sampling/uncertainty reporting.

**Residual.** The explored population is not automatically exhaustive; unique issue examples and presentation cap remain separate from occurrence counts.

**Revisit falsifier.** Reopen if changing collect_top_k changes robustness score for the same completed scenario set, or if an early-stopped sample is presented as complete population coverage.

**Binding seam.** Robustness aggregator before dedupe/cap, run completeness record, and the surfaced metric name.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B106`
**JSON cross-reference.** `partial_triage.json`, finding_id `B106`, `principal_decision_draft_ref: #b106`.

## LA-004 — Shared economics implementation versus distinct model profiles

**Question.** Should the overlapping plugin and base economics implementations share algorithms or remain distinct versioned profiles?

**Premise.** The source card confirms overlap but code disproves equivalence across state, units, timestep, tax base, RNG, and budget accounting.

**Options and costs.**

1. **Share only the proven common kernel.** Extract common mechanics only where contract tables match; keep non-equivalent tax/state/time/RNG/budget behavior under distinct versioned model profiles. Cost: Medium: mapping/contracts and profile selection are required; reduces duplicate code only at verified overlap.

2. **Keep implementations separate with explicit identities.** Preserve separate owners and identifiers; prohibit implicit cross-profile comparison until a compatibility mapping exists. Cost: Medium continuing maintenance and duplicate fixes; lower risk of silently changing model semantics.

**Residual.** No evidence establishes either implementation as universally calibrated or suitable for every base ABI; full caller migration remains open.

**Revisit falsifier.** Reopen consolidation if real paired regimes with equal declared inputs produce different outputs solely because of implementation duplication, or if a profile mapping fails to preserve accounting/RNG behavior.

**Binding seam.** Economic model/profile identity, state/config schema, and the scenario caller selecting the implementation.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-004`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-004`, `principal_decision_draft_ref: #la-004`.

## LA-035 — Name and scope of the early economic policy loss

**Question.** Should the existing normalized policy_loss_fn remain a named baseline, or should a distinct revenue-maximizing objective be added?

**Premise.** The source verifies a normalization that can flatten or alter positive-income ranking, but does not establish a production optimizer using it or a universal user intent to maximize raw income.

**Options and costs.**

1. **Retain as an explicitly named baseline objective.** Preserve the numerical rule under a profile name that states its balance/constraint semantics; do not advertise it as a generic income-maximizing objective. Cost: Low behavior/revalidation cost; requires API/FQN/config cleanup and retains limitations of the baseline.

2. **Add a separate versioned income objective.** Implement a distinct calibrated objective for users whose declared target is income maximization; keep the current baseline available for existing profiles. Cost: High: calibration, migration, optimizer validation, and revalidation for each caller; avoids silent ranking change.

**Residual.** Native optimizer callers, JIT/gradient behavior, and realized policy outcomes are not established; do not remove or retune the baseline on fixture evidence alone.

**Revisit falsifier.** Reopen if an appointed production optimizer claims income maximization and two positive-income policies are ranked contrary to that declared objective by the baseline.

**Binding seam.** Objective FQN/version and config chosen by the optimizer caller, with native loss/guardrail evaluation.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-035`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-035`, `principal_decision_draft_ref: #la-035`.

## LA-023 — Whether PolisySimulator.train means rollout evaluation or learning

**Question.** Should the current rollout loop be named/evaluated as rollout analysis, or connected to a real trainer for a bounded domain?

**Premise.** The inspected train body collects rollout rewards but leaves actor parameters unchanged and makes zero trainer calls; a separate training owner exists.

**Options and costs.**

1. **Relabel current behavior as rollout evaluation.** Return a typed evaluation result and make no learning claim until parameters change; retain rollout/reward collection as a useful capability. Cost: Low implementation cost; CLI and callers lose the current train-shaped success surface and still need a trainer for learning.

2. **Integrate the existing trainer for one compatible domain.** Route through the appointed trainer, persist the learned-state artifact, and prove nonzero-gradient parameter/action change with train/eval, RNG, reset, and continuation semantics. Cost: High implementation and compute cost; requires a compatible state contract and artifact lifecycle.

**Residual.** A local fixture trainer or nonzero gradient is not proof of full domain training quality; keep unsupported domains typed and limited.

**Revisit falsifier.** Reopen the evaluation-only choice if a caller requires learned state and a compatible trainer can demonstrate parameter and subsequent-action change; reopen trainer integration if it only collects rewards.

**Binding seam.** PolisySimulator.train contract, CLI result semantics, trainer orchestration, and persisted learned-state artifact.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-023`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-023`, `principal_decision_draft_ref: #la-023`.

## B210 — RDD bias-correction status and publication semantics

**Question.** Should the product remain limited to an explicitly uncorrected RDD estimate until a real correction is computed, or fund the corrected estimator path now?

**Premise.** The source card reports bias correction as included without computing it; a result label must not imply an estimator step absent from the producer.

**Options and costs.**

1. **Publish only the uncorrected limited result.** Remove/withhold the corrected claim and expose the conventional estimate with its typed limitation until a valid correction artifact exists. Cost: Low to medium: narrower output and possible refusal of a corrected claim; avoids unsupported inferential authority.

2. **Implement the declared bias-corrected estimator.** Add the appropriate local-polynomial correction and compatible variance/inference path, bound to design and bandwidth inputs, before setting corrected status. Cost: High statistical implementation, data, and validation cost; requires specialist owner and broader distinguishing cases.

**Residual.** Bias-correction method, variance behavior, and RDD scope across real designs remain unestablished until a producer and data-backed validation exist.

**Revisit falsifier.** Reopen if any served RDD record says corrected while the producer does not execute/persist the correction, or if a supported design has a validated correction that the bounded profile cannot represent.

**Binding seam.** RDD estimator producer, result DTO correction-status field, inference consumer, and any promotion/publication gate.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B210`
**JSON cross-reference.** `partial_triage.json`, finding_id `B210`, `principal_decision_draft_ref: #b210`.

## LA-055 — One meaning and precedence for DDM promotion permission

**Question.** Is an explicit stored deny a veto, or is promotion_allowed only an advisory baseline overridden by the final evaluator?

**Premise.** A constrained R4 event can persist promotion_allowed=False while the evaluator later returns True from state-only interpretation; ordinary mapper-produced R4 usually emits True. The counterexample does not establish an external release action.

**Options and costs.**

1. **Treat explicit restriction as a veto.** Preserve false/restriction as a binding veto; permit only a separately typed, authorized override with reason and scope. Cost: Medium: new override evidence/schema and caller migration; conservative when an explicit restriction was intended to bind.

2. **Make the event flag an advisory baseline.** Rename it as a baseline/readiness hint and let one evaluator compute final permission; carry any institutional restriction in a separate typed veto field. Cost: Medium to high: schema and all readers must migrate; avoids treating an advisory flag as final authority but risks old consumers assuming the old meaning.

**Residual.** Deployment/live-feed applicability in DDM-02 remains unclaimed; this decision resolves field meaning/precedence only, not feed authority or release service behavior.

**Revisit falsifier.** Reopen if a mapper-produced explicit false is consumed as a veto by a supported caller but the chosen evaluator allows it, or if every supported caller proves the field is advisory and the veto option blocks an authorized path.

**Binding seam.** ReadinessStateEvent/ModelRegistryReadinessRecord schema, readiness mapper, registry builder/evaluator, and final action consumer.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-055`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-055`, `principal_decision_draft_ref: #la-055`.

## LA-018 — Compatibility lifetime of the Lex factlog alias

**Question.** Is the old Lex factlog reader a supported external facade or an internal alias to retire after callers migrate?

**Premise.** The owner has moved to Fabric; the current source does not establish the complete caller census or external API status.

**Options and costs.**

1. **Retain a documented compatibility facade.** Keep a thin re-export for a declared compatibility window; preserve authorization and provenance behavior and publish the support boundary. Cost: Low immediate breakage; continued API/docs/test maintenance and import-surface complexity.

2. **Retire after complete consumer census.** Move all supported internal callers to the Fabric public owner, verify root exports/config/imports, then delete the alias with a release note. Cost: Medium caller/release coordination and possible external break if census is incomplete; lowers ongoing duplication.

**Residual.** External support status and full caller census remain unestablished; no arbitrary sunset date is justified.

**Revisit falsifier.** Reopen alias removal if a supported external consumer still resolves it, or reopen retention after the agreed window if no supported caller remains.

**Binding seam.** Lex factlog alias import path, root exports, package docs/config strings, and compatibility policy.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-018`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-018`, `principal_decision_draft_ref: #la-018`.

## LA-043 — Retirement boundary for the raw generated runtime client

**Question.** Should the raw generated client pair remain a supported compatibility artifact, or move to canonical public outputs and scratch-only intermediates?

**Premise.** Package exports already point to the canonical twin, while repository tests and the standalone checker still consume raw files; broader generated-family freshness exists and should be reused.

**Options and costs.**

1. **Keep raw pair during a declared compatibility window.** Treat raw TS/JS as managed generated intermediates while migrating tests/checker/direct consumers; retain one canonical generator and full-family freshness verification. Cost: Medium ongoing generated-output, registry, test, and duplicate-surface maintenance.

2. **Retire committed raw pair after full consumer migration.** Move tests and verifier to canonical public exports; redirect generation to isolated scratch/managed outputs; remove raw committed files only after the full caller and output-family census passes. Cost: Medium to high migration/typecheck/release cost; may break an undiscovered filesystem consumer.

**Residual.** External filesystem imports and full endpoint correctness remain unestablished; byte agreement alone is not endpoint execution evidence.

**Revisit falsifier.** Reopen removal if a supported raw-file consumer appears or the full required-generated-family gate does not cover a canonical output; reopen retention if the declared window ends with no supported raw consumer.

**Binding seam.** runtime-api-client package exports, generator/output ownership, public imports, tests, standalone contract checker, and generated-artifact registry.

**Source.** `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-043`
**JSON cross-reference.** `partial_triage.json`, finding_id `LA-043`, `principal_decision_draft_ref: #la-043`.

