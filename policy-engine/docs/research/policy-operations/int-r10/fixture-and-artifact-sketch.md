---
title: INT-R10 — Family Composition Artifact and Fixture Sketch
status: delivered
kind: deep-research-support
research_task: INT-R10
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-family-wise-risk-composition
repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
authoritative_for:
  - research-level semantic requirements for a confidence-ledger-owned cross-scope composition projection
  - executable fixture requirements for the INT-R10 mandatory falsifier and negative controls
  - handoff constraints preserving canonical per-problem scope identity and preventing a second confidence ledger
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical schema name or package placement
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - assertion that the sketched artifacts exist in the current repository
  - substitution for live-source recomputation
research_only: true
---

# INT-R10 — Family Composition Artifact and Fixture Sketch

## 1. Standing and non-duplication rule

This document is a **research sketch**, not a schema decision. Names are placeholders. A later
implementation may choose different names or serialization while preserving the semantic
properties.

The canonical owner to extend is the existing confidence ledger in
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py`. The sketch does **not** introduce:

- a second risk ledger;
- a second mutable head;
- a family execution ordinal that competes with each scope’s canonical ordinal;
- a replacement `ConfidenceRiskBudgetScope`;
- a parent scope whose identity subsumes the three design-problem scopes;
- a second promotion gate;
- a new status lattice; or
- an author-written proof record accepted without recomputation.

The family object is a **composition declaration plus a recomputed projection over existing
canonical roots and receipts**. It constrains how much top-level risk each member scope may use for
one named family claim. The per-problem scope remains the unit that owns local ordinals, local
checks, local owner invocation, and local event history.

The present runtime does not implement the sketch. At the pinned baseline it must fail closed with
an equivalent of `family_composition_unavailable`, not simulate success from Markdown.

## 2. Controlled event and theorem interface

For an ordered family `F = (1, ..., m)`, define:

- `R_i`: slot `i` is reached under the prospectively committed stopping rule;
- `P_i`: slot `i` produces a canonical positive promotion terminal;
- `W_i`: that promotion is false with respect to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`: reached slot `i` falsely promotes; and
- `V_F = union_i V_i`: at least one reached family member falsely promotes.

With stop on the first canonical positive, `V_F` is exactly the event that the family’s reported
first promotion is false. The family theorem interface is:

```text
local premise i:
  P(V_i | A_F) <= alpha_i

composition premise:
  alpha_i >= 0 for every i
  sum_i alpha_i <= delta_F

conclusion:
  P(V_F | A_F) <= delta_F
```

No common null, common estimand, exchangeability, or independence is needed for this inequality.
Those properties may improve power under other procedures, but they are not premises of the
minimal theorem.

For adaptive continuation, the local premise must strengthen to:

```text
P(V_i | H_{i-1}, R_i, A_F) <= alpha_i almost surely,
```

where `H_{i-1}` includes every earlier reveal, result, repair decision, source change, model or
prompt change, adjudication, and other fact used to select the slot-i implementation. An equivalent
uniform theorem over all implementations selectable by the permitted repair policy is also
acceptable. A fixed-implementation theorem reused after outcome-dependent repair is not.

## 3. Placeholder artifact: `FamilyRiskCompositionDeclaration`

### 3.1 Semantic purpose

A declaration binds the exact union event and its cap vector before any family member’s
result-bearing owner execution. It is an input to the canonical confidence ledger, not a receipt
from INT-R9 and not authority by itself.

### 3.2 Illustrative shape

```yaml
schema_version: policyos.runtime.confidence_ledger.family_composition.research.v0
family_id: confidence-risk-family:sha256:<content hash>
family_purpose: first_governed_promotion
family_owner_ref: polisyos.runtime.quality.confidence_ledger
consumer_protocol_ref: policy-operations/INT-R9:<content hash>
source_repository_commit: <exact commit>
registry_content_hash: sha256:<hash>
family_delta:
  numerator: 1
  denominator: 100
composition_theorem_profile: weighted_union_v1
allocation_timing: before_any_member_result_bearing_execution
revision_policy:
  kind: fixed_revision_only
  implementation_revision: sha256:<hash>
  adaptive_owner_theorem_ref: null
stopping_rule:
  kind: stop_on_first_canonical_positive
  halt_on_dispute: true
  no_substitution: true
members:
  - slot_id: slot-1
    order: 1
    design_problem_id: problem-A
    problem_content_hash: sha256:<hash-A>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-A>
    local_cap: {numerator: 1, denominator: 300}
  - slot_id: slot-2
    order: 2
    design_problem_id: problem-B
    problem_content_hash: sha256:<hash-B>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-B>
    local_cap: {numerator: 1, denominator: 300}
  - slot_id: slot-3
    order: 3
    design_problem_id: problem-C
    problem_content_hash: sha256:<hash-C>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-C>
    local_cap: {numerator: 1, denominator: 300}
maintained_assumptions:
  local:
    - obligation_completeness
    - validator_soundness
  family:
    - exact_family_membership
    - prospective_allocation
    - canonical_scope_derivation
    - local_cap_enforcement
    - no_outcome_dependent_refund
    - live_source_recomputation
    - fixed_revision
controlled_event:
  any_reached_member_falsely_promotes_under_stop_on_first_positive
authoritative_for:
  - declaring the exact family and prospective cap vector proposed for canonical verification
may_not_use_for:
  - proof that any local certificate is valid
  - proof that the family bound holds
  - promotion authority
  - production capability
  - replacement of a canonical per-problem scope
  - creation of a second risk ledger
research_only: true
```

### 3.3 Binding requirements

A conforming declaration must satisfy all of the following before it can be accepted as an input:

1. `family_id` is recomputed from the canonical serialization of the complete declaration,
   excluding only the identity field itself.
2. `family_delta` and every `local_cap` are exact nonnegative rationals. Floating-point values are
   forbidden in the authority path.
3. `sum(local_cap) <= family_delta` exactly.
4. Member order is total and unique.
5. `slot_id`, `design_problem_id`, problem content hash, and canonical scope ID are unique.
6. Each scope ID is recomputed by the live canonical
   `confidence_risk_scope_for_problem()` path from the exact problem binding. A supplied ID is not
   trusted.
7. The declaration is committed before the earliest result-bearing family execution, under the
   Custody Time Model’s relevant transaction/visibility evidence. A local timestamp is not enough.
8. The consumer protocol, repository commit, registry hash, stopping rule, and revision policy are
   content-bound.
9. The controlled event is explicit. “Shared cumulative confidence” is not a valid event
   definition.
10. The declaration cannot authorize a local probabilistic owner that the registry refuses.

### 3.4 Local-cap enforcement requirement

The family theorem requires each local false-promotion bound to be `alpha_i`, not merely the
registry default `delta`. Before any probabilistic owner call in member scope `i`, the canonical
ledger must therefore enforce an effective top-level ceiling no greater than `alpha_i` for the
family purpose.

This requirement may later be implemented in more than one semantically equivalent way—for
example, a root-bound effective delta or an owner-bound ceiling over risk reservations—but it must
have these observable properties:

- the cap is bound before the first `started` event;
- every within-scope schedule allocation is proved against that cap;
- `prior_spend + next_spend > local_cap` fails before owner execution;
- a receipt exposes the cap and its family binding;
- a verifier recomputes the cap from the family declaration and live source; and
- the ordinary per-problem `scope_id` is unchanged.

Checking after execution that actual spend happened to be small is insufficient. A false positive
could already have been admitted under a larger nominal threshold. The cap must constrain the
owner before result-bearing execution.

## 4. Placeholder artifact: `FamilyRiskCompositionReceipt`

### 4.1 Semantic purpose

The receipt is a canonical confidence-ledger projection proving that the declared family
composition was enforced across the named per-problem scopes. It is not independently authored by
INT-R9.

### 4.2 Illustrative shape

```yaml
schema_version: policyos.runtime.confidence_ledger.family_receipt.research.v0
projection_scope: cross_scope_family_risk_composition
family_id: confidence-risk-family:sha256:<hash>
family_declaration_ref: sha256:<CAS ref>
family_delta: {numerator: 1, denominator: 100}
composition_theorem_profile: weighted_union_v1
source_repository_commit: <exact commit>
deployment_identity: policy-engine-deployment:sha256:<hash>
registry_content_hash: sha256:<hash>
revision_policy_result:
  kind: fixed_revision_only
  valid_for_numeric_composition: true
members:
  - slot_id: slot-1
    order: 1
    design_problem_id: problem-A
    canonical_scope_id: confidence-risk-scope:sha256:<scope-A>
    local_cap: {numerator: 1, denominator: 300}
    ledger_root_ref: sha256:<root-A>
    ledger_receipt_ref: sha256:<receipt-A>
    ledger_receipt_id: confidence-ledger:sha256:<id-A>
    head_event_ref: sha256:<head-A>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: refused
    cap_disposition: retired_no_refund
  - slot_id: slot-2
    order: 2
    design_problem_id: problem-B
    canonical_scope_id: confidence-risk-scope:sha256:<scope-B>
    local_cap: {numerator: 1, denominator: 300}
    ledger_root_ref: sha256:<root-B>
    ledger_receipt_ref: sha256:<receipt-B>
    ledger_receipt_id: confidence-ledger:sha256:<id-B>
    head_event_ref: sha256:<head-B>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: void_result_bearing
    cap_disposition: retired_no_refund
  - slot_id: slot-3
    order: 3
    design_problem_id: problem-C
    canonical_scope_id: confidence-risk-scope:sha256:<scope-C>
    local_cap: {numerator: 1, denominator: 300}
    ledger_root_ref: sha256:<root-C>
    ledger_receipt_ref: sha256:<receipt-C>
    ledger_receipt_id: confidence-ledger:sha256:<id-C>
    head_event_ref: sha256:<head-C>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: promoted
    cap_disposition: terminal_stop
aggregate:
  allocated_cap: {numerator: 1, denominator: 100}
  allocated_cap_within_family_delta: true
  duplicate_scope_count: 0
  unregistered_scope_count: 0
  omitted_prior_member_count: 0
  outcome_dependent_refund_detected: false
  local_cap_violation_count: 0
  canonical_scope_derivation_valid: true
  live_receipts_valid: true
conditionality_clause: >-
  P(any reached member falsely promotes under the declared stop-on-first-positive
  family | maintained assumptions) <= family_delta; this is conditional on every
  member's declared obligation completeness and validator soundness plus the named
  family composition assumptions.
maintained_assumptions:
  - obligation_completeness_by_member
  - validator_soundness_by_member
  - exact_family_membership
  - prospective_allocation
  - canonical_scope_derivation
  - local_cap_enforcement
  - no_outcome_dependent_refund
  - fixed_revision
within_family_budget: true
eligible_for_family_risk_claim: true
refusal_code: null
projection_hash: sha256:<recomputed hash>
authoritative_for:
  - canonical recomputation of the named family cap composition over the bound live per-problem receipts
may_not_use_for:
  - proof of open-world obligation completeness
  - proof of validator soundness
  - population generalization
  - legal compliance
  - institutional competence
  - production readiness
  - authority beyond the named family, revisions, cases, evaluator, and assumptions
research_only: true
```

### 4.3 What the receipt must not contain

A conforming family projection must not acquire independent authority machinery that duplicates
the ledger. In particular it must not contain:

- an independently mutable `family_head`;
- an execution ordinal used to price local checks;
- an independent risk-spend event chain;
- an independently configurable delta registry;
- a second owner/verifier route for local certificates;
- a family scope that replaces the canonical scope IDs; or
- an author-supplied boolean accepted without recomputation.

A projection hash, family declaration reference, and member receipt references are permitted
because they bind and summarize existing authority; they do not create a second accounting owner.

## 5. Canonical recomputation algorithm

The following is semantic pseudocode. It is not implementation authorization.

```text
INPUT:
  declaration D
  exact repository/deployment identity
  live registry G
  live N9 problem bindings B[1..m]
  canonical ledger roots and current-head receipts L[1..m]
  consumer attempt chronology C

1. Validate D's schema and exact rational values.
2. Recompute family_id from canonical D.
3. Require D.registry_content_hash == hash(G).
4. Require D was independently visible before every result-bearing member execution.
5. Require member orders are exactly 1..m with no duplicates.
6. For each i:
     expected_scope_i = live confidence_risk_scope_for_problem(B[i]).scope_id
     require expected_scope_i == D.members[i].canonical_scope_id
     require design_problem_id and problem hash match B[i]
7. Require all expected_scope_i are distinct.
8. Compute allocated = exact_sum(D.members[i].local_cap).
9. Require allocated <= D.family_delta.
10. For each i:
      validate the canonical root and current-head receipt through the existing ledger
      require receipt.scope_id == expected_scope_i
      require receipt's effective family cap == D.members[i].local_cap
      require every probabilistic reservation was made under that cap
      require total_spend <= local_cap
      require receipt conditionality and maintained assumptions are present
11. Recompute attempt chronology from live protocol and ledger artifacts:
      no later member precedes unresolved earlier member
      stop after first canonical positive
      disputes halt
      every earlier refused/void/completed member remains in the projection
      no positive comes from an unregistered scope
12. Apply cap-disposition rules without refund or reallocation.
13. If revisions differ between members:
      require D.revision_policy permits adaptation
      require a canonical owner theorem proving history-conditional or uniform local validity
      otherwise set eligible_for_family_risk_claim = false and
      refusal_code = adaptive_validity_unproved
14. Recompute the family projection and projection_hash from live source and artifacts.
15. Emit eligible_for_family_risk_claim only if every requirement is true.
```

Step 10 is the canonical-owner seam. The family projection cannot infer a local `alpha_i` guarantee
from a Markdown declaration. The ledger must have constrained the local scope before execution and
must expose enough evidence for recomputation.

## 6. Attempt and cap-disposition semantics

A fixed cap vector prevents bypass only when every terminal has a defined effect.

| Member state | Result-bearing information exposed? | Local risk treatment | Sequence treatment | May its cap move to another scope? |
| --- | --- | --- | --- | --- |
| `preflight_refused` before owner execution | No owner result; refusal itself may be informative | Actual spend remains zero, but the member’s assigned cap is retired for this family version | Publish/retain the refusal; next committed member may be reached if protocol allows | **No** |
| Deterministic infrastructure failure proved before any result-bearing execution under a prospective retry rule | No | Same member, same scope, same cap may retry; no new cap is created | Retry does not advance or replace the slot | **No** |
| `started` then owner refusal/error | Yes or potentially yes | Reserved spend is burned; all unused member cap is retired | Retain terminal; next member may be reached only under protocol | **No** |
| `void_result_bearing` | Yes or exposure cannot be excluded | Treat as a consumed member; spend burned and remaining cap retired | Retain void in chronology; no substitution | **No** |
| `disputed` | Yes | Spend burned and remaining cap held/retired; never made available elsewhere | Halt until resolved under the precommitted rule | **No** |
| `completed_negative` / grounded refusal | Yes | Spend burned; remaining cap retired | Advance to next committed member | **No** |
| `promoted` | Yes | Spend remains charged to its member cap | Stop family permanently | **No** |
| `unreached` after earlier positive | No | No execution; assigned cap expires unused when family terminates | Must remain recorded as unreached | **No** |

This conservative no-refund rule is a governance protocol, not the only mathematical possibility.
A more powerful recycling rule could be valid if prospectively specified and proved by the
canonical owner. The baseline has no such theorem. No-refund is therefore the minimal auditable
pattern that closes the bypass without importing a stronger claim.

## 7. Fixture package

### 7.1 Fixture execution boundary

The fixture is designed so another agent can implement it without a design question. It has two
layers:

1. **baseline characterization** at `978e6b958...`: the negative control must reproduce the current
   three-unaccounted-budget path and show that no family receipt exists;
2. **future conformance** after a canonical confidence-ledger extension: the positive control must
   show distinct scopes with constrained local caps and a recomputable family projection.

Passing a hand-built model of the fixture is not closure. The conformance validator must import
and execute the live canonical scope derivation and ledger paths, then corrupt the protected
property while preserving marker names to prove the gate is behavioral rather than form-based.

### 7.2 Common deterministic inputs

```yaml
fixture_id: INT-R10-FWC-001
family_delta: {numerator: 1, denominator: 100}
composition_profile: weighted_union_v1
stopping_rule: stop_on_first_canonical_positive
implementation_policy: fixed_revision_only
problems:
  - {slot: 1, design_problem_id: FWC-A, problem_hash: sha256:<A>}
  - {slot: 2, design_problem_id: FWC-B, problem_hash: sha256:<B>}
  - {slot: 3, design_problem_id: FWC-C, problem_hash: sha256:<C>}
expected_scope_relation:
  all_distinct: true
expected_scope_ordinals:
  first_started_check_in_each_scope: 0
maintained_assumptions:
  - obligation_completeness_by_member
  - validator_soundness_by_member
```

The three problem hashes and every owner certificate fixture must be generated deterministically
from committed fixture inputs. IDs must not be copied from the expected output.

### 7.3 Positive control — three scopes, one bounded family

**Precondition:** the canonical confidence ledger has an approved implementation of the semantic
requirements in this research. The current pinned baseline is expected to refuse this control.

**Declaration:**

```text
alpha_A = 1/300
alpha_B = 1/300
alpha_C = 1/300
alpha_A + alpha_B + alpha_C = 1/100 = delta_F
```

**Execution trace:**

```text
slot 1 -> problem FWC-A -> canonical scope A -> local ordinal 0
       -> terminal preflight_refused or completed_negative
       -> cap A retired, no refund
slot 2 -> problem FWC-B -> canonical scope B -> local ordinal 0
       -> terminal void_result_bearing or completed_negative
       -> cap B retired, no refund
slot 3 -> problem FWC-C -> canonical scope C -> local ordinal 0
       -> canonical positive terminal
       -> family stops
```

**Required assertions:**

1. `scope_A`, `scope_B`, and `scope_C` are recomputed by the live N9 scope function and are pairwise
   distinct.
2. Local ordinal zero in all three scopes is accepted; the fixture does not demand one shared
   ordinal.
3. Before any probabilistic owner call, each scope is constrained to its assigned `1/300` cap.
4. Every reserved probabilistic spend in a member scope is at most its local cap and the ledger
   refuses a reservation that would exceed it.
5. The exact allocated-cap sum is `1/100` using rational arithmetic.
6. Earlier refused, void, or negative terminals remain in the family projection.
7. No unused cap is transferred.
8. The positive scope is exactly the third registered scope.
9. The family receipt is recomputed from live source, live roots, current-head receipts, and the
   consumer chronology.
10. The receipt states the full conditionality; it does not say `P(false promotion) <= 1/100`
    without the declared obligation, validator, family, and revision assumptions.
11. Re-fetching and revalidating the receipt yields byte-equivalent semantic projection content.
12. Corrupting any member cap, scope binding, earlier terminal, or head reference makes validation
    fail.

**Expected result:**

```text
within_family_budget = true
eligible_for_family_risk_claim = true
allocated_cap = 1/100
controlled_event = any reached member falsely promotes
```

### 7.4 Mandatory negative control — three unaccounted top-level budgets

This is the audit’s mandatory falsifier and must execute against the live source.

**Trace:**

```text
slot 1 -> design-problem A -> scope A -> ordinal 0 -> top-level delta 1/100
slot 2 -> design-problem B -> scope B -> ordinal 0 -> top-level delta 1/100
slot 3 -> design-problem C -> scope C -> ordinal 0 -> top-level delta 1/100
stop on first positive
```

**Required baseline observations at `978e6b958...`:**

- all three scope IDs are distinct;
- each scope starts from its own empty event history and can assign ordinal zero;
- each root receives the registry’s top-level `1/100` delta;
- prior spend is summed only inside the current scope;
- no live family declaration, cap binding, cross-scope head, or family verifier blocks the trace.

**Required conformance result after a future extension:**

The same trace must go red before any family risk claim can be emitted. Acceptable equivalent
failure semantics include:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
unregistered_family_scope
```

A passing INT-R9 record or a sentence saying “same cumulative budget” must not override this
failure.

### 7.5 Additional negative and metamorphic controls

| ID | Mutation | Markers retained? | Required result |
| --- | --- | --- | --- |
| FWC-NEG-02 | After slot 1 refuses, add its unused cap to slot 2. | All three family/member names remain. | `outcome_dependent_refund_forbidden` or equivalent. |
| FWC-NEG-03 | Omit slot 1’s refusal from the projection and begin at slot 2. | Cap sum and slot labels remain. | `prior_member_history_incomplete`. |
| FWC-NEG-04 | Substitute problem D/scope D after seeing A fail. | Family count remains three. | `family_member_substitution`. |
| FWC-NEG-05 | Supply scope B under slot A while preserving `scope_id` field shape. | Yes. | `canonical_scope_derivation_mismatch`. |
| FWC-NEG-06 | Duplicate a scope or design-problem ID in two slots. | Yes. | `duplicate_family_scope` or `duplicate_design_problem`. |
| FWC-NEG-07 | Change caps after observing slot 1’s result but keep exact final sum `1/100`. | Yes. | `allocation_not_prospective`. |
| FWC-NEG-08 | Repair implementation between slots and provide no history-conditional/uniform theorem. | All cap arithmetic remains valid. | `adaptive_validity_unproved`; numeric family claim ineligible. |
| FWC-NEG-09 | Hand-author a family receipt whose booleans are green without loading live scope heads. | All schema markers remain. | `family_projection_recomputation_mismatch`. |
| FWC-NEG-10 | Use stale/non-current member receipt while a later head exists. | Yes. | `member_receipt_not_canonical_head`. |
| FWC-NEG-11 | Remove one member’s obligation-completeness assumption but leave `within_family_budget=true`. | Yes. | `family_conditionality_incomplete`. |
| FWC-NEG-12 | Use `delta/3` decimal approximations that sum slightly below `delta` by display rounding but above it exactly. | Yes. | Rational parser/total check rejects. |
| FWC-NEG-13 | Multiply three e-values without a registered conditional merger theorem and call the product family FWER evidence. | Yes. | `family_owner_theorem_unavailable`. |
| FWC-NEG-14 | Let a fourth unregistered scope produce the first positive while the three registered members remain negative. | Family receipt shape remains. | Positive is ineligible for the named family; `unregistered_positive_scope`. |
| FWC-NEG-15 | Keep one implementation hash field constant while changing executable/model/config bytes used in slot 3. | Yes. | Deployment/freeze mismatch; family numeric claim ineligible. |
| FWC-NEG-16 | Make all three design-problem IDs equal to force one scope. | The intended cap sum can look valid. | Reject identity weakening/problem-binding mismatch; no closure by collapsing distinct problems. |

### 7.6 Sharpness witness for the generic `3 * delta` result

The fixture package should include a pure mathematical witness independent of runtime behavior.
For `delta <= 1/3`, construct a probability space with disjoint events `E_A`, `E_B`, `E_C`, each
having probability `delta`. Define each local false-promotion event to be its corresponding event.
Then:

```text
P(E_A) = P(E_B) = P(E_C) = delta
P(E_A union E_B union E_C) = 3 * delta.
```

At the registry’s `delta = 1/100`, the family probability is exactly `3/100`. This proves that
`delta` cannot be recovered from the three local `delta` bounds without extra structure. The
witness is a theorem fixture, not a simulation estimate.

### 7.7 Adaptive-continuation fixture

Use two implementations `R0` and `R1` and an earlier outcome that selects which implementation is
used later:

```text
slot 1 runs R0;
if slot 1 refuses for reason X, choose repair R1 tailored to the revealed failure class;
slot 2 runs R1;
local certificate for R1 was proved only for R1 fixed independently of slot-1 history.
```

The cap arithmetic may still satisfy `sum alpha_i <= delta_F`. Nevertheless the family receipt
must refuse a numeric claim because the local theorem does not cover the selection of `R1` from
`H_1`. The positive control changes only one fact: it provides a canonical theorem reference whose
verifier proves conditional validity for the permitted repair rule. Then, and only then, the
adaptive family claim may become eligible.

This fixture prevents the family compositor from confusing arithmetic validity with statistical
validity.

## 8. Audit R1 acceptance matrix

| R1 requirement | Closure property in this sketch | Fixture evidence |
| --- | --- | --- |
| 1. Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)` is explicit. | Positive receipt and every rejection name the event. |
| 2. Relationship to canonical scopes | Exact member binding recomputed from each N9 problem binding; scope IDs remain distinct. | Positive assertion 1; scope-swap and collapse negatives. |
| 3. No fresh unaccounted top-level budgets | Prospective local caps sum exactly within `delta_F` and constrain each scope before execution. | Positive assertions 3–5; mandatory `3/100` negative. |
| 4. Earlier terminal effects | Refused, void, disputed, negative, positive, and unreached states have no-refund dispositions. | Trace plus FWC-NEG-02/03/14. |
| 5. Aggregate proof | Weighted union theorem plus exact rational cap total. | Positive receipt; sharpness witness. |
| 6. Adaptive continuation | Fixed revision is covered; adaptive repair requires history-conditional or uniform owner theorem, otherwise numeric refusal. | Adaptive fixture and FWC-NEG-08. |
| 7. Canonical owner reuse | Family result is a confidence-ledger projection, with no second head, ordinal, scope, or registry. | Author-written receipt and duplicate-owner structural review. |
| 8. Live reproducibility | Scope derivation, roots, receipts, heads, cap enforcement, chronology, and projection hash are recomputed from live source/artifacts. | FWC-NEG-09/10 and corruption probes. |

## 9. Handoff constraints

A later implementation task may choose package names and serialization only after consolidation
ratifies the research result. It must preserve these invariants:

1. **Per-problem scope identity is unchanged.** Three problems remain three canonical scope IDs.
2. **The confidence ledger remains the only risk-accounting owner.** The family projection is an
   extension/projection of that owner.
3. **Local caps bind before execution.** After-the-fact accounting is not protection.
4. **Exact arithmetic remains exact.** No float or display-decimal authority path.
5. **Within-scope Basel allocation remains inside the local cap.** The family device does not
   replace the local schedule.
6. **No refund by default.** A recycling rule needs its own prospective theorem.
7. **Adaptation is a theorem boundary.** Arithmetic alone cannot validate repaired implementations.
8. **INT-R1 conditionality remains visible.** Family composition does not prove the obligation
   world complete or validators sound.
9. **The verifier executes the real path.** A schema marker or author-written green record cannot
   pass.
10. **The candidate band remains usable.** Missing family composition blocks only the numeric
    cross-problem authority claim; it does not forbid exploratory or candidate work under declared
    limitation.

## 10. Current-baseline expected result

At `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`, a validator built from this specification should
report:

```yaml
family_composition_capability: missing
per_problem_scope_capability: implemented
within_scope_predictable_spending: implemented
cross_scope_cap_binding: missing
cross_scope_live_projection: missing
adaptive_owner_theorem: missing
mandatory_falsifier_blocked: false
single_delta_family_claim_eligible: false
honest_generic_three_slot_bound: min(1, 3 * delta)
registry_instance_at_delta_1_over_100: 3/100
```

That is a successful negative baseline. The research does not authorize a production claim until
the missing owner extension and its behavioral fixtures exist.