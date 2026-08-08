---
title: PAO-R4 — Falsifier suite
research_id: PAO-R4
artifact_role: falsifier-suite
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - amended research-only executable specification of PAO-R4 falsifiers
  - exact detector and expected verdict for each single-world case
  - declaration-falsification and remove-property-keep-markers probes
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# PAO-R4 falsifier suite

## 1. Execution model

This is an executable **semantic specification**, not test code, a schema, an API, a case-management
model, or a product status lattice. A future verifier must exercise the real artifact parser,
semantic classifier, named-history evaluator, projection owner, consumer consultation gate, and
returning-evidence reconciliation.

The required research functions are:

```text
classify_semantics(artifact, source_evidence) -> E | G | X | S | NOT_ESTABLISHED
classify_predicate_provenance(predicate_evidence) ->
    recomputed | independently_reconciled | consumer_asserted |
    institutionally_supplied | not_established
individualizable(artifact, named_history_H) -> true | false | NOT_ESTABLISHED
export_verdict(artifact, request, lineage, named_history_H)
consumer_use_verdict(artifact_ref, subject_ref, protected_action, consultation_event)
return_reconciliation(issue_records, derivative_records, consultation_records,
                      protected_action_denominator)
projection_verdict(source_denials, projected_denials)
```

Marker strings, fixture labels, declared purpose, or a self-reported counterfactual cannot substitute
for the corresponding behavior. This applies `P29`, `P33`, and `P37`.

Local fixture verdicts are not product outcome vocabulary:

```text
ALLOW_NON_INDIVIDUAL
ALLOW_RULE_LEVEL_INPUT
REFUSE_EXPORT
BLOCK_BASIS
BLOCK_PURPOSE
BLOCK_PERMISSION_AMPLIFICATION
BLOCK_COMPOSITION
FIREWALL_VIOLATION
FIREWALL_CLAIM_NOT_ESTABLISHED
NOT_ESTABLISHED
NOT_DETECTABLE
```

Every case below describes one world, names one detector, and has one `expected_verdict`. Conditional
worlds are separate cases.

## 2. Fixture manifest

| Case | Property | Detector | Expected verdict |
|---|---|---|---|
| F-01 | silent allowed-purpose drift into eligibility | consumer consultation gate | `BLOCK_PURPOSE` |
| F-02 | bypass of the F-01 gate | return reconciliation | `FIREWALL_VIOLATION` |
| F-03 | two permitted aggregates reconstruct a subject | named-history export gate | `BLOCK_COMPOSITION` |
| F-04 | aggregate history inventory incomplete | named-history export gate | `NOT_ESTABLISHED` |
| F-05 | Artifact A singleton empirical rate | semantic/individualizability gate | `REFUSE_EXPORT` |
| F-06 | Artifact B deterministic empirical partition | semantic/individualizability gate | `REFUSE_EXPORT` |
| F-07 | Artifact C competent normative rule | semantic/authority-band gate | `ALLOW_RULE_LEVEL_INPUT` |
| F-08 | empirical decision tree using Artifact C syntax | semantic/authority-band gate | `REFUSE_EXPORT` |
| F-09 | projection narrows denied uses | projection gate | `BLOCK_PERMISSION_AMPLIFICATION` |
| F-10 | complete query transcript reconstructs determination | transcript composition gate | `BLOCK_COMPOSITION` |
| F-11 | reconstruction occurs outside any complete transcript | boundary classifier | `NOT_DETECTABLE` |
| F-12 | voluntary channel receives no reports | claim reconciliation | `FIREWALL_CLAIM_NOT_ESTABLISHED` |
| F-13 | voluntary channel receives one incident report | claim reconciliation | `FIREWALL_CLAIM_NOT_ESTABLISHED` |
| F-14 | human rubber stamp after consultation | consumer consultation gate | `BLOCK_PURPOSE` |
| F-15 | population explanation used as individual reason | consumer consultation gate | `BLOCK_PURPOSE` |
| F-16 | corrected record weakens restriction | correction interface gate | `BLOCK_PERMISSION_AMPLIFICATION` |
| F-17 | synthetic exemplar resolves a real subject | semantic/individualizability gate | `REFUSE_EXPORT` |
| F-18 | screenshot/manual application outside instrumentation | boundary classifier | `NOT_DETECTABLE` |
| F-19 | safe large aggregate used for planning | export gate | `ALLOW_NON_INDIVIDUAL` |
| F-20 | false complete-basis declaration retains all markers | predicate-provenance gate | `NOT_ESTABLISHED` |
| F-21 | false “not material” assertion despite consultation | consumer consultation gate | `BLOCK_PURPOSE` |
| F-22 | reference-class shopping for adverse action | consumer consultation gate | `BLOCK_PURPOSE` |
| F-23 | benign purpose synonym masks protected triage | action-effect gate | `BLOCK_PURPOSE` |
| F-24 | lineage disappears through multi-hop relay | governed consumer intake | `NOT_ESTABLISHED` |
| F-25 | controlled derivative drops restrictions | derivative/projection gate | `BLOCK_PERMISSION_AMPLIFICATION` |
| F-26 | semantic class remains mixed or unknown | semantic admission gate | `NOT_ESTABLISHED` |

## 3. F-01 — commissioned falsifier: silent purpose drift

```yaml
case_id: F-01
artifact:
  semantic_class: E
  proposition: "Within cohort R, estimated non-compliance rate is 0.37"
  basis_state: visible
  individualizable_under_H: false
  may_not_use_for: [individual_eligibility_determination]
request:
  declared_purpose: programme_capacity_planning
  consumer: case-system-A
export_event:
  verdict: ALLOW_NON_INDIVIDUAL
later_use:
  subject_ref: person-opaque-17
  protected_action: benefit_eligibility_denial
  consultation: population_rate_thresholded_at_0_30
detector: consumer_consultation_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: protected_action_proceeds
```

The request is truthfully permitted. The red signal must come from the **consumer/use gate**, not the
request or exporter. This is the commissioned word “silently” made executable.

**Remove-property/keep-markers probe:** delete the consumer gate's behavior while retaining the
request purpose, `may_not_use_for`, event fields, and test labels. F-01 must fail because no real
`BLOCK_PURPOSE` is produced. A marker-complete implementation is non-conforming.

## 4. F-02 — bypass of the silent-purpose gate

```yaml
case_id: F-02
artifact_ref: empirical-rate-37
admitted_request_purpose: programme_capacity_planning
subject_ref: person-opaque-17
protected_action: benefit_eligibility_denial
consultation_event: recorded
consumer_gate_event: bypassed
protected_action_event: completed
return_records: complete_and_reconciled
detector: return_reconciliation
expected_verdict: FIREWALL_VIOLATION
forbidden_outcome: bounded_compliance_claim
```

A bypass is a different single world from F-01. The violation record does not retroactively make the
action safe.

## 5. F-03 — aggregate join under complete history

```yaml
case_id: F-03
semantic_class: E
release_history_id: history-complete-03
release_A: {district: d7, occupation: o3, count: 6, value: 1}
release_B: {district: d7, occupation: o3, age_band: a9, count: 1, value: 1}
auxiliary_model_id: directory-model-03
unique_subject_resolution: true
history_inventory_provenance: independently_reconciled
detector: named_history_export_gate
expected_verdict: BLOCK_COMPOSITION
forbidden_outcome: second_release_allowed
```

## 6. F-04 — aggregate history is not established

```yaml
case_id: F-04
semantic_class: E
proposed_release: district_age_aggregate
history_inventory_provenance: consumer_asserted
auxiliary_model_provenance: not_established
detector: named_history_export_gate
expected_verdict: NOT_ESTABLISHED
forbidden_outcome: ALLOW_NON_INDIVIDUAL
```

A declared “complete history” cannot make this case green under `P37`.

## 7. F-05 — Artifact A: singleton empirical rate

```yaml
case_id: F-05
artifact:
  semantic_class_claim: E
  reference_class_predicate: exact_district_age_rare_occupation_filing_minute
  class_cardinality: 1
  empirical_functional: mean_eligibility
  result: 0
named_history_H: independently_reconciled
subject_resolution: true
detector: semantic_individualizability_gate
expected_verdict: REFUSE_EXPORT
forbidden_outcome: aggregate_label_controls
```

The artifact is reclassified X because it reveals a person's outcome.

## 8. F-06 — Artifact B: deterministic empirical partition

```yaml
case_id: F-06
artifact:
  semantic_class_claim: E
  cells: complete_mutually_exclusive_feature_partition
  cell_results: binary_zero_or_one
  case_feature_mapping: total_and_deterministic
named_history_H: independently_reconciled
pointwise_action_mapping: true
detector: semantic_individualizability_gate
expected_verdict: REFUSE_EXPORT
forbidden_outcome: no_person_row_means_safe
```

No explicit identifier, score field, or threshold is needed for pointwise recoverability.

## 9. F-07 — Artifact C: competent normative rule

```yaml
case_id: F-07
artifact:
  semantic_class: G
  rule: "For every applicant x, proven predicate Q(x) entails eligibility"
  executable_parameters: present
source_identity: independently_reconciled
external_authority_competence: institutionally_supplied
request_purpose: rule_level_input
policyos_authority_effect: none
detector: semantic_authority_band_gate
expected_verdict: ALLOW_RULE_LEVEL_INPUT
forbidden_outcome: refused_for_executability
```

This verdict says only that rule-level transport is not prohibited by executability. It does not
establish authority competence, case applicability, fact satisfaction, legal sufficiency, or the
individual determination.

## 10. F-08 — empirical decision tree with Artifact C syntax

```yaml
case_id: F-08
artifact:
  semantic_class: E
  syntax: executable_rule_tree
  variables: [income, district_risk, household_size]
  coefficients: [0.5, 0.3, 0.2]
  threshold: 62
  output: individual_priority
source_identity: empirical_model
pointwise_action_mapping: true
detector: semantic_authority_band_gate
expected_verdict: REFUSE_EXPORT
forbidden_outcome: syntax_matches_normative_rule_therefore_allowed
```

F-07 and F-08 share executable syntax. Semantic class and authority effect produce opposite results.

## 11. F-09 — denied use narrows during projection

```yaml
case_id: F-09
source_denials:
  - individual_eligibility_determination
  - individual_risk_scoring_or_profiling
  - individual_sanction_or_enforcement
projected_denials:
  - individual_sanction_or_enforcement
lineage_state: resolved
detector: projection_gate
expected_verdict: BLOCK_PERMISSION_AMPLIFICATION
forbidden_outcome: projection_pass
```

Controlling invariant: **`PV-K04`**.

## 12. F-10 — complete query transcript reconstructs a determination

```yaml
case_id: F-10
transcript_identity: complete-query-family-10
transcript_provenance: independently_reconciled
queries:
  - count_eligible_in_district_and_age
  - count_excluding_household_h
  - aggregate_score_distribution_for_type_t
  - planning_threshold
combined_effect: unique_subject_and_eligibility_reconstructed
detector: transcript_composition_gate
expected_verdict: BLOCK_COMPOSITION
forbidden_outcome: local_query_passes_compose_to_pass
```

## 13. F-11 — reconstruction outside a complete transcript

```yaml
case_id: F-11
queries: individually_permitted_population_queries
transcript_inventory: absent
reconstructed_individual_action: true
governed_observable: none
detector: boundary_classifier
expected_verdict: NOT_DETECTABLE
forbidden_outcome: complete_non_use_claim
```

`NOT_DETECTABLE` is not permission. The corresponding actionable query class cannot support a
firewall-positive export.

## 14. F-12 — voluntary channel, no reports

```yaml
case_id: F-12
use_time_detection_required: true
returning_channel: voluntary
reports_received: 0
protected_action_denominator: unknown
detector: claim_reconciliation
expected_verdict: FIREWALL_CLAIM_NOT_ESTABLISHED
forbidden_outcome: no_report_means_no_use
```

## 15. F-13 — voluntary channel, one observed incident

```yaml
case_id: F-13
use_time_detection_required: true
returning_channel: voluntary
reports_received: 1
report_integrity: content_bound
protected_action_denominator: unknown
detector: claim_reconciliation
expected_verdict: FIREWALL_CLAIM_NOT_ESTABLISHED
permitted_bounded_claim: one_prohibited_use_was_reported
forbidden_outcome: complete_non_use_or_incidence_rate_claim
```

This is the R11 recovery of value. The observed incident is real; completeness remains unavailable.

## 16. F-14 — human rubber stamp

```yaml
case_id: F-14
semantic_class: E
subject_ref: person-opaque-44
protected_action: individual_priority_or_triage
consultation_event: rank_displayed
human_action: approve_rank
purpose_denied: true
detector: consumer_consultation_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: human_click_cures_use
```

## 17. F-15 — population explanation becomes individual reason

```yaml
case_id: F-15
semantic_class: E
population_claim: cohort_has_higher_default_rate
subject_ref: person-opaque-51
protected_action: licence_denial
consultation_event: population_claim_inserted_as_reason
detector: consumer_consultation_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: report_link_becomes_case_ground
```

## 18. F-16 — correction weakens restriction

```yaml
case_id: F-16
predecessor_denials:
  - individual_eligibility_determination
  - individual_risk_scoring_or_profiling
successor_denials:
  - individual_risk_scoring_or_profiling
supersession_link: resolved
detector: correction_interface_gate
expected_verdict: BLOCK_PERMISSION_AMPLIFICATION
forbidden_outcome: correction_resets_permission
```

This specifies only the PAO-R36 interface obligation; it does not define correction mechanics.

## 19. F-17 — synthetic exemplar resolves a real subject

```yaml
case_id: F-17
semantic_class_claim: S
synthetic_row: {age: 47, district: d2, rare_job: j19, amount: 8123}
named_history_H: independently_reconciled
unique_real_subject_match: true
detector: semantic_individualizability_gate
expected_verdict: REFUSE_EXPORT
forbidden_outcome: synthetic_label_controls
```

## 20. F-18 — screenshot and manual application

```yaml
case_id: F-18
artifact: individually_actionable_empirical_threshold_table
authorized_display: true
screenshot_event: outside_instrumentation
manual_case_application: true
governed_observable: none
detector: boundary_classifier
expected_verdict: NOT_DETECTABLE
forbidden_outcome: lack_of_event_means_compliance
```

## 21. F-19 — permitted aggregate planning use

```yaml
case_id: F-19
artifact:
  semantic_class: E
  denominator: 182000
  cells:
    - {region: r1, count: 54000, rate: 0.12}
    - {region: r2, count: 61000, rate: 0.09}
    - {region: r3, count: 67000, rate: 0.15}
  subject_keys: none
  basis_state: independently_reconciled
  denied_uses: complete_individual_use_set
named_history_H: independently_reconciled
individualizable: false
request_purpose: programme_capacity_planning
detector: export_gate
expected_verdict: ALLOW_NON_INDIVIDUAL
forbidden_outcome: individual_authority_effect
```

This guards the candidate band against abstention inertia.

## 22. F-20 — false complete-basis declaration

```yaml
case_id: F-20
artifact:
  basis_marker: complete
  registered_fields_present: true
  material_selection_assumption_omitted: true
basis_completeness_provenance: institutionally_supplied
detector: predicate_provenance_gate
expected_verdict: NOT_ESTABLISHED
forbidden_outcome: field_presence_grants_export
```

This is the `P37` falsify-the-declaration probe for `B` and `L`.

## 23. F-21 — counterfactual reliance laundering

```yaml
case_id: F-21
semantic_class: E
subject_ref: person-opaque-62
protected_action: sanction
consultation_event: empirical_risk_displayed
operator_materiality_assertion: false
operator_assertion_provenance: consumer_asserted
detector: consumer_consultation_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: self_report_keeps_gate_green
```

The gate turns on consultation, not on the asserted counterfactual. This closes audit Scenario S-2.

## 24. F-22 — reference-class shopping

```yaml
case_id: F-22
semantic_class: E
subject_ref: person-opaque-70
available_cohort_rates: multiple_legitimate_population_rates
selection_event: most_adverse_matching_cohort_chosen_after_case_features_seen
protected_action: enhanced_investigation
consultation_event: selected_rate_used
detector: consumer_consultation_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: each_rate_allowed_therefore_selection_allowed
```

## 25. F-23 — semantic purpose synonym

```yaml
case_id: F-23
semantic_class: E
declared_purpose: workload_balancing
actual_action_effect: delay_one_person_service
canonical_effect_class: individual_priority_or_triage
consultation_event: population_rate_used
detector: action_effect_gate
expected_verdict: BLOCK_PURPOSE
forbidden_outcome: benign_string_controls
```

## 26. F-24 — multi-hop relay loses lineage

```yaml
case_id: F-24
source_artifact: allowed_population_aggregate
relay_system: planning-system-P
relay_output: unlinked_narrative_recommendation
case_consumer: case-system-C
source_digest_at_consumer: absent
protected_action: individual_service_routing
detector: governed_consumer_intake
expected_verdict: NOT_ESTABLISHED
forbidden_outcome: lineage_absence_grants_use
```

The consumer cannot treat an unresolved relay as a fresh unrestricted artifact.

## 27. F-25 — controlled derivative drops restrictions

```yaml
case_id: F-25
source_digest: sha256-source
source_denials:
  - individual_priority_or_triage
  - individual_eligibility_determination
derivative_digest: sha256-derived
derivative_source_link: resolved
derivative_denials: []
detector: derivative_projection_gate
expected_verdict: BLOCK_PERMISSION_AMPLIFICATION
forbidden_outcome: derivative_resets_permission
```

## 28. F-26 — mixed semantic class

```yaml
case_id: F-26
artifact:
  normative_rule_source: unresolved
  empirical_coefficients: present
  case_action_output: present
semantic_class_evidence: conflicting
detector: semantic_admission_gate
expected_verdict: NOT_ESTABLISHED
forbidden_outcome: default_to_G_or_E
```

## 29. Suite-level conformance requirements

A later implementation conforms only when:

1. every manifest row produces its single exact verdict through the named real detector;
2. F-01 cannot be satisfied by request-time purpose checks;
3. deleting the real consumer-gate property while keeping marker strings makes F-01 fail;
4. F-05 and F-06 refuse audit Artifacts A and B;
5. F-07 permits candidate-band rule input and F-08 refuses the identical-syntax empirical decision
   tree, proving executability is not the predicate;
6. F-20 remains non-positive after a false declaration retains every completeness marker;
7. F-21 blocks on consultation despite a false “not material” assertion;
8. F-22 through F-24 close reference-class shopping, semantic-purpose relabeling, and relay lineage
   disappearance;
9. no conditional or disjunctive expected field is used; and
10. the repository capability and owner standing remain `absent/unallocated` until the real chain is
    independently demonstrated.

The amended research does not execute or pass this suite. Adoption remains `NO_GO` pending independent
conformance verification at an exact commit.
