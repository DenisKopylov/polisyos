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
  - distinction between a prospectively fixed member-specific plan vector and outcome-dependent adaptive repair
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

This is a research sketch, not a final schema. A later implementation may rename every field while
preserving the semantic properties.

The canonical owner to extend is the existing confidence ledger in
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py`. The sketch does **not** introduce:

- a second risk ledger;
- a second mutable confidence head;
- a family execution ordinal that competes with each scope's canonical local ordinal;
- a replacement or weakened `ConfidenceRiskBudgetScope`;
- a parent risk scope containing the design-problem scopes;
- a second promotion gate or status lattice; or
- an author-written proof record accepted without live recomputation.

The family object is a **prospective composition declaration plus a recomputed projection over
existing canonical roots and receipts**. Each per-problem scope remains the owner of its local
ordinals, local checks, local owner invocation, and local append history.

At `978e6b958...`, this capability does not exist. A conforming validator must report an equivalent
of `family_composition_unavailable`; Markdown cannot simulate closure.

## 2. Controlled event and theorem interface

For ordered family `F = (1, ..., m)`:

- `R_i`: member `i` is reached under the declared stopping/dispute rules;
- `P_i`: member `i` emits a canonical positive promotion;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`; and
- `V_F = union_i V_i`.

With stop on first canonical positive, `V_F` is exactly the event that the reported first promotion
is false.

### 2.1 Prospectively fixed member-plan theorem interface

Before any family result-bearing execution, bind the exact family/order, cap vector, and complete
member-specific plan vector. Member plans may differ: member A can use revision `R_A`, member B
`R_B`, and member C `R_C`. What matters is that the complete vector is fixed before any family
outcome and that every local theorem covers its own exact member plan.

```text
local premise i:
  P(V_i | A_F) <= alpha_i

composition premises:
  alpha_i >= 0
  sum_i alpha_i <= delta_F

conclusion:
  P(V_F | A_F) <= delta_F
```

No common null, estimand, exchangeability, or independence is required.

### 2.2 Adaptive theorem interface

For outcome-dependent repair or member selection, let `H_{i-1}` contain the complete prior history.
A sufficient interface is:

```text
alpha_i(H_{i-1}) is chosen before member-i outcome;
alpha_i(H_{i-1}) >= 0;
sum_i alpha_i(H_{i-1}) <= delta_F pathwise;
P(P_i and W_i | H_{i-1}, R_i, A_F) <= alpha_i(H_{i-1}) almost surely.
```

An equivalent uniform or selection-aware theorem is acceptable. A theorem for a procedure fixed
independently of `H_{i-1}` is not sufficient when `H_{i-1}` selected that procedure.

## 3. Placeholder artifact: `FamilyRiskCompositionDeclaration`

### 3.1 Purpose

The declaration binds the exact union event, canonical member relation, local cap vector, and
member-plan vector before family outcomes. It is an input admitted by the confidence ledger, not a
receipt authored by INT-R9 and not authority by itself.

### 3.2 Illustrative shape

```yaml
schema_version: policyos.runtime.confidence_ledger.family_composition.research.v0
family_id: confidence-risk-family:sha256:<content hash>
family_purpose: first_governed_promotion
family_owner_ref: polisyos.runtime.quality.confidence_ledger
consumer_protocol_ref: policy-operations/INT-R9:sha256:<hash>
source_repository_commit: <exact commit>
deployment_identity: policy-engine-deployment:sha256:<hash>
registry_content_hash: sha256:<hash>
family_delta:
  numerator: 1
  denominator: 100
composition_theorem_profile: weighted_union_v1
allocation_timing: before_any_family_result_bearing_execution
member_plan_policy:
  kind: prospectively_fixed_member_plan
  plan_vector_hash: sha256:<hash of every member plan>
  adaptive_owner_theorem_ref: null
stopping_rule:
  kind: stop_on_first_canonical_positive
  halt_on_dispute: true
  no_substitution: true
members:
  - slot_id: slot-1
    order: 1
    design_problem_id: problem-A
    problem_content_hash: sha256:<problem-A>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-A>
    local_cap: {numerator: 1, denominator: 300}
    member_plan:
      implementation_revision_hash: sha256:<R-A>
      configuration_hash: sha256:<C-A>
      model_prompt_hash: sha256:<M-A>
      evidence_cutoff_ref: cutoff-A
      evaluator_hash: sha256:<E-A>
      obligation_set_ref: sha256:<O-A>
      local_theorem_profile_ref: theorem-A
  - slot_id: slot-2
    order: 2
    design_problem_id: problem-B
    problem_content_hash: sha256:<problem-B>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-B>
    local_cap: {numerator: 1, denominator: 300}
    member_plan:
      implementation_revision_hash: sha256:<R-B>
      configuration_hash: sha256:<C-B>
      model_prompt_hash: sha256:<M-B>
      evidence_cutoff_ref: cutoff-B
      evaluator_hash: sha256:<E-B>
      obligation_set_ref: sha256:<O-B>
      local_theorem_profile_ref: theorem-B
  - slot_id: slot-3
    order: 3
    design_problem_id: problem-C
    problem_content_hash: sha256:<problem-C>
    canonical_scope_id: confidence-risk-scope:sha256:<scope-C>
    local_cap: {numerator: 1, denominator: 300}
    member_plan:
      implementation_revision_hash: sha256:<R-C>
      configuration_hash: sha256:<C-C>
      model_prompt_hash: sha256:<M-C>
      evidence_cutoff_ref: cutoff-C
      evaluator_hash: sha256:<E-C>
      obligation_set_ref: sha256:<O-C>
      local_theorem_profile_ref: theorem-C
maintained_assumptions:
  local:
    - obligation_completeness_by_member
    - validator_soundness_by_member
  family:
    - exact_family_membership
    - prospective_allocation
    - canonical_scope_derivation
    - local_cap_enforcement
    - prospectively_fixed_member_plan
    - no_outcome_dependent_refund
    - live_source_recomputation
controlled_event:
  any_reached_member_falsely_promotes_under_stop_on_first_positive
authoritative_for:
  - declaring the exact family, cap vector, and member-plan vector proposed for canonical verification
may_not_use_for:
  - proof that any local certificate is valid
  - proof that the family bound holds
  - promotion authority
  - production capability
  - replacement of a canonical per-problem scope
  - creation of a second confidence ledger
research_only: true
```

### 3.3 Declaration acceptance requirements

A canonical implementation must verify at least:

1. `family_id` and `plan_vector_hash` are recomputed from canonical serialization.
2. `family_delta` and every `local_cap` are exact nonnegative rationals; floats are forbidden in the
   authority path.
3. Exact `sum(local_cap) <= family_delta`.
4. Member order is total and unique.
5. Slot IDs, design-problem IDs, problem hashes, and canonical scope IDs are unique and complete.
6. Every scope ID is recomputed through the live canonical N9 scope derivation from the exact
   problem binding; supplied IDs are not trusted.
7. The declaration and complete member-plan vector were independently visible before the earliest
   family result-bearing execution. A local timestamp is insufficient.
8. Repository/deployment/registry/theorem/stopping/terminal rules are content-bound.
9. The controlled event is explicit; “shared cumulative confidence” is not an event definition.
10. Every local theorem profile is admitted by the existing owner; the declaration cannot override
    a local `owner_theorem_unavailable` refusal.
11. If `member_plan_policy.kind` is adaptive, a canonical adaptive theorem reference and verifier
    must exist; otherwise the numeric family claim is ineligible.

### 3.4 Local-cap enforcement requirement

A declaration does not itself reduce a member's false-promotion bound. Before any probabilistic
owner call in member scope `i`, the canonical ledger must enforce an effective top-level ceiling no
greater than `alpha_i`.

Observable properties:

- cap binding precedes the first result-bearing `started` event;
- the local schedule uses the effective ceiling rather than the ordinary full registry delta;
- `prior_local_spend + next_reservation > local_cap` fails before owner execution;
- local receipts expose the effective cap and family relation;
- a verifier recomputes the cap from the declaration and live source; and
- the canonical per-problem `scope_id` remains unchanged.

Checking after execution that actual spend happened to be small is insufficient. The procedure may
already have executed under a larger nominal error threshold.

## 4. Placeholder artifact: `FamilyRiskCompositionProjection`

### 4.1 Purpose

The projection is a canonical confidence-ledger recomputation proving that the named family
composition was enforced over the bound live scopes. It is not independently authored by INT-R9.

### 4.2 Illustrative shape

```yaml
schema_version: policyos.runtime.confidence_ledger.family_projection.research.v0
projection_scope: cross_scope_family_risk_composition
family_id: confidence-risk-family:sha256:<hash>
family_declaration_ref: sha256:<CAS ref>
family_delta: {numerator: 1, denominator: 100}
composition_theorem_profile: weighted_union_v1
source_repository_commit: <exact commit>
deployment_identity: policy-engine-deployment:sha256:<hash>
registry_content_hash: sha256:<hash>
member_plan_result:
  kind: prospectively_fixed_member_plan
  plan_vector_hash: sha256:<hash>
  valid_for_numeric_composition: true
members:
  - slot_id: slot-1
    order: 1
    design_problem_id: problem-A
    canonical_scope_id: confidence-risk-scope:sha256:<scope-A>
    local_cap: {numerator: 1, denominator: 300}
    member_plan_hash: sha256:<plan-A>
    ledger_root_ref: sha256:<root-A>
    ledger_receipt_ref: sha256:<receipt-A>
    head_event_ref: sha256:<head-A>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: refused
    cap_disposition: retired_no_refund
  - slot_id: slot-2
    order: 2
    design_problem_id: problem-B
    canonical_scope_id: confidence-risk-scope:sha256:<scope-B>
    local_cap: {numerator: 1, denominator: 300}
    member_plan_hash: sha256:<plan-B>
    ledger_root_ref: sha256:<root-B>
    ledger_receipt_ref: sha256:<receipt-B>
    head_event_ref: sha256:<head-B>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: void_result_bearing
    cap_disposition: retired_no_refund
  - slot_id: slot-3
    order: 3
    design_problem_id: problem-C
    canonical_scope_id: confidence-risk-scope:sha256:<scope-C>
    local_cap: {numerator: 1, denominator: 300}
    member_plan_hash: sha256:<plan-C>
    ledger_root_ref: sha256:<root-C>
    ledger_receipt_ref: sha256:<receipt-C>
    head_event_ref: sha256:<head-C>
    local_total_spend: {numerator: <n>, denominator: <d>}
    terminal: promoted
    cap_disposition: terminal_stop
aggregate:
  allocated_cap: {numerator: 1, denominator: 100}
  actual_spend: {numerator: <n>, denominator: <d>}
  allocated_cap_within_family_delta: true
  actual_spend_within_family_delta: true
  duplicate_scope_count: 0
  unregistered_scope_count: 0
  omitted_prior_member_count: 0
  outcome_dependent_refund_detected: false
  local_cap_violation_count: 0
  canonical_scope_derivation_valid: true
  live_receipts_valid: true
conditionality_clause: >-
  P(any reached member falsely promotes under the exact family and member-plan
  vector | maintained assumptions) <= family_delta; this is conditional on every
  member's declared obligation completeness and validator soundness plus the named
  family composition assumptions.
maintained_assumptions:
  - obligation_completeness_by_member
  - validator_soundness_by_member
  - exact_family_membership
  - prospective_allocation
  - canonical_scope_derivation
  - local_cap_enforcement
  - prospectively_fixed_member_plan
  - no_outcome_dependent_refund
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
  - authority beyond the named family, member plans, cases, evaluators, and assumptions
research_only: true
```

### 4.3 What the projection must not own

It must not acquire:

- an independently mutable `family_head`;
- an execution ordinal used to price local checks;
- an independent risk-spend event chain;
- an independently configurable delta registry;
- a second owner/verifier route for local certificates;
- a family risk scope replacing the canonical member scope IDs; or
- an author-supplied boolean accepted without recomputation.

A content hash, declaration reference, member receipt references, and derived aggregate are
permitted because they bind and summarize existing authority rather than creating a peer owner.

## 5. Canonical recomputation algorithm

Semantic pseudocode only:

```text
INPUT:
  declaration D
  exact repository/deployment identity
  live registry G
  live N9 problem bindings B[1..m]
  canonical roots/current-head receipts L[1..m]
  consumer chronology C

1. Validate D and all exact rationals.
2. Recompute family_id and member-plan-vector hash.
3. Require D.registry_content_hash == hash(G).
4. Require D and the complete fixed member-plan vector were visible before every
   family result-bearing execution.
5. Require member order exactly 1..m with no duplicates or omissions.
6. For each i:
     expected_scope_i = live confidence_risk_scope_for_problem(B[i]).scope_id
     require expected_scope_i == D.members[i].canonical_scope_id
     require design_problem_id and problem hash match B[i]
     recompute member_plan_hash
7. Require all expected_scope_i are distinct.
8. allocated = exact_sum(D.members[i].local_cap)
   require allocated <= D.family_delta.
9. For each i:
     validate canonical root and current-head receipt through existing ledger
     require receipt.scope_id == expected_scope_i
     require effective local cap == D.members[i].local_cap
     require every probabilistic reservation was made under that cap
     require local_total_spend <= local_cap
     require local conditionality/assumptions are complete
10. Reconstruct chronology from live protocol and ledger artifacts:
      no later member precedes unresolved earlier member
      disputes halt
      stop after first canonical positive
      every earlier refused/void/completed member remains
      no positive comes from an unregistered scope
11. Apply cap-disposition rules without refund or substitution.
12. If any member plan was selected or changed using earlier family outcomes:
      require a canonical selection-valid owner theorem and verifier;
      otherwise eligible_for_family_risk_claim = false and
      refusal_code = adaptive_validity_unproved.
13. Recompute aggregate cap, actual spend, conditionality, and projection hash.
14. Emit eligible_for_family_risk_claim only if every requirement holds.
```

Step 9 is the canonical-owner seam. A Markdown declaration cannot manufacture a local `alpha_i`
guarantee; the owner must have constrained execution and must expose verifiable evidence.

## 6. Terminal and cap-disposition semantics

| Member state | Result-bearing information exposed? | Default local risk treatment | Sequence treatment | Cap transferable? |
| --- | --- | --- | --- | --- |
| `preflight_refused` before owner execution | No owner result; refusal may still reveal eligibility information | Actual spend zero; assigned cap retires for this family version | Retain/publish; advance if protocol permits | No |
| Deterministic infrastructure failure proved before any result-bearing execution | No | Retry same member/scope/cap under prospective rule | Does not replace/advance slot | No |
| `started` then owner refusal/error | Yes or potentially yes | Reserved spend burned; remaining cap retires | Retain terminal; advance only under protocol | No |
| `void_result_bearing` | Yes or exposure cannot be excluded | Spend burned; remaining cap retires | Retain; no substitution | No |
| `disputed` | Yes | Spend remains; remaining cap held/retired | Halt until prospectively resolved | No |
| `completed_negative` / grounded refusal | Yes | Spend remains; unused cap retires | Advance | No |
| `promoted` | Yes | Spend remains charged | Stop family | No |
| `unreached` after prior positive | No | No spend; assigned cap expires unused | Record unreached | No |

No-refund is a governance protocol, not a theorem that recycling can never be valid. A more powerful
recycling rule needs prospective specification, a canonical theorem, and dedicated falsifiers.

## 7. Fixture package

### 7.1 Execution boundary

The fixture has two modes:

1. **Baseline characterization** at `978e6b958...`: reproduce three unaccounted top-level budgets
   and prove no family projection exists.
2. **Future conformance** after a canonical ledger extension: preserve three distinct scopes while
   enforcing local caps and producing a live recomputed family projection.

A hand-built model of the property is insufficient. The validator must import and execute the real
canonical scope derivation and ledger paths, then remove the protected property while retaining
markers to prove behavioral verification.

### 7.2 Common deterministic inputs

```yaml
fixture_id: INT-R10-FWC-001
family_delta: {numerator: 1, denominator: 100}
composition_profile: weighted_union_v1
stopping_rule: stop_on_first_canonical_positive
member_plan_policy: prospectively_fixed_member_plan
problems:
  - slot: 1
    design_problem_id: FWC-A
    problem_hash: sha256:<A>
    implementation_revision_hash: sha256:<R-A>
    local_cap: {numerator: 1, denominator: 300}
  - slot: 2
    design_problem_id: FWC-B
    problem_hash: sha256:<B>
    implementation_revision_hash: sha256:<R-B>
    local_cap: {numerator: 1, denominator: 300}
  - slot: 3
    design_problem_id: FWC-C
    problem_hash: sha256:<C>
    implementation_revision_hash: sha256:<R-C>
    local_cap: {numerator: 1, denominator: 300}
expected_scope_relation:
  all_distinct: true
expected_scope_ordinals:
  first_started_check_in_each_scope: 0
maintained_assumptions:
  - obligation_completeness_by_member
  - validator_soundness_by_member
```

The three revisions may differ; all three member plans must be committed before any family
result-bearing execution. IDs/hashes must be generated from committed inputs, never copied from
expected output.

### 7.3 Positive future-conformance control

```text
slot 1 -> FWC-A -> scope A -> local ordinal 0 -> completed negative/refused
slot 2 -> FWC-B -> scope B -> local ordinal 0 -> result-bearing void/negative
slot 3 -> FWC-C -> scope C -> local ordinal 0 -> canonical positive
stop
```

Required assertions:

1. `scope_A`, `scope_B`, and `scope_C` are recomputed by live N9 and pairwise distinct.
2. Local ordinal zero in all three scopes is accepted; there is no family ordinal substitution.
3. Before any probabilistic owner call, each scope has effective cap `1/300`.
4. Every local schedule reservation is recomputed from the effective cap and overspend is refused.
5. Exact allocated-cap total equals `1/100`.
6. Exact aggregate actual spend is at most `1/100`.
7. Earlier refused, void, or negative terminals remain in the projection.
8. No unused cap moves between members.
9. The first positive is the registered third member and stops the family.
10. The member-plan vector is the exact prospectively committed vector; differing `R-A/R-B/R-C`
    do not invalidate the fixed-plan theorem.
11. The projection is recomputed from live source, roots, current-head receipts, deployment/
    registry identity, member plans, and chronology.
12. Conditionality names all local and family premises.
13. Revalidation yields the same semantic projection.
14. Corrupting any cap, member plan, scope binding, earlier terminal, root/head, or registry identity
    fails validation.

Expected future result:

```text
within_family_budget = true
eligible_for_family_risk_claim = true
allocated_cap = 1/100
actual_spend <= 1/100
controlled_event = any reached member falsely promotes
```

At the pinned baseline, the expected result is an honest refusal because the capability is absent.

### 7.4 Mandatory negative control — three fresh full budgets

Execute:

```text
slot 1 -> problem A -> scope A -> ordinal 0 -> top-level delta 1/100
slot 2 -> problem B -> scope B -> ordinal 0 -> top-level delta 1/100
slot 3 -> problem C -> scope C -> ordinal 0 -> top-level delta 1/100
stop on first positive
```

Baseline assertions:

- all three scope IDs are distinct;
- each scope starts from its own empty history and can assign local ordinal zero;
- each root receives the registry top-level `1/100` delta;
- prior spend is summed only inside the current scope;
- no live family declaration, cap binding, or family projection blocks the trace.

Future conformance result: the same trace goes red before any single-`1/100` family claim, with an
equivalent of:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
unregistered_family_scope
```

A passing INT-R9 record or a sentence saying “same cumulative budget” cannot override the failure.

### 7.5 Negative and metamorphic controls

| ID | Mutation | Required result |
| --- | --- | --- |
| FWC-NEG-02 | After member 1 refuses, move its unused cap to member 2. | `outcome_dependent_refund_forbidden` or theorem-specific refusal. |
| FWC-NEG-03 | Omit member 1's refusal and begin projection at member 2. | `prior_member_history_incomplete`. |
| FWC-NEG-04 | Substitute problem D/scope D after seeing A fail. | `family_member_substitution`. |
| FWC-NEG-05 | Supply scope B under member A while keeping field shape. | `canonical_scope_derivation_mismatch`. |
| FWC-NEG-06 | Duplicate a scope or design-problem ID. | Duplicate-member refusal. |
| FWC-NEG-07 | Change cap weights after member 1 outcome while final sum remains `1/100`. | `allocation_not_prospective`. |
| FWC-NEG-08 | Change member 2 implementation after member 1 outcome; provide no selection-valid theorem. | `adaptive_validity_unproved`. |
| FWC-NEG-09 | Precommit different `R-A`, `R-B`, `R-C` before any result. | **Must remain eligible** if every local theorem/cap is valid; prevents accidental “one identical revision” requirement. |
| FWC-NEG-10 | Hand-author green family projection without loading live scope heads. | `family_projection_recomputation_mismatch`. |
| FWC-NEG-11 | Use stale member receipt while a newer head exists. | `member_receipt_not_canonical_head`. |
| FWC-NEG-12 | Remove one member's obligation-completeness assumption but leave budget booleans green. | `family_conditionality_incomplete`. |
| FWC-NEG-13 | Use rounded decimals that appear within budget while exact rationals exceed it. | Exact rational validation rejects. |
| FWC-NEG-14 | Multiply three e-values without a registered conditional merger theorem. | `family_owner_theorem_unavailable`. |
| FWC-NEG-15 | Let an unregistered fourth scope produce the first positive. | `unregistered_positive_scope`. |
| FWC-NEG-16 | Keep a revision marker constant while changing executable/model/config bytes. | Member-plan/deployment mismatch. |
| FWC-NEG-17 | Give all three problems one owner key to force one scope. | Identity weakening / problem-binding mismatch. |
| FWC-NEG-18 | Remove effective local-cap enforcement but keep declaration/projection fields. | Property-removal control must fail. |
| FWC-NEG-19 | Local actual spend is below `1/300`, but owner executed using ordinary `1/100` threshold. | `local_cap_not_enforced_before_execution`. |

### 7.6 Sharpness witness

For `delta <= 1/3`, construct disjoint events `E_A`, `E_B`, and `E_C`, each probability `delta`.
Define the three local false-promotion events as those events. Then:

```text
P(E_A) = P(E_B) = P(E_C) = delta
P(E_A union E_B union E_C) = 3 * delta.
```

At the live `delta = 1/100`, the family probability is exactly `3/100`. This is a deterministic
theorem fixture, not a simulation estimate.

### 7.7 Adaptive-continuation fixture

Use member 1 outcome to select member 2 implementation:

```text
member 1 runs precommitted R0;
if result class X occurs, choose repair R_X for member 2;
local certificate for R_X was proved only when R_X was fixed independently of X.
```

Even if exact cap totals remain within `delta_F`, the family projection must refuse
`adaptive_validity_unproved`. The positive paired fixture supplies a canonical theorem whose
verifier covers the selector and complete history; only then may the adaptive family claim become
eligible.

This separates arithmetic validity from selection validity.

## 8. Audit R1 acceptance matrix

| R1 requirement | Closure property | Fixture evidence |
| --- | --- | --- |
| Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)`. | Projection and all refusals name the event. |
| Relation to canonical scopes | Live derivation; distinct member scopes preserved. | Positive assertion 1; scope-swap/collapse negatives. |
| No fresh unaccounted budgets | Prospective local caps sum within `delta_F` and bind before execution. | Positive assertions 3–6; mandatory `3/100` negative. |
| Earlier terminal effects | Explicit no-refund/no-substitution dispositions. | Trace plus FWC-NEG-02/03/15. |
| Aggregate proof | Weighted union plus exact rational cap/spend totals. | Positive projection and sharpness witness. |
| Adaptive continuation | Fixed member-plan vector is covered; outcome-dependent change requires selection-valid theorem. | FWC-NEG-08/09 and adaptive pair. |
| Canonical owner reuse | Projection has no second head, ordinal, risk scope, or registry. | Structural review and author-written projection negative. |
| Live reproducibility | Scope derivation, roots, receipts, heads, caps, plans, and chronology recomputed. | FWC-NEG-10/11/18/19. |

## 9. Handoff invariants

A later implementation may choose names and serialization only after consolidation. It must
preserve:

1. Per-problem scope identity unchanged.
2. Confidence ledger as the only risk-accounting owner.
3. Local caps bound before result-bearing execution.
4. Exact rational authority path.
5. Existing Basel allocation inside the effective local cap.
6. No refund by default; recycling needs a theorem.
7. Different prospectively fixed member plans are allowed.
8. Outcome-dependent plan selection is an adaptive theorem boundary.
9. INT-R1 conditionality remains visible per member.
10. Verifier executes live source and survives property-removal probes.
11. Missing family composition blocks the numeric authority claim, not candidate work.

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
best_generic_composition_of_three_valid_local_delta_guarantees: min(1, 3 * delta)
live_registry_instance_at_delta_1_over_100: 3/100
```

That is a successful negative baseline. The sketch does not authorize a production claim until the
canonical owner extension and behavioral fixtures exist.