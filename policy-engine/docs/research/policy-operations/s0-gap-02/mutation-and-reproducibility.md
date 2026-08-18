---
title: S0-GAP-02 — Adjacent-case generator, anti-memorization controls, and reproducibility receipt
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
  - research-only mutation relation catalogue and generation protocol
  - reproducibility receipt requirements
  - S0-K16 bounded-claim template
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

# Adjacent-case generator, anti-memorization controls, and reproducibility receipt

## 1. Objective

A static public corpus tests whether an implementation recognizes known fixtures. It does not establish that behavior depends on custody semantics rather than fixture identifiers, prose fragments, event ordering, or memorized labels. `S0-K15` therefore requires adjacent and hidden cases and preservation of ambiguity/dissent. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K15`.) OPS-R15 already identifies ID branching and adjacent-case risk but supplies no executable generator or sealed population. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:362-386@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`; `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.)

The generator is independent only when its transformation semantics and its relation validator are provenance-diverse from the product and from the evaluator that judges the generated relation. `M_v` may consume the public fixture schema, public semantic relations, and a hidden seed; `J_v` independently validates the mutation certificate. Neither may import production semantics, product fixture helpers, evaluator reducers, plaintext expectation alternatives, or a private semantic table/prompt/model/service shared with `R_v` or `P_v`. Audit attack `A-15` makes that boundary executable.

## 2. Metamorphic relation model

A metamorphic relation `m` is a public statement about two or more inputs and their permitted observable relationship. It does not necessarily reveal the exact expected output.

```yaml
MetamorphicRelation:
  relation_id: stable_identifier
  version: string
  input_preconditions: [declarative_predicate]
  transformation: declarative_transformation
  semantic_class: invariant | monotone | antitone | bounded_change |
                  branch_switch | conservation | commutation | idempotence
  output_relation: declarative_predicate
  prohibited_inferences: [stable_identifier]
  independent_validator_profile: stable_identifier
  rationale_refs: [stable_identifier]
  may_not_use_for: [string]
```

For base fixture `x`, transformation `T_m`, implementation observation function `I`, and output relation `Q_m`, the required relation is:

```text
Q_m(I(x), I(T_m(x))) = true
```

The evaluator may test the relation without knowing a complete trace for either member. Some relations are invariant; others intentionally cross a semantic boundary and require a bounded, declared change.

## 3. Required mutation families

| Family | Input transformation | Required observable relation | Memorization/fault targeted |
|---|---|---|---|
| Opaque ID alpha-renaming | Bijectively rename fixture, event, actor, subject, artifact, and dependency IDs. | Output is isomorphic under the same renaming; no semantic action changes. | Branching on known IDs, prefixes, or numeric ranges. |
| Semantically unordered permutation | Permute events whose declared partial order and dependencies do not constrain one another. | Semantically relevant result is invariant; presentation order may vary only where declared nonsemantic. | Sequence-position memorization and accidental list-order reducers. |
| Equivalent dependency encoding | Reorder adjacency lists, replace equivalent edge-list/map encodings, or rename internal edge IDs while preserving the graph. | Affected-set and custody result are graph-isomorphic. | Dependence on serialization or traversal order. |
| Irrelevant metadata perturbation | Change comments, whitespace, nonsemantic labels, transport correlation IDs, or declared irrelevant metadata. | Semantic observations invariant. | Lexical/prose memorization and parser leakage. |
| Duplicate delivery | Duplicate a declared retryable event with the same idempotency identity and bounded timing variation. | No duplicate irreversible effect; receipts may record the duplicate according to public observation rules. | At-least-once delivery and replay defects. |
| Equivalent split/merge | Replace one compound input event with declared equivalent component events, or merge them, preserving effective facts. | Result equivalent under declared observation relation. | Overfitting to one event granularity. |
| Temporal boundary triplet | Generate values just before, exactly at, and just after a declared boundary. | Output follows the explicitly declared interval convention; neighboring cases that lie on the same side are equivalent. | Off-by-one, timestamp truncation, and hidden inclusivity assumptions. |
| Wrong-scope lookalike | Copy content while changing tenant, cell, matter, purpose, subject, or operation scope. | No cross-scope semantic carryover; only the scoped branch may change. | Payload-only matching and cross-boundary contamination. |
| Authority-only change | Keep payload bytes and evidence identity fixed while changing a stipulated authority assertion or interval. | Only authority-dependent reuse/action observations may change; payload-derived facts remain invariant. | Treating content identity or signature validity as current authority. |
| Payload-only change | Change payload fact while holding authority assertions fixed. | Authority premise remains fixed; payload-dependent observations change only as declared. | Conflation of content and authority. |
| Missing-edge adjacent case | Add or remove one declared dependency edge near an affected-set boundary. | Change is confined to the independently derived dependency consequence; unrelated entities invariant. | Incomplete traversal or global over-invalidation. |
| Observation-delay mutation | Keep effective time fixed while moving observation time within a declared range. | Historical/current views follow public temporal axioms; effective truth is not rewritten. | Conflation of effective, observation, transaction, and run time. |
| Replay/environment mutation | Re-execute identical immutable inputs in a separately declared environment with only nonsemantic differences. | Observable semantics invariant; environment metadata differs in receipt. | Hidden environment dependence and stale cache use. |
| Dissent-preservation mutation | Add a signed dissent, abstention, or recusal record without changing the underlying fixture facts. | Reviewer-state observation changes; substantive scenario result must not be silently rewritten. | Erasure of disagreement or treating abstention as assent. |
| Alternative-order mutation | Reorder sealed admissible alternatives and reviewer positions. | Compatibility result invariant. | First-match/label-order bias in the oracle. |
| Canonicalization differential | Present semantically identical JSON within the allowed input grammar, then canonicalize under the declared profile. | Commitment and parsed semantics agree; noncanonical bytes cannot create a different committed meaning. | Parser/canonicalization attacks. |

The table is a minimum catalogue, not a promise that every relation applies to every fixture.

## 4. Adjacent-case definition

“Adjacent” is not merely small edit distance. A generated case is adjacent only when the transformation has a declared semantic relation and changes a minimal number of semantic dimensions.

Let the public fixture feature vector be partitioned into:

```text
Z = Z_identity × Z_scope × Z_authority × Z_payload × Z_dependency
    × Z_temporal × Z_order × Z_review × Z_transport
```

For relation `m`, define a permitted-change set `D_m` and a fixed set `F_m`. A valid adjacent mutation changes at least one coordinate in `D_m`, changes none in `F_m`, and satisfies the relation’s preconditions. The generator records a change certificate:

```yaml
MutationCertificate:
  base_fixture_digest: digest
  mutated_fixture_digest: digest
  relation_id: stable_identifier
  relation_version: string
  changed_dimensions: [stable_identifier]
  fixed_dimension_checks: [predicate_witness]
  precondition_witnesses: [predicate_witness]
  transformation_witness_digest: digest
  independent_validation_digest: digest
```

A mutation that cannot produce this certificate is not credited as adjacent.

## 5. Generator, relation-validator, and evaluator independence

```yaml
MutationGenerationRequest:
  public_specification_digest: digest
  public_corpus_manifest_digest: digest
  relation_catalogue_digest: digest
  finite_trace_domain_profile_digest: digest
  base_fixture_digests: [digest]
  population_plan_commitment: digest
  seed_commitment: digest
  implementation_submission_digest: digest
  implementation_freeze_time: timestamp

MutationGenerationResult:
  generator_version: string
  generator_source_revision: string
  generator_artifact_digest: digest
  generator_sbom_digest: digest
  generator_provenance_digest: digest
  seed_reveal_or_handle: opaque_value
  generated_fixture_digests: [digest]
  mutation_certificate_digests: [digest]
  generation_started_at: timestamp
  generation_completed_at: timestamp
  signatures: [detached_signature]

MutationValidationResult:
  relation_validator_version: string
  source_revision: string
  artifact_digest: digest
  sbom_digest: digest
  provenance_digest: digest
  validated_certificate_digests: [digest]
  rejected_certificate_digests: [digest]
  private_common_ancestor_findings: [stable_identifier]
  signed_digest: digest
```

For mutation family `m`, let `SemProv_m` include source, generated tables, prompts, models, services, build inputs, authorship/review material, runtime loads, and network calls. The admitted relation path requires:

```text
SemProv_m(M_v) intersect SemProv_m(J_v) subseteq A_m
SemProv_m(M_v) intersect SemProv_m(R_v union P_v) subseteq A_m
SemProv_m(J_v) intersect SemProv_m(R_v union P_v) subseteq A_m
```

where `A_m` contains only the public relation definition and answer-neutral representation substrate. A shared private relation table, prompt transcript, generated code, model, or service violates the gate even when packages or languages differ.

Enforcement requirements:

- `M_v` and `J_v` have separate primary authors/reviewers and build identities;
- neither build receives product source, plaintext expectations, or evaluator private semantics;
- the seed is unavailable to implementation authors before submission freeze;
- generation starts after implementation freeze;
- transformation code derives only from the public relation catalogue;
- `J_v` validates the certificate without importing `M_v` transformation code;
- the R/P evaluator that judges the relation independently implements the public output relation;
- static source/SBOM/generated-file checks, runtime load/network telemetry, and authorship evidence are reconciled across all four components;
- a poisoned private relation-table probe must be rejected before the product is scored (`A-15`);
- generated fixtures pass the answer-leakage linter;
- every exclusion is signed and remains in the population receipt; and
- generator/validator failure or unsupported relation yields a blocking/not-established result under `PV-K06`.

The role-assignment validator in `oracle-custody-and-adjudication-protocol.md` rejects an actor serving as generator author, relation validator, and deciding evaluator for the same relation family/window.

## 6. Population construction

### 6.1 Predeclared plan

Before implementation freeze, commit a plan that fixes:

- base-fixture strata and sampling frames;
- relation families and minimum/maximum counts;
- boundary-value distributions;
- allowed exclusions and their reasons;
- random-seed generation and reveal policy;
- holdback/proficiency separation;
- aggregation rule for mandatory relation failures;
- disclosure budget after the run;
- retirement and reuse policy.

The plan may commit distributions and counts without revealing exact hidden fixtures.

### 6.2 No cherry-picking

After generation, the entire valid committed population is evaluated unless a predeclared exclusion applies. A run operator may not remove cases because the implementation failed, because an evaluator disagreed, or because a fixture is inconvenient. Any exclusion is a signed event and changes the population digest.

### 6.3 Leakage budget and retirement

- Inputs and expectations disclosed after challenges become public knowledge and are not reused as hidden evidence without explicit disclosure of their status.
- Repeated submissions against the same hidden population consume a predeclared leakage budget.
- Adaptive query access is prohibited; an implementation receives a final receipt, not a per-case oracle during development.
- Retired hidden fixtures remain in historical receipts but leave the active holdback pool.
- New hidden cases derive from fresh seeds and, where feasible, fresh semantic templates rather than cosmetic rewrites.

## 7. Anti-memorization and relation decision rules

A mutation-family check is satisfied only when:

1. the base and mutated inputs are both in the committed run population;
2. the mutation certificate is valid under `J_v`;
3. `M_v`, `J_v`, and the deciding R/P relation semantics pass the transitive provenance and role-assignment gates;
4. the implementation outputs are immutable and bound to the same frozen revision/environment profile unless the relation explicitly compares environments;
5. both independent evaluators agree that the declared output relation holds;
6. no expected-answer leakage or adaptive rerun occurred;
7. no mandatory predicate is indeterminate;
8. discriminator liveness/removal/neutralization witnesses are valid for every claimed relation family; and
9. all exclusions, reviewer disagreements, and blocking challenges are preserved.

An ID-renumbered or adjacent unseen case that changes the outcome without a registered semantic reason is a failure even when both individual outputs match some visible product label. The relation, not the label, is the oracle. If relation provenance is shared or not established, no product result is scored and the run is invalid or blocked as specified in `A-15`/`A-17`.

## 8. Reproducibility receipt

### 8.1 Receipt schema

```yaml
CustodyBenchmarkReceipt:
  receipt_id: opaque_identifier
  receipt_version: string
  issued_at: timestamp
  repository_context:
    implementation_repository: opaque_identifier
    implementation_revision: string
    implementation_artifact_digest: digest
    implementation_sbom_digest: digest
  environment:
    image_digest: digest
    os_and_runtime_versions: map<string, string>
    hardware_profile_digest: digest
    configuration_digest: digest
    clock_and_timezone_profile: stable_identifier
    external_dependency_snapshot_digests: [digest]
  benchmark:
    public_specification_digest: digest
    finite_trace_domain_profile_digest: digest
    predicate_dsl_version: S0-GAP-02-PDL-1
    predicate_compiler_proof_digest: digest
    public_corpus_manifest_digest: digest
    actual_population_digest: digest
    fixture_count: integer
    relation_family_counts: map<stable_identifier, integer>
    population_complete: boolean
  generator_and_relation_validator:
    generator_version: string
    generator_artifact_digest: digest
    generator_sbom_digest: digest
    generator_provenance_digest: digest
    relation_validator_version: string
    relation_validator_artifact_digest: digest
    relation_validator_sbom_digest: digest
    relation_validator_provenance_digest: digest
    M_J_R_P_provenance_reconciliation_digest: digest
    seed_commitment: digest
    seed_reveal_or_custody_ref: opaque_value
  oracle:
    expectation_version: string
    expectation_commitment_root: digest
    expectation_tree_size: integer
    specification_assurance_record_digest: digest
    specification_assurance_disposition: established_for_named_scope | not_established
    key_profile_identifier: stable_identifier
  access_evidence:
    oracle_access_log_head: digest
    storage_audit_head: digest | null
    network_audit_head: digest | null
    key_service_audit_head: digest | null
    access_reconciliation_record_digest: digest
    access_reconciliation_disposition: consistent | inconsistent | not_established
  evaluators:
    declarative_reducer:
      version: string
      source_revision: string
      artifact_digest: digest
      sbom_digest: digest
      provenance_attestation_digest: digest
    predicate_metamorphic:
      version: string
      source_revision: string
      artifact_digest: digest
      sbom_digest: digest
      provenance_attestation_digest: digest
    same_code_control:
      version: string
      artifact_digest: digest
      standing: diagnostic_consistency_only
  independence_evidence:
    predicate_provenance_register_digest: digest
    answer_neutral_allowlist_digest: digest
    answer_neutral_probe_report_digest: digest
    independent_answer_neutral_review_digest: digest
    discriminator_register_digest: digest
    discriminator_liveness_digest: digest
    discriminator_removal_digest: digest
    discriminator_neutralization_digest: digest
    role_assignment_window_digest: digest
  observations:
    raw_trace_digest: digest
    evaluator_r_observation_digest: digest
    evaluator_p_observation_digest: digest
    mutation_validation_digest: digest
    integrity_report_digest: digest
    same_code_control_report_digest: digest
  human_record:
    reviewer_qualification_digests: [digest]
    conflict_declaration_digests: [digest]
    dissent_digests: [digest]
    abstention_digests: [digest]
    recusal_digests: [digest]
    adjudication_record_digests: [digest]
  challenges:
    challenge_register_digest: digest
    open_blocking_challenge_digests: [digest]
    open_nonblocking_challenge_digests: [digest]
    no_unresolved_blocking_challenge: boolean
  history:
    log_head: digest
    prior_receipt_ref: digest | null
    supersession_ref: digest | null
  claim_gate:
    implementation_not_refuted_under_committed_specification: boolean
    acceptable_custody_semantics_established: boolean
    evidence_terminal: SPECIFICATION_ASSURANCE_NOT_ESTABLISHED |
                       INDEPENDENCE_NOT_ESTABLISHED |
                       EVALUATOR_COVERAGE_NOT_ESTABLISHED | null
  bounded_claim:
    template_id: S0-K16-BOUND-2
    rendered_text_digest: digest | null
  signatures: [detached_signature]
  may_not_use_for: [string]
```

The same-code control remains present only as `diagnostic_consistency_only`; no field permits it to satisfy an independence, specification, or passage predicate.

### 8.2 Required attachments

- public specification, finite trace-domain, predicate DSL, compiler proof, and corpus manifests;
- frozen P37 predicate-provenance register;
- evaluator, generator, and relation-validator builds plus transitive provenance evidence;
- answer-neutral allowlist, poisoned-helper family matrix, and independent review;
- discriminator register and liveness/removal/neutralization witnesses;
- immutable implementation trace or content-addressed location;
- mutation certificates and `J_v` validation report;
- expectation inclusion proofs and `S_v` specification-assurance record;
- oracle/storage/network/key-service audit heads and reconciliation proof;
- role assignment and reviewer proficiency records;
- conflict, dissent, abstention, recusal, adjudication, and challenge records;
- exact execution recipes and environment lockfiles/image manifests;
- known limitations and unsupported predicates; and
- clean-build consistency report explicitly labeled non-verifying.

## 9. S0-K16 bounded statements and challenge gate

`S0-K16` states that benchmark passage is bounded and carries no authority. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding `S0-K16`.) The amendment separates two statements.

### 9.1 Evidence statement when specification assurance is not established

When all implementation-side gates pass but `S_v` is absent/failed/not established, the receipt may record only:

> For receipt `{receipt_digest}`, the named implementation artifact `{implementation_digest}` at revision `{revision}`, in environment `{environment_digest}`, was not refuted under committed specification `{specification_digest}` and expectation commitment `{expectation_commitment}` for population `{population_digest}` by declarative evaluator `{R_digest}` and predicate/metamorphic evaluator `{P_digest}`, subject to the limitations, evidence classes, and unresolved specification assurance recorded in the receipt. This is not benchmark passage and does not establish acceptable custody semantics.

The receipt also records `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`. That is a valid negative completion under `INT-K08`, not a fourth constitutional outcome type.

### 9.2 Bounded passage sentence

The stronger sentence may render only when `W=1`, scope-specific `S_v` is established, and `no_unresolved_blocking_challenge=true`:

> For receipt `{receipt_digest}`, the named implementation artifact `{implementation_digest}` at revision `{revision}`, executed in environment `{environment_digest}` against fixture population `{population_digest}` under public specification `{specification_digest}`, finite trace-domain profile `{domain_digest}`, sealed expectation version `{expectation_commitment}`, declarative evaluator `{R_digest}`, predicate/metamorphic evaluator `{P_digest}`, generator `{M_digest}`, and relation validator `{J_digest}`, satisfied the tested mandatory predicates and declared metamorphic relations recorded in this receipt, with no unresolved blocking challenge at claim freeze. This statement is limited to those artifacts, versions, inputs, observations, accepted specification-assurance scope, and assumptions. It does not establish untested behavior, general semantic correctness, production readiness, authority, legal sufficiency, or permission to score OPS-R15.

A receipt with one unresolved blocking challenge cannot produce this sentence (`A-21`).

Forbidden language includes:

- “PolicyOS is correct,” “safe,” “compliant,” “authorized,” or “production-ready”;
- “acceptable custody semantics established” when `S_v` is not established;
- “the custody kernel is verified” without the bounded artifact list;
- “all cases,” “all jurisdictions,” or “all future versions”;
- “independent” without attached provenance, answer-neutrality, access-reconciliation, discriminator, role, and proficiency evidence;
- any inference that `C` supplied correctness; and
- any statement that OPS-R15 is unblocked or scored.

## 10. Reproduction procedure

A reproducer must be able to:

1. obtain every public artifact and authorized sealed verification artifact by digest;
2. verify signatures, Merkle inclusion/consistency proofs, and all four access-audit heads;
3. verify the P37 predicate-provenance register and falsify-the-declaration probe;
4. rebuild `R_v`, `P_v`, `M_v`, and `J_v` from frozen sources in declared environments;
5. verify source/SBOM/generated-file/network provenance and role incompatibilities;
6. reproduce answer-neutral poisoned-helper results for every semantic family;
7. reproduce discriminator liveness/removal/neutralization results;
8. regenerate hidden cases when seed policy permits, or verify mutation certificates/commitments when it does not;
9. verify predicate compiler SAT/UNSAT/TAUT/NOT_TAUT certificates;
10. rerun the frozen implementation without altering inputs/environment and reproduce evaluator observations;
11. reconcile oracle/storage/network/key access evidence;
12. reproduce reviewer proficiency, `S_v`, challenge classification, and `no_unresolved_blocking_challenge`;
13. compare every output digest to the receipt; and
14. obtain the same permitted evidence or bounded claim text—or a documented mismatch.

A mismatch is evidence, not automatic attribution to the implementation. Any unsupported theory, timeout, missing proof, unavailable independent audit source, or unresolved decisive predicate blocks under `PV-K06`.

## 11. Standing

The amended generator/receipt model closes the research-specification gaps around M/J/R/P common ancestry, access reconciliation, discriminator adequacy, specification assurance, and blocking challenges. No such operational generator, relation validator, receipt issuer, proof checker, access reconciler, reviewer population, or independent institution is established here. The standing remains `accepted_narrow_scope`; technical execution evidence and the institutional function are both absent. The receipt remains a bounded evidence container, not a score or authority artifact.
