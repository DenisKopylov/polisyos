# S3 empirical value and calibration handoff

This is a local research/handoff record for the S3 empirical slice. It is not a formal E02
closure artifact. The root owns staging and commits.

## Public-surface generation attribution correction

The earlier statement in this handoff that I had not generated the modified public-surface files
was wrong. Root's direct-agent rollout `01a11fc9-f540-7e41-b8dc-a9ab7b3b2377` shows that I ran
`tools/devx/architecture/guardrails.py sync` with `LOCAL/raw` output overrides at 13:21:25Z, then
ran the following command with its default outputs at 13:21:53.823Z:

```text
.venv/bin/python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline
```

The latter run matches the 13:22:01Z modification times of
`architecture/public_surface/inventory.json` and `docs/reference/public-surface.md`. The retained
rollout summary does not include the first invocation's complete override arguments. I withdraw my
earlier denial. The files were preserved; root will regenerate the canonical surfaces after owner
source changes stabilize. I have not run a generator during this continuation.

## Original criteria and source occurrences

I read the complete `closure-decisions/coverage.json` set (127 bundles, 282 findings, 291 canonical
source-block occurrences; file `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json`,
blob `8c0a7af03fbebb3e57475bc3b2fcf0d3eb6104bf`). The target occurrences are:

| Finding | Original source block | Coverage occurrence(s) | Original criterion |
| --- | --- | --- | --- |
| B16 | `source/B_r19_original.md`, lines 387–398; EMP-01 | `B_r19:387–398`, one occurrence | Scope is applied before truncation and aggregation; foreign-region rows cannot crowd out scoped rows; mixed measurement units are not averaged without a declared rule; a truly small sample is not mislabeled complete; changed scope changes consumed rows and identity. The source explicitly does not claim a published causal effect was wrong. |
| B31 | `source/B_r19_original.md`, lines 593–606; EMP-01 | `B_r19:593–606`, one occurrence | Keep native statistical/model uncertainty separate from the identification set; never symmetrize, shrink, or invent a width; retain an asymmetric interval; point identification may remain `[estimate, estimate]`; methods for the same subject/estimand must not become different coordinates solely by method name. The source says production N8 refusal means no erroneous published result is established. |
| B32 | `source/B_r19_original.md`, lines 607–620; FRC-01 | `B_r19:607–620`, one occurrence | Do not reuse one date for distinct time roles or infer credibility/floor from absence; obtain time and evidence from bound owners; no empirical calibration record for an unobserved conditional simulation; preserve old artifacts. |
| LA-051 | `source/LA_r09_original.md`, lines 3712–3746; FRC-01 and FRC-02 | same `LA_r09:3712–3746` block mapped twice; one source block, two coverage memberships | Separate estimator diagnostics from empirical calibration admission; use an actual compatible calibration producer with held-out prediction/outcome evidence, explicit six-role timing and model/rule/source bindings; no positive pass from finite CI, nominal confidence, or caller-constructed refs. Preserve predictive/causal separation and existing WMR/EvalSafety gates. |

The E02 source bundle reproduces the original prose in `bundles/EMP-01.md`, `bundles/FRC-01.md`,
and `bundles/FRC-02.md`. The SHA for B16 is `fddf1601c092be1f87a19a79a3f6975264850d8df9428e3f54bd3f8fe48d8706`; B31 is
`9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f`; B32 is
`68a3acb0a34e8ebfce5217cdc99785a851a21368ea2d552795f68272e7140d6c`; LA-051 is
`5d3fe7ce8b71d77c07f35e5a68fed244c0d40e0f24925714edbf7297c37ea616`.

The coverage ledger's existing statuses are not formal closure: B16 and B32 are `partial`, B31 is
`held`, LA-051 is `partial`, and all four have `closure_now=not_adjudicated`. B32's appendix has a
separate `closed_bounded` notation; it does not replace the original criterion or production-path
check.

## Current owner footprint

- `ValueOuterSet` owns the identification bounds. Before this change, `_value_outer_set_from_foundry_result`
  retained `[point, point]` for `point` but discarded the report CI; for `proxy` it invented a
  symmetric interval from `max(half CI width, 10% of estimate, 0.01)`, and for other statuses it
  widened a zero-width interval by `0.01`. It used the method string as the coordinate. These are
  source facts from `runtime/quality/generation_cycle.py`; no positive production consumer or wrong
  published result is established.
- `UncertaintyEnvelope` and `UncertaintyEnvelopeRef` already exist, with CAS persist/load functions
  in `ir/analytics/uncertainty.py`. The current `ValueGateReceipt` has no envelope ref, source-report
  ref, or resolved subject/unit binding. `NativeValueEstimandBinding` explicitly remains
  `contract_only_nonproduction`, so it cannot be used as a production relation.
- `_value_outer_set_from_foundry_result` has no call site in the live N8 path. `FoundryValuePort`
  currently stops at `treatment_assignment_not_owner_derived`, before an actual method report
  reaches that helper. The helper witnesses below are deterministic projection tests, not a
  production-chain receipt.
- `ForecastOwner` is a real local ETS owner that persists a `BacktestReport` and held-out
  predictions/outcomes. Its result remains `bridge_pending`. `forecast_bridge.py` recomputes and
  reconciles report observations, but a context-free result carries `explicit_context_missing` and
  `persist_empirical_calibration_evidence` refuses it. A full context requires role-bound refs for
  scope, threshold, observed outcomes, predictions, evaluation design, credible evaluation,
  source/method lineage, and all six distinct times.
- The S10 consumer has a resolver seam, but `RealValueOwnerGateway` defaults it to `None`; its
  normal runtime method result does not expose a bridge-produced evidence ref. The positive S10
  fixture injects a resolver and builds synthetic reports/refs. Predictive evidence is explicitly
  `predictive_only` and denies causal, treatment-assignment, and S10 authority. No compatible
  production resolver/context chain is established.

The missing relation is the same S3 binding class one level deeper (P40), not a new contract class:
the owner must persist a source-bound uncertainty envelope and resolved subject/unit; an independent
reader must resolve and content-bind both to the exact report/value claim and recompute the join.
The smallest missing capability is that owner-bound producer/exposure plus consumer readback.
Removing the ref, changing the subject or unit while keeping values the same, or replacing it with a
caller-constructed ref must fail closed. The production owner paths do not currently carry enough
information to implement a generic join law; no such law is introduced here.

### G decision packet: subject/unit binding

This is unresolved semantics, not a reason to mint a generic join contract. Three bounded routes
remain for G:

1. **Reuse an owner-supplied binding:** use an existing producer-owned estimand and canonical-unit
   binding only after the same owner resolves it from the controlled profile; persist the exact
   binding with the source report and envelope. Current `ValueOuterSet` and `ValueGateReceipt` do
   not carry that relation.
2. **Name a new typed relation:** if no current owner supplies the relation, specify the smallest
   producer receipt that binds source-report ref, `UncertaintyEnvelopeRef`, subject/estimand,
   unit, method/rule and source provenance. This requires an appointed resolver/owner and
   independent consumer recomputation. This is a candidate design option, not an implemented
   contract or an admitted law.
3. **Retain candidate-only descriptive endpoints:** preserve the exact report interval in the new
   fields, keep the output limited, and defer any cross-artifact semantic join. This is the current
   safe boundary until options 1 or 2 have an appointed owner and a falsifying test.

Discriminator: hold numbers fixed while changing subject or unit; a valid join must reject. Hold
subject/unit fixed while swapping method provenance; the relation must remain stable if those
methods estimate the same estimand. Remove the persisted ref while leaving endpoint fields present;
the reader must refuse any binding-dependent use. The smallest capability that closes the residual
is an owner-resolved persisted subject-unit envelope binding plus a current consumer that resolves
and content-binds it. The current path lacks both.

## Changes in this candidate

`core/contracts/value_outer_set.py` now accepts optional paired `statistical_lower` and
`statistical_upper` tuples for source-reported interval endpoints. It validates finite values,
pairing, dimensional alignment, and endpoint order; persists the fields; and includes them in
canonical content only when present so existing no-statistics payload hashes retain their prior
shape. They do not change identification bounds, comparison, width, or promotion. The contract
still does not identify the source report, estimand, measurement unit, or authority.

Mirrored tests prove point `[4,4]` plus native CI `[1,10]` survive the contract, promotion stays
unchanged, persisted payload round-trips, and incomplete/misaligned/reversed bounds reject. V1's
deterministic helper change now emits exact native endpoints separately, preserves point
identification at `[4,4]`, and removes proxy symmetrization and artificial `±0.01` widening.
However, `ValueGateReceipt` still has no persisted envelope/source-report ref or subject/unit
binding, and the helper remains uncalled in live N8. Its coordinate is still the method name, so the
same-subject/same-estimand coordinate criterion is unresolved. The P40 residual is the same S3
binding class one level deeper: an owner-resolved, persisted report/envelope/subject-unit relation
plus an independent reader would close it, but those producer and consumer seams are absent.
Capability labels: `implemented_but_not_orchestrated` for the helper change, and
`producer_missing`/`consumer_missing` for the binding. No generic relation law is proposed.

## Empirical criteria outcomes

- **B16 — local synthetic actual reader passes the scoped/truncation/unit checks.** A DuckDB table
  with 20,001 sorted foreign `PL` rows and 4 scoped `UA` rows returned the 4 UA rows for 2020–2023;
  unscoped selection failed closed with `acquire_data:value_owner_rows_truncated`; an additional
  same-unit-period row failed closed with `acquire_data:value_owner_unit_binding_ambiguous`. This
  is local synthetic evidence, not an external fact. A second real DuckDB probe returned 4 UA rows
  for UA and 4 PL rows for PL with different `owner_rows_content_hash` values; reducing UA to 3
  rows returned `None` rather than a complete `ValueDataProfile`. Its output is
  `b16-scope-and-small-sample-probe.txt`. The three stale fake-cursor cases have been replaced with
  real DuckDB fixtures that execute the production query: 20,001 foreign rows cannot trigger
  truncation ahead of scoped mixed-unit refusal or exclude the four valid UA rows; a 20,001-row
  selected panel still fails at the actual cap. All 10 EMP-01 tests and the full 40-test focused
  B16/B31 run now pass. This removes the P38 test-proxy divergence. The real catalog probes are
  `b16-real-catalog-probe.txt` and `b16-scope-and-small-sample-probe.txt`. Across local synthetic
  probes, the original B16 row/scope,
  truncation, mixed-unit refusal, small-sample, and scope-identity criteria exercise correctly;
  this does not convert the historical partial/`not_adjudicated` ledger status into formal closure.
- **B31 — exact interval preservation is repaired in a helper, but the original criterion remains
  partial.** The helper witness passes: identified point `[4,4]` remains distinct from native
  statistical `[1,10]`; asymmetric proxy endpoints remain unchanged; no width is fabricated. The
  complete B16/B31 focused suite passes 40 tests. This is not end-to-end: no live method result
  reaches the helper, and there is no producer-persisted source-report/envelope ref or resolved
  subject/unit relation for a consumer to verify. The method-name coordinate also leaves the
  same-estimand comparison criterion open. Capability labels are
  `implemented_but_not_orchestrated` for endpoint projection and `producer_missing` /
  `consumer_missing` for report/subject-unit binding. Production N8 still refuses the path before
  value publication (`treatment_assignment_not_owner_derived`); no wrong published result is
  established. Full focused output: `b31-b16-focused-tests-final.txt`.
- **B32 — no date or optimistic-calibration fallback remains in the estimator-only path, but this
  does not close LA-051.** `_s10_calibration_evidence_from_report` returns denominator/numerator
  zero, `pass_rate=0.0`, `floor_passed=False`, and no empirical coverage metric for a finite
  estimator report; a missing report returns blocked. A current default
  `RealValueOwnerGateway()` read with finite CI and no empirical evidence ref returned
  `forecast_tier=blocked`, no calibration record, and
  `s10://calibration/fail-closed/empirical_evidence_ref_missing`, with the reason that estimator
  diagnostics are not empirical evidence. The full output is `default-s10-negative-reader.txt`.
  In the current FRC focused run, 42 tests pass and two FRC-01 tests fail. They pass inline,
  caller-supplied `calibration_evidence` mappings directly to the private builder, where the current
  consumer requires loader-resolved evidence. One also expects a limitation ref from that inline
  mapping, but omits the mapping's `calibration_status`. The actual default reader test above proves
  the current owner attaches a typed missing-ref limitation. These failures do not prove a trusted
  binding or the original empirical-calibration criterion; exact origin remains `not_established`
  under P41. Full outputs: `frc-tests-counted.txt` and `frc-tests-current.txt`.
- **LA-051 — partial (`implemented_but_not_orchestrated` / `bridge_missing`).** The actual ETS
  `ForecastOwner` persists a predictive-only `BacktestReport` with held-out predictions/outcomes.
  `forecast_bridge` can recompute and reconcile that report; without required context artifacts and
  role-bound report input edges, it marks `explicit_context_missing` and refuses evidence
  persistence. Synthetic context fixtures prove CAS readback and S10 projection when those
  artifacts are supplied, but they are not a production receipt. The `ForecastOwner` request has
  temporal roles but optional model/policy refs and does not emit the bridge's required
  scope-binding, threshold, observed-outcome, prediction, evaluation-design, credible-evaluation,
  source-lineage, and method-lineage roles. `RealValueOwnerGateway` defaults its evidence resolver
  to `None`, and the current Foundry method result carries no bridge evidence ref. The default reader
  therefore blocks a finite CI with `empirical_evidence_ref_missing`; predictive evidence remains
  prohibited from causal/treatment/S10 authority. No compatible default producer-to-reader
  composition or authenticated subject/unit context exists in this slice.

The earlier fake-cursor B16 red was repaired by replacing the proxy test double with actual DuckDB
execution. The two current FRC-01 red tests inject raw mappings directly into a private builder and
remain `not_established` under P41: this shared candidate contains peer changes, and the exact red
suite has not been replayed from the S3 slice base with a complete input-denominator intersection
proof. The independent default reader probe passes the negative original criterion. Do not re-label
those FRC-01 reds as inherited or as proof of production failure.

## Pattern pass and falsifier

Relevant register rows: P01/P02 (end-to-end producer and bridge), P05/P10 (no authority from
source-reported fields), P07/P08 (rule and time roles), P14 (predictive evidence is not causal),
P27/P29 (reuse the existing envelope and verify actual readback), P31/P32 (owner chokepoint and
resolve/bind/verify), P37/P38 (gate inputs and implementation/property divergence), P40 (same S3
binding class one level deeper), P41 (unattributed test reds). The existing producer gap was
confirmed before adding the new fields. Target pattern: preserve exact native uncertainty, persist
it at the owning producer, and resolve/content-bind the subject-unit relation at the consuming
owner. Missing capability labels are stated above. Acceptance requires an actual producer receipt,
persisted artifact, consumer readback and a negative foreign/missing/mismatched binding test.

The falsifier is not only “CI fields present”: remove/reforge the envelope ref, replace subject,
unit, report or rule while retaining the declared string fields, and ensure the consumer refuses.
For calibration, keep estimator shape fixed while held-out outcomes vary, remove the credible-eval
reference, provide empty or incompatible observations, and verify no calibration pass or causal
authority is minted. No authentic external facts were sourced from local synthetic fixtures.

## Follow-up owner and bridge probe

The actual `ForecastOwner` now has a dedicated end-to-end test at
`tests/unit/remediation/test_frc_02_empirical_bridge.py`. It uses the same training slice and
method for two persisted runs, so the point forecast and all predictive intervals are identical;
only the held-out observations change (`[20, 21, 22]` versus `[1000, 1001, 1002]`). The owner
recomputes different coverage numerators and suitability labels. Loading both persisted reports
through `forecast_bridge.produce_empirical_calibration_evidence` independently reproduces those
counts. With no real role-context artifacts, both results still carry `explicit_context_missing`,
remain unusable for calibration, and cannot be persisted; the CAS artifact set is unchanged after
the persistence attempts. The positive signal is owner-level predictive suitability only, not a
fresh persisted calibration grade or S10 causal result. Full FRC-02 output is
`frc02-empirical-bridge-test.stdout.txt` (33 passed; Ruff passed).

That test exposed and closes a specific time-role proxy gap in `forecast_bridge.py`. The property is
that all six context timestamps equal the timestamps the persisted report owner recorded. Before
the change, the bridge checked only that caller timestamps were distinct and ordered. A shifted but
well-ordered context for the same report returned `context_bound=True` and
`usable_for_calibration=True`. The bridge now compares each role to the report's persisted mapping,
and refuses context when that mapping is missing, malformed, incomplete, or different. The new
witness changes each of the six roles independently and removes the report mapping; all refuse.
The existing S10 time-mismatch consumer test still passes after its fixture persists matching
source roles. This binds the context to the report's recorded times; it does not independently
establish that `ForecastOwnerRequest.temporal_roles` are facts from a source clock. That residual
remains `not_established` until an owner can verify those role values from the source/time owner.

An AST pass over the complete `src/polisyos` Python set (2,707 files; all parsed) found two
`produce_forecast_inputs` definitions and zero production call sites, plus zero calls to
`load_empirical_calibration_evidence`. The complete `runtime/http` Python set (116 files) has no
`ForecastOwner` or empirical-evidence consumer mention. The full census is
`forecast-consumer-source-census.txt`. `FoundryValuePort` still has only an optional resolver set
to `None` by its default owner-gateway construction, and its live N8 path refuses at
`treatment_assignment_not_owner_derived` before a method result/report reaches that S10 resolver.
Passing the same CAS store to a default loader would be necessary but would not create a live
producer-to-consumer call. No predictive grade was sent to S10 or HTTP.

## V3 no-stub reentry probe

The existing active-overlay test uses real local Data Forge production/admission/readback receipts,
but monkeypatches `_run_cycle` to return the source cycle shape. I also invoked
`reenter_after_active_acquisition_overlay` without that stub against the local epoch fixture. It
preserved the same candidate reference and left the source run unchanged, and it read the active
two-observation overlay projection. The next cycle nevertheless had no WMR: both source and
reentry simulation returned `joint_simulation_request_missing` and
`world_model_record_unresolved`; the reentry terminal was `search_ceiling_repair_required`, and its
value result refused with `eval_safety_simulation_provenance_mismatch`. This is a concrete local
refusal, not a same-candidate WMR/N5 positive or an external-source fact. Raw output is
`v3-active-overlay-reentry-probe.stdout.txt`.

The original V3 positive still requires the conditional admitted I1/I3/I4 source supplier. The
minimal L01/I3 receipt identifies source metadata but has no readiness reference, and its live
dataset/run/cursor/event/verifier binding is unresolved. The smallest next probe is a real admitted
source snapshot with one content-changing observation and a paired ID/order/write-time-only control,
then the actual same-candidate WMR/N5/history consumer. If that supplier is unavailable, retain the
current tested refusal and do not label the source-change criterion passed. This is the same
producer/consumer binding class one level deeper under P40, not an invitation to mint source facts
or invent a reissue law.

## Remaining decision packet

V4 and V7 remain partial: `ForecastOwner` supplies true held-out predictive data, but the bridge's
typed `credible_evaluation`, calibration-floor threshold, and several report role artifacts/edges
have no genuine owners on this path; the default predictive consumer is absent. A safe next step is
to appoint/reuse an independent evaluator that can emit content-bound evidence for its actual
evaluation, then let `forecast_bridge` recompute the report-bound join and expose it through a
predictive-only consumer. If only the existing ForecastOwner is retained, preserve its
`bridge_pending` owner suitability as candidate descriptive output and keep calibration admission
refused. Do not treat the rule's nominal coverage as the separate empirical pass threshold, and do
not let predictive coverage satisfy causal S10.

For S3, the remaining G choices are unchanged: reuse an existing owner-resolved subject/unit
binding if one is found; otherwise have an appointed value-data owner emit the smallest persisted
report/envelope/subject/unit relation and a reader that resolves it against the claim; until then,
retain the exact native interval as limited candidate information without claiming a joined
estimand. No such source-derived relation is established by the current Foundry path.

These are decision options, not new contracts or claims of closure:

| Slice | Option | Smallest footprint | Authority and time boundary |
| --- | --- | --- | --- |
| V4/V7 | Reuse compatible evaluator owner | Keep the existing `ForecastOwner` report, CAS, and `forecast_bridge`; appoint an evaluator that can emit real report-bound credible-evaluation and floor artifacts, then wire one default predictive reader and semantic readback test. | Predictive-only. The six roles must come from the source/time owner and match the persisted report; no S10 causal promotion. |
| V4/V7 | Retain current measured diagnostic | No new persistence or consumer mechanism; keep `ForecastOwnerResult.empirical_suitability` as a bridge-pending owner diagnostic and keep neutral evidence persistence refused. | Candidate/descriptive only. Its timestamps remain report-recorded, not independently verified source-clock facts. |
| S3 | Reuse an existing owner relation | Find a current producer that resolves the exact claim subject and canonical measurement unit and already persists its source report/envelope binding; add only the consumer readback and removal/mismatch probes. | Limited until content-bound and recomputed against the exact value claim. Method name or adjacent artifact presence cannot supply subject/unit authority. |
| S3 | Appoint a value-data relation owner | One owner receipt binding the report, existing `UncertaintyEnvelopeRef`, resolved subject/estimand, canonical unit, source/method/rule, plus the consumer that re-resolves and recomputes that join. | Candidate until resolved; never upgrade authority from a caller-chosen relation. Preserve report time roles and distinguish data-valid, observation, prediction, and policy-effective time. |
| V3 | Wait for the conditional source supplier | Admit one immutable I1/I3/I4 source snapshot and run the existing acquisition→active overlay→same-candidate WMR/N5/history path against a content-change and ID/order/write-time control pair. | Local fixture receipts remain local evidence. Production authority needs the admitted source and matching owner context; source time must come from its producer, not file mtime or a changed identifier. |

## B188/B192/B201/B202: bounded posterior source-to-consumer path

The exact original criteria remain one occurrence each in `closure-decisions/coverage.json`:

| Finding | Original occurrence and criterion hash | Historical / appendix status | Current criterion outcome |
| --- | --- | --- | --- |
| B188 | `source/B_r19_original.md:4732–4741`, UQP-02, `845944fcb63293d09ccc282370335bbe03a508973c704ac6a58175d019e86771` | `partial` / `closed_bounded`, `closure_now=not_adjudicated` | The new explicit consumer preserves rows from one content-bound native source law. Default backend selection still does not resolve a common joint law, nor does it infer independence from absence. Bounded candidate-path evidence only. |
| B192 | `source/B_r19_original.md:4772–4781`, UQP-02, `3ba8c9b9a37ba35d3d7e210af7d91ecdfaebbc6d642739172a988840a9c2ef34` | `partial` / `closed_bounded`, `closure_now=not_adjudicated` | The explicit v1.1 consumer uses exact persisted source rows and refuses weights it cannot interpret. Legacy envelope dispatch still does not consume this summary and remains separate. Bounded candidate-path evidence only. |
| B201 | `source/B_r19_original.md:4978–4991`, UQS-01, `8069cd2dfd13bbfca1d2bbf02a7cc761d6614a5e967d7c11b1de299e64960474` | `held` / `held`, `closure_now=not_adjudicated` | The v1.1 route keeps a named point functional separate from equal-tail bounds, and its consumer preserves mean 1 with interval `[0,0]`. The legacy adapter's 99-zero/one-100 case now persists its mean, linear interval, exact input shape/draw carrier, and typed `point_outside_credible_interval` limitation in a caller-input-only candidate artifact; the fresh reader reruns the original summary and refuses a stale point. It remains non-gating, outside default envelope/MC dispatch, and does not establish source provenance or whole B201 closure. |
| B202 | `source/B_r19_original.md:4992–5005`, UQS-01, `8d507abb668fd82e3a58b5b416e8d011d07927198cfae69949d218a6328a16ab` | `held` / `held`, `closure_now=not_adjudicated` | The v1.1 producer persists source draws and its consumer’s matched-marginal/reversed-row control produces opposite products. The original legacy adapter now preserves exact per-parameter carriers and its full positional row matrix in a typed caller-input candidate context; fresh CAS readback and actual MC consumption pass for a representable single parameter. Its paired legacy carriers have no source-bound shared law and the actual consumer refuses both same/reversed pairing inputs. No source relation or caller-supplied joint ID is promoted to law evidence. Bounded candidate-path evidence only. |

Reuse-first chain: the native Bayesian producer already emits the canonical `foundry.bayesian.draws.v1` payload and method result/evidence artifacts. `MethodBackend.run()` now invokes the existing summary creator after persisting the method result and `scientist.method_evidence`; it returns typed `posterior_summary_refs` for both `posterior_mean` and `posterior_median` through `JobResult`. Evidence carries the full producer-issued `method_result_ref` and profile-bound `method_result` input edge. The creator checks the selected result view, sampler family/kernel/draw reference, derives credible mass from the persisted method result, and rechecks source bytes/hash/axes. A fresh CAS reader recomputes the summary and evidence lineage. The explicit `MonteCarloPropagator.propagate_posterior_summary()` evaluates the selected point plus every exact source row, hashes the selected parameter axes/rows, and returns separate output mean, median, equal-tail bounds and row failures. It does not coerce the result into `UncertaintyEnvelope` or promote it into default dispatch, calibration, causal, or policy authority.

The source-bound execution receipt is `raw/posterior-summary-hmc-cas-consumer.receipt.json` (17,811 bytes; SHA-256 `f32fc8fc82862e7ec0d7a30759128a7e5880416dd29cbcd86b60b342a8581285`). It retains the full canonical posterior payload, source/evidence/summary refs, profile-bearing manifest edges, exact `intercept`/`sigma` rows and all evaluator calls. The local fixture uses the actual NumPy HMC method with seed 11, one chain, 32 warmup steps, 32 retained draws, step size 0.02 and four leapfrog steps; the four-observation input is in the receipt. The dimensions are explicit because the native HMC implementation floors both warmup and sample counts at 32. One point call plus 32 row calls were read back. The generated output is only a predictive-location diagnostic over the real HMC rows, not an external outcome or empirical calibration. `run_job` also logged a degraded legacy DAG-adapter artifact write (`CanonViolation: float forbidden in canonical JSON`) while native HMC dispatch and method-result/evidence persistence succeeded; this remains a separate runner bridge warning, not a positive adapter receipt.

Selected-view falsifier: a valid default summary sidecar points to the original method-evidence profile. A sibling summary sidecar has the same payload bytes but points to another profile for the same evidence blob. Before the fix, the fresh reader silently read the valid default sidecar and the test failed with “DID NOT RAISE.” It now uses the existing profile-addressed resolver for a ref with `manifest_profile_sha256`; the default view still passes and the selected mismatched view refuses. Red/green output is in `posterior-summary-selected-profile-red.stdout.txt` and `posterior-summary-selected-profile-green.stdout.txt`. The saved source-to-CAS integration receipt predates automatic summary refs on `JobResult`; the updated integration test asserts that producer bridge but remains unrun because the numerical fit slot was reserved. This is the existing shared ref-selector class one level deeper (P40), now covered at this reader.

The earlier independent legacy-path probe is retained in `posterior-summary-legacy-adapter-residual.txt`; it records the pre-repair `ValidationError` on 99 zeros plus 100 and the dropped carrier. The current original legacy API returns mean `1`, interval `[0,0]`, all 100 samples in `BayesianCalibrationDrawContextCandidate`, and the typed envelope limitation; it does not build an incompatible `UncertaintyEnvelope`. Passing `candidate_store` to the existing legacy summary producer persists the complete summary (including representable envelopes, all exact carriers, original shapes, and row matrix) as a strict caller-input-only CAS artifact; the returned summary exposes its typed `persisted_candidate_ref`. Its fresh reader recomputes the legacy mean and linear interval from exact retained draws, validates representable envelopes against those draws, preserves row order with `row_relation_status=not_established`, and refuses a stale point functional. This preserves the legacy NumPy quantile rule and does not assign a sampler-chain axis or source-method provenance. The candidate consumer sends representable envelopes through the actual legacy Monte Carlo consumer: a single parameter reaches the evaluator with only retained values, while same-marginal and reversed-pairing multi-parameter candidates are freshly loaded then refused as `unestablished_joint_law` before any evaluator call. An off-interval parameter returns a typed `parameter_envelope_unavailable` result containing the mean, interval, and draws without constructing an incompatible envelope or calling the evaluator. A generic caller-provided `joint_sample_id` elsewhere in the legacy consumer remains declaration-only and is not source-law proof. These candidate APIs do not establish default orchestration or persisted paired-law provenance. The explicit v1.1 path remains an alternative candidate route, not full B201/B202 closure. The source-level original statuses remain untouched and no G closure is asserted.

P40 classification: B201 remains the point-functional/interval-semantics class. The legacy mean, linear interval, typed limitation and caller-provided draw context are persisted and recomputed as one candidate artifact; the negative stale-statistic control proves the reader does not trust the stored point. The candidate consumer runs representable inputs through the existing Monte Carlo consumer and emits a typed no-evaluation limitation for off-interval input. This does not change `UncertaintyEnvelope` or v1.1 replay semantics. The artifact remains source-unbound, non-gating and outside default dispatch, so B201's broader route remains bounded and the original G status is unchanged. B202 and B192 share the end-to-end law-preservation class at producer and consumer stages; the HMC candidate widens one source-bound CAS/reader/evaluator cohort, and legacy paired candidates retain exact rows but are refused by the consumer without a producer-owned law relation. The smallest missing capability for legacy paired admission is a producer-owned typed multi-parameter law artifact/ref plus an independent consumer resolver; the bounded current behavior is refusal before evaluation. B188 is related but separate: it requires an admitted joint-law policy before backend selection, which one source's row order does not establish. No default orchestration or common-law admission is claimed.

Capability labels: v1.1 has a typed contract/artifact, existing native producer binding, CAS persistence, explicit consumer, and semantic unit/integration tests; `implemented_but_not_orchestrated` for default workflow dispatch; `not_established` for weights, units, convergence and institutional law admission. The legacy adapter retains samples in memory and existing envelopes; with explicit `candidate_store`, every nonempty summary's caller-input context is persisted and fresh-recomputed. The candidate consumer reaches legacy Monte Carlo for representable envelopes, returns typed limitation for off-interval input, and leaves multi-parameter law refusal to the actual consumer. Production source census (`rg -n 'summarize_bayesian_calibration_posterior\\(' src tests --glob '*.py'`) finds no orchestration caller: only the producer and its fresh-reader recomputation in source, with current call routes in tests. Therefore the original legacy producer remains `implemented_but_not_orchestrated`, candidate-only; its source-method relation and multi-parameter law relation remain `not_established`. The separate native MCMC `run_job` producer binding is established, while default posterior-to-evaluator dispatch remains `implemented_but_not_orchestrated`. The generic legacy caller-string joint ID remains a declared predicate, not recomputed law identity. Public runtime imports are covered. The generated public-surface inventory was reviewed, but its bounded static resolver continues to mark the package `unresolved_exports` because it stops at the ancestor `polisyos.foundry.__init__` future import. The release fragment records that limitation rather than treating candidate names as proven exports.

Focused B188/B192 lightweight rerun after the producer bridge changes passed four tests: the v1.1 matched-marginal/reversed-row consumer, the persisted legacy reversed-row refusal, the persisted single-parameter empirical-carrier consumer, and the caller-input candidate reversed-row readback/refusal. No native HMC or numerical fit was run in this rerun.

## B194 count-proxy test context

The initial combined calibration/IR/Monte Carlo run failed five old assertions that hard-coded 515
negative draws; the observed count was 508. This was a test-context difference, not a source-path
regression: `tests/unit/foundry/calibration/conftest.py` sets `JAX_ENABLE_X64=1` before JAX imports.
A direct same-seed probe reports 515 negatives with x64 disabled and 508 with x64 enabled; the
complete probe output is `mc-x64-count-probe.stdout.txt`. No base replay or disjoint-input proof was
used, so this is not classified as inherited under P41. The five assertions have been widened to
record the actual evaluator input for each draw, exclude nominal preflight calls, and compare the
failure ledger's exact draw indexes to the input predicate. The scoped calibration + IR + Monte
Carlo cohort now passes together under the calibration x64 context; standalone Monte Carlo also
passes under its default context. This repairs the P38 test proxy (a fixed count of negative random
draws) by asserting the actual per-draw failure property.

## Legacy candidate bridge boundary and verification

`summarize_bayesian_calibration_posterior()` has no production orchestration caller in the current
source tree. The source-callers census records only its definition and the fresh-reader recompute
inside `uncertainty_adapter.py`; all external invocations found are tests. The opt-in `candidate_store`
path therefore persists caller input only and does not silently change the default adapter. Its
candidate consumer is a bounded prototype that routes representable carriers to the existing
`MonteCarloPropagator`, returns a typed no-evaluation limitation for an off-interval mean, and
retains the MC consumer's `unestablished_joint_law` refusal for multi-parameter rows. The actual
evaluator is called only for the representable univariate case; same-marginal/reversed-row controls
show the multi-parameter refusal happens before evaluation. This is `implemented_but_not_orchestrated`,
not a production calibration admission route.

The smallest route to default orchestration is an existing source/method-owned calibration caller
that has a persisted artifact store and can pass the actual draw ref and purpose to this producer;
none is present in the current source census. A later source-bound integration must bind that
producer output to method evidence and any subject/unit context before adding default dispatch. The
current candidate route does not invent either relation. The unratified subject/unit G options above
remain: reuse an existing resolved owner relation, appoint an owner for a typed receipt plus
independent reader, or keep the exact result candidate-only. For multi-parameter law, the present
smallest safe behavior is refusal; a positive route requires a producer-owned typed law artifact/ref
and an independent resolver. These options do not assert that an institutional law or source context
exists.

Scoped verification receipt: `posterior-candidate-producer-consumer-tests.stdout.txt` contains the
full output for the two changed test modules (`26 passed`). Exact-path Ruff check passed for the
adapter, its mirrored tests, and `tests/unit/remediation/test_frc_02.py`; the three PT007
parametrization containers there now use list-of-tuples, preserving cases and IDs. Ruff format
check passed for the adapter and its mirrored tests; the remediation file contains additional
format-only hunks in the pre-existing shared edit, which were left untouched. `git diff --check`
passed on the source, tests, README, release, and handoff paths. The updated release fragment
parsed as TOML. No generated public-surface command or numerical fit was run in this verification.

Pattern pass: P01/P02 (new explicit route is wired end-to-end but no default orchestration), P05/P10/P14 (candidate, gate-false, no statistical/causal/external authority), P27/P31 (reuse the native law owner and one source-to-consumer slice), P29/P32/P37/P38 (actual draw/hash/manifest recomputation and selected-view removal falsifier), P40 (bounded residuals above). Acceptance for this slice is the real HMC→method-result/evidence→summary CAS→fresh profile-aware reader→actual paired-row evaluator plus refusal on selected-profile mismatch; it does not adjudicate the separate default workflow or G statuses.
