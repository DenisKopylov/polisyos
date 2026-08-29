---
task_id: INT-R3
stage: 3
artifact_role: amendment_specification
responds_to_audit: ../../audits/int-r3/int-r3-independent-audit.md
audit_head: 8e9be1e5e737312f92579b57a7f011b9b14d3a46
research_head: 819a83a88315a90320fdd4b25fcb328b434c77de
status: amendment_complete
authoritative_for:
  - int_r3_stage3_superseding_clauses
  - amended_benchmark_candidate
may_not_use_for:
  - human_subject_result
  - operator_comprehension_claim
  - owner_appointment
  - governance_threshold
  - ds12_gate_change
---

# INT-R3 amendment specification

This file is an additive stage-3 amendment. It does not erase the audited stage-1 text. Where a
clause below names a stage-1 clause, this file is the later controlling record for the amended package.
The audit defect is cited on the audit line; this file carries the response on the amendment line.

The five properties commended by the audit remain unchanged: behavioral rather than preference
outcomes; eligible-opportunity denominators and attempt/commit separation; three-layer truth with
set-valued `A_i*`; accessible relation preservation; and the preserved NDM-versus-heuristics
disagreement.

## 1. Effective standing and claim boundary

This supersedes the stage-1 use of one `gate_standing` reason.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
gate_basis: DS12_first_public_signature_gate_at_dc7bdf79a
comprehension_claim_use: NO_GO
int_r3_is_ds12_gate_input: false
evidence_standing: not_established
```

`gate_standing` retains the registered `W4-K05` value and now carries the actual first-public gate
basis. `comprehension_claim_use` is the separate local rule: no publication, product, slice or review
may cite this package as evidence that operators understand PolicyOS. INT-R3 does not open DS12 and,
under the master plan at the package pin, does not independently hold DS12 closed. Any future DS12
dependency requires a separate governed change; package frontmatter cannot create it.

No standing axis is upgraded by this amendment.

## 2. Executability split

The phrase “implementable benchmark specification” is narrowed to four independent states:

```yaml
protocol_coherence: established
technical_implementation_readiness: plausible_not_demonstrated
programme_execution_feasibility: not_established
human_study_execution: absent
```

The protocol is internally specific enough to build a candidate runner and item bank. This package
does not establish a recruitment frame, ethics/consent route, accessible-research support, staffed
adjudication panel, pilot envelope, participant-by-item precision model, budget or schedule.

A stronger result, `execution_infeasible_for_declared_scope`, becomes admissible only after a named
deployment sponsor attempts to identify the declared operator population, accessible participation
route, adjudication capacity and minimum pilot, and records that no bounded executable population
exists. No such receipt exists here.

## 3. Instrument ownership

The Atlas master plan allocated the honesty-comprehension instrument to DS6. That allocation is now
classified:

```yaml
allocation_record: DS6_owns_the_instrument
allocation_state: stale
allocation_evidence:
  - POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md / DS6 research-input augment
  - DS6 merged 2026-08-22 at 176276ef0
closure_result: DS6 closed without AuthorityUIComprehensionBenchmark or admitted human result
current_instrument_owner: unowned
route_for_allocation: human_principal
```

This amendment does not appoint a successor. `capability_standing` remains `absent/unallocated`: the
instrument has no current owner and no admitted contract/producer/event/consumer chain.

## 4. Red-first predicate classes

The twelve stage-1 predicates remain in force, but a single `12/12` total is prohibited. Their
effective classes are:

| Predicate | Effective class | What a green result establishes |
| --- | --- | --- |
| `AUI-R01` | `surface_semantic_contract` | weakest-boundary relation is represented and addressable |
| `AUI-R02` | `surface_semantic_contract` | an outer set is not collapsed to a point/distribution |
| `AUI-R03` | `surface_semantic_contract` | typed non-values remain distinct in rendering/action state |
| `AUI-R04` | `enforcement_contract` | unsupported ranking-dependent action is not admitted |
| `AUI-R05` | `surface_semantic_contract` | δ value and its constitutive rider remain one semantic unit |
| `AUI-R06` | `enforcement_contract` | a decision-critical stale basis cannot satisfy currentness |
| `AUI-R07` | `enforcement_contract` | quarantined evidence cannot satisfy an admitted-evidence slot |
| `AUI-R08` | `surface_semantic_contract` | a concrete safe transition and its trigger are exposed |
| `AUI-R09` | `surface_semantic_contract` | accessible structure preserves the qualifying relation |
| `AUI-R10` | `instrument_integrity` | attempt and commit are separately observable |
| `AUI-R11` | `instrument_integrity` | confidence is elicited against admissibility before feedback |
| `AUI-R12` | `instrument_integrity` | keys and metric eligibility are sealed before responses |

Composition:

```yaml
prebuild_predicates:
  surface_semantic_contract: 6
  enforcement_contract: 3
  instrument_integrity: 3
  behavioral_trial: 0
human_comprehension_established: false
```

Behavioral closure is supplied only by scored operator trials using the six mandatory metrics and
construct diagnostics. A report may say `12/12 pre-build predicates`, but must print the composition
above and must also print `human_comprehension_established: false`.

### Narrowed `AUI-R06`

The amended property is:

> For an action whose admissibility is currentness-dependent, where the stale item is part of the
> action’s admitted basis, no independently current basis satisfies the same predicate, and no
> separately governed override authorizes the action, stale or expired evidence cannot be consumed as
> current or support the commit.

Positive red witness: a matched fresh/stale twin in which the stale item is the sole currentness basis
retains the same permitted commit and no typed downgrade/refusal.

Required negative controls:

1. the action is not currentness-dependent;
2. an independently current basis satisfies the predicate; or
3. a separately governed, recorded override authorizes the same action.

In those controls, identical affordance is not a failure if the distinct valid basis or override is
visible and bound to the action.

## 5. Item-flow and exclusion guard

Set-valued truth and genuine disagreement remain. The repair bounds what exclusion may erase.

Every run reports this flow by construct and declared modality:

```text
authored
  -> semantic_verified
  -> scenario_verified
  -> adjudicated
  -> accessible_parity_verified
  -> scored | contestable | invalid
```

For every transition, report count, denominator and reason codes. At minimum, reason codes distinguish
`policy_silent`, `adjudicator_disagreement`, `semantic_ambiguity`, `scenario_nonreplay`,
`accessible_inequivalence`, `event_integrity_failure` and `answer_leak`.

Before an appointed governance owner sets powered coverage thresholds, the fail-closed rule is:

- if any mandatory construct or declared accessibility condition has zero scored items, the result is
  `coverage_insufficient`;
- if a mandatory construct×condition stratum is entirely absorbed by `contestable` or `invalid`, no
  aggregate primary score may be issued;
- pilot reports may show item-flow diagnostics, but cannot claim benchmark passage;
- a main-study claim additionally requires a preregistered participant×item precision model and
  per-stratum eligible-opportunity target.

No numeric maximum contestable/invalid fraction is invented here. The nonnumeric typed non-result is
the bounded substitute while the threshold owner is absent.

## 6. Resolving evidence for the four deferred constructs

| Construct | Discriminating contrast | First target population/condition | Primary behavioral endpoint and eligible denominator | Precision dependency | Transport requirement |
| --- | --- | --- | --- | --- | --- |
| explicit epistemic `unknown` | matched `unknown` ↔ numeric `0` and `unknown` ↔ missing, with action consequence changed only where policy makes the fact decision-critical | declared PolicyOS analysts/reviewers; visual, keyboard-only and screen-reader strata; ordinary and deadline conditions | `unknown-collapse` plus `false_pass`; denominator = all sealed discriminating `unknown` trials where the type changes admissible action | crossed participant×item model; no acceptance threshold until appointed | simulation supports only the declared semantic/action claim; operational actionability requires shadow/actual-use transport |
| pure outer set | matched outer set `[a,b]` with no internal distribution ↔ probabilistic interval with matched geometry | same declared operator population, including measured numeracy strata | point/distribution invention expressed in action or required pre-terminal selection; denominator = all scored outer-set discrimination trials | estimate by display and numeracy stratum with item variance; threshold unappointed | high-fidelity simulation required; field transport required before claiming use under real consequences |
| strict `incomparable` | `incomparable` ↔ tie ↔ insufficient evidence ↔ strict order | operators who must choose, request a criterion, escalate or abstain under the governing relation | unsupported strict ranking and ranking-dependent commit; denominator = all adjudicated-incomparable trials | precision for both ranking assertion and terminal action; threshold unappointed | semantic simulation can establish type discrimination; operational claim requires workflow/field transport |
| remaining policy δ-budget | remaining ↔ spent, low ↔ high, allowance ↔ value/benefit signal, with basis/TTL held or varied explicitly | operators who encounter δ-bearing decisions, stratified by task-relevant numeracy and time pressure | δ-budget inversion and resulting unsafe action; denominator = all sealed discriminating δ trials | participant×item precision plus eligible unsafe-action opportunities; no invented risk threshold | high-fidelity simulation first; actual-use or shadow validation required before incentive/behavior claim |

A construct leaves `deferred_open_problem` only for the evidence layer actually supplied. A successful
semantic simulation does not establish field transport. A result is refuted for a display family when
the matched contrast fails to change the required action semantics or when operators systematically
act on the forbidden interpretation.

## 7. Transfer arguments

### Time pressure (`INT-R3-F005`)

The target bridge is now explicit and remains a hypothesis until tested:

- candidate population: PolicyOS analysts/reviewers using Cycle Board, Case Workspace and Human
  Decision Gate;
- target workflow: locate the binding reason and choose acquire, escalate, abstain, pass or commit;
- shared mechanism: an objective deadline and interruptions reduce search/checking and raise the cost
  of leaving the active script for verification or escalation;
- expected observable effect: changed miss/false-pass/route-choice mix, not a copied source-domain rate;
- non-transfer case: a rehearsed high-validity task with immediate feedback, no meaningful deadline,
  or a transactionally free automatic escalation path.

The external mechanism justifies testing ordinary versus deadline conditions. It does not predict a
PolicyOS effect size or prove that expertise helps or harms in this environment.

### Weakest link (`INT-R3-F007`)

The source tasks are partitioned:

| Source task | Formal object | Permitted use here |
| --- | --- | --- |
| conjunctive probability judgment | product/joint probability | hypothesis that people may overestimate a chain; not evidence about a deterministic status minimum |
| deterministic all-must-pass | Boolean conjunction | direct semantic analogue when any failed prerequisite prohibits pass |
| governance minimum over ordinal states | policy-defined `min`/weakest boundary | PolicyOS rule to be learned from the registered owner, not from probability studies |
| intervention allocation / worst-first | choice of which component to improve | hypothesis about repair fixation, not proof of chain-status misunderstanding |

Stage-1 `F007` is therefore narrowed from a transferred behavioral rule to a
`hypothesis_generator`. Its supported consequence is only to keep blocker identification, overall
action and repair choice as separate endpoints.

The NDM-versus-heuristics disagreement remains unresolved and visible.

## 8. Primary blocker observation

Define:

```text
Bhat_primary_i
  = blocker references selected before terminal action
    OR blocker references carried by the terminal action event as its constitutive trigger

Bhat_posthoc_i
  = blockers named only in retrospective probing
```

The primary `missed_blocker` metric uses `Bhat_primary_i` only. `Bhat_posthoc_i` is diagnostic.
The event schema distinguishes `viewed`, `selected`, `action_triggering` and
`retrospectively_named`.

Negative control: a participant commits an inadmissible action, then correctly names the blocker in
retrospective questioning. The trial remains a primary blocker miss and an incorrect terminal action.

## 9. Evidence traceability

The amended package uses
[`external-source-ledger.md`](external-source-ledger.md). Every `EXT-01`–`EXT-16` row maps to:

1. one of the five exact survey-input digests and a line window;
2. one or more stable primary-source identifiers/official documents;
3. the original population, task, outcome and denominator where a number is used;
4. the PolicyOS transfer decision and its non-transfer boundary.

The five surveys remain external practice, not repository capability or authority. A source that
cannot be independently resolved remains `not_established` for the affected claim rather than being
filled by an unresolvable conversational citation.

## 10. Effective package result

The amendment does not report new human evidence.

```yaml
operator_comprehension: not_established
operator_actionability: not_established
accessible_path_equivalence: not_established
low_numeracy_robustness: not_established
confidence_calibration: not_established
programme_execution_feasibility: not_established
```

The benchmark candidate is more falsifiable and less absorbent after amendment. It is still a
research contract, not a capability, appointment, threshold or publication permission.
