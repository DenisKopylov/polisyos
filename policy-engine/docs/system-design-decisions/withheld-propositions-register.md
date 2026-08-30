---
title: Withheld Propositions Register (`WP-*`)
status: active standing register — append-only
owner: team-architecture
created: 2026-08-30
last_reviewed: 2026-08-30
decision_status: opened by the human principal's ruling of 2026-08-30 that propositions withheld from ratification carry real intellectual and functional value and must have a permanent, appendable home
supersedes: nothing
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/plans/active/DEBT-REGISTER.md
  - docs/reference/policy-operations-research-pipeline.md
related:
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/wave5-evidence-substitution-ratification.md
authoritative_for: [withheld_proposition_record, withholding_reason_classification]
may_not_use_for: [capability_claim, authority_grant, ratified_statement, code_contract, canonical_owner_assignment, implementation_authorization, institutional_appointment]
---

# Withheld Propositions Register

## What this register holds

A **withheld proposition** is researched, evidenced, and deliberately **not bound**, because binding
it would leave the authority band — it would constrain what the system computes or what someone does
in the world, or it would presuppose a capability or an institution that does not exist.

Withholding is a decision about **binding**. It is never a judgement that the content is worthless.
Several entries below are among the most operationally detailed design work the programme has
produced.

### Why a separate register was needed

Nothing already in the repository holds this. Each candidate home fails for a different reason, and
the reasons are worth keeping visible so the register is not later collapsed into one of them:

| existing home | why it does not fit |
| --- | --- |
| a ratification act's §9, *"What this does not ratify"* | a negative scope statement. It names classes and carries no proposition content — which is exactly how researched content becomes unrecoverable |
| the Wave-2 backlog's **Deferred Registry** | deferred *research tasks*: "not yet studied, here is the wake condition". These are studied, and answered |
| the backlog's **Group D** dormant rows | dormant *gaps*. There is no gap here — there is an answer we chose not to bind |
| `DEBT-REGISTER.md` | debts. Nothing is owed |

Through wave 5 this content survived only as a five-bullet tail list in a consolidation file, naming
classes without carrying the propositions. `docs/reference/policy-operations-research-pipeline.md`
§3.6 now makes the withheld set a **named consolidation deliverable**, so the register is fed by
contract rather than by memory.

## The four withholding reasons

`withheld_as` is a closed set. The classification is not bookkeeping — it says what would have to
change for the proposition to become ratifiable, and two of the four are build targets **today**.

| `withheld_as` | meaning | what changes it |
| --- | --- | --- |
| `constrains_computation` | would bind what the system may compute, not what it may claim | evidence — a measured basis for the constraint |
| `constrains_action` | would authorize or restrict action in the world | a scope decision by the principal |
| `presupposes_absent_capability` | correct, but names a producer or artifact that does not exist | **build it** — the row names the task that does |
| `presupposes_absent_institution` | correct, but names a role nobody holds | **build everything around it** — the slot stays typed and empty |

The last two are not deferrals. Per the identity decision
[§9 item 5](policyos-identity-and-custody-boundary.md), an institutional absence binds the **claim**
and never the **capability**: no unappointed institution may defer, narrow or leave unscoped any
work. A `presupposes_absent_*` row that names no task row is an incomplete row.

## Standing admission rule

No entry in this register appoints an owner, signer, adjudicator, producer or gate, or sets a
schedule. An entry records a proposition and the condition under which it may be re-presented; it
grants nothing. (This is wave 5's fifth withheld group, which was a *class* rather than a
proposition, and it is recorded here as the register's own rule.)

## Entry form

```
proposition   the exact statement, quoted from its source line
source        wave · package · terminal response-line SHA · section anchor
value         the design question it answers, or what it would enable
withheld_as   one of the four reasons above
activation    what must exist before it may be re-presented for ratification
non_effect    what nobody may rely on while it is withheld
related       ratified IDs it composes with; the task row carrying its engineering half
```

---

# Wave 5 — 13 entries

**Census note.** The seed set was derived by enumerating the five groups named in
`docs/research/policy-operations/consolidation/wave5/wave5-ratification-candidates.md` §"Propositions
deliberately not presented for ratification" against the five terminal response lines, not by
sampling. The fifth group is a class and became the standing admission rule above, so it contributes
no entry. The remaining four groups yield **13** entries against a planning estimate of ≈12; the
deviation is recorded rather than trimmed and its single cause is group 1, which decomposes into
three propositions (the conjunction, the routine-schedule clause, and the vocabulary precedence the
conjunction's first condition rests on) where the estimate assumed two.

## Group 1 — the `expected_variation` posterior-update request (INT-R4)

### `WP-01` — the eight-condition posterior-update rule

**Proposition.** An effect-posterior proposal may be entered only under the full conjunction:

```text
primary_class == prediction_error
AND no blocking contributor
AND comparison/identification positive
AND maturity/censoring/interference predicates pass
AND evidence provenance ∈ {recomputed, independently_reconciled}
AND update is predeclared and version-specific
AND required authority is established
```

**Source.** Wave 5 · INT-R4 · `329edb60f77867f914581d380acfccf5882d607d` ·
`int-r4-performative-effect-update-diagnosis.md` §4.8.

**Value.** This is the operative content of the ratified `W5-K03`. `W5-K03` binds what PolicyOS may
*claim* after deployment; `WP-01` is the executable predicate that would decide when an update
actually runs. Without it, "diagnosis before learning" has no mechanism.

**`withheld_as`** `presupposes_absent_capability` — the conjunction names a comparison producer, a
contributor lane, a provenance grade and an authority check, none of which is orchestrated. It also
`constrains_computation`, and the principal declined to bind the computation ahead of the producer.

**Activation.** A live SMDV-1 producer, a content-bound realized-versus-predicted comparison, and the
provenance grading of `W4-K02` reaching the comparison inputs.

**Non-effect.** No posterior may be mutated today. The interim rule stands: `GY-O1` performs no
posterior mutation, and `diagnosis_unresolved` freezes the update rather than defaulting to an
attribution.

**Related.** Ratified `W5-K03`. Engineering half: GY plan task `GY-O1`.

### `WP-02` — `expected_variation` enters only a predeclared routine schedule

**Proposition.** *"`expected_variation` may enter only a separately predeclared routine
update/calibration schedule. All other classes route elsewhere. Unresolved freezes learning, not
necessarily protective action."*

**Source.** Wave 5 · INT-R4 · `329edb60…` · §4.8, closing paragraph.

**Value.** This is the answer to the wave's one genuinely open architectural question,
`R4-Q01`: does O1's "posterior update" mean only discrepancy-driven repair, or also routine
predeclared assimilation? The package's own answer is *both, but by different doors* — repair through
`WP-01`, assimilation only through a schedule declared in advance. The audit judged the rider
`correct = yes_with_scope`, warning that *"[O]nly prediction_error may update” must not be read as
banning a separately predeclared routine update under `expected_variation`; protective containment is
outside the learning freeze."*

**`withheld_as`** `constrains_computation`.

**Activation.** The principal rules on `R4-Q01` with `WP-01`'s producers live, so the two doors can
be distinguished in practice rather than on paper. The 2026-08-30 ruling settled the *vocabulary*
question — this is a composition of existing outcome entries, not a fourth kind of claim — and
deliberately left the *update policy* open.

**Non-effect.** No routine assimilation schedule exists, is approved, or may be inferred.

**Related.** `WP-01`; ratified `W5-K03`. Engineering half: `GY-O1`.

### `WP-03` — SMDV-1 decides before S13 routes

**Proposition.** *"SMDV-1 first decides whether movement may inform the predictive mechanism; S13
then routes admitted model-relevant divergence to an accountable component."* The movement-source
vocabulary is `prediction_error` · `implementation_failure` · `observation_process_change` ·
`intervention_delivery_or_version` · `behavioral_response` · `context_or_interference` ·
`diagnosis_unresolved`, each with a declared nearest S13 analogue and the distinction that must
survive the mapping.

**Source.** Wave 5 · INT-R4 · `329edb60…` · §4.7.

**Value.** `WP-01`'s first condition — `primary_class == prediction_error` — is meaningless without
this. It also states the precedence that keeps S13's *destination* taxonomy from being mistaken for a
*movement-source* diagnosis, which the package flags as a live confusion.

**`withheld_as`** `presupposes_absent_capability` — SMDV-1 is an unregistered candidate vocabulary
with no producer, and `FM-OPS-17` records that a second cause vocabulary forking from it is a block
condition.

**Activation.** An owner-placement decision (`R4-Q02`: new registered vocabulary, or a narrow
movement-source axis beside S13) and the total versioned crosswalk (`R4-Q03`).

**Non-effect.** No vocabulary is registered; no crosswalk is authoritative; citation is not
registration.

**Related.** `WP-01`. Engineering half: GY plan task `GY-VC1` (crosswalk) and `GY-O1` (producer);
placement decision registered in `DEBT-REGISTER.md`.

## Group 2 — response operations (OPS-R5)

### `WP-04` — the seven governed response-action families

**Proposition.** Governed response decomposes into seven families, each with a minimum evidence
posture and a required authority:

| family | actions | minimum posture | authority |
| --- | --- | --- | --- |
| `A0_observe` | retain, mature, collect denominator/follow-up | E0/immature | predeclared monitoring only |
| `A1_investigate` | validate, diagnose, acquire sentinel/implementation/context | E1 | case opening may be automatic; no substantive change |
| `A2_contain` | no expansion, degraded mode, cap, protective notice | E1/E2 + waiting-harm/guardrail | preauthorized or escalate |
| `A3_refresh` | correct/revise, bridge, recompute, recalibrate measurement | diagnosed observation/data issue | no policy-effect update |
| `A4_adjust` | repair implementation, narrow scope, partial reissue, version change | E3 + SMDV-1 + authority | competent decision required where policy changes |
| `A5_pause_or_rollback` | pause exposure, rollback future control, withdraw permission | E2/E3/E4 by risk/reversibility | preauthorized emergency or competent decision |
| `A6_terminate_or_redesign` | terminate, redesign, re-ratify, retire claim | E4 or unresolved past legal/safety clock | never from threshold alone |

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §4.4.

**Value.** The most operationally complete design in the wave. It is what makes the ratified `W5-K04`
usable: `W5-K04` says a protective response is not causal evidence, and this says which responses
exist, what each minimally needs, and which may run without a fresh human decision.

**`withheld_as`** `constrains_action` — it would restrict and authorize action in the world, which is
outside the authority band by construction.

**Activation.** A principal scope decision on whether PolicyOS may bind response operations at all,
adjudicated against the identity decision's four-way test. Note the anti-role risk the package itself
flags as `P13`: the mechanical core may be OWN while execution stays INTEGRATE.

**Non-effect.** No containment is authorized, no operation selected, no threshold or waiting-harm
rule set. PolicyOS changes only its own claim and custody state; an external executor acts.

**Related.** Ratified `W5-K04`. Engineering half: GY plan Phase 8 task `GY-CR1`.

### `WP-05` — the transition charter's required field set

**Proposition.** *"Every transition changing exposure/version/claim requires trigger, admissible
evidence, maturity, measurement-validity test, SMDV-1 requirement, waiting/premature losses,
reversibility, blast radius, VOI/next evidence, legal/governance clock, decision/override authority,
restart, version consequence, claim consequence, and sealed audit record. A threshold without this is
a P37/P38 proxy gate."*

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §4.5.

**Value.** This is `W4-K04` — a proxy gate must name its divergent case — instantiated for response.
The fifteen fields are precisely what a threshold alone omits, and the closing sentence is the
falsifier.

**`withheld_as`** `constrains_action`.

**Activation.** With `WP-04`; the charter is that proposition's evidence requirement and the two are
not separately ratifiable.

**Non-effect.** No transition may execute; no charter is required of anyone today.

**Related.** `WP-04`; ratified `W4-K04`. Engineering half: `GY-CR1`, `GY-CR2`.

### `WP-06` — restart is asymmetric

**Proposition.** *"Restart is asymmetric: alert disappearance is not evidence. It requires identified
repair/version, tests, measurement health, bounded probe, renewed authority, and historical-claim
statement. A material change creates a new treatment identity unless predeclared pooling/equivalence
evidence exists."*

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §4.5; failure rows `FM-OPS-11`, `FM-OPS-15`.

**Value.** The sharpest single sentence in the package, and a general result well beyond response
operations: **the absence of a signal is not evidence that its cause was resolved.** It is the same
shape as `W5-K04` — an operational outcome standing in for a causal fact — applied to time.

**`withheld_as`** `constrains_action`.

**Activation.** With `WP-04`.

**Non-effect.** No restart procedure is binding; `v+1` inheriting `v`'s claim is neither permitted nor
prohibited by anything ratified.

**Related.** Ratified `W5-K04`, `W5-K05` (a `t0` fact does not determine a `t1` state). Engineering
half: `GY-CR2`.

### `WP-07` — protection may precede diagnosis; learning may not

**Proposition.** *"`diagnosis_unresolved` may support investigation, containment, or a preauthorized
pause under high waiting harm; never learning or unreviewed redesign."* And: *"Protective action may
occur under lower causal certainty than learning."*

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §4.4 closing, §4.5; failure rows `FM-OPS-06`,
`FM-OPS-07`.

**Value.** The affirmative half of ratified `W5-K04`, and the reason `W5-K04` is expansive rather than
restrictive. `FM-OPS-06` names the unsafe conclusion in the *permissive* direction — *"Unresolved
cause forbids protection under high waiting harm."* — so this proposition guards against
over-restriction as much as over-claiming. It is the near-miss for a fourth outcome-vocabulary entry;
the principal ruled on 2026-08-30 that its assertion-only content is a **composition** of `S0-K06`
*declared unknown*, `INT-K06` *custody without a number* and `INT-K08` negative completion, so the
INT-wave §8 trigger did not fire.

**`withheld_as`** `constrains_action` — the assertion half is ratified as `W5-K04`; only the half
that would license or require protective action is withheld.

**Activation.** With `WP-04`. Should the principal later rule this a distinct claim kind, it becomes
the triggering entry and must be handled in **one consolidated constitutional amendment** together
with the prior outcome vocabulary, never as a separate act.

**Non-effect.** No waiting-harm model, no containment intensity rule, no obligation on any external
institution to act or refrain.

**Related.** Ratified `W5-K04`; `S0-K06`, `INT-K06`, `INT-K08`. Engineering half: `GY-CR1`.

### `WP-08` — preauthorization by family and risk class

**Proposition.** Some response families may be executed without a fresh human decision, under an
authority granted in advance and bounded by risk class — *"After hours, only explicitly preauthorized
actions may execute—typically page, investigate, no-expansion, bounded degraded mode, or emergency
pause."* and *"Owner absence selects the declared conservative state and escalation clock."*

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §8.2; open question `O5-Q04`; failure rows `FM-OPS-12`,
`FM-OPS-16`.

**Value.** The only mechanism that makes a governed system survivable outside working hours without
letting silence become consent. `FM-OPS-16` states the failure precisely: *"Owner silence after hours means approval."*.

**`withheld_as`** `presupposes_absent_institution` — no signer is appointed for reissue, rollback,
termination or override, and `FM-OPS-12` records that an owner or team string does not appoint one.

**Activation.** A named signer and a named after-hours substitute, which per the standing ruling wait
for real-user deployment. **This does not gate any build:** the declared conservative posture, the
escalation clock, the typed absence and the escape counters are all constructible now, with the
signature slot typed and empty.

**Non-effect.** No family is preauthorized; no risk class is defined; no absence is treated as
approval.

**Related.** Identity decision §9 item 5. Engineering half: `GY-CR1`; the typed absence is registered
in `DEBT-REGISTER.md`.

## Group 3 — numerical thresholds

### `WP-09` — the response threshold set, and the discipline any future number must satisfy

**Proposition.** Withheld: any domain-independent threshold, detection rate, horizon, false-signal
rate or reversibility value. Preserved as the condition on re-presentation: *"Future numbers must
name measure, population, horizon, assumptions, and authority source."* Recorded with it:
*"DDM `0.25/0.70` remains local routing"* — an existing number that is **not** a governed threshold
and must not be promoted into one by reuse.

**Source.** Wave 5 · OPS-R5 · `329edb60…` · §4.6.

**Value.** This is `INT-K02`'s declared-set rider generalized past probability to every operating
number, and it is the guard against the most ordinary failure available: a locally-tuned constant
quietly becoming a governance threshold because it was already in the code.

**`withheld_as`** `constrains_computation`.

**Activation.** A named domain, population and horizon with measured operating characteristics — the
package's own `production_candidate` bar.

**Non-effect.** No threshold is set. `0.25/0.70` carries no governance meaning.

**Related.** `INT-K02`; `W4-K01`. Engineering half: GY plan task `GY-AS2` (risk–coverage measurement).

### `WP-10` — the acceptable unresolved rate

**Proposition.** There exists a domain- and consequence-specific rate of `diagnosis_unresolved` above
which a deployment remains accountability-only rather than learning-capable — and that rate must be
established from a sealed holdout, never inherited.

**Source.** Wave 5 · INT-R4 · `329edb60…` · open question `R4-Q06`.

**Value.** Turns `W5-K03` from a per-case rule into a system-level property: it is possible to be
honest case-by-case and still run a system that learns nothing, and this is the number that would
make that visible instead of implicit.

**`withheld_as`** `constrains_computation`; also `presupposes_absent_capability` — no sealed holdout,
oracle or evaluator exists.

**Activation.** The diagnosis corpus, the all-unresolved baseline and the risk–coverage metrics.

**Non-effect.** No abstention or coverage threshold; no claim about how often diagnosis resolves.

**Related.** Ratified `W5-K03`; `S0-GAP-02`. Engineering half: `GY-AS2`, `GY-AS3`.

## Group 4 — language, locale and jurisdiction (INT-R6)

### `WP-11` — the English-pivot admission boundary

**Proposition.** English as a pivot is *"[R]ejected for legal concept definition, co-authentic
equivalence, authority generation, or scope decisions. Admitted for D4-A1 UI authoring, informative
operator aid, indexing, provisional glosses, and explanatory variants with explicit provenance/use
limits."*

**Source.** Wave 5 · INT-R6 · `eb9b135089d4a54b648973db02f0312b276ea2ea` · §"English pivot"; central
invariant *"English is not a mandatory legal pivot"*; finding `F-005`.

**Value.** A four-versus-five split that is genuinely usable: it neither bans English tooling nor lets
it acquire legal weight. Ratified `W5-K06` establishes that presentation cannot confer authority;
this says exactly where the working language may still be used.

**`withheld_as`** `constrains_computation` — it would bind which language a concept resolves through,
and the package's own finding classes it as an `architecture_decision_candidate`.

**Activation.** A principal architecture decision, taken with the multilingual corpus available so the
five admitted uses can be tested rather than assumed.

**Non-effect.** No pivot language is mandated or forbidden by anything ratified; no translation is
authoritative.

**Related.** Ratified `W5-K06`; D4-A1. Engineering half: GY plan task `GY-ML1`.

### `WP-12` — the RTL jurisdiction evidence pack

**Proposition.** A named RTL jurisdiction may be considered only through an evidence pack covering
*"authoritative scripts, Unicode normalisation, shaping, bidi isolation, logical focus/reading order,
locale formatting, copy/search/export, spoofing controls, accessibility, and red-first
mixed-direction fixtures."* Source-content RTL admission is a separate capability question and does
not imply RTL UI.

**Source.** Wave 5 · INT-R6 · `eb9b1350…` · §"RTL"; finding `F-022`.

**Value.** Ten named requirements are a complete, testable admission contract for a class of
jurisdiction the system has never handled — and the source/UI separation prevents the cheapest
mistake, which is treating a rendering capability as a legal one.

**`withheld_as`** `presupposes_absent_capability` — D4-A1 remains `not_supported` for RTL UI and no
corpus exists.

**Activation.** A named jurisdiction with its evidence pack. Not speculative work: the pack is
specified, so it can be built when a jurisdiction is named.

**Non-effect.** No RTL locale is admitted; no jurisdiction is certified.

**Related.** Ratified `W5-K06`. Engineering half: `GY-ML1`.

### `WP-13` — locale-set and jurisdiction-pack admission

**Proposition.** *"[A]dmitting a jurisdictional source language does not itself change the UI locale
set."* And: *"A jurisdiction may be admitted by records only while its requirements fit the already
admitted relation, vocabulary, evidence, and role envelope; a genuinely new semantic category remains
a governance/schema question rather than being forced into data."*

**Source.** Wave 5 · INT-R6 · `eb9b1350…` · §"Scope boundary" and central invariants.

**Value.** The free-growth rule stated for jurisdictions: growth by data is admissible up to the
envelope, and beyond it the honest answer is a governance question rather than a coerced record. It is
also the seam that keeps a UI decision (D4-A1) and a legal-source decision from being made by each
other.

**`withheld_as`** `presupposes_absent_institution` — jurisdiction admission requires a competent
holder and per-jurisdiction co-authentic reconciliation rules, and zero eligible holders exist.

**Activation.** A named jurisdiction and a qualified holder for its purposes. **This does not gate any
build:** the envelope test, the typed refusal naming the missing role, and the record-only admission
path are constructible now.

**Non-effect.** No jurisdiction pack; no locale-set change; no mandatory jurisdiction.

**Related.** Ratified `W5-K06`; D4-A1; identity decision §9 item 5. Engineering half: `GY-ML1`.

---

## Appending to this register

A consolidation stage produces `<wave>-withheld-propositions.md` and routes each row here
(`policy-operations-research-pipeline.md` §3.6). A ratification act's §9 cites the `WP-` IDs its
withheld classes resolve to (§3.7); a class named with no row here is an incomplete act.

Entries are appended, never rewritten. When a proposition is later ratified, its row gains a closing
line naming the act and the ratified ID; the row itself stays, because the record of *why it was once
withheld* is part of the reasoning that produced the ratified form.
