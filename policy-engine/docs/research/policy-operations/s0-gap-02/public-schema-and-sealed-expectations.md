---
title: S0-GAP-02 — Public input schema, fixture corpus, and sealed expectations
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

The public package must let an implementation execute a custody scenario without telling it which action, status, label, mechanism, or trace the evaluator will accept. OPS-R15’s prior art requires an input corpus, hidden mutations, set-valued expectations, and a bounded receipt, but its prose fixtures expose expected traces and do not constitute an executable independent oracle. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:326-470@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, especially `CK-11`; `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.)

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
- The corpus defines observable semantics only and does not require an internal production architecture, preserving `S0-K13`. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K13`.)
- Dissent and uncertainty are retained, preserving `S0-K15`, rather than normalized into a single hidden label. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K15`.)

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
  finite_trace_domain_profile_digest: digest
  predicate_dsl_version: stable_identifier
  predicate_compiler_proof_digest: digest
  specification_assurance_record_digest: digest
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
  predicate_language_version: S0-GAP-02-PDL-1
  normalized_ast_digest: digest
  parameters: map<string, typed_value>
  quantification_scope: fixture | entity_set | event_set | dependency_closure |
                        observation_channel | mutation_family
  required_result: true | false
  indeterminate_policy: blocks_verification
  evidence_requirement: stable_identifier
  compiler_proof_refs: [digest]
```

The predicate language is evaluator-independent and declarative. Its interpreter may not be shared between `R_v` and `P_v` when the interpreter performs semantic reduction; each evaluator independently operationalizes the same normalized public formula. The bundle compiler, not either evaluator, establishes the finite-domain well-formedness and proof obligations below.

#### 4.3.1 Chosen decidability model: finite-domain total predicate DSL

This amendment selects a **total decidable predicate DSL over a finite trace-domain profile**. It does not authorize a final production language or API. An admitted profile must enumerate or bound every domain used by the fixture:

```yaml
FiniteTraceDomainProfile:
  profile_id: stable_identifier
  entity_ids: finite_canonical_set
  event_ids: finite_canonical_set
  dependency_edges: finite_canonical_set
  observation_channels: finite_enum
  event_types: finite_enum
  authority_and_posture_atoms: finite_enum
  integer_range: {minimum: integer, maximum: integer}
  time_ticks: finite_ordered_set
  maximum_trace_events: integer
  maximum_entities: integer
  maximum_edges: integer
  string_atoms: finite_dictionary
  profile_digest: digest
```

A numeric bound is not itself an enumerable domain. Every `finite_canonical_set` is materialized as a committed, canonically ordered member list before bundle admission. Maximum values are validation caps over those lists, not permission for a compiler to invent members later. If any domain needed by a predicate cannot be completely enumerated at admission, the bundle is `not_established` for positive verification and the stronger claim is withheld.

`S0-GAP-02-PDL-1` permits only:

- Boolean connectives over a normalized finite AST;
- equality/inequality, membership, exact bounded integer comparison, and finite cardinality;
- quantification over named finite sets from the domain profile;
- finite set union/intersection/difference and subset relations;
- reachability and partial-order predicates over the bounded declared graph;
- exact event/time ordering over declared finite time ticks; and
- references to public primitive predicates whose own normalized definitions are included in the bundle.

It forbids recursion, unbounded quantification, user-defined executable functions, floating-point approximation, external calls, nondeterminism, implementation callbacks, unbounded strings, hidden model inference, and unsupported theories.

Compilation terminates by construction over the finite domain and emits proof or counterexample certificates for:

```text
SAT(phi)       -- at least one admitted trace satisfies phi
UNSAT(phi)     -- no admitted trace satisfies phi
TAUT(phi)      -- every admitted trace satisfies phi
NOT_TAUT(phi)  -- a counterexample trace exists
```

A resource limit, unsupported operator, malformed proof, or compiler disagreement is not a favourable result. It returns an indeterminate admission finding and blocks the expectation bundle under `PV-K06`.

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

## 5. Decidable bounded ambiguity

For fixture `x`, let `D_x` be the finite trace domain fixed by the admitted `FiniteTraceDomainProfile`. Let `A_x` be the finite nonempty set of admissible alternatives. Each alternative compiles to a total Boolean formula `phi_a(y)` over `D_x`; the mandatory cross-alternative requirements compile to `G_x(y)`. The compatibility relation is:

```text
Compatible(x, y) = (OR over a in A_x of phi_a(y)) AND G_x(y)
```

`Compatible` is decidable because `y` and every quantified domain are finite and every admitted formula is total. Bundle admission requires proof-producing checks:

1. `SAT(phi_a)` for every alternative: no impossible branch;
2. every positive discriminator is `NOT_TAUT` and changes truth value on its bound seed/baseline witness;
3. every negative boundary predicate is `SAT` and `NOT_TAUT`: it can actually occur and actually exclude something;
4. `NOT_TAUT(OR_a phi_a)`: the union of alternatives is not catch-all over `D_x`;
5. `may_vary` is restricted to enumerated representation-only fields and cannot widen `D_x`; and
6. the mandatory formula `G_x` is satisfiable with at least one admitted alternative.

The bundle is invalid when any proof is missing, indeterminate, unsupported, timed out, or fails verification. An evaluator may not treat compiler uncertainty as acceptance.

Genuine ambiguity remains distinct from benchmark uncertainty:

- **Genuine multiple outcomes:** public axioms explicitly permit more than one outcome; each branch is finite, satisfiable, and non-universal.
- **Contested axiom:** reviewer positions and `S_v` remain visible. The stronger custody-semantics claim is withheld unless the named scope's assurance is established.
- **Incomplete information:** the finite domain contains explicit bounded branches, or the fixture is non-claimable. The evaluator may not guess.
- **Reviewer disagreement about an output:** there is no automatic majority rule. The claim remains withheld while a blocking challenge/disagreement is unresolved.

### 5.1 Required rejection fixture: syntactically valid catch-all

The audit's construction is committed as a compiler falsifier:

```yaml
case_id: BUNDLE-CATCHALL-01
finite_trace_domain_profile: bounded_synthetic_trace_domain_v1
alternatives:
  - alternative_id: universal
    mandatory_positive_predicates:
      - "event_count >= 0"
    mandatory_negative_predicates:
      - "event_type == 'x' and event_type != 'x'"
    may_vary: []
expected_compiler_proofs:
  positive_predicate: TAUT
  negative_predicate: UNSAT
  alternative_union: TAUT
expected_admission:
  accepted: false
  findings:
    - POSITIVE_DISCRIMINATOR_TAUTOLOGY
    - NEGATIVE_BOUNDARY_UNSATISFIABLE
    - CATCH_ALL_ALTERNATIVE
  claim_effect: VERIFICATION_BLOCKED
forbidden:
  - expectation_bundle_admitted
  - timeout_or_unsupported_theory_treated_as_acceptance
```

The bundle satisfies the old syntactic checklist but is rejected by the amended decidable semantics. This is the direct evidence for audit finding `S0-GAP-02-VI-001`.

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
predicate_compiler:
  dsl_version: S0-GAP-02-PDL-1
  finite_trace_domain_profile_digest: sha256:...
  alternative_formula_proof_digests: [sha256:..., sha256:...]
  union_not_tautology_proof_digest: sha256:...
  mandatory_formula_satisfiability_proof_digest: sha256:...
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
- missing fixture/specification/axiom/domain-profile digests;
- a predicate outside `S0-GAP-02-PDL-1`, unbounded domain, recursion, external call, nondeterminism, or unsupported theory;
- zero alternatives or wildcard/open-ended alternatives;
- any alternative whose formula is unsatisfiable;
- a positive discriminator that is tautological, has no bound seed/delta witness, or does not change on that witness;
- a negative boundary that is unsatisfiable or tautological;
- an alternative union proved catch-all, or whose non-universality is not proved;
- semantic fields listed as nonsemantic variability;
- unsigned reviewer positions, missing dissent/abstention records, or deleted prior positions;
- plaintext digest inconsistent with canonical bytes;
- commitment root or inclusion proof mismatch;
- a correction without `supersedes_bundle_digest` and a reason;
- an expectation bundle created after implementation output without prior commitment or logged correction;
- a missing or unverified specification-assurance record;
- a mandatory predicate whose indeterminate policy is anything other than `blocks_verification`; and
- timeout, resource exhaustion, compiler disagreement, malformed certificate, or proof-checker `unknown` being converted to acceptance.

Compiler acceptance evidence includes the normalized ASTs, finite-domain digest, satisfiability/non-tautology certificates, exact proof-checker version, and verification results. Prose saying “not catch-all” is not evidence of the gate predicate.

## 10. Standing

The amended format now makes `Compatible(x,y)` decidable within a declared finite trace domain and commits a concrete catch-all rejection fixture. It remains research-only and defines no final package name, serializer, database, API, custodian, or evaluator. No compiler, proof checker, expectation bundle, specification-assurance institution, or operational gate is established by this Markdown. Timeout or unsupported theory blocks under `PV-K06`; agreement under an unassured shared premise yields `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`, a local `INT-K08` negative completion rather than a new product/outcome vocabulary element. Nothing here scores or unblocks OPS-R15.
