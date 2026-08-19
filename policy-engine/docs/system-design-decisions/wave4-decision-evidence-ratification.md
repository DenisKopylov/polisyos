---
title: Decision Evidence And Repository Standing — Ratification Record (W4-K01–W4-K06)
status: ratified design decision — the six statements governing what a deciding procedure may turn on
owner: team-architecture
created: 2026-08-17
last_reviewed: 2026-08-17
decision_status: accepted — ratified by the human principal (owner decision, 2026-08-17); this document is the acceptance record for all six statements, for the refutation list, and for the three architect corrections applied to the consolidation
supersedes: nothing (it ratifies research statements; it amends neither the constitution, the Stage-0 custody kernel, the INT-wave claim-semantics kernel, nor the public-verification kernel)
source_kernel: docs/research/policy-operations/consolidation/wave4/wave4-ratification-candidates.md
parent_lens: docs/system-design-decisions/stage0-custody-kernel-ratification.md
research_scope: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
consolidation_head: 29f5265273d0022f483f940a2d76fe14b153a22b
ops_r14_controlling_head: 62de2c5fe2123c6814596aaf08f3391e650305de
pao_r36_controlling_head: 926326174135ef6e407037ebcbe2094228430729
pao_r4_controlling_head: 0df03f35e9b6403b7f54fd8bd45373a951851d8c
s0_gap_02_controlling_head: c14e3d43506f9a94820cd037aacb73f80dd30dcc
landed_in_register: 176335d97e67c092ec7283e36d8253353278d07f
informs:
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
related:
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/int-wave-claim-semantics-ratification.md
  - docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
authoritative_for: [gate_predicate_evidence_rules, set_level_fact_attribution, capability_label_vocabulary, research_package_standing_axes, wave4_package_dispositions, f_14a_withdrawal]
may_not_use_for: [capability_claim, production_schema, code_contract, wire_format, status_lattice, canonical_owner_assignment, vendor_or_authority_appointment, authority_grant, legal_compliance_conclusion, implementation_authorization, benchmark_passage, publication_permission, first_public_gate_opening, ops_r15_unblock, scoring_permission]
---

# Decision Evidence And Repository Standing — Ratification Record

## 1. What is ratified

Six statements, `W4-K01`–`W4-K06`. They come from the consolidation of four unrelated research
threads and their hostile independent audits, amendments and conformance verifications: `OPS-R14`
(custody resilience and expiring authority), `PAO-R36` (public correction and durable notice),
`PAO-R4` (the individual-decision firewall) and `S0-GAP-02` (the independent benchmark oracle).

Five map from the consolidation's candidates — `W4-K01`←`RC-01`, `W4-K02`←`RC-02`, `W4-K03`←`RC-05`,
`W4-K04`←`RC-06`, `W4-K05`←`RC-03`. **`W4-K06` was not a consolidation candidate**; it was found by
reading the register while preparing this act, and §6.5 records why that matters.

The consolidation's remaining two candidates are not statements and are not ratified as such:
`RC-04` (the `F-14A` withdrawal) is a package correction and appears in §6.2; `RC-07` (no active
research on the first-milestone path) is a standing claim, narrowed in §6.3.

Also ratified, and equally binding: the **refutation list** in §5 and the **three architect
corrections** in §6.

### Why a fourth act

Four ratification records now exist, and each has its own subject:

- **Stage 0** ratified the **custody of claims** — who owns what, and what does not silently become
  something else.
- **The INT wave** ratified **what a number may mean** — δ's basis, when numbers compose, and what
  survives when no number may be issued.
- **The public-verification act** ratified **what a public proof and a public projection may mean**.
- **This act** ratifies **what the deciding machinery may turn on** — the evidence beneath a gate,
  beneath a repository census, and beneath a status label.

The distinction is exact and it is why a fourth record rather than an amendment. The three prior
acts govern **outputs**: a claim, a number, a proof. Every one of them assumes some procedure
decided whether the output was admissible. This act governs **the inputs of that procedure**. The
band lens had been applied to what gates guard and never to what gates run on — so a system whose
outputs were fully governed could still have every gate green because someone said so.

Amending a prior kernel for this subject would blur all four. The records are related by
inheritance, not revision.

## 2. The lens, inherited

The evaluation instrument is unchanged from the Stage-0 record
(`stage0-custody-kernel-ratification.md:46-88`, binding application note at `:164-176`):

> **Does the statement bind only the authority band, or does it leak into the candidate band?**

Its instantiation here is the narrowest of the four acts, and the temptation is again different.
Stage 0 risked forbidding *action*; the INT wave risked forbidding *arithmetic*; the
public-verification act risked forbidding *construction*. This act risks forbidding **measurement** —
declaring that because a number cannot be cited as authority, it may not be produced or relied upon
at all.

It must not, and the wave supplies the proof case. Every wave-4 census figure is **correct**; a
complete controlled walk at the pin reproduces all thirteen tokens in both denominators, including
six zeroes, with positive and negative controls. What was wrong was never the measurement — it was
*who was entitled to cite it*. `W4-K01` therefore constrains attribution and never arithmetic:
measure freely, cite according to what you executed.

All six statements bind only what may be **relied upon as governed evidence for a decision**. None
forbids computing a proxy, running a heuristic gate in a candidate lane, recording an institutional
premise, or exploring a richer provenance vocabulary. `W4-K04` blocks a proxy from *deciding*, not
from being computed. `W4-K02` blocks three refinements from being *labels*, not from being recorded.

## 3. Dispositions

| ID | Statement | Disposition |
| --- | --- | --- |
| **W4-K01** | Set-level facts are holder-relative: a walk settles the number, not who may cite it | Ratified **amended** — compressed to two additions over `P35` (§4.1) |
| **W4-K02** | The five predicate-provenance labels are fixed; refinements are sub-annotations | Ratified **amended** — placement and no-effect-on-eligibility made explicit (§4.2) |
| **W4-K03** | A condition added to preserve a positive is itself a gate predicate | Ratified as written |
| **W4-K04** | A gate implemented against a proxy must name its divergent case | Ratified as written; instance count corrected (§6.4) |
| **W4-K05** | Research, capability and gate standing are separate axes drawn from registered vocabularies | Ratified **amended** — the value vocabularies are bound (§4.5) |
| **W4-K06** | `absent/unallocated` is the weakest capability label; prose is an input, not a chain | Ratified as written; **architect-added, not a consolidation candidate** |

All six landed in the failure-pattern register at `176335d97e67c092ec7283e36d8253353278d07f`
before this act was written. The act is the governance record; the register is the operational lens.

## 4. The statements

### 4.1 `W4-K01` — a walk settles the number, not who may cite it

A complete enumeration establishes a set-level fact. It does not establish that any given document
may rely on that fact. Beyond `P35`'s existing requirements — a complete walk at a pinned ref, the
path denominator, the file-type denominator, and the rule that an index settles neither a zero nor a
positive — a set-level record carries exactly two further things: **the party that executed the
walk**, and the predicate-provenance label **relative to the holder making the present claim**.

The same numeric tuple is therefore legitimately `recomputed` for the holder that ran it and
`institutionally_supplied` for one that did not. And an `institutionally_supplied` census **cannot
settle a zero**: a holder who did not look may not report an absence as established.

**Amendment.** The candidate required seven fields on every census record. Four are already `P35`.
Stated as seven this becomes governance load of exactly the kind `P13` exists to prevent, so the
statement is compressed to the two genuinely new obligations. The substance is unchanged.

**Why this is not pedantry.** Two phrasing families of the same defect survived into terminal text in
two different packages — *"settled true zeroes from a complete walk"* and *"settled because the
architect supplied a complete pinned tree walk"* — and one verifier graded the defect blocking while
another, having written *"not freshly recomputed here"* in its own report, left it standing. The
numbers were right in both. Only the entitlement was wrong.

### 4.2 `W4-K02` — the five labels are fixed; refinements are sub-annotations

The predicate-provenance vocabulary remains exactly `recomputed` · `independently_reconciled` ·
`consumer_asserted` · `institutionally_supplied` · `not_established`, with the last three failing
closed.

`S0-GAP-02` proposed six, adding `machine_observed`, `attested` and `institutionally_accepted`, and
its verifier correctly established that the refinement does **not** widen the non-positive set. The
three distinctions it preserves are real: deterministic recomputation versus bounded machine
observation; a consumer-specific assertion versus a signed attestation by another constrained role;
a premise merely supplied versus one accepted for a named scope after competence, dissent and
challenge review.

They are still not adoptable as **labels**. `machine_observed` is positive-eligible only
conditionally — a subtype of `recomputed`, *or* `independently_reconciled` when retained by a second
non-producing observer, with bare producer telemetry mapping to `not_established`. A gate must
answer positive-eligibility by **fixed lookup**, never by evaluating a declared condition; a
vocabulary that requires the condition to be evaluated reproduces `P37` one level below itself, which
is `W4-K03`.

**Amendment.** The candidate said "required sub-annotations" without saying where they live or what
they may affect. Ratified form: a sub-annotation is recorded **beside** the registered label, it
qualifies the evidence, and it **never alters positive-eligibility**.

### 4.3 `W4-K03` — a condition added to preserve a positive is itself a gate predicate

> Every repair that preserves a positive by adding a condition creates a new gate predicate, which
> must itself be classified. There is no fixed point until the condition is constructed at the level
> of the property it names.

Two packages reached this independently, from unrelated subjects, in the same wave. `OPS-R14` split
a falsifier so a positive survived behind "an independently reconciled **non-producing** authoritative
record", then established the non-producing character by comparing instrument bytes and receipts —
a successor-controlled record agrees perfectly and takes the positive. `S0-GAP-02` added
`machine_observed`, whose eligibility turns on a *declared* frozen scope and second observer.

The decisive test is a **class** check, not a quality check. When the added condition names a
different measurement class than the evidence constructs — content agreement offered for provenance
independence — no strengthening of the comparison ever closes it, and the correct move is to withdraw
the positive rather than commission another round.

Closure signal for any added condition: assign one registered label; name the evidence source and the
non-producing observer; construct the property rather than its marker; and falsify the condition
while keeping its declaration intact.

This is the wave's second result and it came out of the **repairs**, not the research. It also
retro-explains an already-paid cost: the GY-G composition saga's roughly seven `NO-GO` rounds
(`P31`/`P32`/`P33`), where each round satisfied the named condition and a sibling consumer reopened
the class.

### 4.4 `W4-K04` — a gate implemented against a proxy must name its divergent case

A gate built to decide a property but implemented against a cheap adjacent stand-in — an exit code, a
field's *name*, a `file:line`, a byte diff, a program root, a hash prefix — agrees with the property
almost everywhere and diverges **precisely at the boundary the gate exists to police**. Before a gate
is written or accepted: state the property in one sentence, state what the implementation actually
turns on, and **name one divergent case**. If none can be constructed, the implementation is the
property. If one can, the gate consults the distinguishing context, or the divergence is recorded as
a declared bounded limitation — never left implicit.

This is `P37` seen from the consumer's end. A `P37` gate is green because someone said so; a
`W4-K04` gate is green because it measured the wrong thing correctly. The two are checked together.

It binds procedural rules in a plan exactly as it binds code, and it binds instructions: **a stop rule
keyed to a number, a list or a directory the architect supplied is a proxy gate by construction.**

### 4.5 `W4-K05` — three standing axes, each drawn from a registered vocabulary

A research package that can be accepted while its capability and its publication gate remain closed
reports three separate fields, and each draws its values from a vocabulary that already exists:

```yaml
research_standing: <confirmed | accepted_narrow_scope | refuted | blocked | deferred_open_problem>
capability_standing: <absent/unallocated | contract_only | … | implemented>
gate_standing: <GO | NO_GO>
```

`research_standing` takes the Research Quality Bar's five outcomes from the Wave-2 backlog.
`capability_standing` takes the capability labels from the failure-pattern register.
`gate_standing` is the first-public-signature gate. No axis is inferable from another.

**Amendment, and it is the substantive one in this act.** The candidate proposed the three fields and
stated, correctly but negatively, that "an audit verdict is not a standing value". That forbids one
observed instance without closing the class. The positive form binds each axis to a registered
vocabulary — which is what actually prevents recurrence, and which required no invention: all three
vocabularies were already in force and had simply never been connected.

The instance that forces this: `PAO-R4` published `result_standing: GO_WITH_REVISIONS` across seven
artifacts while holding an unre-executed census, a retained attribution overclaim, an
`absent/unallocated` capability chain and no appointed emission owner. `GO_WITH_REVISIONS` is not a
member of the outcome vocabulary at all — it is an *audit verdict* token in a standing field. One
field could not say "the architecture is accepted" and "the repository may not act on it" at once, so
it published the positive. `OPS-R14` carries all three fields across all eleven of its artifacts and
is the reference shape.

### 4.6 `W4-K06` — `absent/unallocated` is the weakest capability label

When no admitted prerequisite chain exists at all — no typed contract, no owner, no producer, no
consumer, and no canonical owner appointed — the honest label is `absent/unallocated`, and the
missing prerequisite is named. It is weaker than every other capability label.

**Prose is an input, not a chain.** A substantive Markdown procedure, a research contract, or a plan
section describing a mechanism does not make a capability `contract_only`; `contract_only`
presupposes a real admitted type with no producer or consumer. All four packages applied this
correctly and each explained why the stronger labels would overstate — `OPS-R14` explicitly removing
the phrase "implemented as documentation artifacts only" because it is not a repository maturity
label.

## 5. What this act refutes

- **That content agreement can establish provenance independence.** It cannot, in either direction
  and at any strength of comparison. Provenance is administration, derivation, storage, key custody,
  failure and observation; bytes are none of these.
- **That `F-14A` could be repaired by strengthening its checks.** Refuted as a category error, not as
  an insufficiency (§6.2).
- **That the six-way predicate vocabulary is adoptable as labels.** Refuted on lookup shape, not on
  substance; the distinctions themselves are ratified as sub-annotations (`W4-K02`).
- **That an institutionally-supplied census can settle a zero.** Refuted; a holder who did not look
  may not establish an absence.
- **That `contract_only` describes a chain that exists only in prose.** Refuted (`W4-K06`).
- **That an audit verdict may serve as a standing value.** Refuted (`W4-K05`).
- **That the wave's shared material gap was a package defect.** Refuted: it was environmental — no
  agent environment could execute a complete tree walk — and it is closed at consolidation level by
  recomputation, not by any package's repair.
- **That `INT-R9` warrants a non-producing-record test.** Refuted by enumeration of that corpus:
  `non-producing` occurs **0** times, `admitted_instrument` **0**, and admission is explicitly
  qualified as *"not authority"*.

## 6. Current standing and three architect corrections

### 6.1 Standing

Across four independent audit registers the wave holds **128 findings** — 28 / 39 / 30 / 31 — of
which **11 were blocking** (1 / 3 / 3 / 4). Amendment dispositions reconcile exactly against that
denominator: **115 accepted · 11 accepted-with-variation · 2 declined = 128**. A further **20 named
verifier findings** sit above them.

| Package | `research_standing` | `capability_standing` | `gate_standing` |
| --- | --- | --- | --- |
| **OPS-R14** | `accepted_narrow_scope`, **conditional on the `F-14A` withdrawal in §6.2** | `absent/unallocated` | `NO_GO` |
| **PAO-R36** | `accepted_narrow_scope` | `absent/unallocated` | `NO_GO` |
| **PAO-R4** | `accepted_narrow_scope` — **not** the `GO_WITH_REVISIONS` its artifacts carry (`W4-K05`) | `absent/unallocated` | `NO_GO` |
| **S0-GAP-02** | `accepted_narrow_scope` | `absent/unallocated` | `NO_GO`, including for scoring and any `OPS-R15` unblock |

Verification verdicts: `PAO-R36`, `PAO-R4` and `S0-GAP-02` each `CONFORMS_WITH_GAPS` with **zero**
blocking findings. **`OPS-R14` remains `NO_GO`** after remediation and delta verification, because
`AV-B02` is `NOT_CLOSED`. Its `NO_GO` is *not* driven by the census gap, which is closed; it is
driven by the `F-14A` provenance-measurement defect.

**No capability moved.** Every complete chain in all four packages is `absent/unallocated`. What the
wave delivered is four research contracts stating what would have to be true — a legitimate result,
and not an advance in what the system can do.

### 6.2 Correction 1 — `F-14A` is withdrawn; `F-14B` stands

`OPS-R14`'s remediation split falsifier `F-14`. **`F-14B` is correct and independently verified**:
with declarations, successor identities, scope markers, `admitted=true` and instrument references
all intact but the succession premise falsified, it returns exactly `succession_scope_not_established`.

**`F-14A` is withdrawn.** It opened a positive route (`scoped_succession_partial`) gated on an
"independently reconciled non-producing authoritative record", and established that record's
non-producing character by comparing instrument bytes, receipts and substantive fields. A
successor-controlled or successor-derived record agrees perfectly and takes the positive — the
`P37` failure the split was meant to close, moved one level down. Its claimed `INT-R9` warrant does
not exist (§5).

The withdrawal costs nothing that was held: `F-14B` is a binding falsifiable procedural claim under
`INT-K06`, and `INT-K08` makes negative completion a valid governed result. A positive may return
**only** after a genuinely disjoint-custody record constructs administration, derivation, storage,
key-custody, failure and observation independence — an institutional artifact, therefore
`institutionally_supplied`, therefore fail-closed until a named institution supplies it. **No
"strengthen `F-14A`" round may be commissioned.**

### 6.3 Correction 2 — the no-active-research claim is narrowed to what was measured

The consolidation's `RC-07` asserts that no active research remains on the first-milestone path. Its
evidence is the wave's own typed agenda — **27 engineering, 21 institutional, 19 further-research**
items, every one of the 19 carrying a conservative fail-closed terminal (refusal, `not_established`,
abstention, bounded claim, withheld specification assurance).

That evidence establishes the narrower statement, which is what is ratified: **no wave-4 item places
new research on the first-milestone path.** The broader claim about the whole path is *inherited*
from the INT-wave and public-verification acts, whose enumerations of that path (`GY-GAP1` plus
institutional facts for promotion; `GY-GAP3` plus institutional facts for disclosure) are not
re-established here. Stated at full width without its own denominator, `RC-07` would be a negative
existential without an enumeration — the very failure `P35` governs.

`INT-R6` is genuinely unresearched and blocks an authoritative multilingual-parity *positive* only;
the fail-closed `not_established` result remains available and no first-milestone result depends on
it.

### 6.4 Correction 3 — the `P38` instance count, and where corrections are still owed

`W4-K04` was registered from the GY plan's §3.5.14 table, which catalogues **four** measured
instances. An architect note held six; the table was checked rather than the memory, and four is the
ratified count, with two further applications elsewhere in that plan and one in the Atlas plan.

Two correction obligations are **registered as owed and are not discharged by this act**:

1. **Five census-attribution sites** — `PAO-R4` `orientation-ledger.md:149` and `:199`,
   `amendment-delivery-readback.md:120`; `PAO-R36` `amendment-ledger.md:58` and `:107`. These require
   editing package artifacts, which consolidation may not do and this act does not do.
2. **`S0-GAP-02`'s six-way vocabulary text**, to be expressed as the registered five plus
   sub-annotations under `W4-K02`.

### 6.5 The wave's own process defects are recorded, not absorbed

This act ratifies research results. It does not launder the process failures that produced them, and
they were substantial: the amendment branches were cut from research rather than from audit, so **no
response-line branch contains its own audit**; four packages produced four different standing shapes
and four different handoff shapes; a capability label carrying every package's conclusion turned out
to be registered nowhere (`W4-K06`, found while writing this act, not by the consolidation); and five
of the six pipeline stages — audit, amendment, verification, remediation, consolidation — are
specified in no document at all.

The honest reading is that the pipeline currently yields more findings about itself than about its
subjects. That is a reason to specify it, and it is recorded here as the wave's most actionable
non-research output.

### 6.6 The pinned artifacts are not edited

No package artifact, audit register, verification record or consolidation deliverable is modified by
this act. The controlling heads in the frontmatter are the evidence; corrections are routed, not
applied.

## 7. Prices accepted

**`OPS-R14` does not close.** A wave that delivered a strong architecture ends with one package at
`NO_GO`, and this act ratifies that rather than resolving it. The alternative — accepting `F-14A` —
would have bought closure with a positive route that a successor-controlled record can walk through.

**A withdrawn capability is not replaced.** `scoped_succession_partial` is gone and nothing takes its
place until an institution supplies a disjoint-custody record. The outcome vocabulary absorbs this
without a new element, which is the third consecutive wave in which that has been true.

**Governance load increases.** `W4-K01`, `W4-K02` and `W4-K04` each add obligations to work that was
already heavy. `W4-K01` was compressed for exactly this reason. **`P37`'s cost at scale remains
unmeasured**: it has been applied in research documents and never yet in code, and the first
implementation that applies it should report what it cost.

**The institutional layer did not move.** Twenty-one institutional questions are handed up,
`INST-01`–`INST-05` are untouched, and `S0-GAP-02` states plainly that a fully specified system could
still lack anyone able to sign. This is the fourth consecutive wave with that result.

**What is not a price:** no research blocker was created. All 67 handed-up items are engineering
wiring, named humans, or research with a conservative terminal already available.

## 8. The outcome vocabulary is unchanged — §8 is not activated

The INT-wave act's §8 recorded that the vocabulary of outcomes had gained two entries in three days,
and instructed that a **third** warrants one consolidated constitutional amendment rather than a
third separate ruling.

**This wave produces no third element, and the count remains three.**

- `succession_scope_not_established` and `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` are typed negative
  completions under the existing `INT-K08`, not a new favorable claim kind.
- `F-14B` is a binding procedural claim carrying no probability — the existing `INT-K06`, in a new
  domain.
- The predicate-provenance labels and the capability labels are **evidence classifications**, not
  outcomes; they qualify how a result was reached and never add a kind of result.
- The three standing axes report on a package, not on a claim.

The constitution is therefore not amended, and the §8 trigger stays armed for a genuine third
element.

## 9. What this does not ratify

No mechanism, algorithm, schema, enum, wire format, package, database table or API. No status
lattice — the standing axes and evidence labels feed the **existing** vocabularies and create no new
one. No canonical owner, vendor, custodian or institutional appointment; in particular no owner for
the policy-to-case emission chokepoint, which remains an open consolidation decision. No claim that
any custody-resilience, public-correction, individual-decision-firewall or benchmark-oracle capability
exists, is bridged, or is verified — all four chains are `absent/unallocated`. No permission to
publish, sign, score, promote or open a gate. No `OPS-R15` unblock. No legal-sufficiency or
jurisdictional conclusion. No claim that `P37` is affordable at implementation scale, since that has
never been measured. No claim about the first-milestone path wider than §6.3 states.

## 10. Impact note (constitution §12 form)

- **Status lattice:** unchanged. `W4-K01`–`W4-K04` constrain what evidence a decision may rest on;
  `W4-K05` and `W4-K06` constrain how a package reports itself. No statement creates a status.
- **Authority boundaries:** narrowed, not reshaped. `W4-K03` and the `F-14A` withdrawal remove an
  issuance path that was never implemented. No authority slot is added.
- **Replay behavior:** unchanged. Rule-version reference: this document's `created` date. Work closed
  before 2026-08-17 is interpreted under the prior, unratified standing; no closed task is reopened
  by this act, and no accepted audit finding is reopened.
- **Affected destinations:** the failure-pattern register (already landed at `176335d97`), the Wave-2
  backlog (wave-4 completion, the standing axes, and a `Pattern Pass` that stops at `P34`), and both
  active plans, which cite `P38` and may now cite it as registered.
- **Failure-pattern register:** **changed**, and this is the first act to change it. `P38` is
  registered; `P37` gains the fixed-point corollary and the fixed-label ruling; `P35` gains the holder
  rider; `absent/unallocated` becomes a capability label. Unlike the public-verification wave, this
  wave's analysis failures were *recurring* and met the register's own recurrence bar.

## 11. Revisit conditions

Each statement carries its own supersession trigger:

- a controlled provenance model lets a holder establish an absence it did not walk — for example a
  signed, independently retained enumeration whose completeness is itself verifiable — in which case
  `W4-K01`'s holder restriction narrows to the unverifiable case;
- a sixth provenance class is proposed whose positive-eligibility is decidable by **fixed lookup**
  rather than by evaluating a declared condition, which would satisfy `W4-K02`'s only objection and
  admit it as a label;
- a repair is demonstrated that preserves a positive by adding a condition **constructed at the level
  of the property it names**, which would not refute `W4-K03` but would establish its fixed point and
  should be recorded as the worked example;
- a gate is shown whose proxy is provably co-extensive with its property over the full input domain,
  which satisfies `W4-K04`'s own stopping clause — the implementation *is* the property;
- a fourth standing axis becomes necessary, or one of the three is shown to be inferable from the
  others, either of which supersedes `W4-K05`;
- a repository state arises that is genuinely between `absent/unallocated` and `contract_only`, which
  would extend `W4-K06`'s vocabulary rather than refute it;
- an institution supplies a disjoint-custody succession record, which reopens the positive route
  withdrawn in §6.2 under the conditions stated there.

Additionally: if the pipeline specification named in §6.5 is written, this act's §6.5 becomes
historical and should be cited as the motivating record rather than as a live finding.
