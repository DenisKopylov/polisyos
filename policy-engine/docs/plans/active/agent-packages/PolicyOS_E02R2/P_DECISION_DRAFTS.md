# Principal decision drafts for E02-R2 partial findings

**Status: proposals only.** These are drafts extracted without changing the embedded triage source. None is a principal ruling, authorization to implement a principal choice, or finding closure. Every decision is `awaiting_principal`; no test result or closure evidence is asserted. The row-by-row reconciliation distinguishes card-level decisions from broader triage next steps. LA-053’s skipped-level-identity next step remains mismatched to its cited alias-migration card and is explicitly left unresolved; LA-055 carries a second, independent applicability-scope question.

**Denominator.** All 16 rows marked `bucket=b` in `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/partial_triage.json` (118 rows in the P118 Appendix C partial-finding triage cohort; counts: 84 engineering a / 16 principal b / 18 typed blocker c). All 16 embedded objects carry the §9.7 fields, but a populated draft object is not by itself proof that its question matches the triage next step; see each reconciliation below. The source declares `decision_draft_count: 16`. Source JSON: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/partial_triage.json@sha256:ba3b6f086823f44caf204c5c2922021f44fb6c9001eb91e39ea80d733b64f994`.

**Census and relation rule.** The current `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md` scans 77 GY task scopes, 22 Atlas slice scopes, and 74 current open/blocked A/B register rows using exact owner-scope matches. For rows below marked `not_established`, the scan admitted no direct relation; this is not proof of no dependency. Scan inputs: `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@sha256:5d06f4cc55541fb28030ec4f6c75f2a10537df53c60f792df84de118d0aeb4c5`; `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@sha256:35c1b64c91aa4209cffed4aed42d89258e5f975afab44464f201111ba0b4d725`; `policy-engine/docs/plans/active/DEBT-REGISTER.md@sha256:133bf46f5835a73e117bcfde31edd87b98a5514c364a23b74926278c9f883f6e`. Crosswalk: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05`.

## Separate decisions that may be reviewed together

Keep these decisions distinct even if reviewed together: B116/B117 bind comparison cohort vs publication concurrency; B169/B170 bind forecast-value semantics vs simulation-count/seed semantics; LA-004/LA-035 bind economics-profile identity vs objective identity. The separate options and binding seams remain per finding.

## b122

**Question.** Which metric-owned tolerance and non-finite policy determines a meaningful plateau near zero?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Metric-owned signed tolerance.** Normalize objective direction, compute signed gain, then apply configured absolute tolerance near zero and relative tolerance away from zero. A non-finite/unknown score is not scientific convergence; the separate resource ceiling may still stop execution. **Cost:** Medium: metric profiles and serialized rule versions must carry direction and tolerances; avoids scale confusion.

2. **Single optimizer-wide absolute threshold.** Keep one configured absolute threshold for all objectives and treat non-finite values under a common explicit stop/unknown rule. **Cost:** Low initial migration; high semantic risk and repeated tuning because income, rates, and normalized losses have different scales.

**Premises.** The controller uses minimization. A zero historical minimum followed by a positive recent value is regression, while a negative value can be genuine improvement; one global machine epsilon cannot define semantic improvement across differently scaled objectives.

**Remainder.** Neither option normalizes every maximize/minimize objective or establishes that a resource stop is scientific convergence; the selected policy must state both separately.

**Falsifier / revisit trigger.** Reopen if a unit conversion or sign reversal for the same objective changes plateau disposition without changing the underlying improvement, or if a non-finite run is recorded as scientific convergence.

**Where it binds.** ImprovementPlateau.check plus the objective/metric contract and its persisted rule version.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the accepted near-zero-scale and non-finite policy, with options, costs, a falsifier and where the rule binds.” This is aligned with the cited card’s near-zero and non-finite plateau question. The options remain proposals; neither choice has been made or validated.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B122`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STP-01.md@sha256:a9fb522de58a5c9e0524fa9cc209080d4f3f72e20f1b111f8872097b280a4d7c`.

**Associated E02 package residual (context only; not a closure claim).** STP-01: near-zero scale / non-finite policy residual

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B122`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L179`.

## b116

**Question.** How should a champion remain comparable when suite, split, loop, or data basis changes?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Re-evaluate the current champion on each new basis.** Reject mismatched candidate/evaluation bindings. When suite, split, metric method, or data basis changes, evaluate the current champion on the new basis before comparing candidates. **Cost:** High compute and latency for expensive benchmarks; preserves one continuously comparable champion.

2. **Maintain a champion per immutable comparison cohort.** Key champion records by suite/version, split, metric method, and data basis; never compare or promote across cohorts without a new bridge evaluation. **Cost:** Medium storage and API complexity; avoids mandatory reruns but fragments the notion of one global champion.

**Premises.** Candidate and evaluation must bind to each other and to an applicable benchmark basis; equal metric names/numbers do not establish comparable evidence.

**Remainder.** This establishes technical comparability only; it does not prove evaluator quality or grant any institutional promotion authority.

**Falsifier / revisit trigger.** Reopen if a candidate from another candidate_ref/loop/split or an incompatible suite can alter the pointer, or if an admitted conversion between two suites is shown equivalent but cannot be represented.

**Where it binds.** ChampionRegistry.consider_promotion, BenchmarkEvaluation binding, SearchLoopRunner caller, and the persisted comparison-cohort identity.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose the supported legacy suite-binding, protocol and pointer compatibility boundary and its removal cost; record falsifier and revisit trigger.” The card and this draft address comparability of candidate/evaluation evidence across changing suite, split, loop and data basis. The triage step also names protocol/pointer compatibility and removal cost; those are not fully decided by the card question. Do not treat this decision as a general legacy-protocol sunset.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B116`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-04.md@sha256:5c2f21464b6af46c3291b1722af179c1106e94aa087aeb0b6dd3fcc378d84684`.

**Associated E02 package residual (context only; not a closure claim).** OPT-04: legacy suite binding, protocol, pointer compatibility open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B116`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L173`.

## b117

**Question.** Which concurrency envelope must the champion read–compare–publish operation support?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Conditional publish through the store owner.** Use the actual store owner's conditional-write primitive only if a complete caller census and source-backed trace prove that owner covers every publisher. Then publish only if the predecessor version/digest still matches, re-read and re-compare on conflict, and keep expensive evaluation outside the transaction. **Cost:** Medium to high: requires the conditional-write primitive and explicit conflict handling; if no owner covers every publisher, the separate appointment/capability prerequisite applies.

2. **One serialized publication owner.** Route all compare-and-publish operations through one writer/lock owner only if a complete caller census proves that owner covers every publisher. Otherwise this option requires a separately authorized owner appointment or the smallest missing capability; this draft does not presume or make that appointment. Reject or queue bypassing publishers. **Cost:** Medium if an existing owner covers all callers; higher if an appointment/capability must be established, plus throughput and availability limits.

**Premises.** Atomic replacement of one pointer does not serialize the predecessor comparison. A stale writer can overwrite a stronger result; the repository card does not establish production multi-process demand.

**Scope note.** Neither option presumes that one current publication owner covers every publisher. Require a complete caller census and source-backed proof. If no current owner covers all paths, an explicit owner appointment or the smallest missing owner capability is a separate prerequisite; choosing an option here does not make that appointment.

**Remainder.** Crash durability and multi-host behavior remain unclaimed unless the selected store primitive and deployment mode establish them.

**Falsifier / revisit trigger.** Reopen if a controlled B(score 2)/C(score 3) schedule leaves score 2 current, or if a second process can bypass the chosen serialization owner.

**Where it binds.** ChampionRegistry predecessor read, comparison, and pointer publication as one owned conditional transition, conditioned on proven publisher coverage by the actual store or a separately authorized serialization owner.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose the supported legacy suite-binding, protocol and pointer compatibility boundary and its removal cost; record falsifier and revisit trigger.” The shared triage step is broader legacy suite/protocol/pointer compatibility, while B117’s card concerns stale compare-and-publish under concurrent writers. This draft decides only the concurrency envelope at the publication seam; suite compatibility and legacy pointer/protocol retirement remain separate.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B117`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-04.md@sha256:5c2f21464b6af46c3291b1722af179c1106e94aa087aeb0b6dd3fcc378d84684`.

**Associated E02 package residual (context only; not a closure claim).** OPT-04: legacy suite binding, protocol, pointer compatibility open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B117`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L174`.

## b133

**Question.** Does run_id name an immutable completed run or a mutable alias to the latest versioned artifact?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Immutable run identity.** Treat a completed run_id as immutable and reject a conflicting re-registration; address the cached history by its immutable ArtifactRef/digest. **Cost:** Low to medium: simple replay semantics, but callers must allocate a new run id for revised history and retain old records.

2. **Versioned mutable alias.** Allow a run_id alias to move only by publishing a new versioned ArtifactRef; key cache entries by the referenced digest/version and keep old refs replayable. **Cost:** Medium: supports updates but needs alias history, cache invalidation, and version-aware readers.

**Premises.** Warm and cold managers must replay the same referenced history. The current cache is keyed only by run_id, while registration can replace the history under that id.

**Scope note.** The source card B133 concerns mutable run_id/cache identity. The Appendix C TRN-02 residual also groups live metadata and distributed atomicity; those are separate residuals, not this decision.

**Remainder.** Memory eviction policy and the separate TRN-02 live-metadata/distributed-atomicity residuals are not decided here.

**Falsifier / revisit trigger.** Reopen if a warm reader sees stale/new bytes differently from a cold reader for the same immutable ref, or if a legitimate caller must repoint run_id without a versioned ref.

**Where it binds.** register_run, _eval_cache keying, history loader, and the immutable artifact reference persisted with each run.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose the required distributed atomicity and compatibility guarantee, including bounded alternatives and cost; issue a falsifier for the chosen guarantee.” The card and draft address mutable `run_id`, cache identity and replay. The triage step and TRN-02 residual additionally name distributed atomicity/compatibility. Those broader guarantees are not decided here; preserve them as separate residuals.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B133`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/TRN-02.md@sha256:e357afdc8a41beeb2a13493b27e4626cf648031c78c602d841989861253ebc12`.

**Associated E02 package residual (context only; not a closure claim).** TRN-02: legacy zero-vector fallback, live metadata, distributed atomicity open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B133`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L190`.

## la-053

**Question.** Should the old Scientist import address remain a supported compatibility facade, or retire after consumers move to the public calibration owner?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Retain a time-bounded compatibility facade.** Keep the old re-export while internal and documented external consumers migrate; publish a compatibility window and preserve equivalent types/exceptions. **Cost:** Low immediate breakage; ongoing alias, docs, import-surface, and maintenance cost until retirement.

2. **Retire after caller and contract census.** Move ordinary tests/imports to polisyos.calibration, keep only a necessary compatibility test during the declared window, then remove the alias if no supported external consumer remains. **Cost:** Medium migration and release coordination; possible breaking change if the external contract census is incomplete.

**Premises.** The original card finds the old address re-exports the shared calibration owner; ordinary tests still use the old path. A full external compatibility contract/caller census is not established.

**Scope note.** The source card is a calibration_curve address migration. The Appendix C PCL-01 residual uses different mixed/identity wording; retain that as a separate residual.

**Remainder.** The E02 PCL-01 note also names mixed valid/empty and skipped-level identity; that package residual is not settled by choosing this import-address lifetime.

**Falsifier / revisit trigger.** Reopen retirement if a supported external import/config reference is observed after the census, or reopen retention if the declared window ends and no supported caller remains.

**Where it binds.** Scientist backtesting calibration_curve import/FQN, root exports, package docs, and the release compatibility contract.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide skipped-level identity semantics and the compatibility cost; record which identity binds and what evidence would falsify the decision.” The cited LA-053 card is the Scientist `calibration_curve` alias/import migration. The triage step instead asks for skipped-level identity semantics. This card-derived draft covers only alias lifetime and does not answer the skipped-level identity question; the source card/triage pairing supplies no identity-specific options or premise here, so do not infer that the alias decision resolves it. The package’s mixed-valid/empty residual is separate as well. **Open reconciliation:** the triage’s skipped-level identity decision has no matching source-card premise/options in the cited material and remains undrafted/unresolved; do not count the alias-lifetime draft as answering that distinct question.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-053`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PCL-01.md@sha256:3d36d370ac353f97551d1df132fded4671812a4c37af9368d35644a0c89ff7b7`.

**Associated E02 package residual (context only; not a closure claim).** PCL-01: mixed valid/empty, skipped-level identity open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-053`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L335`.

## b169

**Question.** May an aggregate scalar/single interval be projected across a time horizon, and under what producer declaration?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Require horizon-aligned values by default.** Require each time point to bind estimand, units, baseline, origin/cutoff, temporal coordinate, and interval semantics. Permit repetition only from a producer explicitly declaring a stationary constant forecast. **Cost:** Medium: richer producer DTOs and some existing scalar outputs become limited/refused until their meaning is supplied.

2. **Retain scalar as an explicitly aggregate profile.** Allow scalar output only as a typed horizon aggregate or explicitly constant profile; prevent it from being scored as an unqualified temporal trajectory. **Cost:** Medium: preserves simple producers but adds profile/consumer branches and limits cross-profile comparisons.

**Premises.** The adapter currently repeats scalar metrics and one interval across the horizon, but the measurement could be a mean effect, period aggregate, constant forecast, or diagnostic. Those meanings are not interchangeable.

**Remainder.** Production metric and uncertainty-envelope semantics remain unestablished; draws or time-varying variance must not be invented.

**Falsifier / revisit trigger.** Reopen if an admitted production producer declares a scalar as a horizon aggregate yet the chosen profile either rejects it or scores it as pointwise forecasts, or if one-point intervals are treated as predictive intervals without matching outcomes.

**Where it binds.** Forecast input DTO and the Scientist adapter in HistoricalValidationPlan/_predict_with_scientist, before scoring or publication.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose whether BKT-01 promises only the bounded local profile or generic historical-input binding; cost the scope and state an executable falsifier.” The card and draft address when scalar or one-interval output may represent a horizon trajectory. The triage step asks whether BKT-01 is bounded to a local profile or promises generic historical-input binding. This finding-level question does not settle that broader profile boundary.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B169`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-01.md@sha256:c76f38ce7aca6293c316ce907f94ca3fd4d4116d61dc30aac914aebb7177d82b`.

**Associated E02 package residual (context only; not a closure claim).** BKT-01: BKT-01 accepted but findings remain open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B169`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L226`.

## b170

**Question.** Does n_simulation_runs mean independent executions, internal draws, bootstrap replicas, or something else?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Implement independent outer executions.** Define n as independently seeded runs, pass an explicit seed plan to the existing execution owner, and persist requested/started/completed/failed counts plus sufficient distribution statistics. **Cost:** High and roughly proportional to n in compute, storage, and failure handling; honest support for repeated validation.

2. **Support n=1 until the owner implements repetitions.** Accept one run; return typed unsupported/limited for n>1 rather than silently dispatching once. Preserve an explicit PROVIDED-replicates path only when real completed replicates are supplied. **Cost:** Low initial compute/implementation; users lose multi-run support until the owner path exists.

**Premises.** The plan validates the count, but the current scenario dispatch makes one Scientist call for n=1 and n=7 alike. A cache hit is not an independent replica.

**Remainder.** The existing workflow’s internal Monte Carlo draws are not established, and the selected policy does not claim them.

**Falsifier / revisit trigger.** Reopen if plans with different n still produce indistinguishable execution manifests, or if a purported replica is only a cache hit or repeated scalar.

**Where it binds.** HistoricalValidationPlan validation, _run_single_scenario/_predict_with_scientist dispatch, seed ownership, and pre-execution budget admission.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose whether BKT-01 promises only the bounded local profile or generic historical-input binding; cost the scope and state an executable falsifier.” The card and draft address the meaning and execution of `n_simulation_runs`. The triage step asks whether BKT-01 promises a bounded local profile or generic historical-input binding. A repetition/seed decision alone does not establish generic history binding or broader BKT-01 closure.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B170`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-01.md@sha256:c76f38ce7aca6293c316ce907f94ca3fd4d4116d61dc30aac914aebb7177d82b`.

**Associated E02 package residual (context only; not a closure claim).** BKT-01: BKT-01 accepted but findings remain open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B170`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L227`.

## b171

**Question.** Should overall error weight every observation equally or every named scenario equally?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Publish micro and macro as distinct metrics.** Make pooled sufficient-statistic micro error the default overall metric; retain equal-scenario macro under an explicit name and stable scenario identity. **Cost:** Medium: schema, serialization, and consumers must carry counts/weighted sums and both metric names.

2. **Keep equal-scenario macro as the only overall metric.** Require stable substantive scenario IDs and explicitly name the result macro error; do not call it partition-invariant overall error. **Cost:** Low numerical implementation cost, but requires scenario identity discipline and leaves observation-weighted performance unavailable.

**Premises.** A technical repartition of the same residuals changes equal-scenario macro RMSE/MAE and can reverse candidate order; micro-RMSE can be reconstructed from pooled sufficient statistics.

**Remainder.** Comparability of units and weights across different metrics or jurisdictions remains a separate contract.

**Falsifier / revisit trigger.** Reopen if merely sharding one named scenario changes the published micro result, or if a supposedly equal-scenario aggregate changes after technical split/merge without a declared scenario change.

**Where it binds.** Scenario aggregator _aggregate, serialized summary sufficient statistics, and the metric name/weighting contract.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the accepted BKT-02 profile boundary and compatibility cost; state what observed case would reopen it.” This draft follows the finding-level BKT-02 weighting/profile question. The decision remains limited to the stated aggregate metric and does not imply closure of other bounded BKT-02 findings.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B171`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-02.md@sha256:2cc34165f61681fcb2f1023dbdbfcfa106f6cf8820ad7320028d87b891e8aa7e`.

**Associated E02 package residual (context only; not a closure claim).** BKT-02: remain bounded

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B171`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L228`.

## la-004

**Question.** Should the overlapping plugin and base economics implementations share algorithms or remain distinct versioned profiles?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Share only the proven common kernel.** Extract common mechanics only where contract tables match; keep non-equivalent tax/state/time/RNG/budget behavior under distinct versioned model profiles. **Cost:** Medium: mapping/contracts and profile selection are required; reduces duplicate code only at verified overlap.

2. **Keep implementations separate with explicit identities.** Preserve separate owners and identifiers; prohibit implicit cross-profile comparison until a compatibility mapping exists. **Cost:** Medium continuing maintenance and duplicate fixes; lower risk of silently changing model semantics.

**Premises.** The source card confirms overlap but code disproves equivalence across state, units, timestep, tax base, RNG, and budget accounting.

**Remainder.** No evidence establishes either implementation as universally calibrated or suitable for every base ABI; full caller migration remains open.

**Falsifier / revisit trigger.** Reopen consolidation if real paired regimes with equal declared inputs produce different outputs solely because of implementation duplication, or if a profile mapping fails to preserve accounting/RNG behavior.

**Where it binds.** Economic model/profile identity, state/config schema, and the scenario caller selecting the implementation.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose separate fiscal/labor profile compatibility and optimizer/caller retirement scope; cost both options and write a falsifier.” The card and draft address whether overlapping plugin/base economics implementations share only proven common algorithms or remain distinct profiles. The triage step also names optimizer/caller retirement scope; no complete caller census or retirement choice is supplied by this finding-level question.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-004`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ECO-01.md@sha256:907f9484c95dd34716dd3fef73d4b0f3025a22739c4515df506843c7ff7900bc`.

**Associated E02 package residual (context only; not a closure claim).** ECO-01: fiscal/labor profiles non-equivalent; optimizer/caller retirement open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-004`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L286`.

## la-035

**Question.** Should the existing normalized policy_loss_fn remain a named baseline, or should a distinct revenue-maximizing objective be added?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Retain as an explicitly named baseline objective.** Preserve the numerical rule under a profile name that states its balance/constraint semantics; do not advertise it as a generic income-maximizing objective. **Cost:** Low behavior/revalidation cost; requires API/FQN/config cleanup and retains limitations of the baseline.

2. **Add a separate versioned income objective.** Implement a distinct calibrated objective for users whose declared target is income maximization; keep the current baseline available for existing profiles. **Cost:** High: calibration, migration, optimizer validation, and revalidation for each caller; avoids silent ranking change.

**Premises.** The source verifies a normalization that can flatten or alter positive-income ranking, but does not establish a production optimizer using it or a universal user intent to maximize raw income.

**Remainder.** Native optimizer callers, JIT/gradient behavior, and realized policy outcomes are not established; do not remove or retune the baseline on fixture evidence alone.

**Falsifier / revisit trigger.** Reopen if an appointed production optimizer claims income maximization and two positive-income policies are ranked contrary to that declared objective by the baseline.

**Where it binds.** Objective FQN/version and config chosen by the optimizer caller, with native loss/guardrail evaluation.

**Triage next step and card reconciliation.** The recorded triage step is: “Choose separate fiscal/labor profile compatibility and optimizer/caller retirement scope; cost both options and write a falsifier.” The card and draft address the identity and naming of the normalized `policy_loss_fn` baseline versus a distinct income objective. The shared triage step also names fiscal/labor profile compatibility and optimizer/caller retirement; those are separate from objective identity and remain unresolved.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-035`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/ECO-01.md@sha256:907f9484c95dd34716dd3fef73d4b0f3025a22739c4515df506843c7ff7900bc`.

**Associated E02 package residual (context only; not a closure claim).** ECO-01: fiscal/labor profiles non-equivalent; optimizer/caller retirement open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-035`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L317`.

## la-023

**Question.** Should the current rollout loop be named/evaluated as rollout analysis, or connected to a real trainer for a bounded domain?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Relabel current behavior as rollout evaluation.** Return a typed evaluation result and make no learning claim until parameters change; retain rollout/reward collection as a useful capability. **Cost:** Low implementation cost; CLI and callers lose the current train-shaped success surface and still need a trainer for learning.

2. **Integrate the existing trainer for one compatible domain.** Only after a separate explicit appointment and contract establish the training owner's scope for that domain, route through that owner, persist the learned-state artifact, and prove nonzero-gradient parameter/action change with train/eval, RNG, reset, and continuation semantics. This technical option does not make the appointment or confer training authority. **Cost:** High implementation and compute cost, plus owner appointment/scope agreement; requires a compatible state contract and artifact lifecycle.

**Premises.** The inspected train body collects rollout rewards but leaves actor parameters unchanged and makes zero trainer calls; a separate training owner exists.

**Scope note.** The separate training owner's existence does not establish its appointment, scope, or authority for PolisySimulator or any domain. Trainer integration is conditional on a separate explicit appointment and contract for the chosen domain; selecting this option does not make that appointment or grant training authority.

**Remainder.** Until the separate appointment/contract and compatible state contract exist, trainer integration remains unavailable. A local fixture trainer or nonzero gradient is not proof of full domain training quality; keep unsupported domains typed and limited.

**Falsifier / revisit trigger.** Reopen the evaluation-only choice if a caller requires learned state and a compatible trainer can demonstrate parameter and subsequent-action change; reopen trainer integration if it only collects rewards.

**Where it binds.** PolisySimulator.train contract, domain-scoped owner appointment/contract, trainer orchestration, and persisted learned-state artifact.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide cross-domain scope, RNG/continuation compatibility and retirement boundary with costs and a falsifier.” This draft follows the card and triage step at the bounded cross-domain training/rollout decision. Any trainer integration remains conditional on explicit domain owner appointment and contract; no such appointment or learning claim is made.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-023`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PLG-02.md@sha256:595bbfa2ef90c84cb00d2598298e652bc635c027431f149456a3be1247467523`, `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/PLG-03.md@sha256:17b3c7a5945a999829d7b940b39a3b61216626547ba711493f664d259bcdb7cf`.

**Associated E02 package residual (context only; not a closure claim).** PLG-03: cross-domain, RNG/continuation, retirement open

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-023`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L305`.

## b210

**Question.** Should the product remain limited to an explicitly uncorrected RDD estimate until a real correction is computed, or fund the corrected estimator path now?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Publish only the uncorrected limited result.** Remove/withhold the corrected claim and expose the conventional estimate with its typed limitation until a valid correction artifact exists. **Cost:** Low to medium: narrower output and possible refusal of a corrected claim; avoids unsupported inferential authority.

2. **Implement the declared bias-corrected estimator.** Add the appropriate local-polynomial correction and compatible variance/inference path, bound to design and bandwidth inputs, before setting corrected status. **Cost:** High statistical implementation, data, and validation cost; requires specialist owner and broader distinguishing cases.

**Premises.** The source card reports bias correction as included without computing it; a result label must not imply an estimator step absent from the producer.

**Remainder.** Bias-correction method, variance behavior, and RDD scope across real designs remain unestablished until a producer and data-backed validation exist.

**Falsifier / revisit trigger.** Reopen if any served RDD record says corrected while the producer does not execute/persist the correction, or if a supported design has a validated correction that the bounded profile cannot represent.

**Where it binds.** RDD estimator producer, result DTO correction-status field, inference consumer, and any promotion/publication gate.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the RDD assumption/scope boundary and its costs; name a falsifying case before claiming broader closure.” This draft follows the card’s correction-status and RDD scope question. Neither option establishes broader RDD validity without its named estimator/data evidence.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B210`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-03.md@sha256:6b35c44617e38afa5621d02d4517cb9ce37f7350c99082e252e8a8be8cdbc91d`.

**Associated E02 package residual (context only; not a closure claim).** CAU-03: not full RDD closure

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B210`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L267`.

## b106

**Question.** May robustness be claimed over the full declared scenario set, or only over a named sampled/early-stopped subset?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Require complete declared-set accounting.** Stream occurrence, tested-scenario, missing/non-numeric, and completeness counts before display cap; mark early-stopped or incomplete runs unknown/limited. **Cost:** Medium compute and schema work; may delay a result until the declared set finishes.

2. **Allow a named sampled estimate.** Keep bounded/adaptive execution but report the sampling design, inspected denominator, uncertainty, and sampled-score label; never call it full-population robustness. **Cost:** Lower compute and faster feedback; weaker claim and added sampling/uncertainty reporting.

**Premises.** Presentation dedupe/top-k truncation must not alter counts of tested scenarios, observed violations, or non-results; adaptive stopping does not automatically estimate the entire space.

**Remainder.** The explored population is not automatically exhaustive; unique issue examples and presentation cap remain separate from occurrence counts.

**Falsifier / revisit trigger.** Reopen if changing collect_top_k changes robustness score for the same completed scenario set, or if an early-stopped sample is presented as complete population coverage.

**Where it binds.** Robustness aggregator before dedupe/cap, run completeness record, and the surfaced metric name.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the empirical completeness profile, cost and limits; require a falsifier for any claimed complete population.” This draft follows the card’s completeness-denominator question. It does not claim a complete empirical population absent the selected accounting or sampling contract.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5#B106`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@sha256:4d1c879c79bd2a20ba5bf82fbce4b638e440b40208d53468eef9ba2062116e28`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/STR-01.md@sha256:e0532566d84e5e3d62d5e8b03a41eaf96d9a11aa155cc5475a0fb2a5d910d966`.

**Associated E02 package residual (context only; not a closure claim).** STR-01: empirical completeness

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#B106`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L163`.

## la-055

**Question.** Is an explicit stored deny a veto, or is promotion_allowed only an advisory baseline overridden by the final evaluator?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Treat explicit restriction as a veto.** Preserve false/restriction as a binding veto; permit only a separately typed, authorized override with reason and scope. **Cost:** Medium: new override evidence/schema and caller migration; conservative when an explicit restriction was intended to bind.

2. **Make the event flag an advisory baseline.** Rename it as a baseline/readiness hint and let one evaluator compute final permission; carry any institutional restriction in a separate typed veto field. **Cost:** Medium to high: schema and all readers must migrate; avoids treating an advisory flag as final authority but risks old consumers assuming the old meaning.

**Premises.** A constrained R4 event can persist promotion_allowed=False while the evaluator later returns True from state-only interpretation; ordinary mapper-produced R4 usually emits True. The counterexample does not establish an external release action.

**Remainder.** Deployment/live-feed applicability in DDM-02 remains unclaimed; this decision resolves field meaning/precedence only, not feed authority or release service behavior.

**Falsifier / revisit trigger.** Reopen if a mapper-produced explicit false is consumed as a veto by a supported caller but the chosen evaluator allows it, or if every supported caller proves the field is advisory and the veto option blocks an authorized path.

**Where it binds.** ReadinessStateEvent/ModelRegistryReadinessRecord schema, readiness mapper, registry builder/evaluator, and final action consumer.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide whether deployment/live-feed applicability is an in-scope promise and cost the evidence and maintenance obligation.” The card-derived decision below is about the semantics and precedence of `promotion_allowed` (baseline, veto, final gate). The triage next step separately asks whether deployment/live-feed applicability is in scope. A companion scope draft follows and is independent: choosing field semantics does not establish feed evidence, consumer identity, maintenance, or release authority.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-055`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DDM-02.md@sha256:02fc4f7f19d1e668b35edf2d4ef547cc85c4ae1c4411e3e4182a9f2aaa48db98`.

**Associated E02 package residual (context only; not a closure claim).** DDM-02: deployment/live feed not claimed

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-055`.

### Separate principal scope question from the LA-055 card decision

This companion addresses the LA-055 triage next step about deployment/live-feed applicability. It is not the card-level `promotion_allowed` precedence decision above. Both remain `awaiting_principal`; neither authorizes a release action.

**Question.** Is deployment/live-feed applicability an in-scope promise for DDM-02, or should the current claim remain bounded to readiness-gate semantics until feed evidence and its consumer are established?

**Options and costs.**

1. **Include deployment/live-feed applicability conditionally on admitted evidence.** Define the supported feed/consumer profile and require an admitted data record with provenance, time, and consumer identity, plus currentness and failure handling, before any deployment/live-feed applicability claim. **Cost:** High: identify the producing and consuming owners, preserve the evidence and maintenance lifecycle, and validate missing, delayed, stale, and complete-window behavior. Until that chain exists, outputs remain typed `not_established` for live applicability.
2. **Keep deployment/live-feed applicability outside the present claim.** Bound DDM-02 to the evidenced readiness-state and gate semantics; require a separately scoped, evidence-backed extension before claiming that a live deployment feed is covered. **Cost:** Lower immediate integration/maintenance cost, but live consumers receive no readiness assurance from this bounded profile and need a distinct owner/evidence path before making that claim.

**Premises.** The LA-055 card reproduces a state-gate disagreement but explicitly does not establish an external release action; it also says an empty signal set is valid only if observation completeness and delivery are assured. The corrected triage puts LA-054 in c for the separate DDM-02 P40 smallest-missing-capability blocker: checker-bound/content-bound validity-owner handoff and model_registry_record contract. The deployment/live-feed data record remains a distinct residual for this LA-055 scope question. Neither fact establishes a supported live consumer or an admitted feed record.

**Remainder.** This choice cannot create the LA-054 checker-bound validity capability or the separate deployment/live-feed data record, appoint an external producer, prove a supported live consumer, or confer release authority. Feed currentness, owner appointment, deployment integration, and upkeep remain unestablished until their own evidence is supplied. The `promotion_allowed` baseline/veto/final precedence remains the separate card-level decision above.

**Falsifier / revisit trigger.** Reopen an out-of-scope boundary if a supported consumer presents DDM-02 as live-feed or deployment assurance, or if a named consumer and admitted evidence record establish a concrete in-scope capability. Reopen conditional inclusion if any live applicability claim is emitted with absent, stale, or unbound feed evidence, or if the evidence-maintenance owner cannot sustain the declared profile.

**Where it binds.** DDM-02 applicability/profile contract at the readiness input and `ReadinessStateEvent`/`ModelRegistryReadinessRecord` projection, with evidence admission before `evaluate_registry_gate` and the consumer’s eligibility interpretation. Any external deployment action remains with its appointed owner.

**Sources for this separate scope question.** Triage: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/partial_triage.json@sha256:ba3b6f086823f44caf204c5c2922021f44fb6c9001eb91e39ea80d733b64f994#LA-055`; separate capability blocker LA-054 plus live-feed residual: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-054` and `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/PARTIAL_TRIAGE.md@sha256:f9cf1d49ed73eb54b2a1302bc44fa9654d121a97184618dfac9d6e5ab8029c1d#LA-054`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L337`.

## la-018

**Question.** Is the old Lex factlog reader a supported external facade or an internal alias to retire after callers migrate?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Retain a documented compatibility facade.** Keep a thin re-export for a declared compatibility window; preserve authorization and provenance behavior and publish the support boundary. **Cost:** Low immediate breakage; continued API/docs/test maintenance and import-surface complexity.

2. **Retire after complete consumer census.** Move all supported internal callers to the Fabric public owner, verify root exports/config/imports, then delete the alias with a release note. **Cost:** Medium caller/release coordination and possible external break if census is incomplete; lowers ongoing duplication.

**Premises.** The owner has moved to Fabric; the current source does not establish the complete caller census or external API status.

**Remainder.** External support status and full caller census remain unestablished; no arbitrary sunset date is justified.

**Falsifier / revisit trigger.** Reopen alias removal if a supported external consumer still resolves it, or reopen retention after the agreed window if no supported caller remains.

**Where it binds.** Lex factlog alias import path, root exports, package docs/config strings, and compatibility policy.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the compatibility lifetime for retained aliases and the cost of preserving or retiring them; state the falsifier.” This draft follows the card and triage next step on the compatibility lifetime of the Lex factlog alias. It does not claim that every downstream consumer has been enumerated.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-018`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/HYG-02.md@sha256:745a0c9188e2a3e50850be4c089dbbbf1b0c06c790b67fb927b1e1e1544cf1fe`.

**Associated E02 package residual (context only; not a closure claim).** HYG-02: Lex factlog facade; _shim retirement; aliases retained

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-018`.

**Plan/register relation.** The complete scoped crosswalk admits no direct GY, Atlas, or live-register relation for this finding (`not_established`; not proof of no dependency). See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L300`.

## la-043

**Question.** Should the raw generated client pair remain a supported compatibility artifact, or move to canonical public outputs and scratch-only intermediates?

**Owner/status.** Principal (Denis); `awaiting_principal`. No ruling is recorded.

**Options and costs.**

1. **Keep raw pair during a declared compatibility window.** Treat raw TS/JS as managed generated intermediates while migrating tests/checker/direct consumers; retain one canonical generator and full-family freshness verification. **Cost:** Medium ongoing generated-output, registry, test, and duplicate-surface maintenance.

2. **Retire committed raw pair after full consumer migration.** Move tests and verifier to canonical public exports; redirect generation to isolated scratch/managed outputs; remove raw committed files only after the full caller and output-family census passes. **Cost:** Medium to high migration/typecheck/release cost; may break an undiscovered filesystem consumer.

**Premises.** Package exports already point to the canonical twin, while repository tests and the standalone checker still consume raw files; broader generated-family freshness exists and should be reused.

**Remainder.** External filesystem imports and full endpoint correctness remain unestablished; byte agreement alone is not endpoint execution evidence.

**Falsifier / revisit trigger.** Reopen removal if a supported raw-file consumer appears or the full required-generated-family gate does not cover a canonical output; reopen retention if the declared window ends with no supported raw consumer.

**Where it binds.** runtime-api-client package exports, generator/output ownership, public imports, tests, standalone contract checker, and generated-artifact registry.

**Triage next step and card reconciliation.** The recorded triage step is: “Decide the public compatibility promise for the full legacy client surface and the cost of removal or ongoing support.” This draft follows the card and triage next step on the public compatibility promise for the legacy generated client. The direct Atlas DS3 artifact overlap is not evidence that all filesystem callers have been found or that the compatibility decision is closed.

**Audit card and package mapping.** Card: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727#LA-043`. Mapping source: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@sha256:5390bc21cab5901487c00b2fa68b6396294a5b95e809fd91bc2053d9f2ab6a8e`; Declared bundle(s): `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CLI-01.md@sha256:ec10690675c935d253d1f8498a311c755d6cab2f9a89a23b8ce9f405c33ef8e2`.

**Associated E02 package residual (context only; not a closure claim).** CLI-01: full client LA not closed

E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`.
E02 record: `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e#LA-043`.

**Plan/register relation.** The admitted relation is `touches code named by` Atlas DS3 for runtime-client compatibility artifacts. It does not establish caller compatibility, generated-surface acceptance, or closure; no direct GY or live-register relation is admitted. See `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L48`, `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md@sha256:05529c78012ab7ec3e265feec50a926b1ba93d7352cb08eb653641fe8f27dc05#L325` and `policy-engine/docs/plans/active/atlas-slices/DS3-runtime-producers.md@sha256:e87bb63c8c34fc5993e06d97ed607e938bcc544abe9158d48130ca96aae51408`.

## Link compatibility

Projection reconciliation: the 16 lowercase decision headings in this committed file match exactly the 16 bucket=b IDs in partial_triage.json. LA-055 keeps a separate applicability-scope question from LA-054’s P40 capability blocker. Triage source: policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/PARTIAL_TRIAGE.md@sha256:f9cf1d49ed73eb54b2a1302bc44fa9654d121a97184618dfac9d6e5ab8029c1d; JSON source: policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/partial_triage.json@sha256:ba3b6f086823f44caf204c5c2922021f44fb6c9001eb91e39ea80d733b64f994.
