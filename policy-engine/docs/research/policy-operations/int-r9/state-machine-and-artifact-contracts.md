---
title: INT-R9 — First-Promotion State Machine and Artifact Contract Sketches
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
bound_int_r10_commit: research/int-r10-revision@a334f7d844733bfd17f1857a4cb56fbf219378ef
bound_int_r1_amendment_commit: research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0
authoritative_for:
  - research-level first-promotion custody-workflow semantics
  - research sketches of evidence-bearing artifacts for later consolidation
  - mapping of first-promotion facts to the adopted Custody Time Model
  - explicit nonnumeric treatment of the adaptive three-slot sequence
  - prevention of a parallel status lattice, confidence ledger, family scope, or oracle framework
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical schema or package placement
  - canonical owner assignment
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - legal compliance conclusion
  - a sequence-level numeric false-promotion claim
  - a canonical useful-design-rate denominator definition
research_only: true
---

# INT-R9 — First-Promotion State Machine and Artifact Contract Sketches

## 1. Standing and non-duplication rule

These are **research shapes**, not production types. Consolidation may reject, split, merge, or rename them. No identifier, field, literal, transition, package, or owner becomes canonical by appearing here.

Existing law remains primary:

- one truthful status surface, not parallel status truths (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:145-230`);
- canonical runtime terminal, obligation, and promotion semantics in the waist and N9 (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:120-310`; `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1-270`);
- local confidence scopes and receipts, with no current cross-scope family projection (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-195`, `:1285-1368`, `:3890-4027`);
- S0-GAP-02 ownership of generic oracle/evaluator custody (`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:75-210`);
- the adopted Custody Time Model; and
- amended INT-R1 `ObligationCoverageEnvelope` semantics.

Accordingly, workflow states are custody facts, not a second authority lattice; `promoted` requires an existing canonical local promotion receipt plus procedural admissibility; local confidence receipts remain separate; result-informed repair is adaptive; late materiality defaults to dispute; useful-design metric membership is not decided here; and a replacement for S0-GAP-02 must be an expressly governed canonical supersession.

## 2. State machine

### 2.1 State table

| Workflow state | Entry evidence | Load-bearing clocks | Permitted exits | Terminal/public meaning |
| --- | --- | --- | --- | --- |
| `pre_registration_drafted` | Editable draft; no candidate or answer access. | Draft transaction history. | `sealed`, `terminal_no_attempt`. | Proposal only; no anti-selection standing. |
| `sealed` | Custodian accepts protocol, pool/order, criteria, prospective materiality rules, panel/conflicts, coverage requirement, stopping, publication, and no-family-number boundary. | CTM receipt, independent transaction visibility, verification, purpose admission, expiry. | `candidate_inspected`, `retired_before_inspection`, `disputed`, `terminal_no_attempt`. | Procedure prospectively fixed; not passage. |
| `candidate_inspected` | Next committed input revealed after exact freeze and eligible current coverage input. | Reveal, first inspection, run, output freeze, source-native times. | `adjudicated`, `void`, `disputed`. | Irrevocably in chronology; metric denominator membership remains external. |
| `adjudicated` | Expectation reveal complete; panel signs raw votes after owner, falsifier, adjacent, conflict, and materiality evidence. | Expectation reveal, vote, verification, adjudication transaction times. | `promoted`, `refused`, `void`, `disputed`. | Completed evaluation; no public positive until final disposition. |
| `promoted` | Canonical local promotion receipt plus every procedural predicate; eligible coverage; panel quorum; no material dissent; bounded wording; no family number. | Promotion action, publication, review/currentness. | Append-only challenge/correction/suspension/withdrawal/supersession. | One bounded earliest qualifying procedural positive. No population or family-risk inference. |
| `refused` | Canonical refusal/unknown/blocker, failed predicate, or predeclared NO-GO. | Refusal and publication. | Next slot if permitted; otherwise `exhausted_without_promotion`; append-only challenge. | No promotion from this slot; does not prove impossibility. |
| `void` | Leakage, wrong slot, post-reveal mutation, unverifiable freeze, hidden rerun, or custody failure. | Incident observation, verification, void action. | Next slot if permitted; otherwise exhaustion; append-only challenge. | No substantive positive; custody failed. Remains in chronology. |
| `disputed` | Material challenge, late/unresolved materiality, unresolved dissent, ambiguity, conflicted/unavailable adjudicator without clean alternate, or custody challenge. | Challenge receipt, verification, response, escalation, resolution. | Canonical resolution to `promoted`, `refused`, `void`, or continuing dispute. | No unqualified current positive; later slot cannot become first while unresolved. |
| `retired_before_inspection` | Affirmative no-access proof; old version and diff retained. | Retirement before any reveal. | New prospective version may be drafted. | Prospective correction; no scored attempt. |
| `terminal_no_attempt` | Draft abandoned or sealed protocol expires without inspection. | Abandonment/expiry. | None for this version. | No candidate inspected and no result exists. |
| `exhausted_without_promotion` | Every committed slot terminal without promotion. | Last terminal and publication. | None for this version. | Finite program produced no positive; publishable primary outcome. |

### 2.2 Transition invariants

1. **Prospective order.** Independent transaction evidence for seal, selection, criteria, materiality, panel, publication, and no-family-number boundary precedes result-bearing access.
2. **No erasure.** Every inspected, refused, void, disputed, or promoted slot remains addressable.
3. **No substitution.** Only the earliest unresolved committed slot may be scored; unregistered success is exploratory.
4. **No best-run selection.** First result-bearing run is scored. Retry needs a prospective infrastructure rule and proof no output or answer was exposed.
5. **One lattice.** Workflow phase, runtime terminal, obligation state, local confidence receipt, coverage posture, and public currentness are linked but not collapsed.
6. **Dispute blocks firstness.** A material unresolved dispute prohibits an unqualified current positive and later-slot firstness.
7. **No retroactive amendment.** Post-inspection changes cannot alter the scored disposition.
8. **Adaptive repair.** A later revision informed by an earlier result is adaptive even when its code is syntactically general.
9. **No family number.** Separate local confidence scopes/receipts cannot be represented by INT-R9 as one cumulative scope, spend, ordinal, `delta`, or `3 * delta`.
10. **Coverage identity.** A material gap cannot be cured by narrowing the same scored action; a narrower action needs new prospective identity/version/fresh cases.
11. **Materiality direction.** If materiality was not validly decided before direction was known, the state is disputed.
12. **Metric boundary.** INT-R9 records chronology but does not define `useful_design_rate` membership.
13. **Bounded public meaning.** Public record names revision, environment, cases, evaluator, protocol, assumptions, purposive-pool and independence residuals, coverage posture, and absence of a family number.

### 2.3 Transition sketch

```text
pre_registration_drafted
  -> sealed
  -> candidate_inspected
  -> adjudicated
  -> promoted | refused | void | disputed

pre_registration_drafted -> terminal_no_attempt
sealed -> retired_before_inspection | terminal_no_attempt | disputed
refused | void -> next committed slot, if one remains and no dispute blocks
all committed slots nonpositive -> exhausted_without_promotion
```

There is no transition from a scored state back to `sealed`; no later positive overwrites an earlier terminal; and no workflow transition creates a family-risk receipt.

## 3. Custody Time Model mapping

INT-R9 reuses CTM roles rather than creating a clock vocabulary (`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:58-151`).

| Fact | CTM role | Meaning |
| --- | --- | --- |
| external case instrument/observation | source assertion/validity/effect roles | source-native time, distinct from PolicyOS access |
| custodian receives protocol/package | receipt | proves receipt only |
| commitment becomes independently visible | transaction visibility | load-bearing prospectivity fact |
| signature/digest/access/freeze checked | verification | cannot backdate visibility |
| artifact admitted for first-promotion purpose | purpose-scoped admission | not authority or legal admission |
| seal/freeze/run/adjudication/promotion/correction | lifecycle/decision action | actor, rule, and transaction time recorded |

Minimum partial order:

```text
protocol_and_pool_transaction_visible
  < selection_execution_transaction
  < implementation_freeze_complete
  < primary_input_reveal
  <= first_inspection
  <= candidate_output_freeze
  < expectation_reveal
  <= adjudication_action
```

If clock uncertainty prevents strict ordering, prospectivity is unproved and the slot cannot promote.

## 4. Common artifact semantics

Every sketch below carries, conceptually:

- durable identity and exact research/implemented version;
- accountable producer and input/source provenance;
- CTM receipt, transaction, verification, admission, action, and correction roles where applicable;
- signatures, commitments, access-log references, and content binding;
- exact purpose, protected action, audience, assumptions, uncertainty, and unknowns;
- correction/challenge/supersession links;
- `authoritative_for` and `may_not_use_for`; and
- `research_only` until a later owner establishes otherwise.

This is descriptive commonality, not a universal production envelope.

## 5. Typed research sketches

### 5.1 `FirstPromotionPreRegistration`

```yaml
FirstPromotionPreRegistration:
  protocol_and_baseline_refs: exact
  implementation_environment_model_prompt_evaluator_freeze_refs: exact
  case_frame_pool_commitments_selection_order_stopping_refs: exact
  canonical_owner_predicate_and_threshold_refs: exact
  procedural_property_refs: exact
  prospective_materiality_specifications: complete
  panel_alternates_authors_custodian_and_relationship_evidence_refs: complete
  obligation_coverage_requirements: exact protected action and future envelope constraints
  publication_dissent_challenge_correction_rules: exact
  transaction_visibility_before_inspection_proof: required
  sequence_level_numeric_family_claim: none
```

The last line is explanatory research notation, not a proposed runtime field.

### 5.2 `FirstPromotionAttemptRecord`

```yaml
FirstPromotionAttemptRecord:
  preregistration_and_slot_refs: required
  exact_freeze_and_reveal_receipts: required
  first_result_bearing_run_ref: required
  local_n9_firewall_confidence_and_owner_receipts: separate, scope-bound
  obligation_coverage_envelope_ref: required
  public_regression_adjacent_falsifier_no_bespoke_refs: required
  deviations_incidents_prior_terminal_refs: complete
  adaptive_repair_ancestry_ref: optional
  local_risk_receipts: preserved_without_aggregation
  family_scope_spend_ordinal_or_bound: absent
```

### 5.3 `ObligationCoverageEnvelope` consumption

INT-R9 does not redefine the amended INT-R1 shape. The attempt record binds its exact protected action, closure basis, obligation-language/compiler version, cutoff, assumptions, unknown remainder, independent review/currentness, challenge/expiry standing, and rider.

```text
known_incomplete -> protected action NO-GO
material open_world_unresolved -> protected action NO-GO
current pinned standing -> open_world_unresolved -> positive blocked
future bounded_complete -> relative exact-scope input only; never world completeness or auto-promotion
```

### 5.4 `MaterialityDecisionSpecification`

```yaml
MaterialityDecisionSpecification:
  question_class_and_scope: exact
  competent_existing_owner_or_owner_composition_ref: required
  decision_rule_and_evidence_requirements: sealed
  conflict_recusal_tie_escalation_rules: sealed
  latest_direction_blind_decision_time: sealed
  unknown_stale_unavailable_reaction: disputed
```

### 5.5 `MaterialityDecisionRecord`

```yaml
MaterialityDecisionRecord:
  specification_ref: required
  accountable_person_or_owner_ref: required
  competence_and_conflict_evidence_refs: required
  input_evidence_and_reason: required
  transaction_time: required
  result_direction_known_before_decision: must_be_false
  invalid_or_unresolved_reaction: disputed
```

### 5.6 `IndependenceEvidenceBundle`

```yaml
IndependenceEvidenceBundle:
  person_identity_and_signature: required
  implementation_case_answer_criteria_materiality_contribution_history: corroborated
  answer_and_scored_output_access_history: corroborated
  employment_reporting_governance_funding_contract_compensation_terms: corroborated_where_available
  shared_network_funder_reputational_relationships: disclosed_and_dispositioned
  evidenced_dimensions: explicit
  declared_not_evidenced_residuals: explicit
  disqualifying_or_unresolved_dimensions: explicit
```

A producer-populated `independent: true` is not evidence.

### 5.7 `AdaptiveRepairRecord`

```yaml
AdaptiveRepairRecord:
  prior_result_bearing_terminal_ref: required
  revealed_information_used: explicit
  changed_revision_and_asset_refs: content_bound
  authors_reviewers_conflicts_times: required
  rationale_and_intended_generality: required
  fixed_protocol_elements_unchanged_receipt: required
  later_sealed_package_nonaccess_proof: required
  prior_slot_rescoring: false
  sequence_level_numeric_claim: none
```

No distinction between “general” and “targeted” repair changes the fact of adaptivity.

### 5.8 `FirstPromotionAdjudicationRecord`

```yaml
FirstPromotionAdjudicationRecord:
  attempt_freeze_reveal_evaluator_refs: required
  canonical_owner_and_local_confidence_receipts: required
  coverage_envelope_ref: required
  public_regression_no_bespoke_source_flip_obligation_adjacent_refs: required
  panel_identity_evidence_conflicts_raw_votes_abstentions_dissent: required
  materiality_decision_records: complete
  workflow_disposition: promoted | refused | void | disputed
  public_claim_permitted: boolean
  sequence_level_numeric_family_claim_permitted: false
  bounded_external_validity_statement: required
```

The union is illustrative local notation, not a frozen enum.

### 5.9 `FirstPromotionPublicRecord`

```yaml
FirstPromotionPublicRecord:
  exact_revision_environment_cases_evaluator_protocol: required
  complete_prior_attempt_chronology: required
  local_owner_receipts_with_scope_and_assumptions: required
  family_risk_statement: no_sequence_level_numeric_bound_claimed_by_INT_R9
  pool_construction_and_external_validity_boundary: required
  independence_evidenced_dimensions_and_residuals: required
  coverage_posture_and_unknown_remainder: required
  raw_votes_dissent_deviation_challenge_refs: required
  terminal_meaning_currentness_and_correction_refs: required
```

### 5.10 `MetricChronologyProjection`

This is deliberately **not** a denominator contract.

```yaml
MetricChronologyProjection:
  selected_unreached_retired_inspected_void_refused_disputed_promoted_refs: observed_facts
  canonical_metric_owner_ref: unresolved_or_existing_external_owner
  denominator_membership: omitted
  numerator_membership: omitted_except_canonical_promotion_fact_ref
```

If the canonical metric cannot map the facts, that is an interface gap, not a new INT-R9 definition.

## 6. One-lattice mapping

```text
sealed / candidate_inspected / adjudicated
  -> custody phases only; no authority upgrade

canonical refusal / known_incomplete / material open_world_unresolved
  -> existing owner failure, unknown, or scope-insufficient posture

disputed
  -> blocks unqualified public positive; does not mint runtime status

promoted
  -> canonical local promotion receipt plus procedural admissibility

exhausted_without_promotion
  -> public workflow outcome; no claim that a positive is impossible
```

No new status enum is frozen. Atlas projects owner-supplied truth and never mints it.

## 7. State-specific expiry, succession, and correction

- **Seal expiry:** expiry before inspection yields `terminal_no_attempt` or a new prospective version, never silent extension.
- **Coverage expiry/perturbation:** expired, suspended, challenged, or materially perturbed envelope blocks the protected action.
- **Human availability:** only a predeclared alternate with clean evidence may replace an unavailable panel member; otherwise dispute.
- **Materiality availability:** unavailable/conflicted/late owner means dispute.
- **Leakage:** credible pre-freeze leakage yields void/dispute, retained chronology, no replacement.
- **Post-promotion defect:** append challenge and canonical suspension/correction/withdrawal/supersession; retain original event and wording.

## 8. Required edge cases

| Edge case | Required reaction |
| --- | --- |
| registered case fails; unregistered case succeeds | registered slot refused; unregistered result exploratory only |
| adjudicator unavailable | clean predeclared alternate or disputed |
| criterion ambiguity after seal | disputed; future-version clarification only |
| holdout leaks | void/disputed; retain chronology |
| promotion later unjustified | append challenge and canonical correction/currentness action |
| two qualifiers overlap | committed order and canonical transaction time decide firstness |
| preregistration error before access | retire only with affirmative no-access proof |
| old hand-coded binding found | NO-GO regardless of contributor departure |
| three local full-delta scopes | preserve local receipts; no family field or public number |
| result-informed syntactically general repair | adaptive repair record; later slot allowed; no family number |
| post-result narrower action proposed | old slot remains nonpositive; new prospective version/identity required |
| materiality owner sees adverse direction first | disputed |
| same-network panel has declarations only | independence unresolved; no positive admission |
| strategic supported refusal of all cases | compliant exhaustion, not proof anti-abstention failed |
| metric owner cannot map retired/unreached facts | interface gap; INT-R9 does not define denominator |

## 9. Canonical-owner and capability chain

| Concern | Producer | Persisted evidence | Bridge/consumer | Current standing |
| --- | --- | --- | --- | --- |
| selection/order | separated selection process | specification and receipt | S0-GAP-02 to scheduler/governance | missing |
| sealed packages | case authors/custodian | commitments, packages, access logs | S0-GAP-02 to run/evaluator | missing |
| local promotion/refusal | N9/waist owners | canonical receipt | existing GY chain to closeout | partial primitives; no demonstrated positive |
| local confidence | N11/confidence ledger | separate scope/head/receipt/profile | existing bridge | local only; no family projection |
| numeric family composition | future canonical confidence extension under INT-R10 | caps and live family projection | future approved consumer | absent; Option B forbids claim |
| coverage | future amended-INT-R1 producer | `ObligationCoverageEnvelope` | admission bridge to N9/adjudication | producer/bridge missing; current unresolved |
| materiality | existing competent owner mapping | specification and decision records | governance to panel/closeout | unresolved; blocks seal |
| human adjudication | named persons | evidence bundles/raw votes/signatures | S0-GAP-02 challenge to closeout | absent |
| public projection | closeout/currentness owners | terminal and corrections | Atlas/audiences | consumer path planned; producer missing |
| useful-design metric | existing metric owner | canonical metric record | existing analytics path | chronology mapping unresolved |

Capability requires producer, persisted artifact/event, bridge, consumer, verification, and surface. A schema alone establishes none.

## 10. Acceptance and invalidation rules

Accept these sketches for consolidation only if they remain noncanonical; local and family confidence objects are not collapsed; the no-family-number boundary is visible on every scored/public record; adaptive repair is not relabeled fixed; materiality is prospective or disputed; amended INT-R1 semantics are exact; useful-design metric ownership is not preempted; S0-GAP-02 has no sibling; and workflow facts feed the one existing public/authority surface.

Invalidate any implementation reading that serializes `cumulative_scope`, `family_ordinal`, `family_delta`, or family spend from INT-R9; treats local receipts as a family guarantee; lets late materiality favor promotion; computes independence solely from declarations; calls a purposive-pool draw independent of tractability judgment; says public controls solve strategic abstention; narrows the same protected action after a coverage gap; defines the useful-design denominator here; loads the retired YAML as protocol law; or appoints a new owner by naming a research shape.
