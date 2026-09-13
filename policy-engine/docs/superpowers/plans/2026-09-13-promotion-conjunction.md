# Promotion conjunction: Stage 1 and implementation plan

> Execute in this lane after the Stage 1 commit has been read from the attached branch.

**Goal:** adjudicate the six requested rows, preserve promotion refusal, and close every
identified engineering link that does not need an unanswered semantic decision.
**Architecture:** extend existing N9, generation decision-front and O0 persistence owners;
reuse CAS and runtime composition. Keep protected-purpose semantic appointment empty.
**Spec:** the user's promotion-conjunction commissioning request, plus findings below.
**Base:** `28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`; `codex/promotion-conjunction`.
Original Stage 1 source findings in this plan and linked research mean
`path@28b8a1a42`. Explicit Stage 2 implementation/probe/census additions instead
refer to the delivered implementation commit named in `execution.md`.

## Binding delivery contract

Local ordinary Git; no push, guardrails sync, DEBT-REGISTER/LEDGER edits, or OpenAPI
snapshot generation. Only targeted test node IDs/files; no directory-wide pytest.
Ledger check and architecture guardrails run alone in separate invocations; retain
actual process status. Source freezes before independent review and final gates.
Contended resources: shared Git commits (root only), each source file (one assigned
writer), and any fixture owner scratch (serialize if discovered). Raw evidence is
ignored locally beside this record; no dependency-copy dumps are committed.

## PC-00 — task zero, predicate before result

The primary unit is a **syntactic return site** whose expression contains a call to
`_satisfied_obligation`, `_failed_obligation`, or `_scope_insufficient_obligation`,
including chained `model_copy`. Walk the complete AST of the one selected Python
file `src/polisyos/runtime/quality/promotion_sequence.py`, then independently scan
its complete lexical return lines. An unread/unparsed member is ambiguous, not zero.

At the base, **4 of 39 syntactic helper-producing return sites** in that complete
single `.py` denominator call `_scope_insufficient_obligation`: lines 4855, 5182,
5380 and 5466. The AST and independent lexical cross-check agree. The corresponding
complete name-only denominator is **29 function definitions whose identifier
contains `obligation`**, including a persister, checks and a hash builder; it is
not a count of producers. The typed producer control is **18 functions annotated
with exactly `PromotionObligationDraft`**, including the three constructor helpers.
There are also **5 direct `PromotionObligationDraft(...)` return sites** outside
that primary helper-return denominator. These different predicates must not be
collapsed into a statement about all return paths.

The declared class denominator is **15 assigned members of
`PromotionObligationClass` in the complete class in `src/polisyos/pdc/_impl/gy_waist.py`**,
independently cross-checked by enum assignment lines. It is not the runtime instance
denominator: `_finalize_obligations` adds a separate effective-independence predicate
and the N8 receipt's decisive-consistency instances, all with source/candidate/problem/
invocation identity. Thus an obligation for promotion means an identified instance,
not a class, function or return site; the primary numerical statement deliberately
counts syntax only. No fixed all-run instance count is published.

Executable census and actual-read receipts:
`docs/superpowers/journals/promotion-conjunction/census.py`; its only output mode
prints selectors, every parsed input/hash, full enumerated sets, independent
cross-check and named `unresolved_by_construction` boundaries. This is a research
instrument run directly, not a claimed production capability.

**PC-01 — is refusal unconditional?** No globally. Independence and MeasurementRoot
have established/refused alternatives; PARAM has resolved G4 / force-promote /
invalid-record alternatives; EVAL_SAFETY is not applicable for data-only. Within
protected modes (`sandbox_pilot`, `field_pilot`, `deployment`) EVAL_SAFETY cannot
currently receive a promotion-authoritative producer result and always refuses.
S6/S7/S8 delegate to additional owner gates outside the counted file. Caller reading,
not the helper count, establishes these findings.

## R1–R5 adjudication and conjunction

Read the full linked research; it is part of this Stage 1 commitment:

- `../journals/promotion-conjunction/rows-research.md`: **PC-R1, PC-R4, PC-R5,
  PC-R1-UPSTREAM**, opening each pointed artifact and distinguishing historical
  findings from current source. PA1/GAP7 producer-missing typing is refuted; GY-J
  refusal custody already names Runtime, but positive scientific acceptance remains
  absent/unallocated. Existing typed demand/custody/refusal mechanism is not rebuilt.
- `../journals/promotion-conjunction/reduction-research.md`: **PC-R01–PC-R05**.
  Reduction rule: authority slot AND purpose/selection scope AND operative refusal
  mechanism AND missing condition must coincide. The current rows duplicate the
  full selected empirical acceptance signal; that duplication does not establish
  one missing field. The single-field explanation is refuted by complete candidate
  evidence missing or post-core classification unwired while the signer is present.
  No counterexample separating the two verbatim registered signals is claimed.
  Precedent **EP-F04** was read before ruling. Consolidating signal aliases is an
  architect register act and subtracts no engineering conjunct.
- `../journals/promotion-conjunction/conjunction-research.md`: full instance,
  confidence, owner, scope, replay and downstream conjunction derived from refusals,
  including currently satisfiable conditions and the actual bounded predicates.

The source reproduces the requested guards at 1929, 4439–4453 and 4576 exactly.
Constructor, semantic replay and independent authority-laundering rejection remain
reachable. Their behavioral and source-removal controls are mandatory below.

## Finite Stage 2 work, caller before mechanism

- [x] **PC-B1: epoch resolver bridge.** Extend
  `runtime/quality/generation_cycle.py` controller → `_apply_promotion_to_summaries`
  → canonical decision-front replay to carry the already-held epoch resolver.
  Non-test caller: `GenerationCycleController.run`; runnable production terminus:
  POST `/api/v1/control/runs` → recursive generation → persisted
  `runtime.compiled_recursive_generation_cycle`. Test actual replay with/without
  resolver and each forwarding seam; never promote an honest negative receipt.
  Stop-rule extension: wire an exact deployment-owned `N9PromotionEvidenceSource`
  through `PromotionRuntime` and the default controller/N9 port. Snapshot configured
  producer inputs, bind problem plus original candidate and whole-summary hashes,
  forward the actual measurement catalog/providers, independence/measurement writer
  inputs, candidate safety-source refs and optional G4 record ref. Persist actual-read
  selector receipts and typed unresolved classes; an empty or ambiguous selection
  supplies no authority. Existing scientific producers still recompute admissibility.
- [x] **PC-B2: O0 post-core classification bridge.** Extend existing
  `runtime/quality/evaluation_safety.py`, control persistence and lifecycle. Reuse
  existing completed run's compiled artifact as source; do not create an uninvoked
  replay-source producer. Deployment source selection slot is typed and empty by
  default. Validate completed source job/manifest/CAS/schema and exact
  tenant/cell/candidate/problem/world/value selection. After freezing the safety
  core, call the existing classifier with runtime epoch/open-world/N9 evidence
  resolvers, persist offer/classification or durable named nonreceipt, reconcile
  existing event/counters. Non-test caller `_admit_evaluation_safety_attempt`, same
  POST run terminus. No request-supplied verdict. Source absence, ambiguity,
  malformed/foreign source, removed resolver and retries must retain safety core,
  blocking and idempotence. Empty institutional source does not block this build.
- [x] **PC-B3: promotion-purpose intake up to the decision.** Extend N9's existing
  `_bind_production_promotion_evidence` path with a strict protected-purpose request,
  source custody/replay and typed-empty semantic acceptance/appointment slot. Use
  existing CAS signature verification for configured source authenticity; do not
  mistake it for semantic acceptance. Actual N9 port persists the bound request and
  source attempt, carries its ref, and consumes it into the protected-mode refusal.
  Non-test caller and runnable terminus are the canonical N9 port in the same
  production control generation chain. Distinct O0 purpose never supplies promotion
  authority. Unknown acceptance semantics remain empty and fail closed. Test signed
  candidate evidence, absent trust, wrong purpose/scope/content and marker-only
  forgery through real binding/replay. Do not invent the missing scientific rule.
- [x] **PC-B4: guard regressions and removal controls.** Build genuine negative N9
  receipts without the obsolete CG2 test fixture. Preserve scope markers while
  removing claimed admissibility or corrupting semantic scope: constructor must
  raise its original marker; replay must retain semantic-scope mismatch and
  authority-laundering failures. In isolated in-process function bytecode disable each guard while
  keeping marker strings; the corresponding test must turn red. Retain each output.
- [ ] **PC-B5: review, targeted verification and committed handoff.** Independent
  review uses the P40 bucket rule: classify new class vs deeper instance before a
  repair; on second same-class escape widen mechanism or declare/run bounded
  residual falsifier. Run targeted affected tests, lint, census and removal probes;
  ledger and architecture separately. No OpenAPI regeneration. Commit at clean
  boundaries and read each delivered commit from the attached branch.

Existing independence/measurement writer inputs are consumed by N9 but their default
production source-selection bridge was missing. PC-B1 now includes that independent
link; the N4 capsule remains a separate source. The deployment selects existing typed
inputs, while existing producers independently decide their admissibility. S6/S7/S8
already have typed-empty slots persisted in N9's canonical owner projection and real
absence refusals. Their historical injected flags do not define verified, protected-
purpose evidence admission; exposing those flags through the new selector would grant
unestablished authority. The remaining semantic mapping is described with its direct
evaluator falsifier in the conjunction journal. Original-construct and relation-gold
lanes already persist bound typed-empty requests and re-read them through real
consumers (PC-R4, PC-R1-UPSTREAM); no additional bridge is established for those slots.

## Pattern pass, acceptance and stopping point

Existing failures: P35 denominator conflation; P36 stale/adjacent authority; P01/P02
missing production bridges; P04/P05/P15 scope/purpose authority risks; P29/P32/P33
form-only evidence risk; P37/P38 signer or marker used as semantic predicate.
Target: existing producers → typed content-bound persisted evidence → actual caller
→ fail-closed consumer → audit surface, with behavioral negative and removal tests.
Capability labels at entry: PC-B1/PC-B2 `bridge_missing`; promotion-purpose semantic
owner `absent/unallocated`, PC-B3 `producer_missing`/`bridge_missing`; PA1 mechanism
already wired; GY-J positive semantic `absent/unallocated` with existing refusal custody.

Stop only at protected-purpose acceptance/authorized producer, original-construct
scientific admission, and the independently verified promotion-purpose S6/S7/S8
evidence-to-posture admission mapping described in execution finding PC-E02-P. Relation correspondence rules, risk composition, budget and
stratum decisions are already settled (PC-R1-CORRECTION); their remaining appointment,
scoped genuine labels and outcome-sensitive application are not an unanswered
estimator decision. HC-F11–HC-F14 instead has a built campaign/finalization path
with operating-declaration and data-pass inputs (PC-R1-HC).
Do not claim a first authentic production candidate, field near-miss or institutional
appointment. Terminal wording: `complete-pending-an-architect-decision on` those exact
links if all independent engineering and verification are delivered.

Incidental findings go to architect transcription of existing exact row IDs, as
specified in PC-R05/PC-R4/PC-R5. The OpenAPI local-digest family goes only to
`openapi-snapshot-pins-environment-derived-digests`. Tooling nonreceipts go to the
lane evidence record; inherited test failures must be replayed at the slice base
with changed-path/input-denominator disjointness before ownership is assigned.
