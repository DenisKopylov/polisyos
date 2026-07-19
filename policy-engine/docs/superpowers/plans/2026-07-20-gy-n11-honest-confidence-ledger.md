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

**Architecture:** One new runtime owner resolves data-registered instrument definitions, binds them
to owner-verifiable certificate evidence, derives schedule slots, records executed checks, and
recomputes the good-event/union-bound receipt. N9 is the sole promotion chokepoint and consumes only
the ledger's narrow promotion-certificate projection. The generation-cycle consumer revalidates the
typed N9 receipt and its embedded ledger before it trusts promotion booleans. A separate frozen N11
artifact accounts real N10/N13b refusal and admission-gate evidence through narrow, acyclic owner
projections. Its future N12 projection carries epoch-reference fields but implements no epoch logic.

**Tech stack:** Python 3.14, Pydantic v2 strict DTOs, `Decimal`/exact rational allocation metadata,
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

Known unrelated inherited debt remains out of scope: the repo-wide Task-0 lifecycle census has 466
global violations, and the HTTP-redaction flake remains in the Atlas/HTTP lane.

## Reuse census and build-new boundary

| Existing owner | Finding | N11 disposition |
| --- | --- | --- |
| `pdc/_impl/gy_waist.py` `PromotionRiskSpendRecord/Summary` | Typed N9 bridge exists, but spend is caller-declared and the ledger ref is an unchecked string. | Extend in place; remove caller authority. |
| `runtime/quality/promotion_sequence.py` | Canonical N9 owner and complete 15-class obligation denominator exist; `_risk_spend_summary` only sums declarations. | Reuse N9 and replace only its spend hook. |
| `ddm/calibration/multiple_testing.py` | `MultipleTestingPlan`, Bonferroni allocation, and an online FDR controller exist for monitoring/O2. Runtime cannot import DDM under the architecture policy, and these contracts do not prove anytime validity or owner provenance. | Do not fork or copy; record as the O2 family census result. |
| `ddm/integration/events.py` | Carries p-value/e-value/ERT evidence but does not establish a promotion-valid guarantee. | Never treat shape/presence as authority. |
| `foundry/methods/selection/advisor.py` `ConfidenceSequence` | Labels an empirical Hoeffding proxy `anytime_valid=True` without a content-bound coverage proof. | Explicitly ineligible for promotion until an owner-verifiable argument exists. |
| `ir/analytics/proof_composability.py` | `ProofComposabilityCertificate`, its witness/index refs, and `persist_*/load_*` helpers already provide typed proof status, artifact-store persistence, and content-addressed input graphs. | Reuse its proof-provenance and persisted-ref patterns for resolve -> bind -> verify intake; do not repurpose its causal-replay statuses as statistical validity. |
| N13b registry/derivation owner | Generic TOML family registration, content-bound receipt, structural verification, and data-only second-family precedent. | Copy the pattern, not its domain types. |
| `statsmodels` | Fixed-time statistical machinery is installed. No existing repo primitive supplies the required adaptive-promotion guarantee. | Do not wrap fixed-time intervals as anytime-valid. |

There is no `scientist/analytics` package or reusable sequential-test/e-process confidence owner in
the current tree. The IR analytics census found proof-carrying certificate persistence, not an
anytime-valid statistical primitive. The DDM and foundry candidates above remain outside runtime's
import boundary or lack the owner-verifiable coverage argument N11 requires.

**Verdict:** the narrow genuinely missing kernel is a typed promotion confidence **accounting** owner:
registry resolution, proof-bearing instrument eligibility, predictable slot derivation, exact spend
accounting, union-bound composition, and projections. N11 does not implement generic e-process,
confidence-sequence, sequential-test, or FDR algorithms. Certificate producers remain responsible
for their mathematics; N11 verifies the registered proof contract and accounts its guarantee.

## Mathematical and semantic invariants

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

For zero-based query index `t` and typed obligation class `q`, the default config declares:

`alpha*_(t,q) = delta * obligation_weight(q) * 6 / (pi^2 * (t + 1)^2)`.

The symbolic Basel schedule proves `sum_t sum_q alpha*_(t,q) <= delta`. The executed receipt stores
the exact inputs and a canonical decimal rendering; the validator recomputes it from registry/config
and never trusts the recorded value. A probabilistic check spends its full recomputed slot only when
executed. An unexecuted slot spends zero. An executed probabilistic check without a unique schedule
slot cannot spend and fails closed. Deterministic owner proofs spend exactly zero.

The schedule mass is tunable as data without changing the runtime branch structure. The registered
Basel-square profile stores an exact rational `mass` and derives
`weight_t = mass * 6 / (pi^2 * (t + 1)^2)`; the default mass is one. The generic profile verifier
accepts only a proof-kernel-supported predictable family and recomputes its symbolic total-mass
upper bound. A custom half-mass profile must account end-to-end; a profile whose recomputed total
mass exceeds one is invalid even when its recorded bound says otherwise. No arbitrary recorded
normalization or finite-prefix claim is trusted.

### Good event and conditionality

For each executed probabilistic check, owner verification must establish its registered guarantee
on event `G_(t,q)`. The ledger defines `Omega_delta` as the intersection of those good events and
uses only the union bound; it does not claim independence. The single canonical clause is:

`P(false promotion | maintained assumptions) <= delta is conditional on obligation completeness + validator soundness (the spec's A4 = our open P29).`

That exact clause is content-bearing in the ledger, the N9 projection, the future N12 projection,
and the frozen artifact. Deleting or paraphrasing it in a projection is corruption.

### Instrument registration and refusal semantics

- Instrument IDs/families are strings resolved from
  `architecture/production_quality/confidence_ledger.toml`; no engine enum names certificate types.
- Initial registered mathematics cover confidence sequences, e-values, e-processes, sequential
  tests, and deterministic owner proofs. The registry also describes fixed-time Bayesian credible
  intervals as non-eligible unless a separately verified coverage argument upgrades the actual
  certificate.
- A registry boolean such as `anytime_valid=true` is not evidence. Intake is one
  resolve -> content-bind -> verifier-provenance path. The runtime owner verifies the generic proof
  language and certificate owner; a rehashed self-attestation cannot satisfy it.
- `unknown_instrument`, `coverage_argument_missing`, `non_anytime_valid`,
  `schedule_slot_missing`, `registry_binding_invalid`, and `owner_reverification_failed` are typed
  refusals. None can silently bypass accounting.
- N10 evidence classes `owner_acquisition_route`, `estimand_binding_refusal`, and
  `owner_data_gap` and the N13b admission-passport class are registry-addressable. Current real data
  contains two of the three N10 classes, zero `owner_data_gap` rows, and zero persisted N13b passport
  instances. The real run must record those zero denominators and must not mint phantom rows.

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
| N11 registry/config | Registry section hashes, schedule proof, obligation partition, rule/schema versions, and conditionality clause. | Every ledger receipt and both exported projections. |
| N11 `n9_promotion_certificate` | Ledger receipt ID, executed promotion rows, registry/schedule projection hashes, total spend, delta, good-event clause, and projection hash. | N9 runtime and frozen N9 artifact bind only this projection. |
| N11 `n12_epoch_reference` | Ledger receipt ID, nullable epoch/model/rule/schema refs, validity placeholder, conditionality clause, and projection hash. | Future N12 only; N11 implements no epochs. |

Declared artifact edges are acyclic: `N10/N13b -> N11 -> N9/N12`. N11 never binds the frozen N9
artifact back into itself.

## Exact ownership and file map

### One new runtime mathematics/accounting owner

- `src/polisyos/runtime/quality/confidence_ledger.py` (new): registry models/loader, generic proof
  verifier, predictable schedule, executed-check intake, union-bound receipt, owner recomputation,
  and narrow projections. This is the only new instrument-mathematics owner.
- `architecture/production_quality/confidence_ledger.toml` (new): delta policy, seven-pool mapping,
  full 15-class partition, schedule law, instrument definitions, proof profiles, and data-only
  certificate-class routing.

### Existing contracts and chokepoints to extend

- `src/polisyos/pdc/_impl/gy_waist.py`: replace pre-N11 declared-spend shapes with strict ledger
  check/receipt/projection contracts; retain `PromotionObligationClass` as the sole obligation enum.
- `src/polisyos/pdc/__init__.py`: export the public N11 DTOs.
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
- Canonical reissue order:
  1. `layer3_gy_intervention_substrate_contract.json`;
  2. `layer3_gy_design_generation_contract.json`;
  3. `layer3_gy_n10_cg1_l2_relation_census.json` from a full offline rederive;
  4. `layer3_gy_value_gate_contract.json` after independently rebinding its two Fork-B hashes;
  5. all five `layer3_gy_second_domain_{census,pack,smoke_design_problem,cycle_entry_trace,free_grow_gaps}.json` artifacts;
  6. `layer3_gy_composition_certificates.json`;
  7. clean upstream commit, then `layer3_gy_depth_n_universality_contract.json`.
- The grounding CG0-CG6 frozen chain also embeds the old WMR/N4 graph and is canonically reissued in
  owner order: credal reference, relation, bind, admission, phrasing defense, active controller,
  benchmark scoreboard. N13a/N13b are validate-only and must remain byte-stable if their declared
  projections correctly exclude WMR identity. The source-committed disposition ledger is
  validate-only after N8.

## Pattern pass

- Relevant patterns: P01/P02/P03, P04/P05/P07/P08/P09/P10/P12/P13/P14/P15, P27-P34.
- Existing anti-patterns:
  - N9 caller supplies risk records and `_risk_spend_summary` trusts them (P05/P32).
  - The generation-cycle consumer trusts raw promotion booleans (P31).
  - N8's fixed-time pass/interval shapes carry no anytime-valid promotion proof (P14/P15).
  - N4 replay pins an obsolete WMR and masks one upstream ripple as seven strangle failures
    (P07/P29/P34).
  - No frozen N11 artifact, producer, bridge, consumer, or surface exists.
- Smallest correct pattern: one registry, one resolve/bind/verify intake, one schedule/accounting
  owner, one N9 draw, one typed consumer revalidation, two narrow projections, one recomputing
  checker, and one real refusal/acquisition run.
- Capability labels before work: `producer_missing`, `artifact_missing`, `bridge_missing`,
  `consumer_missing`, `verification_missing`, `surface_missing`, and `semantic_test_missing`.
- Acceptance signal: an executed probabilistic N9 check receives its recomputed schedule spend and
  can promote only through a valid ledger projection; every bypass/refusal turns RED; real N10/N13b
  evidence produces owner-recomputed rows; the frozen artifact is byte-stable and lifecycle-visible.

## Red-first test denominator

### Step-0 current-WMR replay repair

- `test_n4_current_wmr_rebind_preserves_historical_recording_and_raw_bytes`
- `test_n4_current_wmr_rebind_rejects_forged_owner_projection`
- `test_n4_current_wmr_rebind_rejects_non_wmr_drift`
- `test_n4_current_wmr_rebind_rejects_raw_response_tamper`

### Ledger core

- `test_executed_anytime_valid_check_spends_recomputed_schedule_slot`
- `test_unexecuted_schedule_slot_spends_nothing`
- `test_executed_check_without_schedule_slot_fails_closed`
- `test_over_spend_is_rejected`
- `test_bayesian_credible_interval_without_coverage_argument_is_typed_refusal`
- `test_unknown_instrument_fails_closed_without_spend`
- `test_non_anytime_valid_instrument_cannot_support_promotion`
- `test_deterministic_proof_requires_zero_spend`
- `test_forged_spend_row_is_recomputed_from_schedule`
- `test_rehashed_forged_instrument_definition_fails_owner_verification`
- `test_good_event_conditionality_clause_is_mandatory`
- `test_obligation_budget_split_is_total_over_n9_taxonomy`
- `test_duplicate_schedule_slot_is_rejected`
- `test_custom_predictable_schedule_profile_accounts_end_to_end`
- `test_custom_schedule_total_mass_above_one_is_rejected`

### N9 and the decision-front consumer

- `test_probabilistic_promotion_certificate_is_drawn_from_confidence_ledger`
- `test_probabilistic_certificate_bypassing_ledger_cannot_promote`
- `test_calibration_pass_without_certificate_handshake_stays_shadow`
- `test_generation_cycle_rejects_forged_promoted_receipt_without_valid_ledger_projection`
- `test_authority_trace_binds_n11_promotion_projection`
- `test_unseen_registry_instrument_fails_closed_as_unknown_instrument`

### Real/frozen proof

- `test_real_capstone_refusal_projection_is_accounted`
- `test_real_n13b_admission_denominator_is_accounted_without_phantom_passports`
- `test_frozen_ledger_preserves_conditionality_in_every_projection`
- `test_confidence_ledger_writer_is_byte_stable`
- `test_confidence_ledger_nested_corrupt_fields_turn_red`
- `test_confidence_ledger_source_flip_denominator_is_complete`
- `test_new_data_only_instrument_is_accounted_end_to_end`

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

Nested corrupt-field coverage includes schedule weight, obligation membership, registry hash,
instrument proof profile, execution status, spend amount, owner projection hash, conditionality
clause, promotion projection hash, and future epoch-reference fields.

## Workstream 0 — Restore the inherited receipt chain through canonical owners

- [ ] Add the four N4 reissue tests RED. Prove the current writer cannot repair the pin.
- [ ] Add one offline current-WMR reissue path that resolves `production_composed_world_model_record`,
  preserves historical recording/raw response/prompt identities, changes only the WMR-bound semantic
  projection, and records old -> new owner evidence.
- [ ] Remove the capture utility's pinned WMR default; future capture resolves the owner at runtime.
- [ ] Run focused N4/N8/N10a/capstone tests and Ruff.
- [ ] Execute the canonical writer ripple exactly in the ownership order above; writer x2 plus
  byte-hash equality and `--check` after every node. Recompute the full CG1/L2 census; do not transplant
  expected hashes.
- [ ] Reissue grounding CG0-CG6 serially, then run the warm shared-cache closeout sweep.
- [ ] Validate N13a and N13b without writing and prove their narrow projections remained byte-stable.
- [ ] Re-run the disposition ledger. Its seven N8 cascade findings must disappear.
- [ ] Commit the complete batch as one measured replay ripple before the capstone writer's clean-tree
  requirement; split only where an existing writer explicitly requires a clean upstream commit.

## Workstream 1 — Land strict contracts and observe the ledger REDs

- [ ] Extend `gy_waist.py` with strict receipt/check/refusal/projection DTOs and the exact
  conditionality constant. Keep the existing obligation taxonomy; do not add a second enum.
- [ ] Add the 15 ledger-core tests and PDC strictness tests. Observe failures because the runtime
  owner and registry do not exist.
- [ ] Add N9/consumer REDs showing caller spend, ledger bypass, raw-dict promotion, and fixed-time
  calibration can currently pass too far.
- [ ] Record the RED commands/results in the execution journal; do not commit an intentionally red
  tree.

## Workstream 2 — Implement the generic ledger baseline

- [ ] Add the TOML schema with content-addressed schedule, full typed obligation partition, proof
  profiles, and initial instrument definitions.
- [ ] Implement `confidence_ledger.py`: strict loader, unique resolution, generic proof verification,
  symbolic schedule metadata, exact slot derivation, executed-only spend, deterministic-zero law,
  typed refusals, owner recomputation, good-event receipt, and two narrow projections.
- [ ] Validate the config-declared predictable schedule profile generically: prove the symbolic
  total mass, exercise a half-mass Basel profile end-to-end, and reject a recomputed mass above one.
- [ ] Ensure a present/rehashed registry row cannot attest its own validity. Coverage/proof evidence
  must resolve to the certificate owner and verifier provenance.
- [ ] Turn the core tests GREEN. Add unseen/malformed registry probes and remove-the-owner-validation
  P29 behavior.
- [ ] Focused tests + Ruff + architecture guardrails. Commit the generic baseline.

## Workstream 3 — Make N9 draw from the ledger and close the sibling consumer

- [ ] Delete `CanonicalPromotionInput.risk_spends` and the context-provider forwarding path.
- [ ] Compile obligations, resolve actual certificate handshakes, execute ledger draws, and decide
  promotion only after ledger validation. A missing handshake for a probabilistic pass is typed
  refusal, not zero-spend success.
- [ ] Bind the exact N11 promotion projection into the N9 receipt and authority trace.
- [ ] Recompute registry, certificate evidence, schedule slot, spend, total, and projection in
  `validate_canonical_promotion_receipt`.
- [ ] Replace the generation-cycle raw-dict predicate with typed receipt parsing and revalidation.
- [ ] Turn all N9/consumer REDs GREEN; preserve the total 15-class obligation semantics and unseen
  non-panel probe.
- [ ] Reissue the N9 frozen artifact only after N11's promotion projection exists.
- [ ] Focused tests + Ruff + architecture guardrails. Commit.

## Workstream 4 — Account the real N10/N13b evidence and freeze N11

- [ ] Build N10 projections by structurally recomputing evidence kinds from owners. Current measured
  rows are education `estimand_binding_refusal`, first-vertical `owner_acquisition_route`, and unseen
  `owner_acquisition_route`; record `owner_data_gap` denominator zero.
- [ ] Build N13b projections from its typed owner models. Record 5 live attempts, 2 raw responses,
  zero admitted responses/overlay rows/world growth, and zero persisted passports. Exercise the real
  passport verifier in a warm owner test, but do not represent it as a real frozen passport row.
- [ ] Use the E1 content-keyed cached owner state for all warm accounted-run tests. No test rebuilds
  the composed world independently.
- [ ] Expose an E2 one-process closeout sweep with E5 per-stage/overall timings, E8 effective-config
  journaling, and E9 heartbeats/objective stop diagnostics.
- [ ] Add the canonical writer/checker and the frozen artifact. Declare projection scopes/edges and
  exclude operational values through the shared canonical GY hash policy only.
- [ ] Run writer x2, compare file hashes, run nested corrupt lane, and run the 17 source flips.
- [ ] Register the artifact lifecycle and regenerate reference docs. Prove zero phantoms.
- [ ] Focused tests + Ruff + architecture guardrails. Commit the generic frozen baseline.

## Workstream 5 — U3 data-only novel-instrument proof

- [ ] Record the generic-baseline commit hash.
- [ ] Add a genuinely new instrument type and certificate-class route in TOML only. Route a real
  owner-recomputed refusal through the existing generic proof kernel; do not add a Python branch.
- [ ] Re-run the canonical writer so the new type is accounted end-to-end in the universality proof.
- [ ] Commit only data/config and writer-generated artifact/reference changes.
- [ ] Prove `git diff <generic-baseline>..<data-only-commit> -- '*.py'` is empty.
- [ ] Run the U2 unregistered-instrument probe after the new type lands; it must still return typed
  `unknown_instrument` with accounting intact.

## Workstream 6 — Targeted serial closeout and architect handoff

- [ ] Lane 0: focused PDC/ledger/N9/generation-cycle logic suites.
- [ ] Lane 1: warm cached-owner real accounted run, N11 checker, N9 checker, lifecycle tests.
- [ ] Run the E2 one-process warm sweep and inspect its E5/E8/E9 run record; a warm wall time above
  about five minutes is a finding requiring cache/profile diagnosis.
- [ ] Run Ruff on every changed Python path and architecture guardrails.
- [ ] Run N11 writer/checker x2, corrupt lane, 17 source flips, and validate the canonical receipt
  chain serially: census -> N4 -> N8 -> composition -> capstone -> N13a -> N13b -> disposition.
- [ ] Run the Layer-3 GY validator census: expected raw 41, accepted 40 after excluding the
  operational acquisition executor (accepted 39 -> 40).
- [ ] Run one Lane-2 cold N11 closeout with analytics + solvers and JAX CPU. Do not repeat it per
  mutation.
- [ ] Inspect the cold stage record; a cold wall time above about 25 minutes or 2x the recorded
  historical stage time stops closure for profiling unless the stage is demonstrably advancing.
- [ ] Reopen the failure/repair register and audit P01-P34 closure, especially P05, P07, P14, P15,
  P29, P31-P34.
- [ ] Record frozen file/content/projection hashes, real spend rows, data-only commit and empty-Python
  proof, merge-tree against current main, and clean worktree.
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
