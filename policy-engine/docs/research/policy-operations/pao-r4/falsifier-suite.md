---
title: PAO-R4 — Falsifier suite
research_id: PAO-R4
artifact_role: falsifier-suite
status: research
research_only: true
repository: DenisKopylov/polisyos
baseline_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
authoritative_for:
  - research-only executable specification of firewall falsifiers
  - exact expected semantic outcomes for PAO-R4
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

This suite is an executable **semantic specification**, not an implementation, API, schema, or case
system. A future verifier supplies four functions over real runtime paths:

```text
export_verdict(artifact, request, source_lineage, controlled_history)
consumer_verdict(imported_artifact, declared_purpose, protected_action, material_contribution)
return_reconciliation(issue_records, use_records, protected_action_denominator)
projection_verdict(source_restrictions, projected_restrictions)
```

The evaluator must execute the actual exporter, projection owner, consumer gate, and returning-
evidence reconciliation. Marker-string or constructor-only checks fail pattern **`P29`**.

Canonical research verdicts:

```text
ALLOW_NON_INDIVIDUAL
REFUSE_EXPORT
BLOCK_PURPOSE
BLOCK_PERMISSION_AMPLIFICATION
BLOCK_COMPOSITION
FIREWALL_VIOLATION
FIREWALL_CLAIM_NOT_ESTABLISHED
NOT_ESTABLISHED
NOT_DETECTABLE
```

A test passes only when the exact expected outcome is produced and the stated forbidden outcome is
absent.

## 2. F-01 — commissioned falsifier: population rule used for eligibility

```yaml
case_id: F-01
artifact:
  class: population_predictive_estimate
  proposition: "Within declared cohort R, estimated non-compliance rate is 0.37"
  basis: complete_declared_population_basis
  may_not_use_for: [individual_eligibility_determination]
request:
  consumer: case-system-A
  subject_ref: person-opaque-17
  purpose: individual_eligibility_determination
action:
  type: benefit_denial
  material_contribution: threshold_population_rate_at_0_30
expected:
  export_or_request_gate: BLOCK_PURPOSE
  consumer_gate: BLOCK_PURPOSE
  if_consumed_anyway: FIREWALL_VIOLATION
  returning_evidence_required: true
forbidden:
  - ALLOW_NON_INDIVIDUAL
  - human_review_cures_denied_use
  - population_membership_treated_as_individual_fact
```

**Exact pass condition:** at least one pre-action gate goes red, and a bypass is visible in returning
evidence. If the rule is consumed and every gate remains green, the firewall is falsified.

**Pinned negative comparator:** no individual-purpose vocabulary exists, so the current state has no
required red gate for this use.

## 3. F-02 — two permitted aggregates re-identify a person

```yaml
case_id: F-02
history:
  - export_id: A
    class: aggregate_descriptive_statistic
    cells: [{district: d7, occupation: o3, count: 6, value: 1}]
    initial_verdict: permitted_in_isolation
  - export_id: B
    class: aggregate_descriptive_statistic
    cells: [{district: d7, occupation: o3, age_band: a9, count: 1, value: 1}]
request:
  declared_purpose: programme_planning
auxiliary_information:
  directory_resolves_unique_subject: true
expected:
  export_verdict_B: BLOCK_COMPOSITION
  if_history_or_auxiliary_model_incomplete: NOT_ESTABLISHED
  release_effect: refuse_second_export_or_coarsen_and_retest
forbidden:
  - each_export_safe_therefore_union_safe
  - k_marker_without_composition_evaluation
```

**Exact pass condition:** the proposed release is evaluated against the controlled prefix and known
auxiliary information. Unknown history never inherits safety.

## 4. F-03 — rule-level export is individually executable

```yaml
case_id: F-03
artifact:
  class: general_rule_statement
  text: "Prioritize applicants when score >= 62"
  parameters:
    score: "0.5*income_percentile + 0.3*district_risk + 0.2*household_size"
    threshold: 62
    tie_break: lower_case_id_first
  declared_form: rule_level
request:
  purpose: policy_training
expected:
  export_verdict: REFUSE_EXPORT
  reason: individually_executable_rule
forbidden:
  - allow_because_no_person_row_present
  - allow_because_declared_form_is_rule_level
```

**Exact pass condition:** semantic executability, not the artifact label, controls the verdict. A
rule with sufficient parameters to map case facts to an action is inherently unsafe to cross toward
a case system.

## 5. F-04 — denied use narrowed during projection

```yaml
case_id: F-04
source:
  may_not_use_for:
    - individual_eligibility_determination
    - individual_risk_scoring_or_profiling
    - individual_sanction_or_enforcement
projection:
  may_not_use_for:
    - individual_sanction_or_enforcement
expected:
  projection_verdict: BLOCK_PERMISSION_AMPLIFICATION
  controlling_invariant: PV-K04
forbidden:
  - projection_pass
  - omission_treated_as_editorial_shortening
  - source_denials_replaced_by_surface_default
```

**Exact pass condition:** projected denied uses are a superset of all source and derivation denials.
The test must fail even when every retained claim byte is accurate.

## 6. F-05 — individual determination reconstructed from compliant queries

```yaml
case_id: F-05
queries:
  - "count eligible in district d and age band a"
  - "count eligible in district d and age band a excluding household h"
  - "aggregate score distribution for household type t"
  - "threshold used for programme planning"
individual_queries:
  each_export_verdict: ALLOW_NON_INDIVIDUAL
combined_result:
  unique_subject_resolved: true
  eligibility_determination_reconstructed: true
expected:
  with_complete_transcript: BLOCK_COMPOSITION
  without_complete_transcript: NOT_DETECTABLE
  export_class_disposition_without_transcript: REFUSE_EXPORT
forbidden:
  - all_queries_pass_therefore_sequence_passes
  - unknown_history_treated_as_empty_history
```

**Exact pass condition:** complete controlled history blocks the reconstructing query. If the
boundary cannot make the sequence visible, the class is refused rather than documented as safe.

## 7. F-06 — voluntary returning evidence is silent

```yaml
case_id: F-06
artifact:
  class: population_causal_estimate
  export_requires_use_time_detection: true
consumer_contract:
  returning_evidence: voluntary
observations:
  reports_received: 0
  protected_actions_total: unknown
possible_worlds:
  - compliant_non_use
  - prohibited_use_followed_by_silence
expected:
  export_verdict: REFUSE_EXPORT
  firewall_claim: FIREWALL_CLAIM_NOT_ESTABLISHED
forbidden:
  - no_report_means_no_use
  - terms_of_use_called_firewall
```

**Exact pass condition:** observational equivalence is recognized. Voluntary reporting never
supports a positive firewall claim.

## 8. F-07 — human rubber stamp

```yaml
case_id: F-07
artifact_use:
  subject_resolved: true
  purpose: individual_priority_or_triage
  model_output: rank_1_of_230
human_step:
  reviewer_saw_output: true
  reviewer_changed_output: false
  final_click_by_human: true
counterfactual:
  without_artifact_action_changes: true
expected:
  consumer_gate: BLOCK_PURPOSE
  if_action_occurs: FIREWALL_VIOLATION
forbidden:
  - human_click_breaks_material_contribution
  - formal_finality_only_test
```

**Exact pass condition:** material contribution, not who clicked, determines individual use.

## 9. F-08 — population explanation presented as an individual reason

```yaml
case_id: F-08
population_artifact:
  claim: "Cohort members have higher historical default rates"
case_action:
  outcome: licence_denied
  stated_reason: "Applicants in this cohort present higher default risk"
expected:
  consumer_gate: BLOCK_PURPOSE
  denied_use: individual_reason_generation
  additional_denied_use: individual_risk_scoring_or_profiling
forbidden:
  - population_association_accepted_as_case_specific_ground
  - explanation_link_to_full_report_cures_reason
```

**Exact pass condition:** an individual reason resolves to the actual case facts and competent rule,
not a population association.

## 10. F-09 — correction weakens an individual-use restriction

```yaml
case_id: F-09
predecessor:
  record_id: r1
  may_not_use_for:
    - individual_eligibility_determination
    - individual_risk_scoring_or_profiling
successor:
  record_id: r2
  supersedes: r1
  may_not_use_for:
    - individual_risk_scoring_or_profiling
expected:
  interface_verdict: BLOCK_PERMISSION_AMPLIFICATION
  owner_dependency: PAO-R36
forbidden:
  - later_record_may_silently_relax_denial
  - PAO-R4_defines_correction_mechanism
```

**Exact pass condition:** the successor carries at least the predecessor's individual-use denials.
PAO-R4 states only the interface obligation; `PAO-R36` owns correction mechanics.

## 11. F-10 — synthetic exemplar maps to a real subject

```yaml
case_id: F-10
artifact:
  class: synthetic_exemplar
  rows: [{age: 47, district: d2, rare_job: j19, amount: 8123}]
auxiliary_information:
  unique_real_subject_match: true
request:
  purpose: training
expected:
  export_verdict: REFUSE_EXPORT
  reason: purported_synthetic_record_is_subject_resolvable
forbidden:
  - synthetic_label_overrides_resolution_test
```

**Exact pass condition:** the exemplar's provenance label does not override its actual resolution
risk.

## 12. F-11 — screenshot and off-ledger manual use

```yaml
case_id: F-11
artifact:
  class: individually_actionable_threshold_table
route:
  - authorized_view
  - screenshot
  - manual_case_application
instrumentation:
  screenshot_event: absent
  case_use_event: absent
expected:
  detection_verdict: NOT_DETECTABLE
  export_class_disposition: REFUSE_EXPORT
forbidden:
  - policy_text_treated_as_detection
  - lack_of_event_treated_as_compliance
```

**Exact pass condition:** the architecture says `NOT_DETECTABLE` and refuses the actionable class.
Inventing a downstream observable fails the test.

## 13. F-12 — permitted population planning aggregate

```yaml
case_id: F-12
artifact:
  class: aggregate_descriptive_statistic
  denominator: 182000
  cells:
    - {region: r1, count: 54000, rate: 0.12}
    - {region: r2, count: 61000, rate: 0.09}
    - {region: r3, count: 67000, rate: 0.15}
  subject_keys: none
  executable_case_rule: none
  basis: complete_and_visible
  may_not_use_for: complete_individual_use_set
request:
  purpose: programme_capacity_planning
  consumer: planning-system-P
history:
  composition_safe: established_for_declared_model
expected:
  export_verdict: ALLOW_NON_INDIVIDUAL
  authority_effect: none
  returning_evidence: bounded_planning_use_receipt
forbidden:
  - eligibility_authority
  - case_ranking
  - permission_to_infer_individual_rate
```

**Exact pass condition:** the firewall admits useful population planning while preserving all
individual-use denials. This guards against abstention inertia and overbroad refusal.

## 14. F-13 — incomplete auxiliary-information model

```yaml
case_id: F-13
artifact:
  declared_form: anonymized_aggregate
reconstruction_evaluation:
  known_auxiliary_sources: evaluated
  uncontrolled_external_sources: unknown
  controlled_history_complete: false
expected:
  export_verdict: NOT_ESTABLISHED
  authority_band_effect: REFUSE_EXPORT
forbidden:
  - unknown_defaults_to_safe
  - anonymized_string_treated_as_proof
```

**Exact pass condition:** unknown history or out-of-model channels cannot inherit a safe result,
consistent with **`PV-K06`**.

## 15. F-14 — downstream derivative drops restrictions

```yaml
case_id: F-14
issued_artifact:
  digest: sha256:source
  may_not_use_for: [individual_priority_or_triage, individual_eligibility_determination]
derivative:
  digest: sha256:derived
  source_digest: sha256:source
  may_not_use_for: []
consumer_request:
  purpose: programme_planning
expected:
  consumer_gate: BLOCK_PERMISSION_AMPLIFICATION
  returning_evidence: derivative_violation_record
forbidden:
  - derivative_considered_new_unrestricted_artifact
```

**Exact pass condition:** every derivative carries the union of source restrictions. The violation is
visible at the first governed consumer boundary.

## 16. Suite-level acceptance

A future implementation passes PAO-R4 only if:

1. all fourteen cases produce the exact expected verdicts;
2. F-01 produces a red pre-action gate and a bypass record;
3. F-02 and F-05 evaluate complete history rather than isolated artifacts;
4. F-04, F-09, and F-14 demonstrate denied-use monotonicity;
5. F-06 proves absence is `not_established`, not compliance;
6. F-11 and F-13 retain honest `NOT_DETECTABLE`/`NOT_ESTABLISHED` outcomes;
7. F-12 remains permitted, proving the architecture does not forbid population analysis itself;
8. the tests import and run the real paths rather than checking marker strings.

The pinned repository does not satisfy this suite. The suite authorizes no implementation and no
capability claim.
