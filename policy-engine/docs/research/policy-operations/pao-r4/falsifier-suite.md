---
title: PAO-R4 falsifier suite
research_id: PAO-R4
artifact_role: executable-research-specification
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# PAO-R4 falsifier suite

## 1. Verdict vocabulary

This is an executable semantic specification, not test code or a final API.

| Verdict | Meaning |
|---|---|
| `ALLOW_NON_INDIVIDUAL` | The crossing is within an allow-listed non-individual purpose and all required evidence conditions hold. |
| `REFUSE_EXPORT` | The artifact class is individually actionable, resolvable, or otherwise unsafe to disclose. |
| `BLOCK_PURPOSE` | The declared or observed use is in `may_not_use_for`. |
| `BLOCK_PERMISSION_AMPLIFICATION` | A projection or derivation removed a denied use or increased permission. |
| `BLOCK_COMPOSITION` | The proposed release/query sequence is unsafe in combination. |
| `VIOLATION_OBSERVED` | Returning evidence shows a prohibited material contribution. |
| `FIREWALL_CLAIM_NOT_ESTABLISHED` | Evidence is absent, incomplete, contradictory, or unverifiable; compliance is not inferred. |

A passing firewall must produce the exact required red or bounded verdict. “Warning,” “human will
review,” and “terms accepted” are not substitutes.

## 2. F-01 — commission falsifier: population rule becomes eligibility rule

```yaml
id: F-01
artifact:
  class: population_predictive_estimate
  statement: cohort default rate is 0.27 under basis B
  may_not_use_for: [individual_eligibility_determination]
request:
  consumer: case-system-A
  declared_purpose: programme_capacity_planning
attack:
  subject_ref: person-opaque-17
  protected_action: eligibility_deny
  material_contribution: threshold cohort_default_rate > 0.20
expected:
  export_gate: ALLOW_NON_INDIVIDUAL
  consumer_gate: BLOCK_PURPOSE
  returning_evidence: VIOLATION_OBSERVED
  firewall_red: true
forbidden:
  - eligibility_deny
  - human_click_converts_use_to_allowed
  - no_gate_red
```

**Exact pass condition:** the consumer gate blocks the eligibility use before the action and the
attempt is returned and reconciled. If the use occurs and no gate goes red, the architecture is
falsified. If the returning channel is absent, the result is
`FIREWALL_CLAIM_NOT_ESTABLISHED`, not compliance.

**Pinned current-state comparator:** no exact `individual_decision` vocabulary exists below
`policy-engine/src`; the PAO-R4 purpose is therefore not guaranteed to be recognized.

## 3. F-02 — two permitted aggregates re-identify a person

```yaml
id: F-02
release_history:
  - export: district_x_age_x_rare_condition_count
    local_verdict: aggregate_safe
  - export: district_x_age_x_benefit_status_count
    local_verdict: aggregate_safe
auxiliary_information:
  district_population: 1
attack:
  join: [district, age]
  result: one real subject and benefit status resolved
expected:
  second_export_or_query_gate: BLOCK_COMPOSITION
  subject_resolution_claim: true
  firewall_red: true
forbidden:
  - evaluate_each_export_in_isolation_only
  - anonymized_label_as_permission
```

**Exact pass condition:** the complete controlled release history and declared auxiliary information
make the join visible before release. An incomplete history returns
`FIREWALL_CLAIM_NOT_ESTABLISHED` and refuses the class.

## 4. F-03 — rule-level export is executable against a case

```yaml
id: F-03
artifact:
  class: general_rule_statement
  contents:
    variables: [income, household_size, disability_flag]
    coefficients: [0.8, -0.2, 1.4]
    threshold: 0.65
    output_labels: [eligible, ineligible]
attack:
  apply_to_case: true
expected:
  export_gate: REFUSE_EXPORT
  reason: complete_individual_decision_function
  firewall_red: true
forbidden:
  - classify_as_rule_level_without_parameters
  - rely_on_downstream_attestation
```

**Exact pass condition:** non-executability is assessed behaviorally. Renaming fields or expressing
the function as a table, tree, prompt, or prose does not change the result.

## 5. F-04 — projection narrows a denied use

```yaml
id: F-04
source:
  may_not_use_for:
    - individual_eligibility_determination
    - individual_risk_scoring_or_profiling
projection:
  may_not_use_for:
    - individual_risk_scoring_or_profiling
expected:
  projection_gate: BLOCK_PERMISSION_AMPLIFICATION
  governing_finding: PV-K04
  firewall_red: true
forbidden:
  - editorial_override
  - smaller_projection_means_smaller_denial_set
```

**Exact pass condition:** the projection's denied set is at least the union of every source and
intermediate denial. The source artifact remains unchanged; the projection is rejected.

## 6. F-05 — compliant query sequence reconstructs a determination

```yaml
id: F-05
queries:
  - {question: cohort_rate_for_income_band, local_verdict: allowed}
  - {question: cohort_rate_for_household_size, local_verdict: allowed}
  - {question: threshold_outcome_for_disability_flag, local_verdict: allowed}
  - {question: nearest_cell_difference, local_verdict: allowed}
attack:
  reconstruction: deterministic eligibility outcome for one case
expected:
  transcript_gate: BLOCK_COMPOSITION
  future_query_or_export: REFUSE_EXPORT
  firewall_red: true
forbidden:
  - local_query_pass_implies_sequence_pass
  - delete_prior_queries_from_history
```

**Exact pass condition:** the gate evaluates the complete controlled transcript or returns
`FIREWALL_CLAIM_NOT_ESTABLISHED`. A sequence that reconstructs an individual determination cannot
inherit four local passes.

## 7. F-06 — voluntary returning evidence and silence

```yaml
id: F-06
artifact:
  use_time_detection_required: true
consumer_contract:
  reporting: voluntary
worlds:
  compliant_world: no prohibited use, no report
  violating_world: prohibited individual use, no report
observation_in_both_worlds: no report
expected:
  export_gate: REFUSE_EXPORT
  firewall_claim: FIREWALL_CLAIM_NOT_ESTABLISHED
forbidden:
  - no_report_means_no_use
  - terms_of_use_called_firewall
```

**Exact pass condition:** because the two worlds are observationally identical, no positive firewall
claim is issued. This is an identifiability failure, not an audit inconvenience.

## 8. F-07 — human rubber stamp

```yaml
id: F-07
artifact:
  may_not_use_for: [individual_sanction_or_enforcement]
case_action:
  recommendation: sanction
  human_operator: clicked_approve
counterfactual:
  remove_artifact: no_sanction
expected:
  consumer_gate: BLOCK_PURPOSE
  material_contribution: true
  firewall_red: true
forbidden:
  - human_present_means_not_automated
  - formal_final_decider_only
```

**Exact pass condition:** the counterfactual contribution, not the UI actor, determines use. The
human safeguard belongs to the individual procedure and cannot sanitize the input.

## 9. F-08 — corrected record weakens the restriction

```yaml
id: F-08
predecessor:
  may_not_use_for:
    - individual_eligibility_determination
    - individual_risk_scoring_or_profiling
successor:
  may_not_use_for:
    - individual_risk_scoring_or_profiling
expected:
  correction_interface: BLOCK_PERMISSION_AMPLIFICATION
  predecessor_preserved: true
  firewall_red: true
owner_dependency: PAO-R36
forbidden:
  - correction_as_permission_reset
  - in_place_rewrite
```

**Exact pass condition:** the successor cannot carry a weaker denied-use set. This suite specifies
the interface obligation only; `PAO-R36` owns correction and supersession mechanics.

## 10. F-09 — off-ledger manual use of a readable rule

```yaml
id: F-09
artifact:
  readable_by_operator: true
  individually_actionable_when_memorized: true
boundary:
  screenshot_control: absent
  use_logging: incomplete
attack:
  operator_memorizes_rule_and_applies_it_manually
expected:
  export_gate: REFUSE_EXPORT
  detectability_class: not_detectable_under_declared_boundary
forbidden:
  - downstream_policy_document_as_enforcement
  - post_hoc_sampling_as_complete_evidence
```

**Exact pass condition:** the artifact is refused. The architecture must not claim it can detect the
manual use.

## 11. Suite-level acceptance

The suite passes only when:

1. every fixture produces its exact blocking or bounded result;
2. the checks exercise the real artifact, projection, purpose, controlled history, use event, and
   returning-evidence path rather than marker strings;
3. missing evidence never yields a positive;
4. synonymous and structurally equivalent executable rules are rejected;
5. current-state negatives demonstrate that the pinned repository does not already possess the
   PAO-R4 capability.

Research delivery does not execute or pass this suite. A later implementation claim must run it
against the real owners and include adversarial variants under `P29`, `P31`, `P32`, and `P33`.
