# S3 / V4–V7 default-owner chain review

Read-only source review pinned to `077a572ff5880b3f50a85d3e3db6a232d277659a`
(tree `2895b6c7597215b714275cb4ba83a504724dc89c`). Product claims below come from
`git show <pin>:<path>`; the shared checkout is dirty with peer work and is not the source
baseline. No product source, tests, generators, or Git state were changed by this review. No
numerical fit or test suite was run here.

## Criteria and scope

The original-source pointers are the immutable B/LA criterion rows already cross-referenced by
`closure-decisions/coverage.json` at the pin:

| Criterion | Original block and SHA-256 | Coverage membership and current ledger fields |
| --- | --- | --- |
| B31 | `B_r19_original.md:593–606`, `9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f` | EMP-01 once; historical `held`; `closure_now=not_adjudicated`; capability `absent/unallocated` |
| B32 | `B_r19_original.md:607–620`, `68a3acb0a34e8ebfce5217cdc99785a851a21368ea2d552795f68272e7140d6c` | FRC-01 once; historical `partial`; separate appendix `closed_bounded`; `closure_now=not_adjudicated` |
| LA-051 | `LA_r09_original.md:3712–3746`, `5d3fe7ce8b71d77c07f35e5a68fed244c0d40e0f24925714edbf7297c37ea616` | Same source block mapped to both FRC-01 and FRC-02; historical and appendix `partial`; `closure_now=not_adjudicated` |

B31's criterion is the distinction between identification bounds and native statistical/model
uncertainty for the same estimand and unit: retain the exact native interval, including asymmetry;
point identification may remain `[estimate, estimate]`; do not fabricate a proxy width or treat a
method name as the estimand. B32 and LA-051 require distinct time roles and real compatible
held-out predictive evidence; finite estimator shape, nominal confidence, or a caller-supplied
reference tuple cannot turn into empirical calibration. Predictive evidence remains outside causal
and treatment-assignment authority. The duplicate LA-051 rows are two bundle memberships of one
criterion occurrence, not two independent source blocks.

## Actual N8 value path at the pin

`GenerationCycle.__init__` installs `_DefaultSimulationBoundFoundryValuePort` as its default at
`runtime/quality/generation_cycle.py:5413–5420`. It derives EvalSafety context from the actual N5
output and calls `FoundryValuePort` (`5167–5236`). The default gateway constructed by
`FoundryValuePort.__init__` is only `RealValueOwnerGateway(repo_root, cycle_substrate_context)`;
although both types have optional `ArtifactStore` fields and the port itself accepts a store, this
default construction does not pass the store or an empirical-evidence resolver to the gateway
(`4600–4631`). An acquisition re-entry can explicitly pass its store and observation projection
(`6114–6125`), but still does not install an evidence resolver.

The live `FoundryValuePort.__call__` sequence verifies EvalSafety and WMR, asks the gateway for a
`ValueDataProfile`, derives method-selection inputs, validates the selector's receipt against that
profile, and checks candidate estimand binding (`4847–4974`). It then returns
`treatment_assignment_not_owner_derived` (`4975–4998`). It does not execute the selected method,
obtain a `MethodResult`, call `RealValueOwnerGateway.produce_forecast_inputs`, invoke
`_value_outer_set_from_foundry_result`, or emit `ValueGateReceipt`. The source census below
confirms the last three methods are not merely bypassed in the inspected call stack; they have no
in-tree production callsites at this pin.

The narrow treatment failure is an actual owner boundary, not an absent candidate field. The
gateway resolves the target outcome from the problem or target slot, then queries selected L1
DCAT observations (`9829–9837`, `9849–10238`). `ValueDataProfile` verifies row/unit/period counts,
row hashes and a derived modality (`1120–1213`). It records the outcome, `unit_id`, period,
outcome value, source-row hashes, owner-access ref and hashes. The loader also checks that the
profile has exactly one source dataset and one declared measurement unit; for activated observations
it verifies the passport's canonical unit and identity transform (`9925–9940`, `10152–10238`).
However, measurement units and dataset identity are used in source-row hashes and then are not
fields on `ValueDataProfile`; `unit_id` is an observation grouping key (country or scoped region),
not a treatment assignment. The profile explicitly says
`treatment_assignment_status="owner_assignment_unresolved"`. No emitted profile artifact/ref
preserves a consumer-resolvable link from the rows to a causal treatment/exposure assignment.

`DesignProblem.outcome_of_interest` has a target variable and an estimand string, but those are
problem/request semantics, not an owner-produced treatment relation (`design_problem.py:188–203`).
The candidate's atom and exposure fields are explicitly rejected as world knowledge. The
acquisition planner records exactly two still-unsatisfied alternatives—an owner rollout assignment
or a certified SKG identity bridge—and describes the gap as routing-only (`acquisition_planner.py:346–358`,
`3781–3843`). The Foundry simulation assignment helpers are generated treatment mechanisms for
simulated worlds, not observed production assignments (`foundry/agent_sim/world/operators/interventions.py:13–67`);
they cannot fill this gap.

The source report contract exists, but does not fix the missing bridge. `CausalEffectReport` has a
method enum, free-form `estimand`, point, confidence interval, diagnostics, and generic metadata;
it does not type-bind source rows, subject, or measurement unit (`ir/analytics/causal.py:212–286`).
`persist_causal_effect_report` can persist a report with arbitrary input edges, but no default N8
method run produces one. Its uncertainty conversion preserves report point/interval while marking
the result `gate_eligible=False` until causal identification admission (`288–357`).
`NativeValueEstimandBinding` describes the missing kind of relation, but explicitly says it is a
caller-constructible `contract_only_nonproduction` request (`ir/analytics/uncertainty.py:126–168`).

`ValueOuterSet` now has separate optional `statistical_lower` / `statistical_upper` descriptive
fields alongside identification `lower` / `upper` (`core/contracts/value_outer_set.py:151–188`).
The helper `_value_outer_set_from_foundry_result` keeps a point-identified `[4,4]` separate from
native `[1,10]` and preserves the raw interval (`generation_cycle.py:11681–11740`); the existing
EMP-01 test covers that projection with a synthetic `SimpleNamespace` report and receipts
(`tests/unit/remediation/test_emp_01.py:22–65,362–387`). The helper still uses the report's method
name as its coordinate, and no method report, source-profile ref, unit binding, or envelope ref
reaches `ValueGateReceipt` (`generation_cycle.py:1268–1286`). These are useful exact helper
semantics, not an actual default owner join.

## Actual predictive/calibration owner and missing consumer bridge

`ForecastOwnerRequest` is a real, typed CAS-bound request: it names an observed source ref, exact
train/holdout split, target metric, ETS method, explicit calibration-rule artifact and six
timezone-aware temporal roles. Model/policy refs and additional manifest inputs are optional
(`scientist/methods/backtesting/forecast_owner.py:195–239`). The six times are caller-provided;
the validator checks awareness, distinctness, and order but does not resolve them from the source
clock (`120–156`). The source `DataSnapshot` carries data/artifact refs and stats but no timestamp
axis from which the owner could derive all six roles (`core/contracts/fabric.py:161–175`).

`ForecastOwner.run` resolves the source and the rule artifact, runs the registered ETS method on
the exact training slice, reads real held-out outcomes, validates persisted predictive intervals,
and recomputes coverage numerators, denominators and suitability (`forecast_owner.py:505–649`,
`718–770`, `934–969`). It persists the training slice, method artifact, uncertainty bundle,
diagnostics and a `BacktestReport`; the report records the six request times and the normal source,
rule, method, training, bundle, and diagnostics input edges (`653–699`, `772–887`). Its result is
explicitly `authority_scope="predictive_only"` and `bridge_status="bridge_pending"`.

The existing FRC-02 semantic test is a real positive/negative predictive-owner discriminator:
same training series and same method produce the same point forecast and predictive intervals for
two different held-out outcome vectors; coverage numerator and `empirical_suitability` change.
Fresh report readback and `produce_empirical_calibration_evidence` reproduce those counts. With
no actual semantic context refs, both results remain `context_bound=False`,
`usable_for_calibration=False`, carry `explicit_context_missing`, and persistence is refused without
adding artifacts (`tests/unit/remediation/test_frc_02_empirical_bridge.py:34–99`). The existing local
receipt `s3-empirical/frc02-empirical-bridge-test.stdout.txt` records 33 passing tests; this review
did not rerun it. This proves that real held-out outcomes can change a predictive grade while
intervals stay fixed. It proves no causal effect, treatment assignment, S10 authority, or
context-complete default consumer.

`forecast_bridge.py` already has the right CAS protocol to reuse: eight exact context role profiles
(`scope_binding`, threshold, observed outcome, prediction, evaluation design, credible evaluation,
source lineage and method lineage; lines 70–126); `EmpiricalCalibrationContext` requires the refs,
method/rule/estimand, model-policy pair, threshold and six time roles (`230–317`). The producer
recomputes held-out interval hits, validates every reference profile and the matching report input
edge/payload identity, then derives evidence (`388–500`, `827–897`). Evidence persistence and fresh
readback reproduce the computation rather than trusting DTO status (`502–583`, `623–640`). This
is a strong consumer; the source gap is the producer/orchestration bridge into it.

The current `ForecastOwner` does not emit those eight typed role artifacts. Its required report
edges are ordinary `observed_source`, `observed_data`, `calibration_rule`, `training_slice`,
`method_artifact`, `uncertainty_bundle`, `calibration_diagnostics`, plus optional model/policy
edges. `manifest_inputs` can append caller-supplied edges, but the owner does not turn those refs
into owner-derived facts. Reusing them would make a report look context-complete without resolving
the missing owners. The bridge additionally requires both actual model and policy refs, which the
owner permits omitting. Its persisted role-time comparison now prevents a well-ordered context from
silently rebinding report times, but it only proves equality to times originally supplied in the
request; it does not authenticate those times against a source clock (`forecast_bridge.py:1165–1301`).
The empirical threshold in `EmpiricalCalibrationContext` is also a separate minimum-pass rule; the
forecast request's `CalibrationRuleArtifact.nominal_coverage` is the target prediction interval
level, not that minimum. No source owner presently maps these two semantics.

The other half is not default-wired. `RealValueOwnerGateway` has an optional resolver defaulting to
`None` (`generation_cycle.py:4291–4300`); `produce_forecast_inputs` is defined but not called by
`FoundryValuePort`. `_build_real_s10_forecast_inputs` expects the method result to carry an evidence
ref, expected rule version and temporal roles, and resolves only through the injected resolver
(`10803–10858`, `11036–11078`). The actual generic `MethodResult` contract has output/timing/
reproducibility, optional sidecar artifacts and warnings, but no required empirical evidence
binding (`foundry/methods/backends/protocol.py:177–198`). Even if an evidence ref were added, the
predictive owner is a separate ETS owner; its predictive result must not become the causal effect
CI, the treatment assignment, or a causal/S10 grade.

The S10 estimator-only guard at this pin is honest: a finite report yields denominator/numerator
zero, no interval-coverage or calibration-error metric, `floor_passed=False`, and a blocked forecast
tier (`generation_cycle.py:11141–11180`). An existing default-reader receipt shows a finite CI is
refused with no calibration record and the typed missing-evidence limitation
(`s3-empirical/default-s10-negative-reader.txt`). That negative result does not turn the uncalled
private builder into a capability.

## Complete source census and distinguishing property

I archived the complete pinned `policy-engine/src/polisyos` subtree in memory, parsed every Python
file with `ast.parse`, and counted the complete denominator. There are **2,709 Python source files,
2,709 parsed, zero parse errors**; `runtime/http` contributes 116 of them. On that denominator:

| Source symbol | Definitions | Production calls in `src/polisyos` |
| --- | ---: | ---: |
| `produce_forecast_inputs` | 2 | 0 |
| `_build_real_s10_forecast_inputs` | 1 | 1 (only from the uncalled `RealValueOwnerGateway` method) |
| `_resolve_s10_empirical_evidence` | 1 | 1 (only within the private S10 builder) |
| `produce_empirical_calibration_evidence` | 1 | 1 (its internal replay call in `_reproduce_evidence`) |
| `persist_empirical_calibration_evidence` | 1 | 0 |
| `load_empirical_calibration_evidence` | 1 | 0 |
| `ForecastOwner` | 1 class | 1 construction (only in `run_forecast_owner`) |
| `run_forecast_owner` | 1 | 0 |
| `_value_outer_set_from_foundry_result` | 1 | 0 |

The full-source grep at this pin finds no `ForecastOwner` or empirical-evidence consumer in the
116-file `runtime/http` subset. This census excludes tests and external callers by definition; it
settles the in-tree default wiring question, not what a separately invoked library client may do.
The old README census of 2,707 source files is stale at this pin; this measured denominator is
2,709.

The property/divergence is now explicit (P38): the property is a same-source, same-subject,
same-estimand join that preserves point identification and native statistical CI, while changing
held-out outcomes can alter only the predictive empirical grade. The current implementations
measure two narrower things correctly: the helper projects numeric report fields, and the bridge
recomputes a persisted predictive report when context is supplied. They do not measure the actual
default causal/report-to-profile relation because the default path exits before method execution;
they do not measure source-authentic time roles because the forecast request supplies them. A
report with point `4` and interval `[1,10]` plus a caller-created matching subject/unit string would
therefore still not prove the required relation.

## Reuse-first options and owner proposal

1. **Reuse:** keep `ValueOuterSet`'s separate statistical endpoint fields, `CausalEffectReport`/
   `UncertaintyEnvelope`, the existing `ForecastOwner`, the existing CAS `BacktestReport`, and the
   current `forecast_bridge` reference validation. Do not add another envelope or calibration
   schema that duplicates these owners.
2. **Extend:** only after the source owners exist, extend `ForecastOwner` to emit its own exact
   role projections from the actual source, split, method, rule and persisted evaluation—not
   accept caller-created role refs. A default predictive consumer must fresh-load the persisted
   evidence through the existing resolver protocol. The extension must remain predictive-only.
   The unresolved threshold/credible-evaluation meaning and source-clock roles need named owners
   before this can be `usable_for_calibration`; current request timestamps are declarations, not
   source facts.
3. **Consolidate:** keep one source-bound resolver/bridge as the only path from persisted
   predictive evidence to the predictive forecast consumer. Do not make the causal `FoundryValuePort`
   reuse an ETS report to satisfy a value interval, or enable the private helper merely by wiring
   around the existing treatment-assignment block.
4. **Build-new only if needed:** if source owners cannot express these roles, bring a narrow,
   versioned proposal for the missing predictive evaluation/source-time relation or causal
   value-run relation. Name an owner for each external fact and an authority boundary first. Do not
   infer subject, treatment, threshold, times or credible-evaluation law from `DesignProblem`,
   candidate fields, method strings, or a hand-authored fixture.

For B31, the smallest missing causal input is a real owner-derived treatment/exposure assignment
bound to the profile's actual unit/time rows (or the separately listed certified SKG identity
bridge), followed by an actual method run that binds the report and native envelope to that
profile. The profile's outcome can be reused. Its checked measurement-unit basis must first be
surfaced by the owner; at present it is included only in opaque source-row hashes. Neither fact
proves the exposure relation. Until then, keep the current typed blocker; no positive value receipt
is licensed. For the predictive FRC path, the smallest internal bridge is an owner-produced role
artifact set and a default fresh-reader consumer. The external semantic dependencies still include
an authenticated source-time basis and a declared minimum calibration threshold/credible-evaluation
rule. The existing helper/projection is not a substitute for either bridge.

G decision alternatives if this work is re-opened:

| Route | Owner and smallest footprint | Authority boundary | Timing dependency |
| --- | --- | --- | --- |
| Predictive FRC extension | ForecastOwner owner extends `scientist/methods/backtesting/forecast_owner.py` and its mirrored owner/bridge tests; runtime owner wires a default predictive reader only if there is a real forecast consumer. Reuse the eight `forecast_bridge` profiles and CAS loader. | Predictive-only `ForecastOwnerResult`/evidence; cannot satisfy causal effect or treatment assignment. | Medium engineering footprint; cannot estimate an end date until the source-time owner and minimum calibration/credible-evaluation rule are named. |
| B31 value-run binding | N8 runtime owner plus the owner of the acquired rollout-assignment or SKG identity relation; likely source paths are `runtime/quality/generation_cycle.py`, the source owner that supplies the assignment, and mirrored value-gate tests. Reuse the current report/envelope and `ValueOuterSet` types where possible. | Keep `treatment_assignment_not_owner_derived` until an independently resolved relation is consumed; a candidate report/envelope remains non-authoritative. | Unestimated until the external assignment source and the corresponding subject/unit semantics are available; code-only work cannot supply them. |
| Bounded residual | No product code. Keep the existing refusal and the already available local empirical positive/negative witness. | No new authority. | Available now; residual persists until its source owners provide the required facts. |

## P40 bucket, bounded residual and falsifiers

This is the **same producer-to-consumer binding class one level deeper**, not a new interval or
calibration law: one helper preserved endpoints without an owner report/profile binding; the whole
default method/report/consumer path is absent before that helper. For the second finding in this
class, widen the proposed mechanism to the entire relevant chain or record the bounded residual
below; do not add another fixture-only helper. The source falsifiers already present are concrete:

- `tests/unit/runtime/quality/test_value_gate.py:2515–2592` supplies caller-created treatment IDs,
  `authority="owner_derived"`, a fake ref and fake hash. The real profile is unchanged and the
  port remains blocked without a value receipt. This falsifies “candidate-shaped assignment data is
  owner world knowledge.”
- `tests/unit/remediation/test_frc_02_empirical_bridge.py:34–99` keeps actual predictive intervals
  fixed while held-out outcomes change. Owner suitability and recomputed coverage change, while
  missing semantic context still prevents evidence persistence. This falsifies “same CI means same
  calibration grade” and “heldout data alone supplies all context.”
- `tests/unit/remediation/test_emp_01.py:362–387` falsifies “point identification makes statistical
  uncertainty zero” and “proxy endpoints can be symmetrized.” It is a projection-only test, not a
  source join.

The smallest future full-chain acceptance should add one genuine source fixture with a real owner
assignment, persist the actual profile/method report/native envelope, and consume it through a fresh
CAS reader. With numbers fixed at point `4` and native CI `[1,10]`, change the report's unit,
subject, source profile, estimand, method, or report ref one at a time and require refusal unless
the producer recomputes the exact relation. Preserve same-estimand comparability when only the
method changes. Separately, reuse the existing real forecast-owner control: same intervals with
different actual outcomes must change the predictive grade; empty denominator, malformed/absent
role edges, mismatched threshold, any one changed time role, causal-purpose payload, missing resolver,
and a forged caller ref must all refuse. The resulting forecast artifact must state predictive-only
and cannot enter the causal ValueOuterSet path.

**Bounded residual for this pin:** no owner-derived treatment assignment/SKG identity bridge is
acquired; `ValueDataProfile` has no persisted source/unit binding artifact; the default N8 path
stops before method execution; `ValueGateReceipt` lacks report/envelope/subject-unit refs; and the
predictive owner has no source-authenticated six-role time input or complete role-artifact producer
and no default fresh-reader consumer. These facts are sufficient to keep B31, B32 and both LA-051
memberships `not_adjudicated`; they do not establish an erroneous published value or causal claim.

Pattern pass: P01/P02 (owner chain and orchestration), P05/P10 (no authority from fields or
finite shape), P07/P08 (rule/time binding), P14 (predictive evidence is not causal), P27/P29
(reuse the real owner and prove fresh readback), P31/P32 (close the class at the intake/emission
owners), P37/P38 (classify predicates and the implementation/property gap), P40 (same-class ladder),
and P41 (this is pinned source review, not a replayed test result). Acceptance must be a real
owner-produced artifact, complete CAS edges, fresh consumer recomputation, and the stated removal/
mismatch controls. No synthetic local fixture is presented as an external fact.
