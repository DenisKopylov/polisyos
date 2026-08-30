---
title: Evidence Substitution Boundaries — Ratification Record (W5-K01–W5-K06)
status: ratified design decision — the six wave-5 evidence-substitution invariants
owner: team-architecture
created: 2026-08-30
last_reviewed: 2026-08-30
decision_status: accepted — ratified by the human principal (owner decision, 2026-08-30); this document is the acceptance record for all six statements and for the refutation list in §5. It does not amend the constitution and does not amend any prior kernel.
supersedes: nothing (it ratifies research statements)
source_kernel: docs/research/policy-operations/consolidation/wave5/wave5-ratification-candidates.md
parent_lens: docs/system-design-decisions/stage0-custody-kernel-ratification.md
research_scope: [INT-R2, INT-R3, INT-R4, OPS-R5, INT-R5, INT-R6]
controlling_heads:
  INT-R2: {response: 0afc3779e2894f2793cc40150d6923589bd36ee6, audit: dbdb1243a277f0864cae9af240ff1d13786d99df, verifier: b48cdb131c2a8d4f9b30ce217dfa3efcd65119fa}
  INT-R3: {response: 32cfebd02354b4d70fbf8beaca168aea6f2e72ee, audit: 8e9be1e5e737312f92579b57a7f011b9b14d3a46, verifier: 81635e8878ec99dd6d9e06fc7c53fb6f13ade434}
  INT-R4_OPS-R5: {response: 329edb60f77867f914581d380acfccf5882d607d, audit: ea2eac5575e5b8fb4a5462c068a37bb913076952, verifier: 082ddc26c2f8db55104ccb95518b72d84d94a06b}
  INT-R5: {response: 70f2db6d3a4330664c981721a9305f16bffe369b, audit: 247f89f016f71ee603ed76ef6dbb6403f7e651a0, verifier: d9223d12bf7cb4826c6f1f888d84275364c35fe7}
  INT-R6: {response: eb9b135089d4a54b648973db02f0312b276ea2ea, audit: bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee, verifier: 24b6813d11e87a30e849bf4a799293e682bd7fed}
  consolidation_base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/plans/active/DEBT-REGISTER.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
  - docs/reference/policy-design-case-failure-patterns.md
related:
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/int-wave-claim-semantics-ratification.md
  - docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md
  - docs/system-design-decisions/wave4-decision-evidence-ratification.md
  - docs/system-design-decisions/withheld-propositions-register.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
authoritative_for: [wave5_dispositions, evidence_substitution_rulings]
may_not_use_for: [capability_claim, production_schema, code_contract, canonical_owner_assignment, authority_grant, institutional_appointment, legal_compliance_conclusion, implementation_authorization, benchmark_passage, threshold_selection]
---

# Evidence Substitution Boundaries — Ratification Record

## 1. What is ratified

Six statements, `W5-K01`–`W5-K06`, all ratified as written. They come from the consolidation of five
research packages and their independent audits, amendments and conformance verifications: `INT-R2`
(acquisition of things that are not data), `INT-R3` (whether a real operator acts correctly on an
authority surface), `INT-R4 ‖ OPS-R5` (learning and response after deployment, a declared joint
pair), `INT-R5` (whether a person had the right to make this decision), and `INT-R6` (whether
translations preserve authority semantics).

Also ratified, and equally binding: the **refutation list** in §5.

### The subject, and why it is one subject

The consolidation presented six candidates as six conclusions. They are not six. Read each as a
refusal of a **substitution**:

| statement | what tries to stand in | for what |
| --- | --- | --- |
| `W5-K01` | more rows in the same data stream | a missing non-data object |
| `W5-K02` | conformance of a surface | the behaviour of a person |
| `W5-K03` | observation after deployment | an admitted causal diagnosis |
| `W5-K04` | a detector firing and a safe outcome | a confirmed cause |
| `W5-K05` | a certificate computed through `t0` | validity at `t1` |
| `W5-K06` | translation, locale and structural parity | source-language legal authority |

The subject of this act is **what one kind of evidence may not stand in for**.

That is not a framing convenience. It makes the rule mechanically searchable — *find a place where
evidence of kind X is projected as kind Y* — and it explains the consolidation's own strongest
finding, the cross-package analogue sweep: replay/denominator truth, current-versus-planned state,
producer/owner identity and finite-proof boundaries each recurred across four or five of the five
packages. One defect wearing five costumes. The consolidation concluded such classes *"should be
closed structurally, not per document"*, and naming the class is the first structural step.

### Why this is a separate act, not an amendment

Four subjects already exist and each has its own record: custody of claims (Stage 0) · what a
**number** may mean (INT wave) · what a public **proof and projection** may mean (PV) · what the
deciding **machinery** may turn on (wave 4). Each of those governs a kind of *output* or a kind of
*gate*. This one governs a relation *between kinds of evidence*, which none of them addressed.

Amending a prior kernel for a subject it did not consider would blur both records. The five are
related by inheritance, not revision.

## 2. The lens, inherited

Unchanged from the Stage-0 record (`stage0-custody-kernel-ratification.md` §2):

> **Does the statement bind only the authority band, or does it leak into the candidate band?** A
> statement that binds only the authority band is safe to ratify strictly. A statement that reaches
> the candidate band eats capability.

Its instantiation here is exact and worth stating, because it is what separates the six ratified
statements from the thirteen withheld ones: **a non-substitution rule binds only the projection.** It
forbids treating evidence of kind X as evidence of kind Y. It never forbids producing X, producing Y,
computing over either, or showing either. Every one of the six passes because each restricts what may
be *said*, and none restricts what may be *built*.

Applied to this act, the lens produced a clean split rather than a compromise. `INT-R4 ‖ OPS-R5`
contains both halves of the same subject: the assertion half — a record may carry a verified response
and an unresolved diagnosis together — is `W5-K04`; the action half — which responses may run, under
whose authority, at what threshold — is withheld as `WP-04`–`WP-08`. One package, cut exactly on the
band boundary.

## 3. Dispositions

| ID | Statement | Disposition |
| --- | --- | --- |
| **W5-K01** | Object-specific gap closure | Ratified as written |
| **W5-K02** | Operator comprehension is separately earned | Ratified as written |
| **W5-K03** | Causal diagnosis before learning authority | Ratified as written |
| **W5-K04** | Protective response is not causal evidence | Ratified as written |
| **W5-K05** | Mutable-dependency authority is time-bound | Ratified as written |
| **W5-K06** | Multilingual authority cannot be inferred from presentation | Ratified as written |

Two consolidations were considered and rejected during ratification:

- **`W5-K03` and `W5-K04` are not merged.** Both come from the same package and both concern the gap
  between an event and a cause. The ratification-level test is whether they can be superseded
  independently, and they can: a domain with a fully identified observation process could supersede
  `W5-K03`'s admission requirement while `W5-K04`'s separation of protection from learning still
  binds every domain. Different supersession triggers, therefore separate statements. They also fail
  in opposite directions — `W5-K03` guards against claiming too much, `W5-K04` against both claiming
  too much *and*, through `FM-OPS-06`, refusing to protect when the cause is unknown.
- **The constitution is not amended.** See §8.

Standing is unchanged by this act. Every package remains
`research_standing: accepted_narrow_scope · capability_standing: absent/unallocated ·
gate_standing: NO_GO`. `CONFORMS_WITH_GAPS` is a terminal research-quality verdict and is not a
`W4-K05` standing token.

## 4. The statements

### 4.1 Acquiring what is not data

**`W5-K01` — Object-specific gap closure.**

> PolicyOS may claim that a non-data gap is resolved only when positive evidence establishes the
> required object for that gap type and every applicable ceiling; additional rows in the same data
> stream cannot by themselves establish a missing relation, estimand, mandate, capacity, licence,
> authority or assurance object.

`INT-R2` discriminates eight acquisition types — grounding relation, estimand binding, owner
writability, legal mandate, normative authorization, implementation-capacity evidence, competent
human decision, independent audit — and the audit preserved all **28 pairwise distinctions**, proving
no two collapse. Each type has its own producer, its own sufficiency test, its own admission proof
and its own authority ceiling.

The statement's force is in the second clause, and it is not hypothetical: it is `GY-N13a`'s measured
finding that DS15's acquisition routes are **structural gaps, not data gaps**. Without this rule an
acquisition loop can grow the data pool, a surface can show a gap closing, and the actual blocker —
an absent legal mandate — never moves. That is authority leaking through a progress indicator.

### 4.2 What a person understands

**`W5-K02` — Operator comprehension is separately earned.**

> PolicyOS may claim that an operator population understands and can safely act on an authority
> surface only from population-, modality- and task-bound behavioral evidence; conformance of surface
> semantics, enforcement or instrument integrity cannot be projected as human comprehension.

`INT-R3` separates four properties earlier work could blur: surface semantics, enforcement,
instrument integrity, and real-operator behaviour. Its twelve red-first predicates partition as 6
surface / 3 enforcement / 3 instrument-integrity / **0 behavioral**, and
`human_comprehension_established` stays `false`.

This binds at the moment it is most tempting to cross. DS4, DS5, DS6, DS9 and DS11 are closed and
green; the surface does communicate authority states correctly. That is a fact about the surface.
Accessibility conformance is likewise a fact about the surface. Neither is a fact about a person
under time pressure. The honest product consequence is a limitation carried into the surfaces, not a
comprehension score — and it is the answer PolicyOS will owe a state body that asks whether its staff
can actually use this correctly.

### 4.3 Learning after deployment

**`W5-K03` — Causal diagnosis before learning authority.**

> PolicyOS may claim that post-deployment evidence validates or updates a causal effect only after
> observation validity, intervention/version ancestry, context/interference and supported mechanism
> contributors are admitted; unresolved diagnosis cannot be projected as causal confirmation.

The problem `INT-R4` isolates is **performativity**: a deployed policy changes the observation
environment itself — gaming, selective monitoring, eligibility reshaping the observed sample,
policy-induced measurement change, spillovers, censoring where no reporting channel exists. So when
realized diverges from predicted, at least four causes compete, and only one of them is about the
model. Attributing the delta to `prediction_error` by default corrupts the world model with a
delivery or measurement artifact — and since the north-star product *is* the growing causal world
model, that corruption compounds into every later cycle.

`diagnosis_unresolved` **freezes** the update. Not a weaker update, not a default attribution.

**`W5-K04` — Protective response is not causal evidence.**

> PolicyOS may report a verified protective response and an unresolved causal diagnosis in the same
> record, but it may not project the protective response, detector trigger or safe outcome as
> evidence that a causal explanation was confirmed.

The permissive half is the point. A record may carry *"we contained this"* and *"we do not know
why"* together, so honesty costs no usefulness. What it forbids is the inference that feels most
natural after a good outcome: we acted, it turned out fine, therefore we understood it.

`OPS-R5`'s failure register makes the symmetry explicit — `FM-OPS-06` names *"Unresolved cause
forbids protection under high waiting harm."* as an unsafe conclusion too. The statement guards
against over-restriction as much as over-claiming.

### 4.4 Authority over time

**`W5-K05` — Mutable-dependency authority is time-bound.**

> PolicyOS may not claim that a certificate computed from evidence through `t0` alone determines
> authority at a later `t1` across all admissible future histories when a decisive dependency can
> change; any current-validity claim must declare and evidence its profile-derived currentness
> semantics.

The correction history is the reason this is trustworthy. `INT-R2`'s sibling package originally
claimed authority *must differ* between check time and use time — a false universal inequality, which
the audit (`INT-R5-A-001`) killed. What survives is weaker and sharper: an **information limit**. Two
admissible histories identical through `t0` and divergent on a decisive dependency after `t0` cannot
both be determined by one unchanged certificate.

`snapshot_by_explicit_rule`, `issuer_authorized_lease`, `revalidate_before_commit` and
`continuous_checkpoint_revalidation` are a **supported taxonomy, not a partition** — audit `CL-F03`
is explicit that not every regime fits one without profile interpretation. And hashing caller input
is not an independent producer (`P14`).

Appointments, delegations, mandates and licences are revocable. A promotion certificate signed in one
month and cited in another, with no currentness rule, claims authority it cannot evidence.

### 4.5 Authority across languages

**`W5-K06` — Multilingual authority cannot be inferred from presentation.**

> Translation presence, UI-locale support, structural parity or an English aid cannot by itself
> establish source-language legal authority or semantic equivalence; any equivalence claim is bounded
> to its declared proposition set, purposes, qualified holders and tested denominator.

`INT-R6` holds seven dimensions apart: authored UI locale, translation, frozen locale,
source-language authority, co-authentic sets, role qualification, presentation. Its own falsifiers
are three concrete semantic promotions — `limited` becoming "confirmed with caveat",
`may_not_use_for` becoming an optional recommendation, and `stale`/`superseded`/`withdrawn` collapsed
into one.

The second clause matters as much as the first: a finite MAEP suite issues a certificate bounded to
what it tested, never a general equivalence claim. This is the finite-proof boundary that recurred
across the wave.

Ukrainian law is authoritative in Ukrainian. Rendering a mandate through an English pivot and
treating the two as interchangeable would be a legal claim PolicyOS cannot custody — and it is the
first class of error a state body would find.

## 5. What this act refutes

Ratified as binding negatives. None is available for downstream reliance, and none may be
reintroduced without superseding this record.

1. **Closure by row count.** Volume or precision in an existing data stream never closes a relation,
   estimand or mandate gap.
2. **Conformance as comprehension.** No count of green surface, enforcement or instrument predicates
   establishes that any person understood anything.
3. **Accessibility conformance as comprehension.** A separate refusal, because it is a separate
   temptation and passes different tests.
4. **Default attribution of an unexplained delta.** An undiagnosed realized-versus-predicted gap is
   never `prediction_error` by default.
5. **Outcome as explanation.** A safe result after a protective action is not evidence the cause was
   identified.
6. **Refusal to protect under an unknown cause** (`FM-OPS-06`), where waiting harm is high and the
   action is independently authorized. The freeze binds learning, not protection.
7. **The false universal inequality** that authority must differ between check and use — withdrawn by
   `INT-R5`'s amendment and not recoverable.
8. **The four currentness modes as an exhaustive partition.** They are a supported taxonomy;
   `CL-F03` refuses the stronger reading.
9. **Caller-input hashing as independent production.** `P14` independence inflation.
10. **Structural parity as semantic equivalence**, in either direction: matching keys, paths or
    locale coverage prove nothing about legal modality, qualified holder or status injectivity.
11. **A finite suite as a universal proof.** Neither `INT-R6`'s MAEP suite nor `INT-R2`'s benchmark
    can issue an unbounded claim.
12. **`INT-R6`'s prior current-census positive**, withdrawn rather than laundered during remediation
    and not restorable without an independently executed census.

## 6. Current standing and one architect correction

The wave's own arithmetic, verified at consolidation: **89 audit rows** — 1 blocking, 44 material, 15
minor, 29 commendation — reconciling terminally to 74 closed-or-preserved and 15 carried. The single
blocking row, `INT-R6 IR6-A01`, is closed; none of the 15 carried rows is blocking. All five packages
terminate `CONFORMS_WITH_GAPS`.

**One correction, recorded rather than absorbed.** A standing note in the programme's own memory held
that the path to a first governed promotion carried *"no open research and no open engineering; only
institutional prerequisites remain."* The first half is right and the second is wrong, and the
evidence is in the code rather than in any document. In
`src/polisyos/runtime/quality/promotion_sequence.py`, three of the fifteen compiled obligations
return `scope_insufficient` **unconditionally** — `_effect_obligation` (`GY-K` entailment witness
owner unwired), `_measurement_obligation` (measurement-rooted producer owner unwired, reached after
`del receipt`), and `_eval_safety_obligation` for pilot and deployment modes. `_refusal_reasons`
treats `scope_insufficient` as a refusal outside the `contract_testing` lane, so `promoted` is always
`False` in production and `consumer_promotable=True` is unreachable.

That is engineering, not appointment, and under the identity decision
[§9 item 5](policyos-identity-and-custody-boundary.md) it is exactly the class that may not be
deferred. It is registered against the GY plan and the debt register, with `GY-O0-NC-01` as its
closure signal. The third of the three is additionally a stale text: `GY-O0` merged at `313132b6b`
and `runtime/quality/evaluation_safety.py` is fully built — it is simply never imported by the
promotion sequence, which still reports the owner as *not implemented*.

## 7. Prices accepted

**Thirteen propositions are withheld, and they are substantial.** They are preserved with their
content, source and activation condition in
[`withheld-propositions-register.md`](withheld-propositions-register.md) — the seven governed
response-action families, the transition charter's fifteen fields, the asymmetric restart rule, the
eight-condition posterior-update conjunction, the SMDV-1 precedence, the no-universal-numbers
discipline, the English-pivot admission split, and the RTL evidence pack. Withholding them is a
decision about binding, never a judgement about worth; two of the four withholding classes are build
targets today.

**No comprehension claim is available for any surface, and none becomes available by building more
surface.** `W5-K02` makes that permanent until behavioural evidence exists. DS11 already publishes
341 of 343 claims as blocked, so nothing regresses; the surface was honest before the research proved
it had to be.

**The `expected_variation` update policy stays open** (`WP-02`). The interim rule holds: `GY-O1`
performs no posterior mutation. The principal ruled on 2026-08-30 only the *vocabulary* question —
see §8 — and deliberately left the update policy for a decision taken with live producers.

**What is not a price.** No statement here costs any capability. Each restricts a projection; none
restricts a producer, a computation, a surface or a demonstration. The wave's own routing adds
**zero** obligations to `GY-N11`, whose accumulated load remains the two DS17 witnesses already
recorded.

## 8. The outcome vocabulary is unchanged — §8 is not activated

The INT-wave act's §8 forward note arms a trigger: a **third new element** — the fourth total entry
under the wave-4 count — requires **one consolidated constitutional amendment**, never a separate
act. The vocabulary today is the base pair plus `S0-K06`'s *declared unknown* and `INT-K06`'s
*custody without a number*.

The closest candidate this wave produced is *"protective response while diagnosis remains
unresolved."* **The principal ruled on 2026-08-30 that it is a composition, not a new kind.** The
reasoning, recorded so the ruling can be re-examined rather than merely cited: remove *declared
unknown* and *custody without a number* from it and no assertive content remains. A new vocabulary
element must add something the composition does not supply; this one does not. Its genuinely novel
content is the authority to act protectively, which is outside the authority band and is withheld as
`WP-04`–`WP-08`.

The trigger therefore does not fire and stays armed. Should a later principal rule that this is a
distinct claim kind, it becomes the triggering entry and must be handled in one consolidated
constitutional amendment together with the prior vocabulary.

## 9. What this does not ratify

No producer, artifact, bridge, consumer, schema, enum, package, table or API. No owner, signer,
adjudicator, metric steward or after-hours substitute. No threshold, abstention rate, coverage
target, horizon, detection rate or reversibility value — and `0.25/0.70` in the DDM remains local
routing that no reuse may promote into a governed threshold. No status lattice: all six statements
constrain what may be *projected*, and the one-lattice law is untouched. No claim that the eight
acquisition producers, the comprehension study, the diagnosis corpus, the sealed oracle, the
authority-certificate chain, the multilingual corpus or the H2 response runtime exists. No legal or
jurisdictional conclusion. No permission to publish, promote or open a gate.

Every class named above resolves to at least one row in
[`withheld-propositions-register.md`](withheld-propositions-register.md), per the pipeline's §3.7
requirement:

| class named here | register rows |
| --- | --- |
| posterior-update rule and its vocabulary precedence | `WP-01`, `WP-02`, `WP-03` |
| response operations, charter, restart, protection precedence, preauthorization | `WP-04`, `WP-05`, `WP-06`, `WP-07`, `WP-08` |
| thresholds, rates, horizons, reversibility values | `WP-09`, `WP-10` |
| pivot language, locale set, jurisdiction pack | `WP-11`, `WP-12`, `WP-13` |
| owners, signers, adjudicators, producers, gates, schedules | the register's standing admission rule |

## 10. Impact note (constitution §12 form)

- **Status lattice:** unchanged. No statement creates a status. `W5-K01` and `W5-K03`–`W5-K05`
  constrain what may be *claimed alongside* one; `W5-K02` and `W5-K06` constrain what may be
  *projected from* one.
- **Authority boundaries:** narrowed, not reshaped. Six projection paths are removed. No authority
  slot is added, and no existing slot changes owner.
- **Replay behavior:** unchanged. Rule-version reference: this document's `created` date. Work closed
  before 2026-08-30 is interpreted under the prior, unratified standing; no closed task is reopened.
- **Affected plans:** the GY plan (`GY-O1`'s cause-class rider becomes binding; `GY-O3` gains the
  quarantine rider; `GY-D1`, `GY-K` and the promotion-obligation completion are named by §6), the
  Atlas plan (DS15 gap semantics, DS16–DS18 successor surface inputs, the DS12 gate restatement), and
  the debt register (typed absences and the promotion blocker). Annotations attach to open and future
  tasks only; in-flight agent lanes are untouched.
- **Research backlog:** the Completion Ledger gains five package rows; Group D gains the source-replay
  rows. No dormant row is activated.

## 11. Revisit conditions

- **When a comprehension study returns its first behavioural result:** `W5-K02`'s bar is met for that
  population, modality and task only — re-read the statement rather than generalising the result.
- **When an SMDV-1 producer and a content-bound comparison are live:** `WP-01` and `WP-02` become
  presentable, and `W5-K03`'s admission set can be tested rather than specified.
- **If a jurisdiction is admitted whose currentness regime fits none of the four named modes:**
  `W5-K05`'s taxonomy needs a fifth entry — expected, not a defect, and `CL-F03` pre-authorises the
  reading.
- **If a principal rules that protective-response-under-unresolved-diagnosis is a distinct claim
  kind:** §8's trigger fires; handle it as one consolidated constitutional amendment.
- **After the first governed real-world pilot:** re-adjudicate every `presupposes_absent_institution`
  row in the withheld register against the institutional facts the pilot produces.
