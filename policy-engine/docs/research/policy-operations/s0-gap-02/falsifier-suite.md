---
title: S0-GAP-02 — Independence and oracle-custody falsifier suite
status: research
research_only: true
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_tree_equivalent_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
audited_commit: a7c34cc40b649a10b6878228a8a57acc498f279a
audit_commit: 3abbaf8c2808e31fd7d8f9929b696e78dc91b3d4
amendment_branch: research/s0-gap-02-amendment
amendment_status: audit_amended
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

These are architecture falsifiers, not OPS-R15 scores. A conforming future harness instantiates every case and asserts the exact expected and forbidden observations. The uppercase tokens below are benchmark-local evidence assertions and negative completions; they are not product statuses, do not create a status lattice, and do not activate a fourth constitutional outcome-vocabulary element.

The commissioned cases are `F-01`–`F-06`. The original additional attacks are `A-07`–`A-13`. The audit amendment adds `A-14`–`A-21`. `F-04` remains self-directed and dispositive against product-side circularity; `A-14` separately prevents agreement under a bad shared specification from being called acceptable custody semantics.

```yaml
HarnessOutcome:
  ARCHITECTURE_DETECTED: prohibited architecture condition positively found
  RUN_INVALID: run cannot support a bounded verification claim
  VERIFICATION_BLOCKED: semantic, specification, challenge, or integrity prerequisite absent
  CONTROL_ONLY_PASS: same-code diagnostic agreed and has zero verification weight
  HISTORY_VIOLATION_DETECTED: immutable prior binding or append-only history violated
  DISSENT_PRESERVED: raw conflict, dissent, abstention, recusal, or disagreement retained
  ARCHITECTURE_FALSIFIED: a required discriminating probe defeated the claimed design
  TEST_SETUP_INVALID: falsifier was not instantiated as specified
EvidenceTerminal:
  SPECIFICATION_ASSURANCE_NOT_ESTABLISHED: shared B/O truth not established
  INDEPENDENCE_NOT_ESTABLISHED: decisive independence premise unreconciled or institutionally absent
  EVALUATOR_COVERAGE_NOT_ESTABLISHED: discriminator witness absent, removed, neutralized, or ineffective
```

The evidence terminals are `INT-K08` negative completions. They withhold or degrade a claim; they never authorize a weaker positive. (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:190-235@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `INT-K08`.)

## 2. Common harness contract

```yaml
FalsifierCase:
  case_id: stable_identifier
  target_failure_mode: stable_identifier
  fixture_and_seed_digests: [digest]
  implementation_artifact_digest: digest
  same_code_control_digest: digest
  evaluator_r_digest: digest
  evaluator_p_digest: digest
  generator_digest: digest | null
  relation_validator_digest: digest | null
  expectation_commitment: digest
  predicate_provenance_register_digest: digest
  access_reconciliation_digest: digest
  injected_condition: declarative_fault_or_attack
  expected_observations: [HarnessAssertion]
  forbidden_observations: [HarnessAssertion]
  evidence_requirements: [stable_identifier]
```

Each execution binds exact source/build/run artifacts, injected patch or fixture digest, static and dynamic provenance, network calls, P37 predicate classes, raw traces, evaluator observations, access heads, reviewer/proficiency evidence, challenges, and signatures. A prose assertion that the fault was injected is insufficient.

## 3. Commissioned falsifiers

### F-01 — prohibited implementation semantic import

```yaml
case_id: F-01
setup:
  evaluator_R: direct_import(product_admission)
  evaluator_P: transitive_plugin_import(product_status_projection)
execution:
  - inspect source, generated files, SBOM, dynamic loads, and network calls
  - run provenance gate before fixtures
expected:
  direct_and_transitive_ancestors_named: true
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - VERIFICATION_CLAIM_EMITTED
  - semantic_import_reclassified_as_neutral_by_name
```

The case passes only when both paths are named and rejected before semantic aggregation. It operationalizes `S0-K14` rather than merely citing it.

### F-02 — implementation-visible expected actions or labels

```yaml
case_id: F-02
setup:
  public_fixture_field: expected_action
  implementation_document: prose_expected_trace
  opaque_lookup_table: expectation_derived_label_map
execution:
  - run field lint, semantic text scan, dictionary/entropy probe, and provenance scan
expected:
  leak_channels_named: 3
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - post_freeze_redaction_restores_run
  - exposed_fixture_supports_bounded_claim
```

### F-03 — ID-renumbered or adjacent unseen case changes without semantic reason

```yaml
case_id: F-03
setup:
  mutations:
    - bijective_opaque_id_rename
    - declared_irrelevant_metadata_perturbation
    - same_side_temporal_boundary_shift
  expected_relation: semantic_output_isomorphic_or_equal
execution:
  - freeze implementation before mutation seed reveal
  - run base and all mutations
expected:
  mutation_certificates_valid: true
  unexplained_relation_change_detected: true
  combined_outcomes: [VERIFICATION_BLOCKED]
forbidden:
  - visible_case_label_overrides_relation_failure
  - failed_mutation_removed_from_denominator
```

An invalid mutation certificate yields `TEST_SETUP_INVALID`, not an implementation failure.

### F-04 — seeded shared reducer fault passes incremental and clean-build checks

Use a synthetic affected-set case with three subjects. Inject into the product reducer shared by incremental execution and `C`:

```text
reported_affected_count := correct_affected_count + 100
```

```yaml
case_id: F-04
setup:
  declared_subject_count: 3
  correct_affected_set: [s1, s2, s3]
  correct_count: 3
  product_incremental_count: 103
  product_clean_rebuild_count: 103
  discriminator_witness:
    seed_digest: sha256:fault-delta
    expected_semantic_delta: {field: affected_count, baseline: 3, mutated: 103}
    named_discriminators:
      - R-AFFECTED-CLOSURE-COUNT
      - P-CARDINALITY-MATCHES-SET
      - P-COUNT-WITHIN-DECLARED-SUBJECTS
execution:
  - run C parity
  - run intact R/P discriminators
  - remove P-CARDINALITY-MATCHES-SET
  - neutralize P-COUNT-WITHIN-DECLARED-SUBJECTS to constant_true
expected:
  same_code_control: {parity: true, outcome: CONTROL_ONLY_PASS}
  intact_release:
    evaluator_R: violated
    evaluator_P: violated
    verification: blocked
  removal_probe:
    release_admitted: false
    evidence_terminal: EVALUATOR_COVERAGE_NOT_ESTABLISHED
  neutralization_probe:
    adequacy_gate: violated
    evidence_terminal: EVALUATOR_COVERAGE_NOT_ESTABLISHED
forbidden:
  - C_agreement_contributes_to_W_or_V_custody
  - removed_or_neutralized_discriminator_allows_acceptance
```

**Architecture self-test:** with intact valid setup and independently correct discriminators, force both `R_v` and `P_v` to accept the wrong value `103`. Required result:

```yaml
both_independent_channels_accept_wrong_value: true
exact_outcome: ARCHITECTURE_FALSIFIED
passage_sentence_rendered: false
```

Nothing elsewhere may soften this result.

### F-05 — oracle correction silently changes a prior run

```yaml
case_id: F-05
setup:
  prior_receipt: Q_old
  bound_expectation: O_v
attack:
  substitute_expectation: O_v_plus_1
  preserve_old_receipt_id: true
execution:
  - verify canonical bytes, commitment, inclusion proof, version, and supersession history
expected:
  digest_or_version_mismatch: true
  old_receipt_still_bound_to_O_v: true
  combined_outcomes: [HISTORY_VIOLATION_DETECTED, RUN_INVALID]
forbidden:
  - silent_rescore_of_Q_old
  - old_receipt_rebound_to_corrected_bundle
```

### F-06 — reviewer conflict, abstention, dissent, recusal, or evaluator disagreement discarded

```yaml
case_id: F-06
setup:
  assigned_positions:
    - supports
    - dissents
    - abstains
    - conflict_recusal
  evaluator_disagreement: true
attack:
  published_record_contains: [supports]
execution:
  - compare assignments, signed positions, proficiency records, adjudication, and receipt
expected:
  omitted_records_named: 3
  evaluator_disagreement_preserved: true
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID, DISSENT_PRESERVED]
forbidden:
  - abstention_converted_to_assent
  - dissent_removed_after_adjudication
  - evaluator_disagreement_majority_voted_away
```

## 4. Original additional attacks

### A-07 — generated semantic artifact laundering

```yaml
case_id: A-07
setup:
  product_generated_artifact: generated/status_map.json
  evaluator_import: generated/status_map.json
  provenance_edge: product_projection -> generator -> status_map -> evaluator
expected:
  transitive_edge_named: true
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - json_or_generated_artifact_treated_as_neutral_by_extension
```

### A-08 — poisoned “neutral” helper and falsify-the-declaration probe

```yaml
case_id: A-08
semantic_families:
  - admission
  - transition_reduction
  - dependency_traversal
  - affected_set
  - status_projection
  - authority_projection
  - ambiguity_collapse
  - identifier_branching
  - temporal_ordering
for_each_family:
  declaration_and_allowlist_entry_unchanged: true
  poison: one_family_specific_answer_producing_behavior
execution:
  - run transitive provenance, behavioral vectors, runtime telemetry, and independent review
expected_for_each_family:
  answer_neutral: false
  declaration_class: consumer_asserted   # sub-annotation: attested
  behavioral_probe_class: recomputed
  runtime_envelope_class: independently_reconciled   # sub-annotation: machine_observed; not_established if the trace is producer-retained
  review_class: independently_reconciled
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - attested_neutrality_rendered_as_machine_proved
  - gate_green_because_declaration_is_green
```

All nine poisons must make the gate red. Missing one family fails this falsifier under `P37`.

### A-09 — canonicalization/parser split view

```yaml
case_id: A-09
setup:
  adversarial_documents:
    - duplicate_key_document
    - non_I_JSON_number_document
    - unicode_confusable_document
    - alternate_map_order_document
execution:
  - canonicalize and parse independently at commitment, R, P, and challenge verifier
expected:
  duplicate_keys: rejected
  non_I_JSON_numbers: rejected_or_identical_under_profile
  unicode: explicit_byte_and_codepoint_witness
  alternate_map_order: identical_commitment
  any_split_view: RUN_INVALID
forbidden:
  - evaluated_plaintext_not_bound_by_commitment
```

### A-10 — selective mutation suppression

```yaml
case_id: A-10
setup:
  committed_valid_population: 120
  executed_population: 120
attack:
  reported_population: 117
  omitted_results: [failed, failed, evaluator_disagreement]
expected:
  population_digest_mismatch: true
  omitted_fixture_count: 3
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - denominator_redefined_after_execution
  - post_hoc_unsupported_label
```

### A-11 — adaptive hidden-oracle inference

```yaml
case_id: A-11
setup:
  submission_budget: 1_final_submission
  hidden_epoch: epoch_7
attack:
  submissions: 25
  response_detail: per_fixture_predicate_failures
expected:
  budget_violation: true
  population_compromised: true
  affected_runs_challenged: all_after_first_disclosure
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - later_submission_claimed_independent_against_same_population
```

### A-12 — split-view log or rotation truncation

```yaml
case_id: A-12
setup:
  witness_A: {size: 900, root: root_A}
  witness_B: {size: 900, root: root_B}
  roots_differ: true
  omitted_event: plaintext_expectation_read_before_rotation
execution:
  - exchange signed heads and request inclusion/consistency proofs
expected:
  equivocation_or_gap_detected: true
  omitted_event_preserved: true
  combined_outcomes: [ARCHITECTURE_DETECTED, HISTORY_VIOLATION_DETECTED, RUN_INVALID]
forbidden:
  - rotation_resets_history
```

### A-13 — correlated derivation disguised as diversity

```yaml
case_id: A-13
setup:
  evaluator_languages: [language_A, language_B]
  common_private_derivation_digest: D_private
  common_derivation_absent_from_public_B: true
execution:
  - inspect authorship, derivation records, document provenance, and source similarity
expected:
  structural_diversity_claim: rejected
  shared_semantic_ancestor: D_private
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - independence_accepted_from_language_or_repository_difference
```

## 5. Audit-amendment attacks

### A-14 — shared specification/expectation defect

```yaml
case_id: A-14
setup:
  seeded_bad_axiom:
    proposition: expired_delegation_remains_valid_for_publication
    seeded_truth: false
  B_contains_seed: true
  O_v_derived_from_seed: true
  implementation_matches_B: true
  R_and_P_independent_code: true
execution:
  product_trace: publication_allowed_after_expiry
  evaluator_R: accept
  evaluator_P: accept
  implementation_provenance_gates: pass
  blinded_specification_probe: detects_seed
expected:
  implementation_statement: not_refuted_under_committed_specification
  custody_semantics_claim: withheld
  evidence_terminal: SPECIFICATION_ASSURANCE_NOT_ESTABLISHED
  challenge_required: true
  combined_outcomes: [VERIFICATION_BLOCKED, DISSENT_PRESERVED]
forbidden:
  - acceptable_custody_semantics_established
  - bounded_passage_sentence_rendered
  - terminal_presented_as_new_outcome_vocabulary
```

### A-15 — generator/evaluator common private relation ancestor

```yaml
case_id: A-15
setup:
  generator_private_table: sha256:bad-relation-table
  relation_validator_private_table: sha256:bad-relation-table
  evaluator_P_private_table: sha256:bad-relation-table
  public_relation_does_not_contain_table: true
execution:
  - inspect source, generated files, SBOM, network, authorship, and poisoned relation vector
expected:
  shared_private_semantic_ancestor: detected
  product_execution_started: false
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - generated_case_scored
  - package_or_language_difference_accepted_as_independence
```

### A-16 — competent unanimous reviewer misconception

```yaml
case_id: A-16
setup:
  reviewers: [r1, r2, r3]
  eligibility_and_conflicts: valid
  positions: [supports, supports, supports]
  blinded_specification_seed: AX-BAD-EXPIRY-01
execution:
  proficiency_results: {r1: missed, r2: missed, r3: missed}
expected:
  unanimity_accepted_as_truth: false
  evidence_terminal: SPECIFICATION_ASSURANCE_NOT_ESTABLISHED
  combined_outcomes: [VERIFICATION_BLOCKED]
forbidden:
  - unanimity_satisfies_S_v
  - missed_seed_deleted
```

### A-17 — undeclared private semantic ancestor

```yaml
case_id: A-17
setup:
  declarations_report_shared_ancestor: false
  copied_private_table_digest: sha256:hidden-table
execution:
  - compare repository history, generated artifacts, build caches, SBOM, and network provenance
  - run poisoned generated-table vector
expected:
  declaration_only_gate: insufficient
  forensic_gap: detected_or_unresolved
  combined_outcomes: [RUN_INVALID]
  unresolved_gap_terminal: INDEPENDENCE_NOT_ESTABLISHED
forbidden:
  - independence_accepted_from_attestation_alone
```

### A-18 — universal expectation bundle

```yaml
case_id: A-18
setup:
  finite_trace_domain: bounded_synthetic_trace_domain_v1
  positive: event_count >= 0
  negative: event_type == 'x' and event_type != 'x'
execution:
  - compile under S0-GAP-02-PDL-1
  - verify SAT_UNSAT_TAUT_NOT_TAUT certificates
expected:
  positive: TAUT
  negative: UNSAT
  alternative_union: TAUT
  bundle_admission: rejected
  findings:
    - POSITIVE_DISCRIMINATOR_TAUTOLOGY
    - NEGATIVE_BOUNDARY_UNSATISFIABLE
    - CATCH_ALL_ALTERNATIVE
  combined_outcomes: [ARCHITECTURE_DETECTED, VERIFICATION_BLOCKED]
forbidden:
  - bundle_admitted
  - timeout_or_unsupported_theory_inherits_acceptance
```

### A-19 — access-log head without independent reconciliation

```yaml
case_id: A-19
setup:
  oracle_log_contains_read: false
  storage_audit_contains_read: true
  network_audit_contains_read: true
  key_service_audit_contains_read: true
execution:
  - reconcile all signed heads for the window
expected_when_mismatch:
  access_reconciliation: inconsistent
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
expected_when_decisive_source_unavailable:
  access_reconciliation: not_established
  evidence_terminal: INDEPENDENCE_NOT_ESTABLISHED
  combined_outcomes: [VERIFICATION_BLOCKED]
forbidden:
  - log_silence_treated_as_no_access
```

### A-20 — forbidden role combination

```yaml
case_id: A-20
forbidden_assignments:
  - [scenario_author, expectation_author_without_dual_control]
  - [generator_primary_author, relation_validator_primary_author]
  - [generator_primary_author, evaluator_P_relation_primary_author]
  - [evaluator_R_primary_author, evaluator_P_primary_author]
execution:
  - validate role assignment before artifact freeze
expected:
  each_assignment: rejected
  artifact_freeze_started: false
  combined_outcomes: [ARCHITECTURE_DETECTED, RUN_INVALID]
forbidden:
  - conflict_waived_after_observing_results
```

### A-21 — unresolved blocking challenge still renders passage

```yaml
case_id: A-21
setup:
  open_challenge: {class: specification_correctness, blocking: true, status: unresolved}
execution:
  - recompute complete challenge register
  - invoke claim renderer
expected:
  no_unresolved_blocking_challenge: false
  h: 0
  passage_sentence_rendered: false
  combined_outcomes: [VERIFICATION_BLOCKED]
forbidden:
  - open_challenge_digest_listed_but_ignored
  - passage_sentence_rendered
```

## 6. Suite index and acceptance rule

```yaml
suite_id: S0-GAP-02-FALSIFIERS-2
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
  - A-14
  - A-15
  - A-16
  - A-17
  - A-18
  - A-19
  - A-20
  - A-21
architecture_acceptance_rule:
  all_cases_instantiated: true
  all_expected_observations_matched: true
  no_forbidden_observation_present: true
  F-04_if_both_independent_channels_accept: ARCHITECTURE_FALSIFIED
  A-14_if_shared_bad_spec_is_accepted: SPECIFICATION_ASSURANCE_NOT_ESTABLISHED
  missing_or_neutralized_discriminator: EVALUATOR_COVERAGE_NOT_ESTABLISHED
  unresolved_blocking_challenge: VERIFICATION_BLOCKED
  missing_case_policy: TEST_SETUP_INVALID_AND_ACCEPTANCE_WITHHELD
```

Every case retains base and attack digests, exact recipes, source/generated-file/SBOM/network provenance, the P37 register, answer-neutral probes, discriminator witnesses, finite-domain/compiler proofs, raw traces, `R_v`/`P_v`/`M_v`/`J_v` observations, `O_v`/`S_v`, four access heads and reconciliation, reviewer proficiency and raw positions, role-window validation, challenge register, assertion results, and signatures. A screenshot, prose summary, self-attestation, or same-code unit test does not satisfy a case.

## 7. Interpretation

Passing this suite supports only that the named architecture instance detected the seeded attacks under the named artifacts and environment. It does not establish general independence, legal correctness, institutional competence, or OPS-R15 passage.

`F-04` stays self-directed and dispositive: same-code parity can be green while independent channels reject; if both accept the intact seeded wrong result, the architecture is falsified. `A-14` establishes the distinct specification boundary: diverse evaluators may agree under a bad shared `B`/`O_v`, so the stronger custody-semantics claim is withheld. `A-18` makes bounded ambiguity executable rather than declarative. `A-19`–`A-21` make access, role, and challenge predicates fail closed.

These non-establishment terminals are valid negative completions under `INT-K08`; they do not add an outcome-vocabulary element, score an implementation, or weaken a gate. No operational execution evidence is supplied by this Markdown suite; the standing remains `accepted_narrow_scope` with technical execution and institutional dependencies unestablished.
