# GY-N11 Honest Confidence Ledger Implementation Plan

> **For agentic workers:** execute one mutating workstream at a time. Every code workstream follows
> RED -> observed RED -> minimal GREEN -> focused regression -> scoped commit. Validators that
> materialize shared `.tmp` state run strictly serially. This task is zero-network throughout.

**Goal:** Make every probabilistic N9 promotion certificate anytime-valid under adaptive querying,
spend risk only for executed checks from a predictable schedule, prove total spend is at most
`delta`, and preserve the honest conditional bound in every frozen or runtime projection. Account
the refusal and acquisition evidence that exists today; do not manufacture positive promotion or
admission evidence.

**Canonical design:** GY plan Rev 18,
`docs/plans/active/layer3-slices/GY-engine-subordination.md`, GY-N11, the N9 obligations-compiler
block, and sections 3.5.6, 3.5.7 E1-E10, 3.5.8 U1-U4, 3.5.10, and 3.5.11. This document sequences
that approved design. It does not create a second statistics stack or another promotion owner.

**Architecture:** One new runtime owner resolves data-registered instrument definitions, binds the
claim, polarity, filtration, and predictable schedule slot to owner-verifiable certificate evidence,
durably burns the slot before observing an executed check's outcome, and recomputes the
good-event/union-bound receipt from an append-only lineage. N9 is the sole promotion chokepoint and
consumes only the ledger's narrow promotion-certificate projection. The generation-cycle consumer
revalidates the typed N9 receipt and its embedded ledger before it trusts promotion booleans. A
separate frozen N11 artifact accounts real N10/N13b refusal and admission-gate evidence through
narrow, acyclic owner projections. Its future N12 projection carries epoch-reference fields but
implements no epoch logic.

**Tech stack:** Python 3.14, Pydantic v2 strict DTOs, `Fraction`/directed-downward decimal rendering,
TOML registry/config, existing artifact/CAS and proof-provenance contracts, pytest, Ruff, canonical
JSON writers. `statsmodels 0.14.6`, `ortools 9.15.6755`, and JAX CPU are available in the isolated
worktree environment; N11 does not add a generic confidence-sequence/e-process implementation.

## Isolation and environment receipt

- Base: `b3f11e587a1a57c095ab33514deb0ae9aa5ba768` (`main`, N13b merged).
- Lane: `.worktrees/gy-n11` on `codex/gy-n11-confidence-ledger`.
- Worktree-local interpreter prefix: `.venv`; locked packages are reused from the already-installed
  main environment through an ignored `.pth`, with no network access.
- Required runtime environment: `PYTHONDONTWRITEBYTECODE=1`, `JAX_PLATFORMS=cpu`, and
  `PYTHONPATH="$PWD/src:$PWD"`.
- Production data is an ignored read-only symlink to the main checkout's existing data. No command
  writes below `production_data/**`.
- Atlas lanes stay untouched: no edits below `apps/**`, `runtime/http/**`, or another worktree.

## Step-0 serial field-clear receipt

| Chain node | Result | Measured evidence |
| --- | --- | --- |
| GY engine census | PASS | 69 rows, 0 violations |
| N4 design generation | PASS | committed replay contract validates in its current historical world |
| N8 value gate | RED | N4 atom names `world_model_record_a258...`; current owner rebuild is `world_model_record_11c3...` |
| composition | PASS | committed composition artifact validates |
| N10a second-domain pack | PASS | committed pack validates |
| N10 capstone | RED | `cycle_substrate_l6_bundle_content_mismatch`, the same owner-vocabulary ripple |
| N13a census | PASS | exact production catalog path, zero network |
| N13b acquisition contract | PASS | byte-stable x2; 2 derivation families; 0 admissions; typed deeper terminal |
| disposition ledger | RED | 7 N8 rows masked false because the shared N8 rederive failed |

The root cause is one inherited replay drift, not seven live N8 regressions. N13b commit
`fbb32cb54` added the generic `index` unit to `DEFAULT_UNITS_REGISTRY` after the last N8/N10
rebaseline. The registry bundle changed, so the honestly recomputed WMR changed from `a258...` to
`11c3...`. The N4 replay fixture still pins the old WMR and the current N4 writer merely replays that
pin. Live N8 strangles remain present. Classify this as P07/P29/P34 artifact/rule replay drift.

Before N11 implementation, repair the class with an offline, content-bound current-WMR reissue and
one canonical writer ripple. Never edit the seven disposition rows, relabel the old WMR, or touch
recorded provider bytes.

Known unrelated inherited debt remains out of scope: the Step-0 repo-wide Task-0 lifecycle census
had 466 global violations, and the HTTP-redaction flake remains in the Atlas/HTTP lane. The final
exact-tree rescan reports 444 global issues and zero N11 issues; this measured reduction does not
reclassify the remaining global debt as N11 debt.

## Reuse census and build-new boundary

| Existing owner | Finding | N11 disposition |
| --- | --- | --- |
| `pdc/_impl/gy_waist.py` `PromotionRiskSpendRecord/Summary` | Typed N9 bridge exists, but spend is caller-declared and the ledger ref is an unchecked string. | Extend in place; remove caller authority. |
| `runtime/quality/promotion_sequence.py` | Canonical N9 owner and complete 15-class obligation denominator exist; `_risk_spend_summary` only sums declarations. | Reuse N9 and replace only its spend hook. |
| `ddm/calibration/multiple_testing.py` | `MultipleTestingPlan` is a float-valued finite-family sum check. `OnlineFDRController` is mutable in-memory alpha wealth with no durable history, filtration/claim binding, restart/fork defense, or theorem-bearing owner receipt; it can also apply its alpha floor after wealth reaches zero. Runtime cannot import DDM under the architecture policy. | Do not fork or copy. Keep it in the O2 monitoring family; it cannot authorize N9 promotion or serve as N11's durable budget owner. |
| `ddm/integration/events.py` | Carries p-value/e-value/ERT evidence but does not establish a promotion-valid guarantee. | Never treat shape/presence as authority. |
| `foundry/methods/catalog/causal/conformal_ci.py` | `conformal_calibrate_interval` returns a tuple and method label for split-conformal marginal coverage under held-out/exchangeable calibration. It carries no assumption, filtration, adaptive-selection, stopping-rule, claim, or owner-proof binding. | Reuse only as producer mathematics after an owner supplies the missing guarantee; current output is not an adaptive promotion certificate. |
| `foundry/methods/catalog/forecasting/uncertainty.py` | Residual/reconciled conformal bundles explicitly target marginal or per-horizon coverage and record exchangeability/dependence assumptions; several fallback paths are uncertified. | Preserve their honest scope. Marginal conformal coverage is not silently upgraded to conditional validity under adaptive N9 selection. |
| `foundry/methods/selection/advisor.py` `ConfidenceSequence` | The frozen dataclass defaults `anytime_valid=True`; its `empirical_hoeffding_anytime_proxy` radius is a diagnostic formula without a theorem receipt, filtration, boundedness/dependence proof, or content-bound owner verification. | Explicitly ineligible for promotion until an owner-verifiable theorem establishes the guarantee for the bound process actually used. The boolean/estimator label is not evidence. |
| `ir/analytics/sensitivity.py` `EValueResult` | This is the causal-sensitivity **E-value** (risk-ratio robustness to unmeasured confounding), not a betting e-value or e-process. Its name and `e_value >= 1` shape carry no sequential testing semantics. | Keep as sensitivity evidence. Never resolve or relabel it as an N11 e-value instrument by name/shape. |
| `ir/analytics/proof_composability.py` | `ProofComposabilityCertificate`, its witness/index refs, and `persist_*/load_*` helpers already provide typed proof status, artifact-store persistence, and content-addressed input graphs. | Reuse its proof-provenance and persisted-ref patterns for resolve -> bind -> verify intake; do not repurpose its causal-replay statuses as statistical validity. |
| N13b registry/derivation owner | Generic TOML family registration, content-bound receipt, structural verification, and data-only second-family precedent. | Copy the pattern, not its domain types. |
| `statsmodels` | Fixed-time statistical machinery is installed. No existing repo primitive supplies the required adaptive-promotion guarantee. | Do not wrap fixed-time intervals as anytime-valid. |
| `scientist/orchestration/engine/budget_ledger.py` `FileBudgetLedger` | Reuses a process lock plus fail-closed POSIX `fcntl` lock and reloads mutable state under that lock. Its bounded in-place journal permits release/refund and has no immutable CAS lineage, predictable-claim binding, or fork-proof head. | Reuse the lock/reload/atomic-replace precedent only. Do not reuse its refundable budget semantics as N11 authority. |

There is no `scientist/analytics` package or reusable sequential-test/e-process confidence owner in
the current tree. The IR analytics census found proof-carrying certificate persistence and a
same-name causal-sensitivity E-value, not an anytime-valid statistical primitive. DDM supplies O2
multiple-testing diagnostics but not a durable promotion ledger. Foundry supplies useful conformal
and diagnostic interval producers, but none binds the conditional guarantee required after adaptive
claim selection to N9's filtration and executed claim. Those candidates remain outside runtime's
import boundary or lack the owner-verifiable coverage argument N11 requires.

**Verdict:** the narrow genuinely missing kernel is a typed promotion confidence **accounting** owner:
registry resolution, proof-bearing instrument eligibility, predictable slot derivation, durable
append-only execution accounting, exact spend accounting, union-bound composition, and projections.
N11 does not implement generic e-process, confidence-sequence, sequential-test, or FDR algorithms.
Certificate producers remain responsible for their mathematics; N11's trusted proof kernel verifies
a supported theorem schema and the registry binds an instrument to that schema. Registry data
cannot invent a theorem.

The census also found no useful producer-owned anytime-valid certificate that can honestly turn a
current obligation GREEN. To exercise the probabilistic accounting path without inventing power,
the one owner may expose a construction-verified constant-unit e-process witness: `E_t = 1` is
recomputed by the owner for every index, is a nonnegative martingale under every null, and cannot
cross `1/alpha` for `alpha < 1`. Its exact slot is burned at `started` before the owner returns
`crossed=false`, but it can never satisfy or promote an obligation. Checking a caller-supplied
all-one realization is forbidden; validity must follow from the closed constructor and a
remove-the-constructor flip. All current real statistical offerings remain typed refusals, and
positive certificates remain future free-grow.

## Mathematical and semantic invariants

### Adaptive filtration, claim binding, and execution protocol

Let `F_(t-1)` be the durable ledger history before global executed-check ordinal `t`. Candidate
selection may use all prior outcomes, but the exact claim identity, obligation class `q_t`, claim
polarity/error event, instrument definition and theorem, owner evidence/data snapshot, filtration
ref, and schedule slot must all be `F_(t-1)`-measurable. They are content-bound into one
`claim_execution_binding` before the owner can observe or return the check outcome. A certificate for
one estimand, null/alternative, direction, data snapshot, or refusal/admission/bind polarity cannot
be replayed against another, even if its numeric payload is unchanged.

For a probabilistic instrument, owner verification must prove the conditional guarantee actually
needed by adaptive composition:

`P(false_claim_t | F_(t-1), maintained assumptions) <= alpha*_(t,q_t)`.

An unconditional fixed-time or marginal-coverage statement is insufficient after adaptive claim
selection. A confidence sequence/e-process/sequential test must bind the process, filtration,
stopping rule or time-uniform theorem, and protected claim event; a terminal value plus an
`anytime_valid` label is insufficient. This conditional step guarantee, predictability of the slot,
and a pathwise total budget at most `delta` are what permit tower-property plus union-bound
composition at every stopping time.

Execution has a durable three-state append protocol. `prepared` resolves and verifies the
definition and claim binding without observing an outcome and spends nothing. Immediately before
invoking the owner, `started` atomically appends the unique ordinal, parent-head hash,
executed-check ID, binding, slot, and full burn. Once `started` exists, a non-rejection, typed
statistical refusal, owner error, timeout, or crash cannot refund the slot. `completed` appends the
outcome or refusal afterward. Unknown or ineligible instruments rejected during `prepared` never
execute and spend zero; a check already executed outside this handshake is an unaccounted bypass
and cannot reach promotion.

The history is append-only and has one compare-and-swap canonical head per owner-derived risk-budget
scope. The root ledger ID binds that scope and registered delta policy; a caller cannot mint a new
root for the same scope, and N11 has no “fresh budget” API. Restart resolves the durable head and
continues at `max(t) + 1`; a caller cannot reset to an earlier receipt to recover large early slots.
Two children of one head cannot both become canonical: a stale branch gets `ledger_head_conflict`
and must reprepare at a fresh ordinal. An exact idempotent request may read the existing completed
receipt only when it does not execute again. Any retry that observes new output receives a new
executed-check ID, ordinal, and burn; reused IDs with different content and duplicate ordinals/slots
are corruption. Every started deterministic or probabilistic attempt receives one global ordinal,
while only eligible probabilistic `started` rows have nonzero spend.

### Obligation split

The config exposes the seven requested pools while proving a total partition of the existing
`PromotionObligationClass` denominator. Pool membership is data, but every member must resolve to an
actual N9 typed class exactly once.

| Pool | Weight | N9 obligation classes |
| --- | ---: | --- |
| `value` | 0.20 | `normative`, `value` |
| `ground` | 0.15 | `syntax`, `type`, `slot`, `param` |
| `id` | 0.20 | `effect`, `identification`, `measurement` |
| `cal` | 0.15 | `calibration` |
| `data` | 0.10 | `data` |
| `eval` | 0.10 | `implementation`, `eval_safety` |
| `mc` | 0.10 | `coupling`, `equilibrium` |

The owner divides a pool's weight across its typed members by exact rational arithmetic. Missing,
duplicate, extra, or certificate-type-keyed allocation is RED.

### Predictable schedule and spend law

For global zero-based executed-check ordinal `t` and typed obligation class `q`, the default config
declares the ideal Basel envelope:

`alpha^ideal_(t,q) = delta * obligation_weight(q) * 6 / (pi^2 * (t + 1)^2)`.

No binary float or rounded-up decimal participates in authority. The proof kernel derives the
executable coefficient from the certified rational upper enclosure `pi < 355/113`:

`c_B = 6 * 113^2 / 355^2 = 76614 / 126025 < 6 / pi^2`,

and allocates the exact rational burn

`alpha*_(t,q) = delta * obligation_weight(q) * c_B / (t + 1)^2`.

Thus every executable slot is a conservative downward realization of the declared default, and
`sum_t sum_q alpha*_(t,q) < delta` follows from the Basel theorem without floating-point summation.
`delta`, pool/member weights, profile mass, every slot, and cumulative spend are canonical
numerator/denominator pairs. A decimal field is display-only, rendered with directed rounding toward
zero, and the validator rejects a rendering above its exact fraction.

At `started`, a probabilistic check irrevocably spends its full recomputed slot before the outcome is
known. An unexecuted `prepared` row or untouched schedule slot spends zero. An executed
probabilistic check without a unique precommitted schedule slot cannot execute through the owner and
fails closed if presented post hoc. A failed, non-rejecting, or refusing executed check does not
refund risk. Deterministic owner proofs execute at a unique ordinal but spend exactly zero.

The schedule mass is tunable as data without changing the runtime branch structure. The registered
Basel-square profile stores an exact rational `mass` and derives
`weight_t = mass * c_B / (t + 1)^2`; the default mass is one. The proof kernel recomputes the
symbolic ideal envelope, the exact downward coefficient, and total-mass bound. A custom half-mass
profile must account end-to-end; a profile whose recomputed mass exceeds one is invalid even when
its recorded bound says otherwise. No arbitrary recorded normalization, decimal approximation, or
finite-prefix claim is trusted.

### Proof-kernel and registry boundary

Instrument families and certificate-class routes remain data-registered, but mathematical truth is
not. The TOML may select a proof-kernel theorem ID, declare exact parameters and maintained
assumptions, name the owner verifier, and bind those declarations into the receipt. It cannot define
a new theorem, verifier semantics, or arbitrary proof program. The trusted Python kernel contains a
small typed set of theorem schemas: deterministic owner proof, time-uniform confidence-sequence
coverage, Ville/e-process thresholding, sequential-test type-I control, and the Basel-square schedule
bound. Each schema recomputes its premises from owner evidence; unknown theorem IDs fail closed.

Engine control flow is generic over instrument records and dispatches only on the proof theorem
schema, never on instrument-family or certificate-class names. Consequently U3 may add a new
instrument type in TOML only by reusing an already implemented theorem schema and owner verifier.
A genuinely new statistical theorem is code/proof-kernel work and cannot be smuggled through the
data-only universality lane.

### Good event and conditionality

For each executed probabilistic check, owner verification must establish
`P(G_t^c | F_(t-1), maintained assumptions) <= alpha*_(t,q_t)` for the exact adaptively selected
claim and protected error polarity. The claim/slot selection is predictable, and cumulative exact
burn is pathwise at most `delta`; applying the tower property and union bound therefore gives the
same bound for any user stopping time. The ledger defines `Omega_delta` as the intersection of
those good events and does not claim independence, exchangeability, or optional-stopping validity
unless the selected owner theorem proves the needed premise. In the N9 projection `false_claim_t`
specializes to false promotion; refusal and admission rows retain their own confident-wrong error
events and polarity-specific spent subset under the same union bound. The single canonical clause is:

`P(false promotion | maintained assumptions) <= delta is conditional on obligation completeness + validator soundness (the spec's A4 = our open P29).`

That exact clause is content-bearing in the ledger, the N9 projection, the future N12 projection,
and the frozen artifact. Deleting or paraphrasing it in a projection is corruption.

### Instrument registration and refusal semantics

- Instrument IDs/families are strings resolved from
  `architecture/production_quality/confidence_ledger.toml`; no engine enum names certificate types.
- Initial definitions cover confidence sequences, betting e-values/e-processes, sequential tests,
  and deterministic owner proofs by selecting supported proof-kernel schemas. The causal-sensitivity
  `EValueResult` is explicitly not a betting e-value. The registry also describes fixed-time
  Bayesian credible intervals and marginal conformal intervals as non-eligible unless a separately
  verified coverage argument upgrades the actual adaptively selected certificate.
- A registry boolean such as `anytime_valid=true` is not evidence. Intake is one
  resolve -> content-bind -> verifier-provenance path. The runtime owner verifies the selected
  proof-kernel theorem and certificate owner; a rehashed self-attestation or registry-declared new
  theorem cannot satisfy it.
- The constant-unit e-process is a no-power conformance witness only. Its owner generates and
  recomputes the process from construction, binds its filtration, derives the threshold from the
  pre-outcome burned slot, forces `crossed=false`, and rejects any satisfaction/promotion claim. It
  is never evidence of real statistical power or the source of the real artifact's non-vacuity.
- `unknown_instrument`, `coverage_argument_missing`, `non_anytime_valid`,
  `conditional_validity_missing`, `claim_binding_invalid`, `claim_polarity_mismatch`,
  `schedule_slot_missing`, `ledger_head_conflict`, `duplicate_execution_conflict`,
  `unknown_proof_theorem`, `registry_binding_invalid`, and `owner_reverification_failed` are typed
  accounting refusals. None supports the underlying policy claim or silently bypasses accounting.
  Pre-execution refusals spend zero; once `started` is durable, the same refusal/error outcome keeps
  the full burn.
- N10 evidence classes `owner_acquisition_route`, `estimand_binding_refusal`, and
  `owner_data_gap` and the N13b admission-passport class are registry-addressable. Current real data
  contains two of the three N10 classes, zero `owner_data_gap` rows, and zero persisted N13b passport
  instances. The real run must record those zero denominators and must not mint phantom rows.

### Claim polarity and honest refusal accounting

Every accounted row binds a protected claim polarity and its false-claim event: false positive
bind/promotion, confident-wrong refusal, or confident-wrong admission. Direction is mathematical,
not presentation metadata: a lower-bound theorem cannot certify an upper-bound refusal, and a
certificate cannot be reused merely by negating its label. The proof-kernel verifier recomputes the
null/alternative, estimand, direction, decision rule, and error event from the owner certificate.

An accounting refusal such as `unknown_instrument` means “this offered instrument cannot authorize
the policy claim”; it is not evidence that the policy claim itself is false. Conversely, a real N10
`estimand_binding_refusal` is an affirmative, owner-custodied refusal claim. If that claim rests on a
probabilistic instrument, it burns risk against the confident-wrong-refusal event exactly as a
positive bind burns risk against false promotion. The current real refusals spend zero only because
their structural owner proofs are deterministic, never because negative polarity is assumed safe.

### Day-one evidence instruments and spend semantics

The class route is data-registered; the owner evidence decides whether the executed check is a
deterministic proof or a probabilistic instrument. The current frozen evidence is structural, so its
honest spend is zero, not a manufactured positive alpha draw. Future probabilistic certificates in
the same classes use scheduled spend through the same intake.

| Evidence class | Current instrument/proof profile | Current spend | Owner evidence recomputed before accounting |
| --- | --- | ---: | --- |
| `owner_acquisition_route` | deterministic route-obligation proof | `0` | N10 route projection, owner gap/source, strategy, terminal blocker, and missing-field witness |
| `estimand_binding_refusal` | deterministic estimand-binding refusal proof | `0` | N10 estimand/gap binding and the structural refusal reasons from the capstone owner |
| `owner_data_gap` | deterministic owner-gap existence proof; denominator currently zero | `0` when present | N10 owner gap identity/source and unresolved required-data witness |
| N13b admission passport | deterministic resolve -> raw-byte bind -> parse/policy revalidation proof; real denominator currently zero | `0` when present | `revalidate_admission_passport` plus authority-owner, quarantine, admission, and world-growth projections |

The real frozen ledger therefore contains executed, owner-revalidated rows and an exact zero-spend
record. That is non-vacuous accounting: removing any row, owner proof, denominator, or zero-risk law
turns RED. It does not launder deterministic evidence into a probabilistic claim. If an owner later
supplies a probabilistic refusal/admission certificate, its registered anytime-valid profile draws
the unique scheduled slot exactly like a positive bind certificate.

## Compute-economics gate map (E1-E10)

- **E1:** use the existing content-hash-keyed shared owner cache; stale/mismatched owner hashes fail
  closed. All real accounted-run tests consume one cached N10/N13b baseline.
- **E2:** add one N11 closeout-sweep entry point that runs the warm receipt chain, real accounting,
  checker, and flips in one process over one owner build.
- **E3:** keep Lane 0 synthetic logic under 10 seconds with zero owner I/O, Lane 1 on the E1 cache,
  and run one cold Lane 2 only at closeout.
- **E4:** mutate one cached baseline for corrupt/source flips, with at least one behavioral flip for
  every decisive property class; never rebuild the world per mutation.
- **E5:** every N11 validator/sweep records wall time by stage and overall. Approximately five
  minutes warm or 25 minutes cold is the review threshold; an overrun is a finding, not silently
  normalized.
- **E6:** no N11 live acquisition/provider call is authorized. Reuse N4's journal-first persisted
  raw recordings and N13b's existing raw evidence; never build a second journal. The execution
  journal remains set-accumulating and never archives without raw evidence refs.
- **E7:** provider pre-live work is not applicable because this lane is zero-network. Preserve the
  applicable gauntlet offline: near-valid parse/validate fuzz, replay existing recordings through
  the changed path, and scripted local e2e smoke. No provider call follows.
- **E8:** every expensive/cold attempt records the complete effective config (registry/config
  hashes, paths, cache mode, JAX platform, rule/schema versions, and the one varied input) in its run
  record.
- **E9:** the one-process runner emits stage heartbeats and compares progress/wall time with the
  recorded historical stage timings. CPU-active plus advancing waits; wall time beyond 2x history
  stops for profiling. A progressing cold build is never killed merely for being slow.
- **E10:** Step 0 and all later diagnosis begin from committed artifacts, cached receipts, and logs
  already on disk before any fresh owner build.

## Projection-scope map

| Producer | Narrow projection | Consumer/use |
| --- | --- | --- |
| N10 capstone | Route ID, structurally recomputed evidence kind, owner gap/source, terminal/blocker evidence, and projection hash. Reuse the N10/N13a route projection algebra. | N11 refusal/acquisition rows; never the whole capstone hash. |
| N13b | Authority-owner, quarantine, world-growth, admission denominator, and any actual passport identity after `revalidate_admission_passport`. | N11 admission/refusal rows; zero real passports stays zero. |
| N11 registry/config | Registry section hashes, selected proof-kernel theorem IDs, exact rational schedule proof, obligation partition, rule/schema versions, and conditionality clause. | Every ledger receipt and both exported projections. Registry data never supplies theorem semantics. |
| N11 append lineage | Owner-derived risk-budget scope/root ID, canonical head/parent hashes, unique executed-check ordinals/IDs, prepared/started/completed events, claim/filtration/polarity bindings, exact burns, and cumulative spend. | Runtime recovery and owner recomputation; an alternate root, earlier prefix, or competing fork cannot become a fresh budget. |
| N11 frozen semantic append lineage | Stable scope/authority/deployment and registry/schedule/budget bindings; semantic parent/check/event hashes; predictable-filtration projection; execution ordinal/ID; stable owner-invocation-claim and good-event identities; exact burns and current-check projection. Physical lock inode, CAS refs, runtime event/check/head/receipt IDs, and their contaminated hashes are excluded only after the full live receipt validates. | Frozen N11 artifact, frozen N9 audit projection, and frozen N12 locator. The runtime durability receipt remains intact and is never accepted interchangeably with this projection. |
| N11 `n9_promotion_certificate` | At runtime: canonical live receipt/head plus executed promotion rows. In the frozen audit artifact: the producer-owned semantic ledger projection hash, stable promotion rows with ordinal and claim projection binding, registry/schedule hashes, exact total spend, delta, good-event clause, and projection hash. | N9 runtime consumes only the live projection; the frozen artifact records only its narrow stable audit projection. |
| N11 `n12_epoch_reference` | Stable semantic-ledger projection hash, nullable epoch/model/rule/schema refs, validity placeholder, conditionality clause, and projection hash. | Future N12 only; N11 implements no epochs. |

Declared artifact edges are acyclic: `N10/N13b -> N11 -> N9/N12`. N11 never binds the frozen N9
artifact back into itself.

## Exact ownership and file map

### One new runtime mathematics/accounting owner

- `src/polisyos/runtime/quality/confidence_ledger.py` (new): registry models/loader, typed proof
  kernel, exact predictable schedule, claim/filtration binding, durable compare-and-swap append
  intake, executed-check ordinal/recovery rules, union-bound receipt, owner recomputation, and narrow
  projections. This is the only new instrument-mathematics owner.
- `architecture/production_quality/confidence_ledger.toml` (new): delta policy, seven-pool mapping,
  full 15-class partition, schedule theorem selection, instrument definitions, theorem parameters,
  owner-verifier bindings, and data-only certificate-class routing. It contains no executable or
  self-authored theorem semantics.

### Existing contracts and chokepoints to extend

- `src/polisyos/runtime/quality/confidence_ledger.py`: single-own the strict ledger
  check/receipt/projection contracts. `src/polisyos/pdc/_impl/gy_waist.py` extends only the existing
  public N9 display bridge (`PromotionRiskSpendRecord`, `PromotionRiskSpendSummary`, authority-trace
  bindings, and the exact conditionality constant); retain `PromotionObligationClass` as the sole
  obligation enum.
- `src/polisyos/pdc/__init__.py`: export the display/N9 compatibility types and caveat, not the
  canonical ledger DTO surface.
- `src/polisyos/runtime/quality/promotion_sequence.py`: remove caller-authoritative `risk_spends`,
  draw executed probabilistic certificates through the ledger, bind the promotion projection, and
  recompute it during receipt validation.
- `src/polisyos/runtime/quality/generation_cycle.py`: close
  `_promotion_receipt_allows_decision_front` raw-dict trust; parse and revalidate the typed N9/ledger
  receipt before any decision-front update.
- `tools/quality/validation/check_layer3_gy_promotion_contract.py`: replace the declared-spend
  fixture with a real ledger draw, add bypass/source flips, and canonically reissue the N9 artifact.

### Frozen N11 artifact and verification

- `tools/quality/validation/layer3_gy_confidence_ledger_contract.py` (new): audit composer and narrow
  N10/N13b projection adapters; it is not an authority owner.
- `tools/quality/validation/check_layer3_gy_confidence_ledger.py` (new): canonical writer/checker,
  byte-stability, cold rederive, nested corrupt lane, and source-flip harness.
- `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json` (new): one frozen N11
  artifact with real accounted run, promotion projection, epoch projection, registry proof, and
  universality proof.
- `architecture/policy_design_case/layer3_gy_promotion_contract.json`: canonical N9 rebaseline.
- `architecture/generated_artifacts.toml` plus generated reference docs: lifecycle registration.

### Tests

- `tests/unit/runtime/quality/test_confidence_ledger.py` (new).
- `tests/unit/runtime/quality/test_promotion_sequence.py`.
- `tests/unit/runtime/quality/test_generation_cycle.py`.
- `tests/unit/pdc/test_gy_waist_contracts.py`.
- `tests/repo_quality/tools/test_layer3_gy_confidence_ledger_contract.py` (new).
- `tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py`.

### Step-0 replay repair owners and artifacts

- `tools/quality/validation/check_layer3_gy_design_generation_contract.py`: add deterministic,
  content-bound current-WMR reissue while preserving historical recording/provider bytes.
- `tools/quality/validation/capture_layer3_gy_design_generation_replay.py`: remove the pinned
  `a258...` default and resolve the current WMR owner for any future capture.
- Canonical reissue order before the clean capstone boundary:
  1. `layer3_gy_intervention_substrate_contract.json`;
  2. `layer3_gy_design_generation_contract.json`;
  3. `layer3_gy_n10_cg1_l2_relation_census.json` from a full offline rederive;
  4. `layer3_gy_value_gate_contract.json` after independently rebinding its two Fork-B hashes;
  5. all five `layer3_gy_second_domain_{census,pack,smoke_design_problem,cycle_entry_trace,free_grow_gaps}.json` artifacts;
  6. `layer3_gy_composition_certificates.json`;
  7. grounding CG0-CG6 in owner order;
  8. clean upstream commit, then `layer3_gy_depth_n_universality_contract.json` as a second batch.
- The grounding CG0-CG6 frozen chain also embeds the old WMR/N4 graph and is canonically reissued in
  owner order: credal reference, relation, bind, admission, phrasing defense, active controller,
  benchmark scoreboard. CG0-CG5 require writer x2 byte identity; CG6 deliberately excludes latency
  from semantic drift, so use write -> check -> write -> check rather than raw-byte equality.
  During this W0 WMR-only repair, N13a/N13b are validate-only and remain byte-stable because their
  declared projections exclude WMR identity. The historical U3 refusal-route addition changed the
  structurally owned capstone route projection and therefore required the separate canonical ripple
  N8 (`1ff19637e`) -> N10a (`479533278`) -> capstone/N13a (`8c506eb93`) -> N13b
  (`f3c8e1780`) -> N11 (`fcd110334`). Those writes are narrow projection rebindings, not
  whole-contract pinning. The source-committed disposition ledger is validate-only after N8.

### 2026-08-02 convergence journal: registry-derived reissue topology

- Registry snapshot: `architecture/generated_artifacts.toml`, 59 families,
  `sha256:261d569a6b8758da826f3de4bc4549de0c409683e4df71d61634dd85520d6aaa`.
- The registry's exact output-to-`source_of_truth` edges place
  `policy-design-case-layer3-gy-second-domain-pack` before
  `policy-design-case-layer3-gy-depth-n-universality-contract`; the latter explicitly consumes
  `layer3_gy_second_domain_pack.json` and `layer3_gy_composition_certificates.json`. Its declared
  narrow owner edges then continue N10 capstone -> N13a -> N13b -> N11. N11 also consumes N10
  directly. The disposition family is validate-only and therefore closes after the final upstream
  receipts.
- Fixed upstream boundary at `369065e8b`: N6 generation-cycle and N8 value-gate receipts are
  canonical and source has remained byte-frozen since `86a79fe96`.
- One-pass topological order from the current dirty node:
  1. second-domain pack (five-output family; only changed outputs are rewritten);
  2. depth-N universality/capstone;
  3. N13a only if its declared N10/value projection changes;
  4. N13b only if its declared N13a projection changes;
  5. N11 after N10/N13b closure;
  6. disposition ledger validate-only;
  7. downstream checker walk and lifecycle/guardrail closeout.
- At every rewritten node: canonical writer twice with identical bytes, then the recomputing
  checker. Composition and grounding are sibling inputs to depth-N, not descendants of the dirty
  second-domain node; their previously validated unchanged receipts are not reissued in this pass.
- Ordering stop rule: an upstream RED stops the walk at that node. No downstream checker is used to
  discover upstream staleness, and no completed upstream node is revisited unless its declared input
  changes.

## Pattern pass

- Relevant patterns: P01/P02/P03, P04/P05/P07/P08/P09/P10/P12/P13/P14/P15, P27-P34.
- Existing anti-patterns:
  - N9 caller supplies risk records and `_risk_spend_summary` trusts them (P05/P32).
  - The generation-cycle consumer trusts raw promotion booleans (P31).
  - N8's fixed-time pass/interval shapes carry no anytime-valid promotion proof (P14/P15).
  - Existing diagnostic `anytime_valid`/conformal/e-value-shaped records do not bind an adaptively
    selected claim, filtration, theorem, or protected error polarity (P14/P32).
  - A receipt-only spend sum would permit outcome-conditioned refunds, restart-to-early-slot budget
    resets, and competing forks from one prefix (P05/P07/P31).
  - N4 replay pins an obsolete WMR and masks one upstream ripple as seven strangle failures
    (P07/P29/P34).
  - No frozen N11 artifact, producer, bridge, consumer, or surface exists.
- Smallest correct pattern: one registry selecting a small trusted proof kernel, one
  resolve/bind/verify intake, one durable append-only schedule/accounting owner with pre-outcome
  burn, one N9 draw, one typed consumer revalidation, two narrow projections, one recomputing
  checker, and one real refusal/acquisition run.
- Capability labels before work: `producer_missing`, `artifact_missing`, `bridge_missing`,
  `consumer_missing`, `verification_missing`, `surface_missing`, and `semantic_test_missing`.
- Acceptance signal: an adaptive probabilistic N9 attempt binds its claim/filtration/slot to the
  prior durable head, burns its exact rational spend before outcome, and can promote only through a
  valid completed ledger projection; restart/fork/refund/rebind bypasses turn RED; real N10/N13b
  evidence produces owner-recomputed polarity-correct rows; the frozen artifact is byte-stable and
  lifecycle-visible.
- Post-implementation capability reality: producer, persisted artifact, N9 bridge, generation-cycle
  consumer, recomputing verification, audit surface, and semantic tests are implemented. The
  lifecycle-visible frozen JSON is the MACHINE/EXPERT audit surface. A stable Python ledger API,
  HTTP/dashboard projection, and public export are `surface_out_of_scope`: N11 is an internal
  authority-sensitive gate consumed through narrow verified projections, and any future external
  surface must be a read-only projection rather than a second intake or authority path.
- **Typed capability debt: `semantic_test_missing` — authority-scoped deployment identity.**
  - **Owner:** `team-runtime-quality`; canonical owner:
    `polisyos.runtime.quality.confidence_ledger._deployment_relative_paths`.
  - **Problem:** deployment identity binds `pyproject.toml`, `uv.lock`, and all 2,551
    `src/polisyos/**/*.py` files (2,553 files total), while
    `_resolve_authority_import_closure` already computes the real 120-module authority closure.
    This is a measured 21x over-binding, and current tests provide no unrelated-drift negative
    control.
  - **Authority consequence:** unrelated source drift can conservatively withdraw authority,
    irreversibly poison an active ledger scope, and force N9 -> generation-cycle -> N11 replay even
    when the changed bytes cannot affect the signed decision path. This is false withdrawal and
    replay/governance cost, not an unsafe authority grant.
  - **Bounded closure move:** in the next slice, extend the existing repository-local import-closure
    and loaded-code provenance mechanisms into a deterministic authority-bearing file closure.
    Retain explicit project, lock, runtime-ABI, and transitive authority-dependency bindings; fail
    closed when an authority callable or dynamic import cannot be resolved into that closure.
  - **Behavioral closure signal:** editing a module outside the authority closure leaves deployment
    identity unchanged and an active canonical session usable without poison. Editing
    `confidence_ledger.py`, a transitive authority dependency, `uv.lock`, or the runtime ABI changes
    identity, rejects authority, and preserves irreversible-poison behavior. Reissue the affected
    frozen chain twice with byte equality and independent checks, then record replacement hashes.
- Closeout P01-P34 audit:
  - P01/P02/P03 are closed by the real producer -> frozen artifact -> N9 bridge -> typed
    generation-cycle consumer -> lifecycle-visible audit projection chain; only the explicitly
    named external surfaces remain `surface_out_of_scope`.
  - P05/P10/P14/P15/P29/P31/P32/P33 are closed by one ledger draw chokepoint, exact
    resolve -> content-bind -> owner-reverify intake, structural polarity/coverage checks,
    recomputing writers/checkers, 50 nested corruptions, and 17 behavioral source flips.
  - P07 is closed for the inherited WMR drift by the canonical owner-order replay; N11 records
    registry, rule, deployment, filtration, and future epoch-reference identities. P08 adds no
    conflated runtime time role, and P09/P11/P12 add no warning, memory, or producer-handshake
    semantics.
  - P04 adds no status enum; P06 adds no shim; P13 is bounded to one accounting owner and one
    config registry; P16-P26 add no universal-axis authority. P27/P30 extend domain owners rather
    than create a slice statistics stack. P28 deletes caller-authored spend authority and closes
    the raw-boolean sibling consumer.
  - P34 exclusions are evidenced rather than relabeled: N11 has zero lifecycle phantoms; the
    repo-wide lifecycle debt is the disclosed base debt; and the five remaining architecture
    deltas are in untouched `runtime/http/**`/Lex Atlas files, with zero N11 deep-import delta.

## Red-first test denominator

### Step-0 current-WMR replay repair

- `test_n4_current_wmr_rebind_preserves_historical_recording_and_raw_bytes`
- `test_n4_current_wmr_rebind_rejects_forged_owner_projection`
- `test_n4_current_wmr_rebind_rejects_non_wmr_drift`
- `test_n4_current_wmr_rebind_rejects_raw_response_tamper`

### Ledger core

- `test_started_probabilistic_check_burns_before_outcome_and_survives_restart`
- `test_cancelled_prepared_attempt_has_no_ordinal_and_spends_zero`
- `test_executed_check_without_schedule_slot_fails_closed`
- `test_over_spend_is_rejected_even_when_receipt_is_rehashed`
- `test_bayesian_credible_interval_without_coverage_argument_is_typed_refusal`
- `test_unknown_instrument_preflight_fails_closed_without_start_or_spend`
- `test_non_anytime_valid_instrument_cannot_support_promotion`
- `test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification`
- `test_forged_spend_row_is_recomputed_from_schedule`
- `test_rehashed_forged_instrument_registry_fails_content_binding`
- `test_conditionality_clause_is_required_in_receipt_and_both_projections`
- `test_obligation_budget_split_is_total_over_n9_taxonomy`
- `test_duplicate_schedule_slot_is_rejected`
- `test_custom_predictable_schedule_profile_accounts_end_to_end`
- `test_schedule_mass_above_one_is_rejected`
- `test_nonrejecting_constant_unit_e_process_burns_but_cannot_promote`
- `test_caller_supplied_all_one_trace_is_not_a_coverage_argument`
- `test_adaptive_claim_selection_requires_conditional_validity_given_prior_filtration`
- `test_every_valid_history_prefix_preserves_the_delta_bound_at_user_stop`
- `test_claim_instrument_and_slot_are_bound_before_outcome_is_observed`
- `test_certificate_cannot_be_rebound_to_a_different_claim_snapshot_or_polarity`
- `test_marginal_split_conformal_interval_is_not_adaptive_promotion_certificate`
- `test_foundry_anytime_valid_label_without_owner_theorem_is_refused`
- `test_ir_sensitivity_e_value_is_not_resolved_as_betting_e_value`
- `test_ddm_online_fdr_decision_is_not_a_promotion_ledger_receipt`
- `test_started_owner_refusal_or_error_does_not_refund_slot`
- `test_orphan_started_event_fast_forwards_head_and_preserves_burn`
- `test_same_scope_cannot_mint_fresh_root_with_changed_owner_projection`
- `test_crash_recovery_never_reexecutes_and_next_start_uses_fresh_ordinal`
- `test_stale_history_token_cannot_fork_canonical_head`
- `test_completed_idempotent_request_is_returned_without_new_execution`
- `test_reused_request_key_with_different_binding_is_corruption`
- `test_retry_after_observed_output_gets_fresh_ordinal_and_burn`
- `test_exact_rational_basel_slot_is_below_declared_ideal_weight`
- `test_upward_rounded_schedule_rendering_is_rejected`
- `test_registry_cannot_self_declare_new_proof_theorem`
- `test_probabilistic_refusal_burns_against_confident_wrong_refusal_event`
- `test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification`

U3 is an operational binary proof rather than a second test alias: baseline `5a5d422a8`,
data-only commit `cb83a4c13`, an empty
`git diff 5a5d422a8..cb83a4c13 -- '*.py'`, and recomputed artifact universality evidence.

### N9 and the decision-front consumer

- `test_schedule_slot_is_reserved_before_obligation_outcomes`
- `test_n9_port_rebinds_every_adaptive_receipt_to_one_final_ledger_head`
- `test_probabilistic_certificate_bypassing_ledger_is_rejected`
- `test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow`
- `test_generation_cycle_check_revalidates_forged_embedded_receipt`
- `test_promotion_trace_requires_current_ledger_binding`
- `test_unknown_instrument_preflight_fails_closed_without_start_or_spend`

### Real/frozen proof

- `test_real_capstone_and_admission_denominator_are_accounted`
- `test_conditionality_clause_is_required_in_receipt_and_both_projections`
- `test_confidence_ledger_writer_is_byte_stable_and_corruptions_turn_red`

The `f489ba0ee` source-flip report is historical pre-`86a79fe96` evidence. The current frozen source
at `86a79fe96` has a separate operational 17/17 RED report with byte restoration (`844.533s`); the
U3 data-only end-to-end witness is the binary commit/diff/recomputed-artifact proof above.

## Required 17 source flips

The checker patches source, observes RED, and restores bytes in `try/finally` for every mutation:

1. `source_flip_over_spend_admission`
2. `source_flip_schedule_slot_validation_removed`
3. `source_flip_unknown_instrument_bypass`
4. `source_flip_bayesian_ci_relabelled_anytime_valid`
5. `source_flip_n9_ledger_draw_bypass`
6. `source_flip_forged_spend_row_trusted`
7. `source_flip_rehashed_forged_registry_trusted`
8. `source_flip_conditionality_clause_deleted`
9. `source_flip_deterministic_proof_nonzero_spend`
10. `source_flip_unexecuted_check_spend_admitted`
11. `source_flip_owner_certificate_recomputation_removed`
12. `source_flip_registry_content_binding_removed`
13. `source_flip_generation_cycle_ledger_revalidation_removed`
14. `source_flip_obligation_split_denominator_truncated`
15. `source_flip_duplicate_schedule_slot_accepted`
16. `source_flip_non_anytime_instrument_promoted`
17. `source_flip_projection_drops_conditionality_or_binds_whole_contract`

Nested corrupt-field coverage includes exact schedule numerator/denominator and display rounding,
obligation membership, registry hash, proof-kernel theorem ID, ledger/parent head, executed-check ID
and ordinal, filtration/claim/polarity binding, prepared/started/completed status, spend amount, owner
projection hash, conditionality clause, promotion projection hash, and future epoch-reference fields.

## Workstream 0 — Restore the inherited receipt chain through canonical owners

- [x] Add the four N4 reissue tests RED. Prove the current writer cannot repair the pin.
- [x] Add one offline current-WMR reissue path that resolves `production_composed_world_model_record`,
  preserves historical recording/raw response/prompt identities, changes only the WMR-bound semantic
  projection, and records old -> new owner evidence.
- [x] Remove the capture utility's pinned WMR default; future capture resolves the owner at runtime.
- [x] Run focused N4/N8/N10a/capstone tests and Ruff.
- [x] Execute the canonical writer ripple exactly in the ownership order above; writer x2 plus
  byte-hash equality and `--check` after every node. Recompute the full CG1/L2 census; do not transplant
  expected hashes.
- [x] Reissue grounding CG0-CG6 serially, then run the warm shared-cache closeout sweep.
- [x] Validate N13a and N13b without writing and prove their narrow projections remained byte-stable.
- [x] Re-run the disposition ledger. Its seven N8 cascade findings must disappear.
- [x] Commit the complete batch as one measured replay ripple before the capstone writer's clean-tree
  requirement; split only where an existing writer explicitly requires a clean upstream commit.

## Workstream 1 — Land strict contracts and observe the ledger REDs

- [x] Add the strict receipt/check/refusal/projection DTOs to the single runtime ledger owner; extend
  `gy_waist.py` only with the N9 display bridge and exact conditionality constant. Include exact
  rational spend, claim/polarity/filtration binding, append-event/head, and unique executed-check
  ordinal fields. Keep the existing obligation taxonomy; do not add a second enum.
- [x] Add the complete ledger-core denominator above and PDC strictness tests. Observe failures
  because the runtime owner and registry do not exist.
- [x] Add N9/consumer REDs showing caller spend, ledger bypass, raw-dict promotion, and fixed-time
  calibration can currently pass too far.
- [ ] Historical RED command/result output was not retained in the execution journal. The exact
  red-first test denominator and the final 17/17 behavioral source-flip evidence are committed, but
  closeout must not retroactively invent missing command output.

## Workstream 2 — Implement the generic ledger baseline

- [x] Add the TOML schema with content-addressed schedule, full typed obligation partition,
  proof-kernel theorem selections/parameters, owner verifiers, and initial instrument definitions;
  reject registry-authored theorem semantics.
- [x] Implement `confidence_ledger.py`: strict loader, unique resolution, typed proof kernel,
  adaptive claim/filtration/polarity binding, exact rational/downward Basel slots, durable
  compare-and-swap prepared -> started -> completed append protocol, unique global ordinals,
  pre-outcome burn, deterministic-zero law, restart/fork/duplicate defenses, typed refusals, owner
  recomputation, conditional good-event receipt, and two narrow projections.
- [x] Validate the config-declared predictable schedule profile through the trusted kernel: prove
  the symbolic ideal and exact rational downward total mass, reject upward display rounding,
  exercise a half-mass Basel profile end-to-end, and reject a recomputed mass above one.
- [x] Ensure a present/rehashed registry row cannot attest its own validity. Coverage/proof evidence
  must resolve to the certificate owner and verifier provenance.
- [x] Add only the construction-verified constant-unit e-process as the no-power probabilistic
  conformance witness. It burns its pre-outcome slot, always recomputes `crossed=false`, and cannot
  make any obligation pass; caller-supplied all-one traces fail closed.
- [x] Turn the core tests GREEN. Add unseen/malformed registry probes and remove-the-owner-validation
  P29 behavior.
- [x] Run focused tests and Ruff; commit generic baseline `5a5d422a8`.
- [x] Run final architecture guardrails after all source/artifact reissues. N11 contributes zero
  deep-import delta; the full command remains RED only on five untouched Atlas HTTP/Lex imports.

## Workstream 3 — Make N9 draw from the ledger and close the sibling consumer

- [x] Delete `CanonicalPromotionInput.risk_spends` and the context-provider forwarding path.
- [x] Compile obligations, resolve the canonical ledger head, and route each probabilistic owner
  execution through durable prepare -> pre-outcome start/burn -> complete. Bind the adaptively
  selected claim and prior-history filtration before invoking the owner; N9 may decide promotion
  only after the completed lineage validates. A missing handshake for a probabilistic pass is typed
  refusal, not zero-spend success.
- [x] Bind the exact N11 promotion projection into the N9 receipt and authority trace.
- [x] Recompute registry/theorem binding, claim/polarity/filtration evidence, canonical
  head/ordinal chain, exact schedule slot and burn, cumulative total, certificate evidence, and
  projection in `validate_canonical_promotion_receipt`.
- [x] Replace the generation-cycle raw-dict predicate with typed receipt parsing and revalidation.
- [x] Turn all N9/consumer REDs GREEN; preserve the total 15-class obligation semantics and unseen
  non-panel probe.
- [x] Perform the final N9 frozen reissue after the last deployment-closure source edit; writer x2
  and the independent recomputing check are byte-stable.
- [x] Run focused tests and Ruff; commit the N9/consumer implementation.
- [x] Run final architecture guardrails; N11 scoped delta is clean and the five remaining findings
  are in the excluded Atlas HTTP/Lex lane.

## Workstream 4 — Account the real N10/N13b evidence and freeze N11

- [x] Build N10 projections by structurally recomputing evidence kinds from owners. Current measured
  rows are education `estimand_binding_refusal`, first-vertical `owner_acquisition_route`, and unseen
  `owner_acquisition_route`; record `owner_data_gap` denominator zero. Bind refusal polarity and
  false-refusal scope explicitly; spend zero only after deterministic owner-proof verification.
- [x] Build N13b projections from its typed owner models. Record 5 live attempts, 2 raw responses,
  zero admitted responses/overlay rows/world growth, and zero persisted passports. Exercise the real
  passport verifier in a warm owner test, but do not represent it as a real frozen passport row.
- [x] Use the E1 content-keyed cached owner state for all warm accounted-run tests. No test rebuilds
  the composed world independently.
- [x] Expose an E2 one-process closeout sweep with E5 per-stage/overall timings, E8 effective-config
  journaling, and E9 heartbeats/objective stop diagnostics.
- [x] Add the canonical writer/checker and the frozen artifact. Declare projection scopes/edges and
  exclude invocation-local lock/CAS identities through one typed producer semantic projection
  after full live-receipt validation. Do not broaden the shared GY volatile-field policy or weaken
  the runtime durability receipt.
- [x] Run writer x2, compare file hashes, run nested corrupt lane, and run the required source flips.
- [x] Register the artifact lifecycle, regenerate reference docs, and prove the N11 family has one
  producer/one declared output with zero N11 phantoms. The disclosed 466-violation Task-0 global
  census remains inherited debt and is not recast as N11 debt.
- [x] Run focused tests and Ruff; commit the generic frozen baseline.
- [x] Run final architecture guardrails; N11 scoped delta is clean and the five remaining findings
  are in the excluded Atlas HTTP/Lex lane.

## Workstream 5 — U3 data-only novel-instrument proof

- [x] Record generic-baseline commit `5a5d422a8`.
- [x] Add a genuinely new instrument type and certificate-class route in TOML only. Route a real
  owner-recomputed refusal through an already implemented proof-kernel theorem and owner verifier;
  do not add a Python branch or declare new theorem semantics in TOML.
- [x] Re-run the canonical writer so the new type is accounted end-to-end in the universality proof.
- [x] Commit only data/config and writer-generated artifact/reference changes as `cb83a4c13`.
- [x] Prove `git diff 5a5d422a8..cb83a4c13 -- '*.py'` is empty.
- [x] Run the U2 unregistered-instrument probe after the new type lands; it must still return typed
  `unknown_instrument` with accounting intact.

## Measured execution evidence

- Real N10 accounting has three deterministic rows: one `estimand_binding_refusal` and two
  `owner_acquisition_route` rows; `owner_data_gap` has measured denominator zero. All spend exactly
  zero by independently reverified owner proof, not by polarity or nonexecution.
- The real N13b denominator is 5 attempts / 2 raw responses / 0 admissions / 0 passports. No
  positive passport or world-growth row is fabricated.
- The construction-verified constant-unit e-process conformance draw spends exactly
  `0.000303963499305693314818488395159690537591747669`; it is never promotion-eligible.
- The required post-`86a79fe96` source-flip lane is 17/17 RED with byte restoration
  (`844.533s`); `f489ba0ee` is retained only as the historical pre-fix run.
- Cold-closeout progress handling is corrected by `b5ca9af0a` and witnessed by
  `test_objectively_progressing_cold_worker_may_exceed_two_x_without_termination`.
- The final deployment-closure artifacts are byte-stable with file SHA-256 values N9
  `03479f68e1babc404f2ae8081ab780f1ca2c6c118dd9b11f61ee4be9310f51fe`, generation-cycle
  `37abd82bb64926ca392734baf8bacec1a3c3fe559ff26bfd88f230148d4e8675`, and N11
  `a844a0c318a95e6f653dda34c3a7f6db6592070b8abe25b0b9e9b1bdc2824781`.
- N11's semantic artifact hash is
  `sha256:62df18eb9d78368cacc607790541d2237f66f9a7ab381ef83bf6116fdea4f225`; its real-ledger,
  N9-promotion, future-N12 epoch-reference, and accounted-run projection hashes are respectively
  `sha256:28b5fce156439549b05fd4912f6ef783f10bcdb1d1bd24aba11db78704f0d46d`,
  `sha256:a74034343d8fd80301d57b67815c88789ef88ee7cf5bebba17f81d3708a0fec1`,
  `sha256:f294e772c46fed7870cc0768f8380e3d935967ebe14a17cb590f9d9430d7ed9b`, and
  `sha256:bf8028d248b61c37efe57b3b49c645acd77890be6c405590aab99c9b1ec9b962`.
- The dependency-ordered final N11 writes completed in `1173.279650s` and `1111.911306s` with
  identical bytes. The independent recomputing check completed in `898.666254s`; every run stayed
  within the measured 1500s cold budget and reported `profiling_stop_required=false`.

### 2026-08-02 dependency-ordered closeout receipt

- Source is byte-frozen from `86a79fe96`: both the committed range and working-tree comparisons
  under `src/polisyos/**` are empty. The final pass changed no implementation byte.
- Registry topology source is the 59-family
  `architecture/generated_artifacts.toml` snapshot
  `sha256:261d569a6b8758da826f3de4bc4549de0c409683e4df71d61634dd85520d6aaa`.
  The single pass followed second-domain -> depth-N -> projection-gated N13a -> projection-gated
  N13b -> N11 -> disposition -> downstream checkers; no completed upstream node was revisited.
- The second-domain family is committed at `c732eaa58`: pack
  `b976c2b4fe0b0da8438b062da777bc78b6b6a459f603e0e1d246b94cf66426e5`, cycle-entry trace
  `973a4cb903958c18281737da404e86e13d03032a84d6c03265b66bca5258b363`, and free-grow gaps
  `b95973d7cbda8c03869530f91b8c3a4f25072219b6804376e1bc1a0f8a56048b`; writer x2 and its
  recomputing check are GREEN.
- Depth-N writer x2 is byte-identical at
  `a0c2840bc5337abda2e41d7e747567899ac6d764f556038e5bfb96f58da36196`, with semantic content
  `sha256:d940c4571e746bcdaecdc56b1a11a5e7fc034acd10a727143a3169c3bf7ad3fe`; its independent
  checker is GREEN. N13a's capstone demand/route and value projections remained respectively
  `sha256:55f44ad9dc9fe12f829b086bab64723f7b25ca25487388111bd4a9e8eb68305e`,
  `sha256:9c433f8759c80c194a25b8a3746f4a832973e694de589be830d04ff28c8c913c`, and
  `sha256:84486eb5ef6f79b025338f79920e093afe2012fbb1b64a70018118a525ff1617`, so N13a was
  validate-only. N13b was likewise validate-only and recomputed GREEN at contract
  `sha256:9ff916db4c044c028bd58c815d3a0cb6e2a9c4486741b5cd4185f123ffaebb20`.
- The generation-cycle promotion projection contains four refused rows: every row has
  `execution_status=refused`, `eligible_for_promotion=false`, `supports_obligation=false`, and zero
  spend. Its total spend is `0` and `within_budget=true` against `delta=1/100`; the frozen N11
  promotion projection itself has zero promotion rows. Separately, the frozen accounted run has
  three executed deterministic, non-promotable N10 rows (one identification refusal and two data
  acquisition routes), total spend `0/1`, and the measured N13b denominator 5/2/0/0
  (attempts/raw/admissions/passports). The conditionality clause remains byte-present in the full
  receipt and both consumer projections.
- U3 remains the binary data-only proof: generic baseline `5a5d422a8`, novel-instrument commit
  `cb83a4c13`, and an empty `git diff 5a5d422a8..cb83a4c13 -- '*.py'`. U2 still returns typed
  `unknown_instrument` without bypassing accounting.
- Disposition recomputed GREEN with 34 strangled obligations checked, 26 landed, 7 pending, and
  zero issues. The final generation-cycle, composition, and CG0 -> CG6 checker walk is GREEN; CG6
  scoreboard hash is `sha256:f224c6a5d8b77ac84a1e0240cacac1eeb1fd0fcd5063fde9dea0767f27eddb58`.
- Final architecture guardrails retain exactly the five disclosed untouched Atlas HTTP/Lex
  deep-import findings. The lifecycle audit retains 444 inherited global issues but zero N11
  phantoms. Both are typed inherited RED receipts, not exclusions relabeled GREEN.

## Workstream 6 — Targeted serial closeout and architect handoff

- [x] Lane 0: focused PDC/ledger/N9/generation-cycle logic suites.
- [x] Run the warm cached-owner real accounted run and focused N11 lifecycle-owner test.
- [x] Re-run final N11/N9/generation checkers after the deployment-closure artifact replay; all
  independent checks pass and the writers are byte-stable x2.
- [x] Run the E2 one-process warm sweep and inspect its E5/E8/E9 run record; a warm wall time above
  about five minutes is a finding requiring cache/profile diagnosis.
- [x] Run Ruff on every changed Python path.
- [x] Run architecture guardrails after the final artifact replay; N11 scoped delta is clean, while
  the full gate reports five untouched Atlas HTTP/Lex imports.
- [x] Run N11 writer/checker x2, corrupt lane, and required source flips.
- [x] Perform the final deployment-identity affected-slice replay serially: final N9 ->
  generation-cycle -> N11 -> disposition. The upstream census/N4/N8/composition/capstone/N13a/N13b
  owner chain was already reissued and validated in owner order and was not changed by the final
  deployment-closure source edit.
- [x] Run the Layer-3 GY validator census: raw 41, accepted 40 after excluding the
  operational acquisition executor (accepted 39 -> 40).
- [x] Run one Lane-2 cold N11 closeout with analytics + solvers and JAX CPU. Do not repeat it per
  mutation.
- [x] Inspect the cold stage record; a cold wall time above about 25 minutes or 2x the recorded
  historical stage time stops closure for profiling unless the stage is demonstrably advancing.
- [x] Reopen the failure/repair register and audit P01-P34 closure, especially P05, P07, P14, P15,
  P29, P31-P34.
- [x] Record frozen file/content/projection hashes, real spend rows, data-only commit, and
  empty-Python proof.
- [x] Prove the source-frozen dependency-order journal is committed at a clean boundary.
- [ ] Run the merge-tree against current main from the final receipt commit and record its tree hash.
- [ ] Request exact-head code review. Do not merge or push; preserve the branch for architect review.

## Verification command families

All commands run from `policy-engine/`, strictly serial when they touch `.tmp`:

```bash
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python -m pytest -q tests/unit/runtime/quality/test_confidence_ledger.py
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python -m pytest -q tests/unit/runtime/quality/test_promotion_sequence.py
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python -m pytest -q tests/repo_quality/tools/test_layer3_gy_confidence_ledger_contract.py
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --check
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --corrupt-field-drift-check
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --source-flip-mutations
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --cold-rederive
PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu PYTHONPATH="$PWD/src:$PWD" \
  .venv/bin/python tools/quality/validation/check_layer3_gy_n13b_acquisition_contract.py --check \
  --catalog-path production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb \
  --l5-path production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json
uv run polisyos-tools architecture guardrails check
```

Do not run full pytest, backend verify, CI parity, or any network-bearing capture. If an existing
primitive's anytime-validity remains genuinely ambiguous after owner/proof inspection, stop with the
measured evidence rather than approximating or laundering the mathematics.
