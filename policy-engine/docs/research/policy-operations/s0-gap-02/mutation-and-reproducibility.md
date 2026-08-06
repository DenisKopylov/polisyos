---
title: S0-GAP-02 — Adjacent-case generator, anti-memorization controls, and reproducibility receipt
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
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

A static public corpus tests whether an implementation recognizes known fixtures. It does not establish that behavior depends on custody semantics rather than fixture identifiers, prose fragments, event ordering, or memorized labels. `S0-K15` therefore requires adjacent and hidden cases and preservation of ambiguity/dissent. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K15`.) OPS-R15 already identifies ID branching and adjacent-case risk but supplies no executable generator or sealed population. (`policy-engine/docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md:362-386@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/docs/research/policy-operations/audits/ops-r15/ops-r15-test-and-probe-verification.md:80-160@1a7a2d05ebba22fae80e9934329e4b880806588e`.)

The generator is independent by construction. It may consume the public fixture schema, public semantic relations, and a hidden seed. It may not import production semantics, product fixture helpers, evaluator reducers, or plaintext expectation alternatives.

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

## 5. Generator interface and independence

```yaml
MutationGenerationRequest:
  public_specification_digest: digest
  public_corpus_manifest_digest: digest
  relation_catalogue_digest: digest
  base_fixture_digests: [digest]
  population_plan_commitment: digest
  seed_commitment: digest
  implementation_submission_digest: digest
  implementation_freeze_time: timestamp

MutationGenerationResult:
  generator_version: string
  generator_artifact_digest: digest
  generator_sbom_digest: digest
  seed_reveal_or_handle: opaque_value
  generated_fixture_digests: [digest]
  mutation_certificate_digests: [digest]
  validation_report_digest: digest
  generation_started_at: timestamp
  generation_completed_at: timestamp
  signatures: [detached_signature]
```

Enforcement requirements:

- generator build has no product checkout and no plaintext expectation access;
- seed is unavailable to implementation authors before submission freeze;
- generation starts after the implementation artifact digest is logged;
- transformation code is derived only from the public relation catalogue;
- an independent relation validator checks the mutation certificate; it may share syntax but not semantic transformation code;
- generated fixtures pass the same expected-answer leakage linter as public fixtures;
- any manual exclusion is signed with reason and included in the population receipt;
- generator failures or unsupported relations are visible and cannot inherit a satisfactory result, by analogy to `PV-K06`. (`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:164-182@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `PV-K06`.)

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

## 7. Anti-memorization decision rules

A mutation-family check is satisfied only when:

1. the base and mutated inputs are both in the committed run population;
2. the mutation certificate is valid;
3. the implementation outputs are immutable and bound to the same frozen revision/environment profile unless the relation explicitly compares environments;
4. both independent evaluators agree that the declared output relation holds;
5. no expected-answer leakage or adaptive rerun occurred;
6. no mandatory predicate is indeterminate;
7. all exclusions and reviewer disagreements are preserved.

An ID-renumbered or adjacent unseen case that changes the outcome without a registered semantic reason is a failure even when both individual outputs independently match some visible product label. The relation, not the label, is the oracle.

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
    public_corpus_manifest_digest: digest
    actual_population_digest: digest
    fixture_count: integer
    relation_family_counts: map<stable_identifier, integer>
    generator_version: string
    generator_artifact_digest: digest
    seed_commitment: digest
    seed_reveal_or_custody_ref: opaque_value
  oracle:
    expectation_version: string
    expectation_commitment_root: digest
    expectation_tree_size: integer
    access_log_head: digest
    key_profile_identifier: stable_identifier
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
  observations:
    raw_trace_digest: digest
    evaluator_r_observation_digest: digest
    evaluator_p_observation_digest: digest
    mutation_validation_digest: digest
    integrity_report_digest: digest
    same_code_control_report_digest: digest
  human_record:
    conflict_declaration_digests: [digest]
    dissent_digests: [digest]
    abstention_digests: [digest]
    recusal_digests: [digest]
    adjudication_record_digests: [digest]
    open_challenge_digests: [digest]
  history:
    log_head: digest
    prior_receipt_ref: digest | null
    supersession_ref: digest | null
  bounded_claim:
    template_id: S0-K16-BOUND-1
    rendered_text_digest: digest
  signatures: [detached_signature]
  may_not_use_for: [string]
```

### 8.2 Required attachments

- public specification and corpus manifests;
- evaluator build and provenance attestations;
- immutable implementation trace or content-addressed location;
- mutation certificates and relation-validation report;
- expectation inclusion proofs or authorized verification evidence;
- access-log consistency proof;
- conflict, dissent, abstention, and adjudication records;
- exact commands or declarative execution recipes;
- environment lockfiles/image manifests;
- known limitations and unsupported predicates;
- clean-build consistency control report, explicitly labeled non-verifying.

## 9. S0-K16 bounded-claim template

`S0-K16` states that benchmark passage is bounded and carries no authority. (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding `S0-K16`.) A receipt may render only the following form, with every placeholder bound to a digest:

> For receipt `{receipt_digest}`, the named implementation artifact `{implementation_digest}` at revision `{revision}`, executed in environment `{environment_digest}` against fixture population `{population_digest}` under public specification `{specification_digest}`, sealed expectation version `{expectation_commitment}`, declarative evaluator `{R_digest}`, predicate/metamorphic evaluator `{P_digest}`, and generator `{M_digest}`, satisfied the tested mandatory predicates and declared metamorphic relations recorded in this receipt. This statement is limited to those artifacts, versions, inputs, observations, and assumptions. It does not establish untested behavior, general semantic correctness, production readiness, institutional acceptance, authority, legal sufficiency, or permission to score OPS-R15.

Forbidden receipt language includes:

- “PolicyOS is correct,” “safe,” “compliant,” “authorized,” or “production-ready”;
- “the custody kernel is verified” without the bounded artifact list;
- “all cases,” “all jurisdictions,” or “all future versions”;
- “independent” without attached provenance/access evidence;
- any inference that a same-code clean rebuild supplied correctness;
- any statement that OPS-R15 is unblocked or scored.

## 10. Reproduction procedure

A reproducer must be able to:

1. obtain every public artifact and authorized sealed verification artifact by digest;
2. verify signatures, Merkle inclusion/consistency proofs, and access-log head;
3. rebuild `R_v`, `P_v`, and `M_v` from frozen sources in declared environments;
4. verify SBOM/provenance denylist and allowlist controls;
5. regenerate hidden cases when the seed policy permits, or verify their mutation certificates and commitments when it does not;
6. rerun the frozen implementation artifact without altering inputs or environment;
7. reproduce evaluator observations and relation checks;
8. compare all output digests to the receipt;
9. observe all dissent, abstention, recusal, challenge, and correction records;
10. obtain the same bounded claim text—or a documented mismatch.

A mismatch is reported as evidence. It is not automatically attributed to the implementation; it may identify environment drift, evaluator nonreproducibility, key/log problems, or an invalid original receipt.

## 11. Standing

This design resists fixture memorization by construction only after an independent generator, relation validator, sealed population process, and competent custodial function exist. None is appointed or implemented by this research. The receipt is a bounded evidence container, not a score or authority artifact.
