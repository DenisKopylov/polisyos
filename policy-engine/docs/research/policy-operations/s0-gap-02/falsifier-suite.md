---
title: S0-GAP-02 — Independence and oracle-custody falsifier suite
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: accepted_narrow_scope
authoritative_for:
  - research-only executable falsifier cases and exact expected outcomes
  - architecture acceptance probes, including the seeded shared-reducer fault
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner, evaluator, custodian or vendor appointment
  - reviewer panel or evaluator-team appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal-sufficiency conclusion
  - permission to score OPS-R15
  - claim that OPS-R15 is unblocked
  - automatic amendment of any plan, backlog or system-design decision
---

# Independence and oracle-custody falsifier suite

## 1. Purpose and standing

These are architecture falsifiers, not OPS-R15 scores. A conforming future harness should be able to instantiate each case and assert the exact observations below. The uppercase outcome tokens are test-harness assertions local to this research package; they are not product statuses and do not create a new status lattice.

The commission’s six cases are `F-01` through `F-06`. Additional attacks constructed here are `A-07` through `A-13`. `F-04` is the discriminating test: if a shared reducer defect survives both independent channels, the claimed architecture is false even when all same-code consistency checks are green.

## 2. Harness observation vocabulary

```yaml
HarnessOutcome:
  ARCHITECTURE_DETECTED: a prohibited condition was positively found
  RUN_INVALID: the run cannot support any bounded verification claim
  VERIFICATION_BLOCKED: semantic or integrity prerequisites are unsatisfied
  CONTROL_ONLY_PASS: the same-code diagnostic agreed but has no verification weight
  HISTORY_VIOLATION_DETECTED: an immutable prior binding was challenged or altered
  DISSENT_PRESERVED: conflict, dissent, abstention, or disagreement remains in evidence
  ARCHITECTURE_FALSIFIED: the design failed a required discriminating probe
  TEST_SETUP_INVALID: the falsifier was not instantiated as specified
```

A test passes when the harness produces the specified expected observations. “Run invalid” here means only that the evidence package cannot support the bounded benchmark claim.

## 3. Common harness inputs

```yaml
FalsifierCase:
  case_id: stable_identifier
  target_failure_mode: stable_identifier
  fixture_and_seed_digests: [digest]
  implementation_artifact_digest: digest
  same_code_control_digest: digest
  evaluator_r_digest: digest
  evaluator_p_digest: digest
  generator_digest: digest
  expectation_commitment: digest
  access_log_head: digest
  injected_condition: declarative_fault_or_attack
  expected_observations: [HarnessAssertion]
  forbidden_observations: [HarnessAssertion]
  evidence_requirements: [stable_identifier]
```

Each result binds all artifacts and the fault-injection patch/fixture digest. A narrative claim that a fault was injected is insufficient.

## 4. Commissioned falsifiers

### F-01 — prohibited implementation semantic import

**Commissioned condition:** the evaluator imports implementation admission, reducers, dependency traversal, or status projection.

```yaml
case_id: F-01
setup:
  - build evaluator-R with a direct import of product admission logic
  - build evaluator-P with a transitive plugin import of product status projection
  - record static imports, dynamic module loads, SBOMs, generated-file provenance, and network calls
execution:
  - run provenance gate before any fixture evaluation
expected:
  provenance_gate: violated
  offending_ancestors:
    - product_admission_module
    - product_status_projection_module
  combined_outcomes:
    - ARCHITECTURE_DETECTED
    - RUN_INVALID
forbidden:
  - VERIFICATION_CLAIM_EMITTED
  - offending_import_treated_as_allowed_neutral_substrate
```

**Exact pass condition for the falsifier:** both the direct and transitive paths are named in evidence; the run is rejected before semantic results are aggregated. Missing the transitive path fails this falsifier.

**Rationale:** `S0-K14` expressly disallows shared admission, reducers, traversal, and projection for the scoring oracle. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:143-199@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K14`.)

### F-02 — implementation-visible expected actions or labels

**Commissioned condition:** implementation-visible files expose expected actions or labels.

```yaml
case_id: F-02
setup:
  - place fields named expected_action and expected_status in one public fixture
  - place a prose expected trace in an implementation build-context document
  - encode a third label through an opaque-looking lookup table whose provenance names the expectation source
execution:
  - run field-name lint, semantic text scan, entropy/dictionary probe, and provenance scan
expected:
  leak_findings: 3
  combined_outcomes:
    - ARCHITECTURE_DETECTED
    - RUN_INVALID
forbidden:
  - leak_redacted_after_implementation_freeze_and_run_retained
  - fixture_used_for_bounded_claim
```

**Exact pass condition:** all three leak channels are detected before submission or, if discovered later, every exposed run is challenged and cannot support a bounded claim.

The in-tree grounding benchmark and semantic fixture owners contain visible expected fields/signals, demonstrating that production-test formats cannot be reused unchanged. (`policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:90-140@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

### F-03 — ID-renumbered and adjacent unseen case changes without semantic reason

**Commissioned condition:** an ID-renumbered or adjacent unseen case changes the outcome without a semantic reason.

```yaml
case_id: F-03
setup:
  base_fixture: committed_fixture_x
  mutations:
    - bijective_alpha_rename_all_opaque_ids
    - perturb_declared_irrelevant_metadata
    - move_boundary_value_within_same_declared_interval_side
  relation: semantic_output_isomorphic_or_equal
execution:
  - freeze implementation before mutation seed reveal
  - run base and all three mutations
expected:
  mutation_certificates_valid: true
  evaluator_r_relation: violated
  evaluator_p_relation: violated
  combined_outcomes:
    - VERIFICATION_BLOCKED
forbidden:
  - changed_output_accepted_because_each_case_has_a_visible_label
  - mutation_removed_from_population_after_failure
```

**Exact pass condition:** the harness identifies the smallest relation witness that differs and proves that no declared semantic dimension changed. If the mutation certificate is invalid, the result is `TEST_SETUP_INVALID`, not an implementation finding.

### F-04 — seeded shared reducer fault passes incremental and clean-build checks

**Commissioned and discriminating condition:** a seeded shared reducer fault passes both incremental and clean-build checks.

#### Seed

Use a synthetic affected-set scenario with three declared subjects. Inject into the product reducer shared by incremental execution and clean rebuild:

```text
fault_delta: reported_affected_count := correct_affected_count + 100
```

The raw trace must expose the reported count and affected subject IDs. Evaluator `R_v` independently derives the graph closure; evaluator `P_v` independently checks both cardinality consistency and the bound `affected_count <= declared_subject_count`.

```yaml
case_id: F-04
setup:
  declared_subject_count: 3
  independently_correct_affected_set: [s1, s2, s3]
  independently_correct_count: 3
  shared_product_fault_output_count: 103
execution:
  incremental_product_output_count: 103
  clean_rebuild_output_count: 103
expected:
  same_code_control:
    parity: true
    outcome: CONTROL_ONLY_PASS
  evaluator_r:
    derived_count: 3
    result: violated
  evaluator_p:
    predicate_cardinality_matches_set: violated
    predicate_count_within_declared_subjects: violated
  combined_outcomes:
    - VERIFICATION_BLOCKED
forbidden:
  - same_code_parity_used_as_correctness
  - bounded_verification_claim_emitted
architecture_failure_condition:
  if_evaluator_r_and_evaluator_p_both_accept: ARCHITECTURE_FALSIFIED
```

**Exact pass condition:** incremental and clean-build paths agree on the wrong value, producing `CONTROL_ONLY_PASS`; both independent channels reject; combined verification is blocked. If either independent channel was implemented from the shared product reducer, `F-01` also fires. If both independent channels accept 103 despite valid setup, output is exactly `ARCHITECTURE_FALSIFIED`.

The prior OPS-R15 probe demonstrated the same logical shape: a faulty reducer produced `3` in both incremental and rebuild paths while an independent correct result was `103`. (`policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:1-80@1a7a2d05ebba22fae80e9934329e4b880806588e`.) This falsifier reverses the numbers only to make the cardinality property self-evident; no repository semantic claim depends on the numbers.

### F-05 — oracle correction silently changes a prior run

**Commissioned condition:** an oracle correction silently changes a prior scored run.

```yaml
case_id: F-05
setup:
  old_expectation_digest: O_v
  old_receipt_digest: Q_v_bound_to_O_v
  corrected_expectation_digest: O_v_plus_1
  supersession_record: absent_initially
attack:
  - replace the expectation pointer used to display Q_v with O_v_plus_1
  - leave Q_v identifier and displayed run time unchanged
execution:
  - verify receipt bindings, Merkle inclusion, log consistency, and supersession graph
expected:
  receipt_binding_mismatch: true
  combined_outcomes:
    - ARCHITECTURE_DETECTED
    - HISTORY_VIOLATION_DETECTED
    - RUN_INVALID
  preservation:
    - Q_v remains retrievable with O_v
    - O_v_plus_1 requires a new commitment and supersession record
forbidden:
  - Q_v_recomputed_in_place
  - old_run_displayed_as_if_evaluated_against_O_v_plus_1
```

**Exact pass condition:** substitution is detected cryptographically and historically; the old receipt is preserved; no old result is silently changed.

### F-06 — reviewer conflict, abstention, dissent, or evaluator disagreement discarded

**Commissioned condition:** reviewer conflict, abstention, or disagreement is discarded.

```yaml
case_id: F-06
setup:
  reviewer_positions:
    - {id: p1, value: supports}
    - {id: p2, value: dissents}
    - {id: p3, value: abstains}
    - {id: p4, value: conflict_recusal}
  evaluator_results:
    R: compatible
    P: violated
attack:
  - construct receipt omitting p2, p3, p4
  - replace evaluator disagreement with majority_acceptable
execution:
  - compare committed reviewer-record root, evaluator observations, and receipt contents
expected:
  omitted_records_detected: [p2, p3, p4]
  evaluator_disagreement_detected: true
  combined_outcomes:
    - ARCHITECTURE_DETECTED
    - DISSENT_PRESERVED
    - VERIFICATION_BLOCKED
    - RUN_INVALID
forbidden:
  - abstention_counted_as_support
  - recusal_removed_from_denominator
  - evaluator_disagreement_resolved_by_unplanned_majority_vote
```

**Exact pass condition:** every original position remains retrievable and bound to the run; the attempted omission invalidates the receipt. This operationalizes `S0-K15`. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K15`.)

## 5. Additional attacks constructed by S0-GAP-02

### A-07 — generated semantic artifact laundering

**Attack:** evaluators avoid direct product imports but consume a generated schema, lookup table, compiled ruleset, snapshot, or model derived from product admission/reducer/projection behavior.

```yaml
case_id: A-07
setup:
  product_generated_artifact: generated/status_map.json
  evaluator_import: generated/status_map.json
  direct_product_imports: none
  provenance_edge: product_projection_source -> generator -> status_map -> evaluator
expected:
  provenance_gate: violated
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - generated_artifact_treated_as_neutral_because_file_extension_is_json
```

**Exact pass condition:** the transitive provenance edge is named and the evaluator artifact is rejected. Import lint alone is insufficient.

### A-08 — poisoned “neutral” helper

**Attack:** both product and evaluators share a helper marketed as canonicalization, but it folds aliases into product statuses, orders events by product priority, or computes dependency closure.

```yaml
case_id: A-08
setup:
  shared_helper_name: neutral_normalizer
  hidden_semantic_behavior:
    - product_status_alias_mapping
    - dependency_closure
  shared_by: [implementation, evaluator_R, evaluator_P]
expected:
  helper_reclassified_as_semantic: true
  shared_provenance_violation: true
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - helper_allowed_based_on_package_name_or_team_ownership
```

**Exact pass condition:** behavioral inspection or conformance probes expose both semantic functions; all affected evaluator versions are invalidated.

### A-09 — canonicalization and parser split-view

**Attack:** the commitment operator and evaluator parse equivalent-looking bytes differently—for example duplicate keys, number normalization, Unicode normalization, or map ordering—allowing one plaintext to be committed and another to be evaluated.

```yaml
case_id: A-09
setup:
  adversarial_documents:
    - duplicate_key_document
    - non_I_JSON_number_document
    - unicode_confusable_document
    - alternate_map_order_document
execution:
  - canonicalize and parse independently at commitment, evaluator-R, evaluator-P, and challenge verifier
expected:
  duplicate_key_document: rejected
  non_I_JSON_number_document: rejected_or_identical_under_declared_profile
  unicode_confusable_document: explicit_byte_and_codepoint_witness
  alternate_map_order_document: identical_commitment
  combined_outcomes_on_any_split_view: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - evaluator_uses_a_plaintext_not_bound_by_the_published_commitment
```

**Exact pass condition:** all accepted documents yield one canonical byte sequence and digest; ambiguous documents are rejected before sealing.

### A-10 — selective mutation suppression

**Attack:** the run operator drops failed generated cases and reports only the passing subset.

```yaml
case_id: A-10
setup:
  committed_population_count: 120
  valid_generated_count: 120
  executed_count: 120
attack:
  reported_count: 117
  omitted_case_results: [failed, failed, evaluator_disagreement]
expected:
  population_digest_mismatch: true
  omitted_fixture_digests_named: 3
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - denominator_redefined_after_execution
  - omitted_cases_labeled_unsupported_without_predeclared_rule
```

**Exact pass condition:** the receipt verifier detects all omissions and refuses population-level aggregation.

### A-11 — adaptive hidden-oracle inference

**Attack:** an implementation team submits repeated near-identical revisions or queries a comparison endpoint until it infers hidden expectations.

```yaml
case_id: A-11
setup:
  predeclared_query_budget: 1_final_submission
  hidden_population_epoch: epoch_7
attack:
  submissions_in_epoch: 25
  response_detail: per_fixture_predicate_failures
expected:
  budget_violation: true
  population_compromised: true
  affected_runs_challenged: all_epoch_7_runs_after_first_disclosure
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - later_submission_claimed_independent_against_same_population
```

**Exact pass condition:** the access/submission logs expose the adaptive sequence; the hidden population is retired or challenged under the predeclared leakage policy.

### A-12 — split-view append-only log or rotation truncation

**Attack:** different observers receive different log histories, or key rotation omits an earlier access event.

```yaml
case_id: A-12
setup:
  witness_A_tree_head: {size: 900, root: root_A}
  witness_B_tree_head: {size: 900, root: root_B}
  root_A_not_equal_root_B: true
  omitted_event: plaintext_expectation_read_before_rotation
execution:
  - exchange signed tree heads
  - request inclusion and consistency proofs
expected:
  equivocation_or_gap_detected: true
  omitted_access_event_preserved_as_challenge_evidence: true
  affected_runs: VERIFICATION_BLOCKED
  combined_outcomes:
    - ARCHITECTURE_DETECTED
    - HISTORY_VIOLATION_DETECTED
    - RUN_INVALID
forbidden:
  - key_rotation_treated_as_permission_to_reset_history
```

**Exact pass condition:** inconsistent equal-size roots or missing consistency proofs cause a public integrity finding and invalidate affected receipts.

### A-13 — correlated evaluator derivation disguised as diversity

**Attack:** `R_v` and `P_v` use different languages but were generated from the same private pseudocode, prompt transcript, or product-authored semantic notes.

```yaml
case_id: A-13
setup:
  evaluator_languages: [language_A, language_B]
  common_private_derivation_digest: D_private
  common_derivation_not_in_public_B: true
execution:
  - inspect authorship attestations, derivation records, document provenance, and source similarity
expected:
  structural_diversity_claim: rejected
  shared_semantic_ancestor: D_private
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - independence_accepted_based_only_on_language_or_repository_difference
```

**Exact pass condition:** the shared private semantic ancestor is identified; both evaluators must be independently re-derived or the architecture remains invalid for the window.

## 6. Machine-readable suite index

```yaml
suite_id: S0-GAP-02-FALSIFIERS-1
required_cases:
  - F-01
  - F-02
  - F-03
  - F-04
  - F-05
  - F-06
  - A-07
  - A-08
  - A-09
  - A-10
  - A-11
  - A-12
  - A-13
architecture_acceptance_rule:
  all_cases_instantiated: true
  all_expected_observations_matched: true
  no_forbidden_observation_present: true
  F-04_if_both_independent_channels_accept: ARCHITECTURE_FALSIFIED
  missing_case_policy: TEST_SETUP_INVALID_AND_ACCEPTANCE_WITHHELD
```

## 7. Evidence bundle per falsifier

Every execution retains:

- base artifact and injected-fault/attack digests;
- exact build and run recipes;
- static imports, dynamic loads, network calls, SBOMs, and provenance graph;
- public fixture, mutation certificate, and hidden seed commitment where applicable;
- raw implementation traces and same-code control report;
- both independent evaluator observations;
- expectation commitment/inclusion evidence;
- access and append-only log proofs;
- reviewer conflicts, dissent, abstention, recusal, and adjudication records;
- harness assertion results and signatures.

A screenshot, prose summary, or same-code unit test alone does not satisfy a falsifier.

## 8. Interpretation

Passing this suite would support only the proposition that the named architecture instance detected the seeded attacks under the named artifacts and environment. It would not establish general independence, legal correctness, institutional competence, or OPS-R15 passage. Failure of `F-04`, `F-01`, or `F-02` is especially dispositive because it recreates the circularity or leakage that `S0-K14` was ratified to prevent.
