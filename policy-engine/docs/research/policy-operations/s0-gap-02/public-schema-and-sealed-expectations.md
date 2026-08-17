---
title: S0-GAP-02 — Public input schema, fixture corpus, and sealed expectations
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: accepted_narrow_scope
authoritative_for:
  - research-only public input and corpus semantics
  - sealed set-valued expectation requirements
  - bounded ambiguity and leakage controls
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

# Public input schema, fixture corpus, and sealed expectations

## 1. Design objective

The public package must let an implementation execute a custody scenario without telling it which action, status, label, mechanism, or trace the evaluator will accept. OPS-R15’s prior art requires an input corpus, hidden mutations, set-valued expectations, and a bounded receipt, but its prose fixtures expose expected traces and do not constitute an executable independent oracle. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:326-470@1a7a2d05ebba22fae80e9934329e4b880806588e`, especially `CK-11`; `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

The split is therefore strict:

```text
public package  = public semantics + input-only fixtures + conformance vectors
sealed package  = admissible outcomes + exclusions + predicates + reviewer record
run package     = frozen implementation output + evaluator observations + receipt
```

No public or implementation-visible package contains a resolvable expected action or product label.

## 2. Public package model

This section is a machine-readable research specification. It is intentionally not a final JSON, API, database, or serialization contract.

### 2.1 Public package manifest

```yaml
PublicBenchmarkPackage:
  specification_id: stable_identifier
  specification_version: semver_like_string
  specification_digest: digest
  corpus_id: stable_identifier
  corpus_version: semver_like_string
  corpus_manifest_digest: digest
  authority_axiom_profile:
    profile_id: stable_identifier
    version: semver_like_string
    digest: digest
    standing: synthetic_research_scenario
  trace_observation_profile:
    profile_id: stable_identifier
    version: semver_like_string
    digest: digest
  canonicalization_profile:
    identifier: stable_identifier
    version: string
  fixtures:
    - fixture_id: opaque_identifier
      fixture_digest: digest
      byte_length: integer
      schema_version: string
      declared_relations: [stable_identifier]
  exclusions:
    implementation_visible_expectations: prohibited
    product_status_labels: prohibited
    product_gold_records: prohibited
  may_not_use_for: [string]
```

A corpus manifest may expose fixture identifiers and digests. It must not expose expectation-bundle identifiers whose naming or count reveals acceptable alternatives.

### 2.2 Input-only fixture

```yaml
CustodyFixture:
  fixture_id: opaque_identifier
  schema_version: string
  scenario:
    title: non_normative_string
    purpose: bounded_research_question
    observation_window:
      begins_at: timestamp_or_relative_marker
      ends_at: timestamp_or_relative_marker
    jurisdiction_profile: synthetic_profile_identifier
    declared_uncertainties: [UncertaintyDeclaration]
  entities:
    - entity_id: opaque_identifier
      entity_kind: actor | subject | artifact | authority_source | external_system
      declared_attributes: map<string, scalar_or_reference>
  authority_axioms:
    - axiom_ref: stable_identifier
      local_parameters: map<string, scalar_or_reference>
      standing: stipulated | contested | unknown
      dissent_refs: [opaque_handle]
  initial_facts:
    - fact_id: opaque_identifier
      proposition_type: stable_identifier
      subject_ref: opaque_identifier
      object: scalar_or_reference
      effective_interval: Interval
      observed_at: timestamp_or_relative_marker
      provenance_ref: opaque_identifier
      contestability: stipulated | contested | unknown
  events:
    - event_id: opaque_identifier
      event_type: stable_identifier
      actor_ref: opaque_identifier
      subject_refs: [opaque_identifier]
      effective_at: timestamp_or_relative_marker
      observed_at: timestamp_or_relative_marker
      scope:
        tenant_ref: opaque_identifier | null
        cell_ref: opaque_identifier | null
        matter_ref: opaque_identifier | null
        purpose_ref: opaque_identifier | null
      payload: map<string, scalar_or_reference>
      declared_dependencies: [opaque_identifier]
      provenance_ref: opaque_identifier
  requested_observation:
    protected_operation_ref: stable_identifier
    observable_channels: [stable_identifier]
    horizon: timestamp_or_relative_marker
  semantic_relations:
    - relation_id: stable_identifier
      relation_kind: id_renaming | unordered_permutation | irrelevant_metadata |
                     duplicate_delivery | temporal_boundary | scope_lookalike |
                     authority_only_change | equivalent_graph_encoding |
                     split_merge_equivalence | other_declared_relation
      parameters: map<string, scalar_or_reference>
  nonsemantic_fields:
    - field_path: json_pointer_like_string
      permitted_variation: stable_identifier
  generation:
    source: public_fixture | derived_public_fixture | sealed_mutation
    parent_fixture_digest: digest | null
    mutation_relation_id: stable_identifier | null
    seed_commitment: digest | null
  may_not_use_for: [string]
```

### 2.3 Uncertainty declaration

```yaml
UncertaintyDeclaration:
  uncertainty_id: stable_identifier
  subject_path: json_pointer_like_string
  kind: "factual_contest | normative_contest | missing_fact | measurement_interval | timing_interval | identity_ambiguity"
  permitted_values: "[typed_value] | null"
  bounded_interval: "{lower: typed_value, upper: typed_value} | null"
  reviewer_positions: [opaque_handle]
  effect_on_fixture: "alternative_branches | evaluator_abstention_allowed | fixture_not_scorable"
```

Uncertainty is data, not an excuse to accept any output. Each declaration must identify a finite value set, a bounded interval, an explicit branch, or an explicit `fixture_not_scorable` consequence.

## 3. Public fixture-corpus requirements

### 3.1 Publishability test

A fixture is publishable only when all of the following hold:

1. Its bytes can be given to an implementation before submission freeze without materially narrowing the accepted result beyond the public specification.
2. It contains no field or free-text phrase that resolves an expected action, state, label, status, mechanism, affected set, sequence, score, or evaluator predicate.
3. Its identifiers are opaque and carry no semantic class through prefixes, ordering, or numeric ranges.
4. Its prose title and comments are non-normative; machine behavior is determined only by typed fields and referenced public axioms.
5. Every apparent “gold,” “expected,” “correct,” “oracle,” “pass,” “fail,” “label,” and `*_expected` field is absent or causes lint failure.
6. Hidden-run metadata, mutation seeds, alternative counts, and reviewer identities are absent.
7. A leakage review compares the fixture against implementation-visible OPS-R15 traces and production fixture helpers.

The existing in-tree benchmark owners demonstrate why these rules are necessary: `grounding_benchmark.py` carries visible `obligation_labels`, `expected_atom_id`, `expected_operator`, `expected_target`, and decisive-mechanism expectations, while `semantic_fixtures.py` carries visible semantic signals and adjudication records. (`policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py:90-140@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py:1-150@1a7a2d05ebba22fae80e9934329e4b880806588e`.) Those patterns may be valid for product tests but are disqualifying for this verification corpus.

### 3.2 Corpus strata

| Stratum | Visibility | Purpose | Expectation handling |
|---|---|---|---|
| Public conformance fixtures | Public before implementation | Demonstrate syntax, trace observability, and noncontroversial semantic relations. | Expectations remain sealed; a small number of non-semantic parser conformance vectors may be public. |
| Public challenge fixtures | Public before implementation | Allow external criticism of scenario axioms and coverage. | Expected custody outcomes remain sealed. Challenges are logged against fixture and axiom digests. |
| Sealed adjacent fixtures | Input withheld until implementation freeze | Test boundary cases and nearby values. | Input commitment or generation-recipe commitment is published before reveal; expectations separately sealed. |
| Post-freeze generated fixtures | Generated after submission digest | Resist memorization and adaptive coding. | Generator, seed commitment, and relation are committed; exact input and expectation are revealed according to run policy. |
| Holdback proficiency fixtures | Restricted to evaluator qualification | Test evaluator competence with seeded defects. | Never used to claim implementation passage. Results qualify or disqualify an evaluator version. |

### 3.3 Corpus invariants

- Every fixture digest binds the exact bytes and schema version.
- Any correction creates a new fixture version and digest; prior runs remain bound to prior bytes.
- A public fixture may be superseded but not overwritten.
- The public package includes the full `may_not_use_for` block.
- The corpus defines observable semantics only and does not require an internal production architecture, preserving `S0-K13`. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K13`.)
- Dissent and uncertainty are retained, preserving `S0-K15`, rather than normalized into a single hidden label. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K15`.)

## 4. Sealed expectation format

### 4.1 Bundle envelope

```yaml
SealedExpectationBundle:
  expectation_bundle_id: opaque_identifier
  expectation_version: semver_like_string
  fixture_digest: digest
  benchmark_specification_digest: digest
  authority_axiom_profile_digest: digest
  trace_observation_profile_digest: digest
  canonicalization_profile: stable_identifier
  created_at: timestamp
  admissible_alternatives: [AdmissibleAlternative]
  mandatory_cross_alternative_predicates: [PredicateRequirement]
  prohibited_observations: [PredicateRequirement]
  ambiguity_record: AmbiguityRecord
  reviewer_record_commitment: digest
  challenge_state_commitment: digest
  supersedes_bundle_digest: digest | null
  correction_reason_ref: opaque_handle | null
  salt: secret_random_bytes
  plaintext_digest: digest
  encrypted_payload_digest: digest
  commitment_leaf: digest
  signatures: [DetachedSignature]
  may_not_use_for: [string]
```

The salt is secret until the commitment policy permits reveal. A bare hash of a small outcome vocabulary is vulnerable to dictionary guessing; salting and encryption are therefore both required.

### 4.2 Admissible alternative

```yaml
AdmissibleAlternative:
  alternative_id: opaque_identifier
  applicability:
    axiom_branch_refs: [stable_identifier]
    preconditions: [PredicateRequirement]
  must_observe: [PredicateRequirement]
  must_not_observe: [PredicateRequirement]
  ordering_constraints: [OrderingConstraint]
  cardinality_constraints: [CardinalityConstraint]
  required_affected_set_relation: PredicateRequirement | null
  permitted_variation:
    - field_path: json_pointer_like_string
      rule_ref: stable_identifier
  positive_discriminators: [stable_identifier]
  negative_discriminators: [stable_identifier]
  rationale_refs: [stable_identifier]
  reviewer_position_refs: [opaque_handle]
```

An alternative is invalid if it has no positive discriminator, no negative boundary, or a permitted-variation rule over authority, status, admission, affected-set, or action semantics.

### 4.3 Predicate requirement

```yaml
PredicateRequirement:
  predicate_id: stable_identifier
  predicate_language_version: string
  parameters: map<string, typed_value>
  quantification_scope: fixture | entity_set | event_set | dependency_closure |
                        observation_channel | mutation_family
  required_result: true | false
  indeterminate_policy: blocks_verification
  evidence_requirement: stable_identifier
```

The predicate language is evaluator-independent and declarative. Its interpreter may not be shared between `R_v` and `P_v` if the interpreter itself performs semantic reduction; each evaluator must independently operationalize the public predicate definition.

### 4.4 Ambiguity and reviewer record

```yaml
AmbiguityRecord:
  ambiguity_kind: none | genuine_multiple_outcomes | contested_axiom |
                  incomplete_information | reviewer_disagreement
  accepted_as_set_valued: boolean
  alternatives_in_scope: [opaque_identifier]
  excluded_catch_all: true
  unresolved_questions: [stable_identifier]
  reviewer_positions:
    - position_id: opaque_identifier
      reviewer_pseudonym: opaque_identifier
      position: supports | dissents | abstains | conflict_recusal
      alternative_refs: [opaque_identifier]
      rationale_digest: digest
      signature: DetachedSignature
  adjudication_record_ref: opaque_handle | null
```

`abstains` and `conflict_recusal` are first-class values. They are never converted to assent and never deleted when a later adjudication occurs.

## 5. Bounded ambiguity: preserving alternatives without becoming unfalsifiable

For fixture `x`, let `A_x` be the finite nonempty set of admissible alternatives. Each alternative `a` denotes a set of raw traces satisfying all of its positive requirements and none of its exclusions. Let `G_x` be the mandatory cross-alternative predicates. The expectation-side compatibility relation is:

```text
Compatible(x, y) = (exists a in A_x: y satisfies a) and (y satisfies every g in G_x)
```

The bundle is structurally invalid when any of the following is true:

- `A_x` is empty;
- an “other,” wildcard, “reasonable outcome,” or open-ended branch exists;
- every possible raw trace matches at least one alternative;
- an alternative has no positive discriminator or no exclusion boundary;
- `may_vary` covers a semantic field;
- a reviewer disagreement is hidden by taking the union of positions without preserving the dissent;
- an indeterminate mandatory predicate is treated as true;
- an alternative was added after observing an uncommitted implementation output without a correction/supersession record.

Genuine ambiguity is different from uncertainty about the benchmark itself:

- **Genuine multiple outcomes:** the public axioms explicitly permit more than one outcome; each is enumerated and bounded. Any listed branch may satisfy the fixture.
- **Contested axiom:** reviewers disagree about the premise. The disagreement remains visible. The fixture may be marked non-claimable until the challenge protocol resolves or explicitly accepts a set-valued premise.
- **Incomplete information:** the fixture branches on a bounded missing fact, or it is not claimable. The evaluator may not guess.
- **Reviewer disagreement about an output:** there is no automatic majority rule. The run remains challengeable and the bounded verification claim is withheld unless the predeclared adjudication protocol is satisfied.

## 6. Commitment construction

The research profile uses stable, public cryptographic building blocks without appointing an algorithm or vendor as the final production choice.

1. Serialize each plaintext expectation bundle under an invariant canonicalization profile, such as the JSON Canonicalization Scheme, RFC 8785.
2. Generate at least 256 bits of random salt per bundle and domain-separate all hashes.
3. Compute:

```text
leaf = H("PolicyOS-S0-GAP-02:expectation:v1" || salt || canonical_plaintext)
```

4. Place leaves in a deterministic ordered Merkle tree. Publish the root, tree size, canonicalization profile, hash identifier, bundle-version map commitment, and detached signatures before implementation outputs are accepted.
5. Encrypt plaintext bundles under a versioned key-custody profile. Store ciphertext digest separately from the Merkle leaf.
6. At run time, grant least-privilege, time-bounded access to evaluator-scoped plaintext or a constrained comparison service; log every grant, read, denial, and revocation.
7. Reveal the salt, bundle, and inclusion proof only according to the challenge/release policy. An inclusion proof establishes that the revealed bundle was committed; it does not establish that its semantics are correct.
8. Corrections append a new leaf and supersession record. They never replace an old leaf or rebind a prior receipt.

RFC 8785 supplies deterministic JSON representation; RFC 9162 supplies a mature append-only Merkle-log and consistency-proof pattern; NIST SP 800-57 Part 1 Rev. 5 supplies key-management lifecycle concepts. These are transfers of mechanism, not claims that a certificate-transparency log or NIST profile is the final implementation.

## 7. Example: public fixture with no answer leakage

```yaml
fixture_id: fx_7f2d0b16
schema_version: s0-gap-02-research-0.1
scenario:
  title: authority assertion changes while payload remains byte-identical
  purpose: observe custody behavior under a stipulated authority-only event
  observation_window: {begins_at: T0, ends_at: T9}
  jurisdiction_profile: synthetic-J1
  declared_uncertainties: []
entities:
  - entity_id: e_subject_1
    entity_kind: subject
    declared_attributes: {}
  - entity_id: e_authority_1
    entity_kind: authority_source
    declared_attributes: {}
authority_axioms:
  - axiom_ref: AX-AUTH-RECHECK-01
    local_parameters: {subject_ref: e_subject_1}
    standing: stipulated
    dissent_refs: []
initial_facts:
  - fact_id: f_1
    proposition_type: payload_digest
    subject_ref: e_subject_1
    object: sha256:0123...
    effective_interval: {from: T0, to: open}
    observed_at: T0
    provenance_ref: p_1
    contestability: stipulated
events:
  - event_id: ev_1
    event_type: authority_assertion_changed
    actor_ref: e_authority_1
    subject_refs: [e_subject_1]
    effective_at: T4
    observed_at: T5
    scope: {tenant_ref: t_1, cell_ref: c_1, matter_ref: m_1, purpose_ref: u_1}
    payload: {payload_digest: sha256:0123...}
    declared_dependencies: []
    provenance_ref: p_2
requested_observation:
  protected_operation_ref: OP-REUSE-01
  observable_channels: [custody_event, attempted_external_act, public_projection]
  horizon: T9
semantic_relations:
  - relation_id: MR-AUTHORITY-ONLY-01
    relation_kind: authority_only_change
    parameters: {payload_digest_must_remain_equal: true}
nonsemantic_fields:
  - field_path: /events/0/event_id
    permitted_variation: opaque_identifier_renaming
generation:
  source: public_fixture
  parent_fixture_digest: null
  mutation_relation_id: null
  seed_commitment: null
may_not_use_for:
  - benchmark passage
  - legal-sufficiency conclusion
```

Nothing in the fixture says whether an action should occur, which label should be emitted, which affected set is correct, or which mechanism is decisive.

## 8. Example: sealed, set-valued expectation shape

The following demonstrates structure only and is not an OPS-R15 answer:

```yaml
admissible_alternatives:
  - alternative_id: alt_a83c
    applicability: {axiom_branch_refs: [AX-BRANCH-A], preconditions: [PR-001]}
    must_observe: [PR-010, PR-011]
    must_not_observe: [PR-090]
    ordering_constraints: [OR-004]
    cardinality_constraints: [CA-002]
    required_affected_set_relation: PR-020
    permitted_variation:
      - {field_path: /trace/receipts/*/opaque_id, rule_ref: VAR-ID-RENAME}
    positive_discriminators: [D-010, D-011]
    negative_discriminators: [D-090]
    rationale_refs: [AX-BRANCH-A, SEM-014]
    reviewer_position_refs: [pos_1, pos_2]
  - alternative_id: alt_f102
    applicability: {axiom_branch_refs: [AX-BRANCH-B], preconditions: [PR-002]}
    must_observe: [PR-012, PR-013]
    must_not_observe: [PR-090, PR-091]
    ordering_constraints: [OR-005]
    cardinality_constraints: [CA-003]
    required_affected_set_relation: PR-021
    permitted_variation:
      - {field_path: /trace/receipts/*/opaque_id, rule_ref: VAR-ID-RENAME}
    positive_discriminators: [D-012, D-013]
    negative_discriminators: [D-090, D-091]
    rationale_refs: [AX-BRANCH-B, SEM-015]
    reviewer_position_refs: [pos_3]
ambiguity_record:
  ambiguity_kind: genuine_multiple_outcomes
  accepted_as_set_valued: true
  alternatives_in_scope: [alt_a83c, alt_f102]
  excluded_catch_all: true
  unresolved_questions: []
```

## 9. Validation rules for a bundle compiler

A future bundle compiler must reject, rather than warn on:

- public fixture fields matching the prohibited-answer vocabulary;
- missing fixture/specification/axiom digests;
- zero alternatives or wildcard alternatives;
- alternatives without positive and negative discriminators;
- semantic fields listed as nonsemantic variability;
- unsigned reviewer positions, missing dissent/abstention records, or deleted prior positions;
- plaintext digest inconsistent with canonical bytes;
- commitment root or inclusion proof mismatch;
- a correction without `supersedes_bundle_digest` and a reason;
- an expectation bundle created after the implementation output without a prior commitment or a logged correction process;
- a mandatory predicate whose indeterminate policy is anything other than `blocks_verification`.

## 10. Standing

This specification is machine-readable enough to test architecture and leakage rules, but it remains research-only. It defines no final package name, serializer, database, API, custodian, or evaluator. Its acceptance cannot score OPS-R15 until independent implementations, custody, challenge, and institutional competence are separately established and accepted.
