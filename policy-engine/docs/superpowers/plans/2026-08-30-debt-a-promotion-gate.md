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

## 8. Round 3 execution addendum (2026-08-31)

Round 3 has two hard-separated phases. Phase 1 is specification archaeology
and may change only this plan, its design specification, and the execution
journal. No source edit may precede the committed Phase-1 ruling. Phase 2 then
orchestrates the two already-built evidence writers; it does not reopen the
EFFECT evaluator decision.

The prompt names a Wave-2 Group-A row `GY-N9-EFFECT-REFERENT`. That identifier
is not present in the phase-entry revision's governed sources: `git grep` over
all 10,371 tracked files under `policy-engine/` exits 1, including the 1,133
tracked Markdown files under `docs/`. The architect-owned
row `gy-n9-effect-class-has-no-referent` is present and contains the same
question, evidence exclusions, and three terminal outcomes. Phase 1 uses that
visible contract and records the missing backlog alias as an ownership question
for the architect; this lane does not create or edit the protected backlog.

### 8.1 Phase 1 ruling: EFFECT is a distinct obligation

The ruling is outcome 3: retain `PromotionObligationClass.EFFECT` and give it
the RACE `O_effect` referent plus a real evaluator in a later governed slice.
It is neither an early name for IDENTIFICATION nor a misnamed ADMISSIBILITY
slot.

The decisive evidence is specification history, not current code shape:

1. Commit `584bd7b72` (2026-06-28) is the first repository occurrence of both
   GY-N9's “entailment / grounding (GY-K)” clause and the adopted obligations
   compiler. The parent contains neither. In that one commit, GY-N9 names
   `effect` and `identification` as separate members of the typed `O(x)`
   taxonomy.
2. The RACE spec introduced in the same commit defines `O_effect(x)` and
   `O_id(x)` as separate sets. Its effect obligations are exactly: bind the
   declared epsilon to an estimand; establish a causal path or mechanism; and
   establish that the effect claim is entailed, bounded, or explicitly
   ungrounded. Identification instead requires a point/partial/proxy/blocked
   result, explicit assumptions, a stored proof, and risk spend.
3. The missing `z_effect` coordinate does not negate `O_effect`. Section 6.2
   defines `z_ground` as the aggregate status of all active grounding
   obligations, while §12.4 defines grounding as the intersection of those
   obligations. Section 12.5 separately requires grounding obligations and
   identification certificates. Treating the status vector as the obligation
   denominator was a P38 proxy error.
4. CGF was adopted later, in commit `115536dba` (2026-07-05), as the typed atom
   grounding/linker layer. Its decision record makes GY-K a per-axis witness,
   never the decider; CG0-CG6 establish relation, joint typing, bind/admit,
   anti-proxy, acquisition, and benchmark behavior. Crediting current
   IDENTIFICATION with that CGF/CG2 grounding still leaves RACE `O_effect`
   unclaimed.
5. The initial N9 implementation corroborates but does not decide the ruling:
   it emitted separate EFFECT and IDENTIFICATION records. Its GY-K-ref-presence
   pass was later removed as non-authoritative, leaving an honest refusal; that
   implementation repair did not supersede the already-adopted taxonomy.

The future EFFECT evaluator must resolve, content-bind, and independently
recompute a candidate/problem/epoch-bound producer artifact. Its positive
predicate is the conjunction supplied by the spec: declared effect threshold
or claim bound to the estimand; current causal path/mechanism grounding; and an
entailed or bounded effect disposition. Explicitly ungrounded is a decisive
negative, and missing/malformed/foreign/self-attested evidence remains
`evidence_not_established`. A GY-K witness alone cannot satisfy it.

### 8.2 Governed version consequence

The later EFFECT evaluator is a new semantic rule beyond the expressly
EFFECT-excluding v2 design. It therefore requires:

- `n9_obligation_scope.v2 -> .v3`;
- `n9_promotion.v5 -> .v6`, with authentic v5/v3/v2 bytes retained as
  structural history and rejected for current authority;
- `n9_evidence_bridge.v1 -> .v2` if the shared strict bridge union is extended
  with the effect evidence kind, with v1 retained for readback;
- no owner-projection shape bump if the effect ref travels through the existing
  `producer_root_refs`; `n9_owner_projection.v3` remains the exact shape. A new
  top-level field would instead require v4 and is not the selected design.

Round-3 Phase 2 does not implement that evaluator and does not advance any of
these versions. Writer orchestration for the two existing v1 bridge kinds
remains inside the current v5/v3/v2 authority epoch.

### 8.3 Existing-row termination on the ruling

- `gy-promotion-obligations-scope-insufficient` is `blocked`, not closed. The
  MEASUREMENT mechanism is built, but its registered signal is the exact
  production `consumer_promotable=True` GY-O0 receipt. That cannot execute
  until the governed EFFECT evaluator lands; the field-pilot signal also
  retains the separately named promotion-authority EvalSafety producer gap.
- `GY-O0-NC-01` is `blocked` on the same EFFECT evaluator/rule epoch and on its
  already-measured field-pilot promotion-authority EvalSafety producer. The
  structural O0 safety closure stays untouched.
- `gy-n9-unmet-check-absence-kind-conflated` is `blocked` until EFFECT resolves
  through a dotted producer or an honest not-established resolution under the
  v3 rule. The ruling removes ambiguity about the class but does not create the
  missing evaluator.

### 8.4 Phase 2 writer sequence

1. Add one red integration witness for
   `persist_effective_independence`: a real production generation path must
   persist and carry the bridge ref, and N9 must reach a decisive producer
   outcome rather than `evidence_not_established`.
2. Add one red integration witness for `persist_measurement_root`: the running
   `MeasurementRootProducer` envelope must be bound and carried by a production
   path, and N9 must reach a decisive measurement outcome.
3. Wire independence as `bridge_missing + implemented_but_not_orchestrated`;
   retain the named `policy_design_case.graded_independence_weights` report
   flag as a non-N9 caller, not as promotion orchestration.
4. Wire measurement as `bridge_missing` only; reuse the already-running
   workspace producer rather than invoking a second producer.
5. Keep `generation_cycle.py` additive: carry existing refs/dependencies and
   add writer calls without reordering or replacing existing control flow or
   return shapes.
6. Close each writer row only after a source grep finds a non-test caller and
   its integration witness proves a resolved decisive obligation outcome.

### 8.5 Round 3 commit boundaries

1. Phase-1 plan/spec/journal ruling, EFFECT hash, and source-immutability
   receipt.
2. Independence writer red fixture, production orchestration, focused green,
   and caller census.
3. Measurement writer red fixture, production orchestration, focused green,
   and caller census.
4. Targeted blast-radius checks, protected baselines, five-row dossier, and
   freeze receipts.

## 9. Round 4 execution addendum (2026-08-31)

Round 4 implements the consequence of the accepted Round-3 ruling. It owns
exactly two rows: `gy-n9-unmet-check-absence-kind-conflated` and
`gy-n9-effect-obligation-producer-and-evaluator-missing`. The former closes
when an unconstructed real-semantics obligation is receipt-distinct from a
genuinely out-of-scope obligation. The latter closes only when the three RACE
§12.3 conjuncts are evaluated symmetrically: a design that fails is refused
and a design that meets them is not refused by EFFECT.

The governed epoch advances once: promotion v5 to v6, obligation scope v2 to
v3, and evidence bridge v1 to v2. Owner projection v3 remains current because
the bridge ref travels through the existing `producer_root_refs` carrier.
Authentic v5/v3/v2 bytes remain exact readable history and are rejected at
every current-authority entry point.

### 9.1 Authority boundary before red tests

The admitted `InterventionAtomBinding` is produced by the L6 owner path
`polisyos.runtime.quality.intervention_substrate.resolve_intervention_lever`,
whose internal owner builder emits a `grounded` atom. The EFFECT writer must
re-run that public owner resolver from the content-bound substrate, operator,
parameter, and WMR inputs and match its atom id/hash, operator, slots, and
world binding to the supplied atom. A `candidate_unverified` atom emitted by
`polisyos.runtime.quality.design_generation`, an atom carrying CG1/CG2 shadow
provenance as its binding authority, or an owner label without a matching
resolver result is a decisive negative, never a positive.

CG1 is crossed only to compute entailment after that independent atom binding
has resolved. `GroundingRelationEngine` does not select or construct the
binding. Its shadow certificate remains `shadow_only` and
`no_bind_admit_promote`; supplying even a valid certificate without the owner
binding and the N9 effect bridge leaves EFFECT `UNKNOWN` with
`evidence_not_established`.

The no-engine alternative is insufficient: checking only mutual consistency
among declared epsilon, estimand, and mechanism cannot establish §12.3's
third conjunct that the effect claim is entailed or bounded by the grounded
reference.

### 9.2 Red-first matrix

Before runtime changes, add exact failing witnesses for:

1. missing bridge evidence: EFFECT is `UNKNOWN`, has real semantic scope, and
   is visibly not `SCOPE_INSUFFICIENT`;
2. a valid supplied CG1 shadow certificate alone: it cannot satisfy EFFECT;
3. a CG1-derived/candidate-unverified atom: it cannot satisfy EFFECT even when
   its labels are well shaped;
4. no epsilon-to-estimand mapping: decisive
   `effect_estimand_mapping_missing`;
5. no causal path or mechanism: decisive
   `effect_causal_path_or_mechanism_missing`;
6. contradicted, unresolved, or explicitly ungrounded entailment: decisive
   `effect_claim_ungrounded`;
7. exact entailment and certified specialization: EFFECT is satisfied (the
   specialization case records the bounded disposition);
8. authentic 48,568-byte v5 history: byte-exact round-trip under v5 and typed
   rejection as current v6 authority.

Each conjunct falsifier must reach its own limitation code rather than fall
through a common evidence-missing path. The pass and fail fixtures use the
same production writer/resolver/evaluator chain and differ only in the
relevant RACE predicate.

### 9.3 Implementation sequence

1. Extend the strict evidence repository with an `effect_obligation` producer
   record and v2 bridge. Persist exact source inputs and fixed verifier
   provenance; read back exact CAS bytes and recompute the L6 owner binding,
   CG1 relation, candidate/problem binding, and disposition.
2. Invoke the writer from `_bind_production_promotion_evidence` only after the
   canonical candidate/problem input exists. Carry only its returned ref.
3. Make `_effect_obligation` consume only the resolved result. Missing evidence
   is `UNKNOWN / unknown / real_semantics`; a real negative is `FAILED`; exact
   or bounded entailment is `SATISFIED`. Remove the test-knob decision from
   EFFECT without changing the safety core.
4. Advance current receipt/scope/bridge versions and retain exact v5/v2 and
   bridge-v1 history models. Prove old bytes read under their own epoch and
   cannot regain current authority.
5. Run only the new EFFECT nodes plus the existing owner-replay, bridge,
   refusal-census, and generation-order blast nodes. Then freeze the new
   `_effect_obligation` AST bytes/hash and measure both carried reds and the
   two protected baseline checks without regenerating anything.

### 9.4 Commit boundaries

1. This approved Round-4 plan/spec/journal boundary, before tests or source.
2. Red-first provenance, three-conjunct, distinction, and history witnesses.
3. v6/v3/v2 producer/bridge/resolver/evaluator implementation and focused
   green.
4. Targeted blast radius, freeze measurements, and the two-block append-only
   register dossier.
