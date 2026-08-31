# Debt A Promotion Gate Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans`,
> `superpowers:test-driven-development`, and
> `superpowers:verification-before-completion`. Execute only the targeted nodes
> named here; a directory-wide or full-suite run is forbidden.

**Goal:** Remove the three known minting paths from the canonical N9 promotion
gate, version the receipt-affecting obligation change, and leave every
unavailable positive authority chain visibly fail-closed without changing the
EFFECT ruling or the attempted-evaluation safety core.

**Architecture:** Reuse the existing CG2 admissibility producer, the real N5
negative vocabulary, the measurement-root producer, and the attempted-
evaluation safety contracts. Current authority moves from promotion v4 with
`n9_obligation_scope.v1` to promotion v5 with `n9_obligation_scope.v2`;
authentic v4/v1 receipts remain readable only as history. The current owner
projection drops the two caller assertions. Missing effective-independence and
coupling evidence becomes an explicit refusal, never an inferred pass.

**Spec:**
`docs/superpowers/specs/2026-08-30-debt-a-promotion-gate-design.md`

## 1. Standing, source freeze, and scope

Execution is attached to
`refs/heads/codex/debt-a-promotion-gate` in the existing worktree
`.worktrees/debt-a-promotion-gate`. The immutable slice base is
`784d020148c56e9bfb3a3631909ba11232210a9f`. Do not create another worktree,
branch, rebase, reset, force-push, or use a stash as storage.

The task denominator is exactly these five registered rows:

1. `gy-promotion-obligations-scope-insufficient`
2. `gy-n9-caller-asserted-gate-predicates`
3. `gy-n9-coupling-obligation-cannot-fail`
4. `gy-n9-unmet-check-absence-kind-conflated`
5. `GY-O0-NC-01`

The binding task is `GY-PR1` in
`docs/plans/active/layer3-slices/GY-engine-subordination.md`. The five source
rows were read in full from `docs/plans/active/DEBT-REGISTER.md`; neither file
may be edited in this lane. `docs/plans/active/LEDGER.md`, the Atlas master
plan, and `tools/quality/validation/check_debt_ledger.py` are also read-only.

### Binding exclusions

- Keep `_effect_obligation` byte-for-byte unchanged. Do not decide what EFFECT
  means, rename its class, correct its owner string, or use it as a test
  control.
- Do not change the EvalSafety decision core, `safety_semantic_hash`,
  `decision_id`, certificate authority envelope, or attempted-evaluation
  admission behavior.
- Do not add a new promotion obligation class or status. If honest absence
  requires vocabulary the current lattice lacks, record the row open.
- Do not manufacture `n5_coupling_blocked`, a measurement marker, an
  independence pass, or an EvalSafety promotion certificate.
- Do not edit
  `tests/integration/runtime_quality/test_first_governed_promotion.py`.
- Do not edit `src/polisyos/runtime/http/dependencies.py`: the read-through
  found that it is not the execution composition root for either N5 or
  EvalSafety.

## 2. Pattern pass

The relevant failure-register rows are `P01`/`P02` (contract or producer with
no bridge), `P04`/`P05` (status and authority leakage), `P07` (receipt replay),
`P10` (semantic adequacy), `P14` (independence inflation), `P17` (coupling-
gated composition), `P29` (behavioral gate), `P31`/`P32` (class repair and
trust by form), `P33` (adversarial variants), `P37`/`P38` (predicate provenance
and proxy divergence), `P40` (repair bucket), and `P41` (red provenance).

Current capability reality, before changes:

| Predicate | Reality label | Decisive fact |
| --- | --- | --- |
| Admissibility | `bridge_missing` in production assembly | CG2 already produces and content-verifies `admissibility_closed`; the standalone Boolean is redundant and inert. |
| Effective independence | `producer_missing` for N9 authority | General calculators exist, but no candidate-bound persisted N9 artifact, resolver, or verifier-provenance chain exists. |
| Coupling | `bridge_missing` | N5 emits typed blockers on `SimulationPortObservation`; N9 reads different ad-hoc strings from `CandidateSummary.value_blockers`. |
| Measurement | `bridge_missing` | `MeasurementRootProducer` exists, but its artifact is not carried through ValueGateReceipt into N9. |
| Evaluation safety for attempted work | implemented and orchestrated | Its certificate explicitly forbids use for promotion. A separate promotion predicate is `producer_missing`. |

The target correct pattern is: caller declarations have no authority surface;
positive predicates require resolve + content-bind + verifier provenance;
missing evidence refuses; historical receipts remain readable but cannot regain
current authority; tests exercise real owner behavior and mutation, not marker
presence.

## 3. Per-row acceptance matrix

| Row | In-lane target | Closure signal | Stop/open signal |
| --- | --- | --- | --- |
| caller-asserted predicates | Remove both current input fields and reject both context keys. Reuse CG2 for admissibility. Add an explicit effective-independence non-receipt. | A truly inadmissible CG2 design is red and caller `True` is structurally rejected; effective independence resolves through a candidate-bound producer. | If no N9-scoped independence producer exists, eliminate minting but leave the row `open`, naming the producer. |
| coupling cannot fail | Replace absence-as-success with fail-closed behavior over the actual N5 evidence boundary. | A real unresolved joint-simulation outcome reaches N9 and COUPLING refuses. | If `SimulationPortObservation` cannot reach N9 without editing another owner, leave `open` as `bridge_missing`; do not broaden the token list. |
| scope-insufficient obligations | Correct only in-scope owner/basis statements and wire only evidence that can be verified. | The production refusal set is reduced honestly; no constructed marker can pass. | EFFECT remains; measurement or promotion-grade EvalSafety without an admitted bridge remains open. |
| absence kind conflated | Distinguish an existing producer with missing bridge from an absent/unallocated promotion owner in details and owner refs. | Every in-scope row names a resolvable owner or explicit `absent/unallocated`, and unconstructed is distinguishable from out-of-scope. | If a new status is required, retain the existing fail-closed status and record the vocabulary requirement `open`. |
| `GY-O0-NC-01` | Preserve the structural O0 closure and update only the empirical non-closure basis. | A real current production promotion disagrees with an EvalSafety block; forged receipts cannot close it. | Required verdict is `open`; never construct a promotion. The dossier must state every remaining real conjunct measured on this branch. |

## 4. Task sequence

### Task 1 — Bind the environment and record baselines

- [ ] Run `uv sync --frozen` in `policy-engine/`.
- [ ] Run the current targeted promotion test node(s) named below before edits.
- [ ] Run the two protected documentation checks and record direct exits plus
      the docs-lifecycle finding count.
- [ ] Record the exact EFFECT function bytes/hash so closeout can prove it did
      not move.

Commands:

```bash
uv sync --frozen
uv run pytest tests/unit/runtime/quality/test_promotion_sequence.py -q
PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

If the whole promotion unit file is too broad after collection measurement,
run only the exact new/affected node IDs. No directory-wide substitution is
allowed.

### Task 2 — Red-first minting tests

- [ ] Add a fixture proving current `CanonicalPromotionInput` and the N9
      context bridge reject caller `admissibility=True` and
      `effective_independence=True`.
- [ ] Add a real CG2 inadmissibility fixture proving the content-bound owner
      keeps promotion red without consulting caller input.
- [ ] Add a real N5 blocker-spelling fixture proving
      `unsupported_coupling_class:feedback` is not treated as a coupling pass.
- [ ] Add a no-N5-evidence fixture proving absence is not success.
- [ ] Move the generic scope-insufficient anti-vacuity mutation from EFFECT to
      the resolvable G4 PARAM absence path.
- [ ] Move the owner-recomputation mutation from EFFECT/MEASUREMENT to a real
      owner refusal such as the forged G4 PARAM record.

Run only the new node IDs and record the expected failures before source
changes.

### Task 3 — Governed v5/v2 compatibility seam

- [ ] Set the current promotion input/receipt schema to v5 and obligation scope
      to v2.
- [ ] Add exact v4/v1 history models and dispatch; v4 must parse and round-trip
      as history but fail every current-authority entry point.
- [ ] If the current owner projection drops the two Boolean fields, bump it to
      v3 and retain exact v2 for v4 history.
- [ ] Advance the current comparison projection rule when its typed current
      owner changes; retain the prior rule for history.
- [ ] Validate that every current row carries the recomputed v2 scope hash.
      A self-consistent v4/v1 receipt merely restamped as v5 must fail.
- [ ] Do not migrate a v4 receipt into current authority. A fresh owner replay
      is the only reissue path.

### Task 4 — Repair the three minting paths

- [ ] Remove the caller Boolean fields from current input/projection/replay and
      reject their context spellings.
- [ ] Keep admissibility on the existing CG2 certificate/resolver path.
- [ ] Emit one explicit fail-closed decisive predicate for missing
      candidate-bound effective-independence authority.
- [ ] Change COUPLING from absence-as-success to `scope_insufficient` until a
      verified N5/S5 projection is present. Do not enumerate more blocker
      strings.
- [ ] Preserve class totality and mixed-outcome refusal composition.

### Task 5 — Owner truthfulness without safety-core mutation

- [ ] Correct MEASUREMENT detail/ownership to the existing
      `MeasurementRootProducer` and state the N8→N9 bridge gap.
- [ ] Correct EvalSafety text: attempted-evaluation safety is implemented, but
      its certificate is not promotion authority. Do not import it as proof.
- [ ] Leave `_effect_obligation` exactly unchanged.
- [ ] Re-run focused tests, then inspect the diff for any safety-core or EFFECT
      movement. Stop if either moved.

### Task 6 — Generated companion decision

The promotion contract is a governed generated artifact and the obligation
compiler is a freshness trigger. After source freeze, run its check once. If
the check says the frozen artifact must be reissued and the task-owned writer
can do so without a wider suite, reissue only
`architecture/policy_design_case/layer3_gy_promotion_contract.json`, verify it,
and record the command. If reissue requires changing another lane's owner or
an unapproved downstream artifact family, do not fabricate freshness; record
the generated companion as open.

### Task 7 — Closeout and dossier

- [ ] Reopen the failure-pattern register and classify any new finding under
      P40 before repairing it.
- [ ] Run targeted tests, Ruff on changed Python files, and relevant
      architecture/public-surface checks only.
- [ ] Run the two protected documentation commands; debt-ledger exit must be 0
      and docs lifecycle must remain exactly six findings.
- [ ] Verify branch attachment and commit every coherent boundary.
- [ ] Finish the journal with five dossier blocks, the exact deciding commands,
      direct exits, decisive output, append-only register prose, and arithmetic
      `5 = closed + open + blocked + ambiguous`.
- [ ] Request an independent code review after source freeze; batch blocking
      findings before the final targeted wave.

## 5. Patch/generalise boundary

This lane begins on the **narrow-patch** side. The scoped defects teach two
different properties: caller assertions are not authority, and absence of a
producer token is not success. A second spelling of either property triggers
generalisation. At that point stop enumerating strings and implement one
source-derived admissibility rule requiring a resolvable dotted owner plus an
input capable of producing a refusal. The journal records whether that trigger
occurred and which finding caused it.

## 6. Commit boundaries

1. Plan, design, and initial journal — before source changes.
2. v5/v2 history/readability seam plus red/green compatibility tests.
3. Caller-predicate and coupling minting repair.
4. Owner-truthfulness/test-control repair.
5. Generated companion, verification receipts, and final dossier if required.

Immediately before every commit run `git status -sb` and
`git symbolic-ref -q HEAD`; both must name
`codex/debt-a-promotion-gate` as an attached branch.

## 7. Round 2 execution addendum (2026-08-31)

Round 1 is the committed starting point. This addendum supersedes its open-row
handoff without rewriting it. The approved repair is resolve-and-bind
orchestration through the existing `producer_root_refs` and `value_blockers`
coordinates. It does not restore caller Boolean predicates, copy producer
payloads into `CanonicalPromotionInput`, modify either producer module, or
touch EFFECT.

### 7.1 Measured capability states

The complete `src/**/*.py` denominator is 2,611 files.

- `MeasurementRootProducer` is constructed once in production, by
  `runtime/quality/workspace/loop.py`. Its N9 state is `bridge_missing`: the
  producer runs and persists a CAS payload, but its envelope is not resolved
  and candidate/problem-bound by promotion.
- `build_effective_independence_graph` has one feature-flagged source call in
  `runtime/quality/evidence_independence.py`; the enclosing map builder has no
  promotion-path caller. Its N9 state is `bridge_missing` plus
  `implemented_but_not_orchestrated`.
- `n5_coupling_blocked` occurs zero times in the same source denominator.
  N5 already emits a typed unsupported coupling classification; N6 drops that
  classification before `CandidateSummary`, so the missing link is executable.

These labels are deliberately asymmetric. Treating the first two producers as
equally absent would repeat W5-K01 and the scoped absence-kind defect.

### 7.2 Round 2 acceptance signals

1. `gy-n9-caller-asserted-gate-predicates`: persist and independently resolve a
   real effective-independence graph binding; a dependent graph makes the
   decisive predicate refuse even when legacy caller `True` is attempted.
2. `gy-n9-coupling-obligation-cannot-fail`: a real unsupported N5 result emits
   `n5_coupling_blocked`, the selected summary carries it, and COUPLING refuses.
3. `gy-promotion-obligations-scope-insufficient`: a real
   `MeasurementRootProducer` envelope is CAS-resolved, content/provenance
   checked, and candidate/problem-bound; the MEASUREMENT obligation then has a
   real satisfied and a real refusal path.
4. `GY-O0-NC-01`: record `blocked_by:
   gy-n9-effect-class-has-no-referent` under the 2026-08-30 ruling. The
   field-pilot census also decides whether an EvalSafety promotion-authority
   producer must be named.
5. `gy-n9-unmet-check-absence-kind-conflated`: retain `blocked`; EFFECT cannot
   be retyped while its ruled investigation is outstanding.

Every verdict is decided by a rerunnable command and is either `closed` or
`blocked`. No row may end `open` in this round.

### 7.3 Red-first and implementation order

1. Commit this plan, the design addendum, and the initial journal before any
   test or source edit.
2. Pin authentic pre-Round-2 v5 receipt bytes and add red tests for structural
   history readback, independence refusal, measurement resolution, N5 token
   emission/carry, and N9 COUPLING refusal.
3. Add one CAS-backed N9 evidence-bridge repository in
   `promotion_sequence.py`. Both bridge kinds use exact readback, producer
   content validation, candidate/problem binding, and verifier provenance;
   their different orchestration states remain visible in diagnostics.
4. Make the N5 projection change additive in `generation_cycle.py`: append the
   typed token for the existing unsupported classification and union only that
   token into the selected summary. Do not reorder control flow or change a
   return model.
5. Run the before/after refusal census for data-only and field-pilot classes at
   both production and contract-testing lane semantics. This table, not the
   Round-1 inference, decides the GY-PR1 plan correction.
6. Freeze source, run only affected nodes plus the exact E-adjacent and
   D-adjacent consumers identified by the touched-field census, then append the
   five-block dossier.

### 7.4 Receipt-version ruling to prove

Keep current `n9_promotion.v5 / n9_owner_projection.v3 /
n9_obligation_scope.v2`. V2 is an unmerged provisional epoch created for this
owner-truthfulness repair; owner outcomes changing under that rule rekeys the
receipt chain but does not change the input/projection shape or scope-hash
algorithm. A `.v3` scope bump would require freezing/publishing v2 or changing
that algorithm.

The ruling is accepted only if authentic Round-1 v5/v2 bytes still parse and
round-trip exactly as history, fail current owner-authority replay, and a newly
resolved owner changes its obligation and gate hashes while retaining the v2
instance-scope coordinate. The governed-artifact census is part of the
receipt: no durable v5 receipt is currently published in the 656-file
JSON/TOML/Markdown denominator, so no current artifact may be silently
restamped.

### 7.5 Pattern and patch/generalise ruling

Relevant patterns are P01/P02/P12 (producer handshake), P14 (independence
inflation), P31/P32 (class repair and resolve/content-bind/provenance), P37/P38
(gate predicate versus proxy), and P40 (same-class widening). Round 2 crosses
to the **generalise** side for producer evidence: independence and measurement
are the second spelling of the same resolve-and-bind property, so one typed
repository/resolver handles both. Coupling stays a narrow, separate typed
negative bridge because it is a different property and already has a real
producer classification.

The expected honest residual is named before implementation: if a producer is
not invoked or its bridge ref is not carried, its obligation refuses for
`evidence_not_established`. This is safer than minting but can keep production
non-promotable. The dossier must name the invocation that would supply each
missing bridge rather than calling this semantic absence.

### 7.6 Round 2 commit boundaries

1. Approved plan/spec/journal addenda.
2. Red-first bridge, history, and coupling fixtures.
3. Independence and measurement resolve-and-bind implementation.
4. Additive N5-to-N9 coupling transport.
5. Targeted verification, independent review, and append-only dossier.
