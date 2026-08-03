---
title: INT-R10 — Specification Conformance
status: delivered
kind: independent-audit
research_task: INT-R10
audited_branch: research/int-r10-family-wise-risk-composition
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
overall_verdict: NO_GO
research_only: true
authoritative_for:
  - independent grading of INT-R10 against the eight requirements in INT-R9 audit revision R1
  - verification of the mandatory three-fresh-scope falsifier
  - separation of research-level closure criteria from capability actually present at the pinned baseline
  - identification of conclusions safe for the parallel INT-R9 amendment and conclusions that must wait
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - assertion that all eight R1 requirements are closed
  - assertion that a live family-wise numeric projection exists
---

# INT-R10 — Specification Conformance

## 1. Baseline for grading

The controlling specification is R1 in
`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105`.
Its eight rows are acceptance evidence, not topics that can be marked complete because a document
mentions them. This audit therefore grades three different standings separately:

- **mathematical answer:** has the report established the claimed theorem?
- **research closure criterion:** has it stated what a valid owner extension would have to prove?
- **pinned capability:** can a verifier reproduce the property from live source and artifacts now?

INT-R10's §4.11 collapses those standings into one self-graded “Answer” column. That presentation is
too favorable. Several requirements are well answered as research while remaining intentionally
unimplemented; requirement 5 is mathematically wrong in its pinned-source application.

---

## 2. Requirement-by-requirement audit

### R1-1 — State the exact family event

**Requirement:** control the event that any slot in the precommitted stop-on-first-positive sequence
falsely promotes.

**Evidence in INT-R10:** §§1.2 and 4.2 define

```text
V_i = R_i ∩ P_i ∩ W_i
V_F = union_i V_i.
```

`R_i` is reach, `P_i` canonical positive, and `W_i` false relative to the declared obligation set
and maintained assumptions. Under stop on first positive, this is exactly false reported first
promotion. Earlier refused, void, disputed, and negative attempts remain in chronology; later
members are unreached.

**Independent grade:** **MET.**

**Preserve:** the event definition and the explicit distinction from efficacy, usefulness,
population inference, world completeness, or legal effect.

---

### R1-2 — Relate the family to canonical N9 problem scopes

**Requirement:** make the family-to-scope relationship explicit without weakening
`design-problem` identity.

**Evidence in INT-R10:** every member binds one real N9 problem binding and recomputed scope from
`confidence_risk_scope_for_problem()`; three fresh problem IDs remain three distinct scope IDs. The
family is described as a relation/projection over those scopes, never a replacement risk scope.

**Independent grade:** **MET.**

**Repository check:** `promotion_sequence.py:356-375` confirms the mapping. No proposal collapses
A/B/C into one scope.

---

### R1-3 — Prevent fresh unaccounted top-level budgets

**Requirement:** distinct `design_problem_id`s must not each obtain a fresh unaccounted top-level
budget while the protocol publishes one family delta.

**Evidence in INT-R10:** the report concedes that this is possible at the pinned baseline. It
proposes an effective local ceiling `alpha_i`, bound before execution, with exact aggregate cap at
most `delta_F` and a ledger-owned family projection.

**Independent findings:**

1. The baseline negative is honest: there is no live family declaration/projection.
2. The proposed future mechanism would prevent three *declared effective caps* from exceeding the
   family delta if implemented.
3. The report's premise that each root-level `budget_delta` represents a spendable local event cap
   of `delta` is false for the pinned owner. The exact schedule and class weights already impose a
   much smaller prospective envelope. Equal `1/300` recapping is therefore not established as the
   required remedy.

**Independent grade:** **PARTIALLY MET AS A CLOSURE CRITERION; NOT MET AS PINNED CAPABILITY.**

The requirement cannot be marked complete until the revised research composes the actual schedule
envelope and states what family relation, if any, remains missing after that arithmetic.

---

### R1-4 — Define non-bypassable effects of earlier terminals

**Requirement:** refused, void, disputed, and completed attempts must have a defined effect that
cannot be bypassed by opening the next scope.

**Evidence in INT-R10:** §4.6 and fixture §6 specify:

- preflight refusal retained; assigned cap retires;
- deterministic infrastructure retry limited to the same member/scope/cap;
- `started` refusal/error burns reserved risk;
- result-bearing void remains and receives no substitution/refund;
- dispute halts;
- completed negative advances with unused cap retired;
- valid positive stops; and
- later members are recorded unreached.

The recomputation algorithm requires complete chronology, no omitted prior member, no unregistered
positive, and no refund/substitution. Metamorphic negatives cover omitted terminals, scope swaps,
substitution, and cap movement.

**Independent grade:** **MET AS A RESEARCH-LEVEL GOVERNANCE RULE; NOT IMPLEMENTED.**

The report correctly labels no-refund as conservative governance, not a theorem that all recycling
is impossible. The pinned trace can still bypass because the family verifier does not exist; the
report does not hide that fact.

---

### R1-5 — Prove the aggregate bound under maintained assumptions

**Requirement:** show that aggregate allocation/composition satisfies the declared bound.

**Evidence in INT-R10:** Theorem A correctly proves weighted union from genuine local bounds and
prospective caps. §4.3 then claims `3 * delta` is sharp for three ordinary canonical scopes and
uses live `delta = 1/100` to publish `3/100` as the strongest generic baseline statement.

**Independent finding:** the abstract union theorem is correct, but the pinned-source corollary and
sharpness claim are not. The owner prices every probabilistic check by

```text
delta * obligation_weight(q_t) * mass * (76614/126025)/(t+1)^2
```

under one global local ordinal. With maximum expanded class weight `3/20` and mass at most one, one
scope's complete schedule envelope is strictly below `(3/20) * delta`; three scopes are strictly
below `(9/20) * delta`. The disjoint events of probability `delta` do not satisfy this stronger
source premise.

**Independent grade:** **NOT MET — BLOCKING.**

The report has proved a correct theorem from coarse local statements and then represented it as
sharp for a richer source. Requirement 5 remains open until exact live-owner composition is
re-derived.

---

### R1-6 — Cover adaptive continuation or narrow the claim

**Requirement:** keep the proof valid under permitted repair, or expressly exclude a numeric
adaptive theorem.

**Evidence in INT-R10:** the report does both:

- it correctly says the pinned registry has no theorem covering INT-R9's outcome-dependent repair,
  so the current numeric family claim is blocked; and
- it proposes Theorem B under history-conditional local validity and pathwise predictable caps.

**Independent findings:**

- The narrowed current claim is honest and sufficient to prevent misuse by INT-R9.
- Theorem B's displayed proof omits formal measurability of the cap, selected procedure, and reach
  indicator; its “or equivalent uniform/selection-aware theorem” disjunct is not characterized.
- The qualitative boundary is correct: adaptation is possible only if the local theorem covers the
  actual selector/history.

**Independent grade:** **MET FOR THE PINNED CLAIM NARROWING; MATERIAL REVISION REQUIRED FOR THE
CLAIMED ADAPTIVE THEOREM.**

INT-R9 may rely on “no numeric theorem for outcome-dependent repair today.” It may not cite the
present Theorem B as a completed formal result.

---

### R1-7 — Reuse the canonical owner

**Requirement:** extend the confidence ledger rather than creating a second ledger or weakening
scope identity.

**Evidence in INT-R10:** the proposed family object is a declaration plus recomputed projection
owned by `runtime.quality.confidence_ledger`. It is expressly forbidden from owning a mutable head,
local ordinal, independent registry, local verifier, replacement risk scope, or promotion decision.

**Independent grade:** **MET.**

No second ledger, parent risk scope, or collapsed problem identity is proposed. This is one of the
strongest parts of the deliverable.

---

### R1-8 — Reproduce composition from live source and artifacts

**Requirement:** a verifier must reproduce the composition from real scope derivation, roots,
heads, caps, chronology, assumptions, and source identities—not an author-written record.

**Evidence in INT-R10:** fixture §5 supplies a 14-step recomputation algorithm and negative controls
for hand-authored projection, stale head, cap-marker-without-enforcement, omitted history, source
identity, and plan drift. The report also states that the baseline must refuse because the family
cap/projection capability is missing.

**Independent findings:**

- The **negative baseline** is reproducible: three canonical scopes exist and no family projection
  exists.
- The **positive family composition** is not reproducible today because the proposed cap and
  projection paths do not exist.
- The proposed positive oracle embeds the incorrect `3/100` / `1/300` arithmetic from requirement
  5.
- The supporting sketch is detailed enough to behave as a de facto schema despite its disclaimer,
  before the corrected owner arithmetic and placement are ratified.
- Thirty-two GY-GAP2 citations point to frontmatter rather than the live substantive gap block.

**Independent grade:** **PARTIALLY MET AS A FUTURE BEHAVIORAL TEST SPECIFICATION; NOT MET AS LIVE
CAPABILITY.**

The self-graded matrix's word “Answer” must not be read as “closure evidence exists now.”

---

## 3. Summary matrix

| Requirement | Research answer | Pinned capability | Audit disposition |
| --- | --- | --- | --- |
| 1. Exact family event | complete | not capability-dependent | preserve |
| 2. Canonical scope relation | complete | implemented locally | preserve |
| 3. No fresh unaccounted budgets | proposed, but based on wrong source envelope | missing family owner | re-research exact schedule composition |
| 4. Earlier-terminal effects | complete governance rule | missing verifier | preserve as future criterion |
| 5. Aggregate proof | abstract theorem valid; pinned sharpness false | no family projection | **blocking** |
| 6. Adaptive continuation | honest current narrowing; theorem formalism incomplete | theorem unavailable | preserve narrowing; revise theorem |
| 7. Canonical owner reuse | complete | no extension yet | preserve |
| 8. Live reproduction | good negative/future fixture structure; wrong numeric oracle | positive verifier missing | partial; revise and implement later |

The report does **not** close all eight rows. It safely resolves 1, 2, 4, and 7 at research level;
it safely narrows 6 for the current runtime; 3 and 8 remain future-owner criteria; and 5 is
incorrect in its canonical-source application.

---

## 4. Mandatory falsifier

### 4.1 Baseline trace

The exact trace remains locally admissible:

```text
slot 1 -> problem A -> canonical scope A -> local ordinal 0
slot 2 -> problem B -> canonical scope B -> local ordinal 0
slot 3 -> problem C -> canonical scope C -> local ordinal 0
stop on first positive
```

Each scope has its own root and local history. No source object binds the three into a family or
emits a family projection. INT-R10 explicitly concedes this in §4.11 and fixture §10.

**Verdict:** the report is honest that the mandatory falsifier is **not blocked at the pinned
baseline**.

### 4.2 What the falsifier does not establish

The trace does not show that each ordinal-zero check consumes probability `delta`, and it does not
show that the three scopes' exact schedule envelopes total `3 * delta`. The report's negative
control conflates “three root-level delta policies exist” with “three false-promotion events can
each attain delta under the pinned owner.” That is the blocking mathematical defect.

A corrected fixture must separately test:

1. scope/root multiplicity;
2. exact per-check and all-path local schedule envelopes;
3. exact cross-scope composition of those envelopes;
4. absence/presence of a canonical family declaration and projection; and
5. adaptive-selection validity.

---

## 5. Findings

### INT-R10-E-001 — The self-graded R1 matrix overstates conformance

- **Severity:** `material`
- **Disposition:** replace the single “Answer” column with `research theorem`, `future closure
  criterion`, and `pinned capability` standing. Do not present proposed artifacts as evidence that
  requirements 3, 5, or 8 are closed.

### INT-R10-E-002 — Requirement 5 fails on the exact canonical source

- **Severity:** `blocking`
- **Disposition:** withdraw the live `3 * delta` sharpness/current corollary and recompute from the
  schedule/weight owner. This blocks consolidation regardless of the otherwise valid abstract
  theorem.

### INT-R10-E-003 — Requirement 6 is honestly narrowed for current INT-R9

- **Severity:** `commendation`
- **Disposition:** preserve the statement that outcome-dependent repair has no current numeric
  theorem. Revise, but do not rely on, Theorem B's formal extension.

### INT-R10-E-004 — Requirements 1, 2, 4, and 7 are strong

- **Severity:** `commendation`
- **Disposition:** preserve the exact event, unchanged scope identity, terminal/no-refund table, and
  single-owner constraints.

### INT-R10-E-005 — The mandatory falsifier is honestly reported as open

- **Severity:** `commendation`
- **Disposition:** preserve the negative capability standing, but replace its `3/100` probability
  oracle.

### INT-R10-E-006 — Positive live reproducibility remains unavailable

- **Severity:** `material`
- **Disposition:** requirement 8 can be stated as a future closure test, not claimed as present
  evidence. Correct the arithmetic and anchor set before handing the fixture to implementation.

---

## 6. What the parallel INT-R9 amendment may rely on

Safe now:

- the exact union event;
- distinct canonical scopes remain correct;
- there is no live canonical family declaration/projection;
- “one cumulative scope” must not be restored;
- current outcome-dependent repair has no numeric family theorem;
- all probability remains conditional on member obligation completeness and validator soundness;
- family composition belongs to the confidence-ledger/N11 owner; and
- missing numeric authority does not prohibit candidate-band work.

Must wait for corrected INT-R10:

- `3 * delta` or `3/100` as the sharp/strongest pinned-source bound;
- equal `1/300` caps as the necessary solution;
- the fixture failure `family_budget_exceeded: allocated=3/100` as a probability proof;
- Theorem B's present tower-property display;
- a claim that R1 requirements 3, 5, and 8 are closed; or
- any sentence saying a canonical single-`delta_F` projection exists now.

## 7. Conformance verdict

The deliverable answers the right owner-level question and contains a correct fixed-family theorem,
but it does not meet the specification as a whole. Requirement 5 is blocking, and the self-graded
matrix obscures the difference between a future design criterion and live evidence. Overall
specification verdict: **NO_GO pending mathematical amendment and re-verification**.