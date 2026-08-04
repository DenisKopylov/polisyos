---
title: INT Wave Claim Semantics — Ratification Record (INT-K01–INT-K08)
status: ratified design decision — the eight INT-wave claim-semantics invariants
owner: team-architecture
created: 2026-08-04
last_reviewed: 2026-08-04
decision_status: accepted — ratified by the human principal (owner decision, 2026-08-04); this document is the acceptance record for all eight statements, for the refutation list, and for the current standing of INT-R9
supersedes: nothing (it ratifies research statements; it does not amend the constitution and does not amend the Stage-0 custody kernel)
source_kernel: docs/research/policy-operations/consolidation/int-wave/int-wave-ratification-candidates.md
parent_lens: docs/system-design-decisions/stage0-custody-kernel-ratification.md
research_scope: [INT-R1, INT-R9, INT-R10]
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
  - docs/reference/policy-design-case-failure-patterns.md
related:
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/policy-design-custody-time-model.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
authoritative_for: [int_wave_dispositions, claim_semantics_rulings, int_r9_current_standing]
may_not_use_for: [capability_claim, production_schema, code_contract, canonical_owner_assignment, authority_grant, legal_compliance_conclusion, implementation_authorization, benchmark_passage, bounded_complete_issuance, numeric_family_claim]
---

# INT Wave Claim Semantics — Ratification Record

## 1. What is ratified

Eight statements, `INT-K01`–`INT-K08`, all ratified as written. They come from the
consolidation of three research threads and their independent audits, amendments, and
conformance verifications: `INT-R1` (obligation coverage under an open world), `INT-R9`
(first governed promotion), and `INT-R10` (family-wise risk composition).

Also ratified, and equally binding: the **refutation list** in §5. An act that fixes only
what may be said, and leaves unfixed what may not, is half an act.

### Why this is a separate document, not a Stage-0 amendment

The Stage-0 custody kernel ratified **custody of claims** — who owns what, and what does
not silently become something else. It was deliberately silent on a second dimension:
**what a number may mean.** The confidence ledger has lived with `delta`, the Basel-square
schedule, and pool weights for some time, but the semantics of those numbers were spread
across code and prose and had never been adjudicated.

This wave is that adjudication. Different subject, therefore a different record. Amending a
kernel ratified two days earlier, for a subject it did not address, would establish kernel
churn as normal. The two documents are related by inheritance, not by revision: the
authority-band lens is the parent, this act is its instantiation for quantities.

## 2. The lens, inherited

The evaluation instrument is unchanged from the Stage-0 record
(`stage0-custody-kernel-ratification.md` §2, lines 46–88; binding application note at 164–176):

> **Does the statement bind only the authority band, or does it leak into the candidate
> band?** A statement that binds only the authority band is safe to ratify strictly. A
> statement that reaches the candidate band eats capability.

Its instantiation for quantities is narrow and worth stating exactly, because the
temptation here differs from the custody case. For custody the risk was forbidding *action*.
For numbers the risk is forbidding *arithmetic* — declaring that because a public number is
unavailable, the computation behind it is illegitimate. It is not. Every statement below
forbids **projecting** a number as authority. None forbids computing one, exploring one,
holding one as a candidate-band diagnostic, or publishing one inside research under its
qualifications. `INT-K03` blocks the issuance of `bounded_complete`, not the running of
relative-inclusion checks. `INT-K07` blocks a family number for adaptive repair, not the
repair. `INT-K04` constrains what a family bound may claim, not what the ledger may compute.

All eight passed on that test. None was amended.

## 3. Dispositions

| ID | Statement | Disposition |
| --- | --- | --- |
| **INT-K01** | Relative obligation completeness | Ratified as written |
| **INT-K02** | Declared-set conditional for every `delta` claim | Ratified as written |
| **INT-K03** | Constructed independence for `bounded_complete` | Ratified as written; commissions `INT-GAP-02` as dormant |
| **INT-K04** | Family bounds require enforced caps and canonical custody | Ratified as written |
| **INT-K05** | Per-problem confidence scopes remain non-resettable and distinct | Ratified as written |
| **INT-K06** | Custody claim without risk claim | Ratified as written, **with its stated limitation discharged** (§6) |
| **INT-K07** | No numeric adaptive-repair claim without selection-valid local validity | Ratified as written; commissions `INT-GAP-01` as dormant |
| **INT-K08** | Negative completion is a valid governed result | Ratified as written |

Two candidate consolidations were considered and rejected during ratification:

- **`INT-K01` and `INT-K02` are not merged.** They look like one fact at two altitudes —
  completeness is basis-relative, and `delta` must display its basis. The ratification-level
  test is whether they can be superseded independently. They can: a competent institutional
  closure model could supersede `INT-K01`'s impossibility boundary for one named domain while
  `INT-K02`'s rider remains mandatory for every `delta` everywhere. Different supersession
  triggers, therefore separate statements.
- **The constitution is not amended.** See §8.

## 4. The statements

The wave forms one chain, and the sections follow it. `INT-R1` fixes what a single member's
number can mean; `INT-R10` fixes when several such numbers may be combined; `INT-R9` fixes
what survives when no number may be issued at all.

### 4.1 Member semantics — what one number means

**`INT-K01` — Relative obligation completeness.**

> No finite trace certifies global obligation completeness while an observationally
> invisible decisive extension remains admissible. Any positive completeness statement is
> relative to a declared, content-bound basis, obligation language, scope, purpose,
> audience, and cutoff, and every protected use carries an evidenced closure disposition.

The impossibility is premise-relative, which is what makes it usable rather than paralysing.
Each protected use carries one of `closed_by_competent_basis`, `open_under_unseen_extension`,
or `closure_not_established`; only the first defeats the premise, and only for its exact
boundary. This does **not** establish that every PolicyOS domain is open — that inference was
explicitly rejected. Governance, mutation testing, reperformance, and currentness support
reliance; they do not generate semantic truth.

**`INT-K02` — Declared-set conditional for every `delta` claim.**

> A PolicyOS `delta` statement is incomplete and may not be projected as authority unless it
> identifies the declared obligation set and maintained assumptions and visibly carries the
> relative-basis rider. `delta` is not a probability that no applicable obligation was omitted.

This is the statement with the widest blast radius, because it binds every surface that has
ever rendered a confidence number — public, reviewer, expert, and machine. The declared set
may still be wrong, stale, or incomplete; the rider exposes that fact rather than repairing it.
The runtime already carries the machinery this constrains
(`src/polisyos/runtime/quality/confidence_ledger.py:39-52`: `CONDITIONAL_VALIDITY_CLAUSE`
and `_MAINTAINED_ASSUMPTIONS`).

**`INT-K03` — Constructed independence for `bounded_complete`.**

> `bounded_complete` may not be issued from declared independence, role labels, a second
> function name, producer-filled metadata, or a self-authored benchmark. The required
> independence must be constructed and evidenced across the relevant organization,
> implementation, source/data, oracle, incentive, competence, and temporal dimensions.

The audit's finding was sharp: independence was **specified but not constructed**. Naming the
dimensions is not the same as building a producer chain that satisfies them. The repository
cannot issue `bounded_complete` today, and this act records that as a ruling rather than as a
temporary absence. What closes it is `INT-GAP-02`, registered dormant (§7).

### 4.2 Composition semantics — when numbers may be combined

**`INT-K04` — Family bounds require enforced caps and canonical custody.**

> For a fixed exact family, a family-wise false-promotion statement over several design
> problems is valid only when the exact reached-member event is declared, valid local bounds
> are fixed and enforced before member execution, their sum is within the declared family
> bound, and the canonical owner can reproduce family membership, chronology, current heads,
> and assumptions. Prose asserting a cumulative budget is not an invariant.

The mathematics is Boole's inequality and is genuinely permissive: the theorem is
heterogeneous, requiring no shared null, estimand, exchangeability, or independence between
members. What it does require is that the caps be **prospective and enforced** — fixed before
the member runs, by an owner that can later reproduce the fact. The last sentence is the
operative prohibition, and it is a lesson this project learned the expensive way: the original
INT-R9 protocol asserted a cumulative budget in prose over scopes that the ledger keys
separately, and no owner enforced anything.

**`INT-K05` — Per-problem confidence scopes remain non-resettable and distinct.**

> Canonical per-design-problem confidence scope identity is the correct primitive and must not
> be weakened, merged, or replaced merely to obtain composition. A future family relation is a
> reproducible declaration/projection over existing roots and receipts inside the same
> confidence owner, not a parent risk scope or second ledger.

This is the protective statement of the act. `confidence_risk_scope_for_problem()` keys risk on
`design-problem:<design_problem_id>` (`src/polisyos/runtime/quality/promotion_sequence.py:354-368`),
and that is **correct**, not a limitation to be engineered away. The predictable future failure
is an implementer who reads "we need composition" and introduces a parent scope or a second
ledger to get it. `INT-K05` forbids exactly that: composition is a projection over existing
roots, inside one owner.

**`INT-K07` — No numeric adaptive-repair claim without selection-valid local validity.**

> When earlier outcomes influence a later implementation, evaluator, evidence set, procedure,
> or allocation, the sequence is adaptive. No family-wise number may be attached unless the
> canonical owner verifies a local guarantee valid for the actually history-selected procedure
> and a pathwise aggregate bound; predictable accounting or an anytime-valid label alone is
> insufficient.

Adaptation is not proved impossible. The statement identifies the premises a valid theorem must
meet and records their current absence in the live owner. The failure mode it blocks is subtle
and would otherwise be very easy to commit: every allocation field and chronology marker can be
present and correct while a compliant repair selector has altered the law of the later
procedure. Markers are not validity. What closes it is `INT-GAP-01`, registered dormant (§7).

### 4.3 Custody without a number

**`INT-K06` — Custody claim without risk claim.**

> A first governed promotion may carry a bounded custody and anti-selection statement even when
> it carries no sequence-level risk number. The statement may cover prospectivity, firstness,
> substitutions, chronology, adjudication, deviations, negative terminals, publication, and
> correction; it must not be projected as statistical family control, population performance,
> compliance, competence, or production readiness.

**This is the most consequential statement in the act, and it is expansive rather than
restrictive.** Before this wave the system's vocabulary of outcomes had two entries: a grounded
claim carrying `delta`, or an honest refusal. `INT-K06` establishes a third — a binding,
falsifiable claim about **procedure**, carrying no probability at all.

It was not designed. It was found, by running into the impossibility: INT-R9 keeps
outcome-informed repair, `INT-K07` therefore withdraws every number, and what remained after the
withdrawal turned out to be substantial rather than empty. A statement that the earliest
qualifying attempt was governed, that commitments were sealed before results, that no prohibited
substitution occurred in the governed record, that dissent was preserved and negatives published
— this is checkable, falsifiable, and useful, and it needs no probability.

This is the direct answer to the honesty-against-usefulness tension that has run through this
entire stage. The resolution is not a better number. It is a third kind of claim.

**`INT-K08` — Negative completion is a valid governed result.**

> Refusal, void, dispute, terminal no-attempt, and exhaustion without promotion are valid
> completed outcomes of a first-promotion protocol. No success quota, deadline, substitution, or
> public compression may turn the absence of a positive into permission to weaken the gate or
> hide the chronology.

`INT-K08` is `INT-K06`'s enforcement at the outcome level, and constitution Rule 5 ("optimize
honesty, never `useful_design_rate`") stated where it bites hardest — at the moment a protocol
has run and produced nothing. It does not prove any particular refusal substantively correct,
and it does not eliminate strategic abstention; the constitution's T6 tradeoff still governs
there.

## 5. What this act refutes

Ratified as binding negatives. None of the following is available for downstream reliance, and
none may be reintroduced without superseding this record:

1. Global obligation completeness inferred from a finite trace without a competent scoped
   closure premise.
2. Current issuance of `bounded_complete`, under any evidence now in the repository.
3. A cumulative family budget created by prose over distinct canonical scopes.
4. Root policy `delta` treated as an attainable member-event probability or as an ordinal-zero
   reservation.
5. The withdrawn original INT-R10 source-sharpness result and its equal-share remedy.
6. A live canonical family declaration, chronology verifier, aggregate current-head projection,
   or public owner statement — none exists.
7. A numeric family theorem for INT-R9's outcome-dependent repair.
8. A fixture, schema-shaped sketch, frontmatter line, or self-authored ledger treated as its own
   authority.
9. Secrecy or within-pool randomization treated as proof of pool-level independence.
10. Any promotion, compliance, efficacy, competence, or production-readiness claim inferred from
    these research artifacts.
11. The universal inference that all PolicyOS domains are open-world — `INT-K01` requires a
    per-scope disposition and expressly denies the universal conclusion.
12. A commendation treated as ratifiable merely because an auditor praised it. Commendations
    preserve strengths in the research record; only authority-band statements survive the lens.

## 6. Current standing of INT-R9

The consolidation is pinned at `a548a2f939995ad81b4febe3402bdcb35ae11bad` and carries INT-R9 as
`verified_pending`, because at that pin no amendment-verification artifact existed. **That
standing is superseded.**

The INT-R9 amendment conformance verification
(`research/int-r9-amendment-verification`, verifying `research/int-r9-amendment@bb322361e`)
returned **`CONFORMS_WITH_GAPS`**. Option B is confirmed executed in the amended research text,
not merely in its own ledger: the protocol emits no family scope, family ordinal, cumulative
spend, `delta`, `3 * delta`, `3/100`, `1/300`, or other first-positive risk number. R1–R14 are
substantively executed, the 852-line YAML is genuinely retired
(`yaml.safe_load(...) is None`, 61 comment-only lines), all thirteen corrected adjudication
ranges resolve, and independent re-enumeration of all fifteen manifests reproduces the
set-level facts.

Two gaps were carried, both bookkeeping and neither reopening Option B: an incomplete INT-R10
rebinding across five frontmatter keys plus a YAML comment, and uneven preservation of
commendation `J-004`. **Both were closed by the architect before this ratification** (repository
commit `65b0beb72`).

Two consequences follow for this act:

- **`INT-K06` ratifies cleanly.** Its stated known limitation — "INT-R9 conformance is still
  verified-pending" — is **discharged**. What remains true, and is not a limitation on the
  statement, is that the protocol is not executable at the current pin because its institutional
  prerequisites do not exist.
- **The consolidation's own standing line is stale, and is corrected here rather than in it.**
  Editing another agent's pinned artifact to make it agree with a later fact would destroy the
  evidence of what was known when. This is the consolidation's own §7 lesson applied to our own
  merge: a correction must reach every dependent binding, and the right place for a correction is
  the current authority, not the superseded record.

## 7. Prices accepted

**`bounded_complete` is unavailable, and stays unavailable.** Not pending implementation — pending
a constructed independence model that does not exist. Atlas DS17 already renders
`open_world_unresolved` as an honest steady state rather than a placeholder, so nothing is broken
by this; the surface was correct before the research proved it had to be.

**No family number, in public or internally.** Every consumer that might have wanted one gets a
custody claim instead. Under `INT-K06` that is a real product, not a degraded one.

**Two research commissions are registered dormant**, both with explicit activation triggers, both
off the critical path:

- **`INT-GAP-01`** — a selection-valid family control for outcome-dependent repair. Activates only
  if a numeric claim is wanted for outcome-dependent continuation. Blocks nothing today.
- **`INT-GAP-02`** — constructed independence for bounded obligation coverage. Activates before any
  plan proposes `bounded_complete` issuance. `S0-GAP-02` is an **input** to it, not a substitute:
  that commission owns benchmark oracle and evaluator custody, and this wave adds consumers to it
  without broadening its scope.

**What is not a price, and is the wave's most important structural result:** the critical path to a
first public governed promotion no longer runs through any open research. `INT-GAP-01` and
`INT-GAP-02` are off it. `GY-GAP2` is off it — a family projection is needed only for a family
number. What remains on it is institutional and engineering: fresh decisive cases, named humans, a
materiality owner, sealed custody — none of which a research artifact can self-supply — plus
obligation-instance identity (`GY-GAP1`), because the INT-R1 seam maps `known_incomplete` to NO-GO
and a real promotion must therefore reach an honest coverage disposition.

Research has outrun execution. The binding constraint has moved.

## 8. The outcome vocabulary — forward note

The constitution is **not** amended by this act, on the precedent the Stage-0 record set in its
§6: sixteen ratified custody invariants did not amend it either. The bar for the constitution is
deliberately higher than "an important ruling landed."

But a pattern is now visible and should be recorded before it is forgotten. The system's vocabulary
of outcomes has acquired two new entries in three days, from two different waves and by two
different routes:

- **declared unknown** — Stage-0 `S0-K06`'s band split: the candidate band may work under an
  unknown scope when the unknown is *declared*, rather than silently substituted.
- **custody without a number** — `INT-K06`: a binding procedural claim carrying no probability.

Both expand what the system can honestly say. Both were found by running into a wall, not by
design. If a third such element appears, the right response is **one** consolidated constitutional
amendment about the outcome vocabulary as a whole — not a third separate ruling. Serial
constitutional patches for one coherent subject is the failure to avoid here.

## 9. What this does not ratify

No canonical family record, schema, or owner API. No allocation policy, family size, or public UI.
No obligation-instance identity key, aggregation algorithm, or persistence shape. No independence
evidence profile, producer appointment, or competence determination. No coverage-specific status
lattice — the existing one-lattice law is untouched. No benchmark passage. No claim that a positive
first promotion is achievable, or that the INT-R9 protocol is executable at the current pin. No
materiality owner, panel membership, or case set. The engineering conveniences in the INT-R9
protocol — three slots, six pairs, three panel members, two alternates — remain replaceable
research conveniences and are not ratified as anything.

## 10. Impact note (constitution §12 form)

- **Status lattice:** unchanged. No statement creates a status. `INT-K02` constrains what may be
  *displayed alongside* one; `INT-K05` constrains what may *own* one.
- **Authority boundaries:** narrowed, not reshaped. `INT-K03` and `INT-K07` remove two issuance
  paths that were never implemented. No authority slot is added.
- **Replay behavior:** unchanged. Rule-version reference: this document's `created` date. Work
  closed before 2026-08-04 is interpreted under the prior, unratified standing; in particular, no
  closed task is reopened by this act.
- **Affected plans:** the GY plan (`GY-GAP1` acceptance test, `GY-GAP2` status, an `N12` note), the
  Atlas plan (DS12 consumption constraints and the no-number default), and the Wave-2 backlog
  (completion ledger and two dormant Group-D rows). Annotations attach to open and future tasks
  only. In-flight agent lanes are untouched.
- **Failure-pattern register:** two new patterns, routed separately.

## 11. Revisit conditions

Each statement carries its own supersession trigger, adopted verbatim from the consolidation. The
act as a whole must be reopened if any of the following is demonstrated:

- a competent institutional model soundly establishes stronger closure for a named domain
  (`INT-K01`);
- a superseding risk semantics explicitly includes and controls the omitted-obligation event
  (`INT-K02`);
- an independence model with implemented producers, falsifiers, and independent acceptance is
  ratified (`INT-K03`);
- a composition theorem and owner contract at least as conservative and reproducible is ratified
  (`INT-K04`);
- an owner redesign proves equivalent or stronger non-reset and audit properties without parallel
  authority (`INT-K05`);
- a later ratified first-promotion protocol preserves the same claim boundary (`INT-K06`);
- a selection-valid theorem, verifier, and live owner profile are accepted (`INT-K07`);
- a protocol supplies stronger anti-abstention guarantees without forcing authority (`INT-K08`).

A demonstration that any refuted item in §5 is in fact available reopens this record immediately,
independently of the triggers above.
