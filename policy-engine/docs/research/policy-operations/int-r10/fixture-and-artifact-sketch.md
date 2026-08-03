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

## 1. Standing, owner, and baseline anchors

This is a research sketch, not a final schema. Names and serialization are replaceable; the semantic
properties are not.

The canonical owner to extend is the existing confidence ledger. It already owns one stable,
non-resettable budget scope per owner key
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`), canonical roots and
scope-local receipts
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752`), local ordinal/spend
assignment and risk burn before owner execution
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`), typed refusal for
unavailable theorems
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3740-3855`), and exact
recomputation of local spend
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`). N9 derives one
canonical scope from each design-problem binding
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).

At the pinned baseline, no cross-scope/family/parent-scope composition exists; GY-GAP2 records this
as a missing capability rather than a defect in per-problem scope identity
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). The live registry
sets `delta = 1/100` and exposes no family cap vector
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`). Relevant adaptive
owner theorem profiles remain unavailable
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

Accordingly, this sketch does **not** introduce:

- a second risk ledger or mutable confidence head;
- a family ordinal competing with each scope's local ordinal;
- a replacement or weakened `ConfidenceRiskBudgetScope`;
- a parent risk scope containing the problem scopes;
- a second promotion gate or status lattice; or
- an author-written proof record accepted without live recomputation.

The family object is a **prospective composition declaration plus a recomputed projection over
existing canonical roots and receipts**. At `978e6b958...`, a conforming validator must refuse an
equivalent of `family_composition_unavailable`, consistent with
`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`.

## 2. Controlled event and theorem interfaces

For ordered family `F = (1, ..., m)`:

- `R_i`: member `i` is reached under declared stopping/dispute rules;
- `P_i`: member `i` emits a canonical positive promotion;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`; and
- `V_F = union_i V_i`.

With stop on first canonical positive, `V_F` is exactly the event that the reported first promotion
is false.

### 2.1 Prospectively fixed member-plan interface

Before any family result-bearing execution, bind the exact family/order, cap vector, and complete
member-specific plan vector. Member A may use revision `R_A`, B `R_B`, and C `R_C`; all may differ.
The fixed-plan theorem requires the complete vector to be committed before outcomes, not identical
implementations.

```text
P(V_i | A_F) <= alpha_i
alpha_i >= 0
sum_i alpha_i <= delta_F
--------------------------------
P(V_F | A_F) <= delta_F
```

No common null, estimand, exchangeability, or independence is required.

### 2.2 Adaptive interface

For outcome-dependent repair, let `H_{i-1}` contain the full prior history. A sufficient interface
is:

```text
alpha_i(H_{i-1}) is chosen before member-i outcome;
alpha_i(H_{i-1}) >= 0;
sum_i alpha_i(H_{i-1}) <= delta_F pathwise;
P(P_i and W_i | H_{i-1}, R_i, A_F) <= alpha_i(H_{i-1}) almost surely.
```

An equivalent uniform or selection-aware theorem is acceptable. A local anytime-valid label alone
is insufficient; the live registry's relevant owner profiles are unavailable at
`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.

## 3. Placeholder declaration

### 3.1 Purpose

`FamilyRiskCompositionDeclaration` prospectively binds the exact union event, member relation,
local caps, and member-plan vector. It is an input admitted by the confidence ledger, not an INT-R9
receipt and not authority by itself.

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
family_delta: {numerator: 1, denominator: 100}
composition_theorem_profile: weighted_union_v1
allocation_timing: before_any_family_result_bearing_execution
member_plan_policy:
  kind: prospectively_fixed_member_plan
  plan_vector_hash: sha256:<hash of all member plans>
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

### 3.3 Acceptance requirements

A canonical implementation must verify:

1. family and plan-vector hashes from canonical serialization;
2. exact nonnegative rational caps and exact `sum(local_cap) <= family_delta`;
3. total unique member order and unique slot/problem/scope identities;
4. every scope through live N9 derivation, whose source is
   `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
5. declaration and complete member-plan visibility before any family result-bearing execution;
6. content-bound repository/deployment/registry/theorem/stopping/terminal rules;
7. explicit controlled event rather than “shared cumulative confidence” prose;
8. every local theorem profile through the existing owner refusal machinery at
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3740-3855`; and
9. for adaptive policy, a canonical selection-valid theorem and verifier.

### 3.4 Effective local-cap requirement

A declaration does not itself reduce the local false-promotion bound. Before a probabilistic owner
call in scope `i`, the confidence ledger must enforce an effective ceiling no greater than
`alpha_i`:

```text
effective_local_ceiling <= assigned_family_cap
prior_local_spend + next_reservation <= effective_local_ceiling
```

Observable requirements:

- cap binding precedes the first result-bearing `started` event;
- the local schedule uses the effective ceiling instead of the ordinary full registry delta;
- overspend fails before owner execution;
- local receipts expose the effective cap/family binding;
- the verifier recomputes the cap from live source; and
- canonical per-problem `scope_id` remains unchanged.

This extends the current pre-execution risk-burn path at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`; after-the-fact low spend
is not enough.

## 4. Placeholder projection

### 4.1 Purpose

`FamilyRiskCompositionProjection` is a confidence-ledger recomputation over the bound live scopes.
It is not independently authored by INT-R9.

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
  vector | maintained assumptions) <= family_delta; conditional on every member's
  declared obligation completeness and validator soundness plus the named family assumptions.
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

### 4.3 Anti-duplication

The projection must not own an independent mutable head, execution ordinal, risk-spend chain,
registry, local verifier route, replacement risk scope, or promotion decision. These constraints
follow the repository's owner/behavioral-proof rules at `AGENTS.md:17-27` and `AGENTS.md:37-55`.

A content hash, declaration reference, member receipt references, and derived aggregate are allowed
because they summarize existing authority. Local roots/receipts remain the local owners, following
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557` and
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752`.

## 5. Canonical recomputation algorithm

```text
INPUT:
  declaration D
  exact repository/deployment identity
  live registry G
  live N9 problem bindings B[1..m]
  canonical roots/current-head receipts L[1..m]
  consumer chronology C

1. Validate D and exact rationals.
2. Recompute family_id and member-plan-vector hash.
3. Require D.registry_content_hash == hash(G).
4. Require D and the complete fixed member-plan vector were visible before every
   family result-bearing execution.
5. Require member order exactly 1..m with no duplicates or omissions.
6. For each i:
     expected_scope_i = live confidence_risk_scope_for_problem(B[i]).scope_id
     require expected_scope_i == D.members[i].canonical_scope_id
     require problem identity/hash and member-plan hash match
7. Require all expected scopes distinct.
8. Require exact_sum(local caps) <= family_delta.
9. For each i:
     validate canonical root/current-head receipt through existing ledger
     require receipt.scope_id == expected_scope_i
     require effective local cap == declared local cap before execution
     require every probabilistic reservation was made under that cap
     require local_total_spend <= local cap
     require local assumptions/conditionality complete
10. Reconstruct chronology:
      no later member before unresolved earlier member
      disputes halt
      stop after first canonical positive
      every earlier terminal remains
      no positive from unregistered scope
11. Apply declared cap dispositions without unproved refund/substitution.
12. If any member plan was selected/changed using earlier family outcomes:
      require canonical selection-valid theorem;
      otherwise refuse adaptive_validity_unproved.
13. Recompute aggregate cap, actual spend, assumptions, and projection hash.
14. Emit numeric eligibility only if every check passes.
```

Steps 6 and 9 must execute the real scope and receipt paths at
`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` and
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`; supplied markers are not
proof.

## 6. Terminal and cap-disposition semantics

| Member state | Default local risk treatment | Sequence treatment | Cap transferable? |
| --- | --- | --- | --- |
| Preflight refusal before owner execution | Actual spend zero; assigned cap retires for this version. | Retain/publish; advance if declared rule permits. | No |
| Proven deterministic infrastructure failure before result-bearing exposure | Retry same member/scope/cap. | Does not replace/advance slot. | No |
| `started` then owner refusal/error | Reserved spend burned; remaining cap retires. | Retain terminal; advance only under protocol. | No |
| Result-bearing void | Spend burned; remaining cap retires. | Retain; no substitution. | No |
| Dispute | Spend remains; remaining cap held/retired. | Halt until prospectively resolved. | No |
| Completed negative / grounded refusal | Spend remains; unused cap retires. | Advance. | No |
| Promoted | Spend remains charged. | Stop family. | No |
| Unreached after prior positive | No spend; cap expires unused. | Record unreached. | No |

Local preflight refusal behavior is already typed at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1175-1298`. The no-refund rule is a
conservative governance protocol; a recycling rule requires its own canonical theorem and tests.

## 7. Executable fixture package

### 7.1 Common inputs

```yaml
fixture_id: INT-R10-FWC-001
family_delta: {numerator: 1, denominator: 100}
composition_profile: weighted_union_v1
stopping_rule: stop_on_first_canonical_positive
member_plan_policy: prospectively_fixed_member_plan
members:
  - {slot: 1, problem: FWC-A, revision: sha256:<R-A>, local_cap: 1/300}
  - {slot: 2, problem: FWC-B, revision: sha256:<R-B>, local_cap: 1/300}
  - {slot: 3, problem: FWC-C, revision: sha256:<R-C>, local_cap: 1/300}
expected_scope_relation: all_distinct
expected_first_local_ordinal: 0
```

The revisions may differ; all member plans must be committed before any family result-bearing
execution. IDs/hashes are generated from committed inputs, never copied from expected output.

### 7.2 Positive future-conformance control

```text
slot 1 -> FWC-A -> scope A -> local ordinal 0 -> completed negative/refused
slot 2 -> FWC-B -> scope B -> local ordinal 0 -> result-bearing void/negative
slot 3 -> FWC-C -> scope C -> local ordinal 0 -> canonical positive
stop
```

Required assertions:

1. live N9 produces three pairwise distinct scopes, using
   `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
2. local ordinal zero remains valid in all three scopes, consistent with
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`;
3. each scope has effective cap `1/300` before owner execution;
4. every reservation is recomputed from the effective cap and overspend is refused;
5. exact allocated cap equals `1/100` and exact actual spend is at most `1/100`;
6. earlier terminals remain and no cap moves;
7. the positive is the registered third member and stops the family;
8. differing `R-A/R-B/R-C` remain eligible because the vector was prospectively fixed;
9. live roots/current heads, registry/deployment identity, plans, assumptions, and chronology are
   recomputed; and
10. corrupting any cap, plan, scope, terminal, root/head, or source identity fails.

At the pinned baseline, this control must honestly refuse because GY-GAP2 is open
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

### 7.3 Mandatory negative control

Execute:

```text
slot 1 -> problem A -> scope A -> ordinal 0 -> top-level delta 1/100
slot 2 -> problem B -> scope B -> ordinal 0 -> top-level delta 1/100
slot 3 -> problem C -> scope C -> ordinal 0 -> top-level delta 1/100
stop on first positive
```

Baseline assertions:

- distinct scope IDs from
  `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
- independent local ordinal/spend histories from
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`;
- root-level `1/100` per scope from
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557` and
  `policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`; and
- no family cap/projection from
  `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`.

A future implementation must make this trace go red before any single-`1/100` family claim:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
unregistered_family_scope
```

INT-R9 prose cannot override the failure.

### 7.4 Metamorphic controls

| ID | Mutation | Required result |
| --- | --- | --- |
| FWC-NEG-02 | Move unused member-1 cap after refusal. | Unproved refund refusal. |
| FWC-NEG-03 | Omit member-1 terminal from projection. | Prior history incomplete. |
| FWC-NEG-04 | Substitute problem/scope D after A fails. | Member substitution. |
| FWC-NEG-05 | Supply B's scope under A while preserving field shape. | Live scope derivation mismatch. |
| FWC-NEG-06 | Duplicate scope/problem ID. | Duplicate-member refusal. |
| FWC-NEG-07 | Change cap weights after outcome while final sum stays `1/100`. | Allocation not prospective. |
| FWC-NEG-08 | Change member-2 plan after member-1 outcome without adaptive theorem. | `adaptive_validity_unproved`. |
| FWC-NEG-09 | Precommit different `R-A/R-B/R-C`. | Must remain eligible if local theorems/caps are valid. |
| FWC-NEG-10 | Hand-author green projection without live heads. | Recalculation mismatch. |
| FWC-NEG-11 | Use stale receipt while newer head exists. | Non-current head refusal. |
| FWC-NEG-12 | Remove one member's obligation assumption. | Conditionality incomplete. |
| FWC-NEG-13 | Hide exact overspend behind rounded decimals. | Exact-rational refusal. |
| FWC-NEG-14 | Multiply e-values without registered merger theorem. | Owner theorem unavailable. |
| FWC-NEG-15 | Unregistered fourth scope produces positive. | Unregistered positive. |
| FWC-NEG-16 | Keep revision marker but change executable/config/model bytes. | Plan/deployment mismatch. |
| FWC-NEG-17 | Force three problems into one scope. | Identity weakening refusal. |
| FWC-NEG-18 | Remove effective cap enforcement but keep fields. | Property-removal test must fail. |
| FWC-NEG-19 | Actual spend is low, but owner executed under ordinary `1/100`. | Cap not enforced before execution. |

The marker-preserving property-removal requirement follows `AGENTS.md:17-27`.

### 7.5 Sharpness witness

For `delta <= 1/3`, construct disjoint `E_A`, `E_B`, `E_C`, each probability `delta`. Then

```text
P(E_A union E_B union E_C) = 3 * delta.
```

At live `delta = 1/100`, the family probability is exactly `3/100`. This is a theorem fixture, not a
simulation.

### 7.6 Adaptive fixture

Member 1's result selects member 2 implementation `R_X`; the local theorem for `R_X` covered only a
procedure fixed independently of that result. Cap arithmetic remains valid, but projection must
refuse `adaptive_validity_unproved`. The positive pair supplies a canonical theorem covering the
selector/full history. The current registry has no such owner profile
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

## 8. Audit R1 matrix

| Requirement | Closure property | Evidence |
| --- | --- | --- |
| Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)`. | Projection names it. |
| Relation to canonical scopes | Live N9 derivation; distinct scopes preserved. | Positive plus scope-swap/collapse negatives. |
| No fresh budgets | Prospective local caps sum within `delta_F` and bind before execution. | Positive plus mandatory `3/100` negative. |
| Earlier terminal effects | Explicit no-refund/no-substitution dispositions. | Terminal table and negatives. |
| Aggregate proof | Weighted union and exact rational cap/spend totals. | Positive plus sharpness witness. |
| Adaptive continuation | Fixed vector allowed; outcome-dependent change requires selection-valid theorem. | FWC-NEG-08/09 and adaptive pair. |
| Canonical owner reuse | No second head, ordinal, scope, or registry. | Structural constraints and hand-authored projection negative. |
| Live reproducibility | Scope derivation, roots, heads, caps, plans, chronology recomputed. | FWC-NEG-10/11/18/19. |

## 9. Handoff invariants

A later implementation must preserve:

1. per-problem scope identity from
   `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
2. confidence ledger as sole risk-accounting owner;
3. local caps bound before execution, extending
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`;
4. exact rational authority path and local recomputation from
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`;
5. existing local Basel allocation inside the effective cap;
6. no refund by default;
7. different prospectively fixed member plans allowed;
8. outcome-dependent selection treated as an adaptive theorem boundary;
9. INT-R1 conditionality visible per member
   (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`);
10. behavioral live-source verification; and
11. missing composition blocks only numeric authority, consistent with
    `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`.

## 10. Pinned-baseline expected result

A validator at `978e6b958...` should report:

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

Evidence: per-problem scope and local spending are implemented at
`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` and
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`; the live `delta` is at
`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`; cross-scope
composition remains missing at
`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`; and adaptive owner
profiles remain unavailable at
`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.

That negative baseline is successful research. It does not authorize a production claim.