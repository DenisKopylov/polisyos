---
title: INT-R10 — Family Composition Fixture and Semantic Handoff Sketch
status: delivered
kind: deep-research-support
research_task: INT-R10
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-revision
historical_audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: f5c9103ba390d471dd3f2806ca10e2b0f1288a08
revised_after_audit: research/int-r10-independent-audit@7f41bf8b7f6ca8e20bc885656314563de2e2cfc6
inspection_date: 2026-08-03
authoritative_for:
  - research-level fixture properties for canonical family-risk composition
  - semantic invariants for a future confidence-ledger-owned family relation and aggregate projection
  - behavioral falsifiers for pre-execution reservation, exact schedule recomputation, family completeness, chronology, and currentness
  - preservation of canonical per-problem scope identity and a single risk-accounting owner
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, class, enum, package, database, or serialization contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - assertion that the sketched family relation or projection exists in live source
  - substitution for a separate owner-design and implementation decision
  - proof that a local statistical theorem is sound on real data
research_only: true
---

# INT-R10 — Family Composition Fixture and Semantic Handoff Sketch

## 1. Standing and deliberate demotion

This support file is a **semantic test and handoff sketch**, not a loadable contract.

The audited version supplied complete class-like names, schema-shaped YAML, package-like references,
enumerated terminal/refusal vocabularies, and a near-complete algorithm. Those choices have been
removed. A later owner-design task must still choose every record name, package location,
serialization, content-identity rule, lifecycle vocabulary, error code, and public projection
shape.

Only these invariants survive:

1. N9 continues to derive one canonical scope per design problem
   (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
2. The existing confidence ledger remains the only risk-accounting owner.
3. Exact schedule reservations are computed from the root-bound registry before owner execution.
4. A family result is a recomputed relation over existing roots and current-head receipts, not a
   parent scope or second ledger.
5. Family membership, chronology, assumptions, currentness, and fixed/adaptive standing must be
   verified behaviorally.
6. At the pinned baseline, a positive family projection must refuse because the declaration,
   chronology verifier, aggregate current-head projection, and public owner statement are absent
   (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

The baseline gap is unchanged and real. The corrected arithmetic shows that the gap is custody and
reproduction, not an inflated sum of root policy ceilings
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 2. Mathematical fixture oracle

### 2.1 Controlled event

For ordered exact family `F`, retain:

```text
V_i = R_i intersect P_i intersect W_i
V_F = union_i V_i
```

where reach, canonical positive, and false-promotion status are defined by the primary report.

### 2.2 Exact local reservation law

For scope `s`, root policy `delta_s`, root-bound schedule mass `M_s`, local ordinal `t`, and expanded
class weight `w(q_{s,t})`, the fixture recomputes:

```text
alpha_{s,t}
  = delta_s
    * w(q_{s,t})
    * M_s
    * (76614/126025)
    / (t+1)^2.
```

The source of the coefficient and exact formula is
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:20-52` and
`:3998-4015`. The registry expansion gives

```text
max_q w(q) = 3/20.
```

The fixture therefore checks the all-path envelope:

```text
sum_t alpha_{s,t} < delta_s * M_s * 3/20.
```

For an exact family, it checks:

```text
family_envelope
  = sum_s delta_s * M_s * 3/20,
```

with a strict inequality from the certified downward Basel coefficient. For the three-member
mass-one common-delta fixture, the mathematical envelope is below `(9/20) * delta`; at the live
policy value it is below `9/2000`.

This is not calculated by counting roots. Every term is re-derived from the live root, registry,
expanded class map, schedule mass, executed ordinal sequence, and exact rational coefficient.

### 2.3 Relationship to actual reservations

The fixture records both:

- the exact sum of reservations that actually occurred on the represented path; and
- the conservative all-path envelope permitted by the bound root/schedule configuration.

Neither field alone creates family authority. The exact path sum may be small after the fact; the
all-path envelope may be mathematically valid; but the family claim remains ineligible unless
membership, chronology, current heads, local theorem standing, and assumptions are canonically
verified.

---

## 3. Common fixture ingredients

The implementation team may choose any concrete serialization. The test must nevertheless generate
these semantic inputs rather than copy expected outputs:

| Ingredient | Required property |
| --- | --- |
| three design problems | distinct problem IDs and distinct content bindings |
| three canonical scopes | derived by the live N9 function, not supplied as trusted markers |
| three roots | current canonical roots binding policy delta, registry, and schedule profile |
| local histories | at least one result-bearing local execution per reached member, with known class and ordinal |
| family order | committed before family outcomes |
| member plans | either completely fixed before outcomes or explicitly adaptive |
| terminal chronology | earlier refusals/voids/negatives/disputes retained; stop after first valid positive |
| maintained assumptions | member obligation basis plus validator soundness, carried into the family statement |
| source identity | exact repository, deployment, registry, and theorem versions |

The fixture may use synthetic closed-construction evidence. It must not claim empirical calibration
or a real governed promotion.

---

## 4. Positive future-conformance fixture

### 4.1 Trace

Use a fixed exact family with three distinct problems:

```text
member A -> canonical scope A -> completed non-positive terminal
member B -> canonical scope B -> result-bearing non-positive terminal
member C -> canonical scope C -> canonical positive terminal
stop
```

The local histories may use different prospectively fixed plans. The fixed-family theorem does not
require identical implementation bytes; it requires the complete plan vector to be visible before
family outcomes.

### 4.2 Required assertions

A future owner implementation passes this fixture only if it:

1. derives A/B/C scopes through the real N9 path;
2. validates each root and current-head receipt through the real confidence ledger;
3. recomputes every local ordinal and expanded class weight;
4. recomputes each exact rational reservation from the root-bound schedule;
5. verifies the `started` reservation was durably appended before owner invocation
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1356-1382`);
6. verifies every local theorem profile and its protected error event;
7. derives each scope's exact path sum and all-path envelope;
8. composes the exact family envelope without substituting root policy ceilings;
9. proves that A/B/C are the complete registered family and no unregistered positive exists;
10. reconstructs chronology, retains earlier terminals, and verifies stop after C;
11. verifies the fixed member-plan vector was prospective;
12. projects all maintained assumptions and limitations; and
13. recomputes the aggregate output from live source rather than accepting a supplied green record.

### 4.3 Pinned-baseline expectation

At `f5c9103...`, the mathematical parts can be independently calculated, but no live owner object
can satisfy assertions 9–13 as one canonical family projection. The positive fixture must therefore
refuse at the family-claim boundary
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

That refusal is a successful baseline result. It does not imply the local ledgers or corrected
arithmetic are wrong.

---

## 5. Mandatory structural negative control

### 5.1 Trace

Execute the ordinary local path:

```text
problem A -> fresh root-level policy A -> local ordinal-zero reservation A
problem B -> fresh root-level policy B -> local ordinal-zero reservation B
problem C -> fresh root-level policy C -> local ordinal-zero reservation C
stop on first positive
```

The exact wording matters: every fresh scope receives a fresh **root-level policy and schedule
series**; every ordinal-zero check receives its own exact **reservation**, not the whole policy
ceiling.

### 5.2 Expected evidence

The control must demonstrate:

- three distinct canonical scope identities;
- three canonical roots;
- three local ordinal-zero reservations computed from their classes and masses;
- exact local receipts that remain valid independently;
- the corrected all-path scope and family envelopes; and
- absence of a canonical family relation, chronology verifier, and aggregate projection
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 5.3 Required red property

A public family-risk claim must remain ineligible because exact family custody is missing. The red
reason is structural:

```text
local accounting is valid
mathematical cross-scope envelope is derivable
canonical family membership/currentness/chronology is not attested
public family statement is unavailable
```

The control must **not** infer a probability by counting root `budget_delta` fields. Changing only a
root display or adding a family-shaped document cannot turn it green.

### 5.4 Mandatory falsifier standing

The original mandatory trace remains possible at the pinned baseline. It is unblocked as a family-
custody trace: N9 and the local ledger do not prohibit opening the next canonical problem scope.
The corrected arithmetic removes the former inflated probability interpretation, but it does not
create the missing family owner chain
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 6. Terminal and allocation-disposition fixtures

These are semantic test categories, not frozen enum values.

| Earlier state | Required family behavior | Required accounting behavior |
| --- | --- | --- |
| preflight refusal before owner execution | retain and advance only under declared rule | zero local spend; no replacement member appears |
| deterministic infrastructure failure before result-bearing exposure | retry only the same member under prospective rule | no fresh family member or root substitution |
| owner refusal/error after start | retain result-bearing terminal | reservation remains burned |
| result-bearing void | retain and prohibit substitution | existing reservations remain visible |
| material dispute | halt | no later family authority while unresolved |
| completed negative/refusal | advance | prior terminal remains in projection |
| valid positive | stop | later members recorded unreached |
| unreached member | no execution | no fabricated reservation |

No-refund is the default conservative fixture posture. A future recycling design must carry a
separate theorem and its own red/green pair.

---

## 7. Metamorphic and property-removal controls

The concrete test framework may choose identifiers. It must cover these property classes.

| Mutation class | Required failure property |
| --- | --- |
| omit an earlier terminal | family chronology incomplete |
| substitute a new problem after an unfavorable result | family membership changed after outcome |
| supply another member's scope | live N9 derivation mismatch |
| duplicate a problem or scope | family identity not one-to-one |
| keep the final arithmetic but change a root-bound schedule | source/root version mismatch |
| alter an expanded class weight | registry recomputation mismatch |
| hide exact overspend behind decimals | rational recomputation failure |
| keep reservation fields but move append after owner invocation | pre-execution enforcement removed |
| supply a stale receipt while a newer head exists | currentness failure |
| omit one member's maintained assumption | conditionality incomplete |
| add an unregistered positive scope | family completeness failure |
| hand-author a green aggregate record | live-source recomputation failure |
| collapse all problems into one scope | canonical identity weakened |
| create a second mutable family ledger | duplicate owner |
| change a later member plan after an earlier outcome | adaptive theorem required |
| multiply e-values without an admitted merger theorem | local/family theorem unavailable |

The P29 control is explicit: remove the real property while retaining every marker. For example,
leave all reservation-shaped fields present but move the durable append until after owner execution.
The fixture must fail. The current append ordering is visible at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1356-1382`.

---

## 8. Adaptive fixture pair

### 8.1 Negative adaptive control

Member A's revealed result selects member B's implementation or evaluator. The supplied local
theorem covers only a procedure fixed independently of A. Exact schedule arithmetic remains valid,
but family numeric eligibility must refuse because the actual selector is outside the theorem.

A timestamp saying the new plan was recorded before B's output is insufficient. The selected
procedure and allocation must be measurable with respect to the declared prior-history sigma-field,
and the theorem must be valid for that selected procedure.

### 8.2 Future positive criterion

A positive adaptive test is not executable at the pinned baseline. A future candidate must provide
a separately specified theorem satisfying the filtered-space premises in the primary report. Its
controlled event, filtration, selector, assumptions, owner profile, verifier, source binding, and
falsifier must be independently auditable.

An unqualified label such as “anytime-valid,” “uniform,” or “selection-aware” cannot make the test
green.

---

## 9. Semantic handoff invariants

A later owner-design task must preserve all of the following while remaining free to choose the
actual contract shape.

### 9.1 Prospective relation

Before family outcomes, independently visible evidence must bind:

- the exact family event and purpose;
- ordered membership and canonical problem bindings;
- root/registry/schedule/source identities;
- fixed plans or adaptive posture;
- stopping, dispute, retry, substitution, and allocation-disposition rules;
- local theorem references and obligation bases; and
- maintained assumptions.

This relation is not authority by itself.

### 9.2 Recomputed aggregate projection

The existing confidence owner must recompute:

- live scopes from problem bindings;
- canonical roots and current heads;
- exact reservations and all-path envelopes;
- complete chronology and all family-relevant positives;
- fixed/adaptive theorem standing;
- assumptions and limitations; and
- the bounded family statement plus currentness.

The projection must not own a second mutable head, risk-spend chain, registry, local ordinal, local
proof verifier, replacement risk scope, or promotion decision.

### 9.3 Unresolved choices

The following remain explicitly unresolved:

- record and field names;
- package/module placement;
- wire and database encoding;
- content-derived identity format;
- terminal/refusal vocabulary;
- correction, suspension, and reissue lifecycle;
- public/API shape; and
- exact test IDs and error codes.

An implementation team cannot copy this file verbatim and claim that research appointed a schema.

---

## 10. Pinned-baseline expected result

A behavioral verifier at `f5c9103...` should be able to establish:

| Property | Expected standing |
| --- | --- |
| per-problem scope derivation | implemented |
| exact local schedule reservation | implemented |
| durable reservation before owner execution | implemented |
| exact receipt recomputation | implemented |
| all-path local envelope below `delta_s * mass_s * 3/20` | mathematically derivable |
| exact three-scope mass-one envelope below `(9/20) * delta` | mathematically derivable for the declared fixture |
| canonical family declaration | missing |
| chronology/current-head aggregate verifier | missing |
| public family projection | missing |
| useful adaptive selector theorem | missing |
| mandatory family-custody trace blocked | false |
| numeric family claim eligible | false |

The missing capability is recorded at
`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`.

This fixture package proves no real positive statistical power. It preserves the one-owner,
pre-execution, exact-rational, property-removal, and bounded-passage requirements while refusing to
freeze a future wire contract.