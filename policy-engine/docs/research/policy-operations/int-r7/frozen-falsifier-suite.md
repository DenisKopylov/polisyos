---
title: INT-R7 — Frozen Public Verification Falsifier Suite
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
remediated_after_verification: research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d
suite_id: INT-R7-PV-FALSIFIERS-v1
amended_suite_id: INT-R7-PV-FALSIFIERS-v2
controlling_remediation: "§10 — Bounded remediation after conformance verification"
suite_frozen: true
research_only: true
int_r8_seam: proof_only
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - permission to publish a governed result
  - automatic amendment of any plan or system-design decision
---

# Frozen falsifier suite

## 1. Conformance target

This suite is an executable semantic specification for the verifier/proof lifecycle. It does not choose a package format, programming language, database, API, cryptographic provider, CA, TSA, log, witness, or archive.

A conforming harness supplies:

```text
verify_public_record(
    record,
    proof_closure,
    trust_snapshot,
    status_snapshot,
    witness_snapshot,
    algorithm_policy,
    verification_time,
    mode = online | offline
) -> VerificationResult
```

`VerificationResult` exposes at least:

```text
top_level_outcome
as_of
predicate_vector
reason_codes[]
evidence_ids[]
network_dependencies_contacted[]
profile_version
verifier_revision
```

The predicate vector contains the semantic predicates named in `threat-model-and-verification-predicates.md`, including content/signature, authority, trusted time/status, INT-R8 projection, transparency/common view, GY-N12 epoch/currentness, preservation, algorithm policy, and offline closure.

## 2. Freeze rules

1. Cases `F-01` through `F-18` are the frozen minimum.
2. A case passes only when the exact terminal outcome and all listed predicate expectations hold.
3. A warning attached to a stronger positive result is failure.
4. Missing evidence fails closed; the harness may not switch to “signature-only verification.”
5. Test fixtures must be generated from a valid positive baseline unless the case says otherwise.
6. Every mutation must alter only the named property; unrelated corruption does not prove the target invariant.
7. Human and machine projections must agree on the terminal outcome and reason codes.
8. Offline cases run with network access blocked at the process/sandbox boundary and assert zero contacted dependencies.
9. Suite passage is bounded by `S0-K16`: it proves only that the named implementation, revision, environment, evaluator, and fixture set produced the expected predicates.
10. Future cases may be added under a new suite version; existing IDs and expected outcomes are not weakened in place.

## 3. Canonical baseline fixture

The harness constructs a baseline `B0` satisfying:

```yaml
baseline_id: B0-valid-current-procedural
claim_class: procedural_custody_claim
profile: recognized
canonical_statement: valid
record_commitments: match
int_r8_projection_relation: valid
audience: citizen_public
audience_use: citizen_public
jurisdiction: configured_and_accepted
authority_boundary: configured_and_accepted
gy_n12_epoch: current
procedural_history:
  prospective_seal: valid
  firstness_commitment: valid
  chronology: valid
  prohibited_substitution: none
  adjudication: valid
  dissent_and_negatives: committed
issuer:
  signature: valid
  credential_at_issuance: valid
  authority_at_issuance: valid
trusted_time: valid
issuance_before_revocation_or_compromise: true
transparency:
  inclusion: valid
  consistency: valid
  witness_policy: satisfied
status_snapshot:
  authentic: true
  current: true
  stale: false
  withdrawn: false
  superseded: false
preservation:
  originals: retained
  validation_material: complete
  chain: valid
algorithm_policy: satisfied
offline_closure: complete
expected_outcome: VERIFIED_CURRENT_AS_OF
```

A `delta` baseline `B1` is identical where applicable and additionally binds a non-empty declared obligation set, maintained assumptions, relative-basis rider, and proof profile.

## 4. Frozen cases

```yaml
suite:
  id: INT-R7-PV-FALSIFIERS-v1
  frozen: true
  cases:

    - id: F-01
      name: forged_legacy_fnv_packet
      threat: public deterministic client-side self-consistency masquerades as authority
      base: legacy_publication_packet
      mutation:
        - replace every attacker-chosen JSON field, including claimed issuer and status
        - recompute the public-salt 32-bit FNV value exactly as publicationPacket.ts does
        - construct a syntactically valid legacy URL/token
      execution:
        mode: online
        trust_inputs: independent
      expected:
        top_level_outcome: LEGACY_SELF_CONSISTENCY_NOT_AUTHORITY
        predicates:
          SignatureValid: false
          AuthorityValidAtIssuance: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
          - AUTHENTIC_HISTORICAL_WITHDRAWN
          - unqualified_Verified
        required_reason_codes:
          - LEGACY_PUBLIC_HASH_NOT_CRYPTOGRAPHIC_PROOF
      invariant: public recomputation can never create authority

    - id: F-02
      name: replaced_payload_under_valid_proof
      threat: content substitution
      base: B0-valid-current-procedural
      mutation:
        - change one semantically material record byte after proof issuance
        - keep original proof closure, signatures, timestamps, log proof, and status snapshots
      execution:
        mode: online
      expected:
        top_level_outcome: TAMPERED_OR_SIGNATURE_INVALID
        predicates:
          ContentBound: false
          SignatureValid: false_or_not_applicable_after_content_failure
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: not_projected_as_positive
        required_reason_codes:
          - RECORD_COMMITMENT_MISMATCH
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
      invariant: exact record bytes and semantic commitments are signed

    - id: F-03
      name: package_payload_signature_and_key_replacement
      threat: self-authenticating offline package
      base: B0-valid-current-procedural
      mutation:
        - replace record and canonical statement
        - generate attacker key and signature over replacement
        - replace package-bundled public key and key identifier
        - leave independently authenticated trust snapshot unchanged
      execution:
        mode: offline
        network: denied
      expected:
        top_level_outcome: AUTHORITY_NOT_ESTABLISHED
        predicates:
          SignatureValid: true_under_attacker_key_only
          SignerCredentialValidAtIssuance: false
          AuthorityValidAtIssuance: false
          HistoricalAuthenticity: false
          OfflineClosureComplete: true
        required_reason_codes:
          - PACKAGE_KEY_NOT_IN_INDEPENDENT_TRUST
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
        network_dependencies_contacted: []
      invariant: an untrusted package cannot supply its own root of trust

    - id: F-04
      name: forged_after_effective_revocation
      threat: compromised signer backdates a post-revocation signature
      base: B0-valid-current-procedural
      mutation:
        - use compromised issuer key to sign replacement statement after authenticated revocation time t_r
        - set signer-controlled signed_at to a time before t_r
        - obtain trusted timestamp t_s where t_s >= t_r
        - include otherwise valid content and log evidence
      execution:
        mode: online
      expected:
        top_level_outcome: TAMPERED_OR_SIGNATURE_INVALID
        predicates:
          SignatureValid: true
          TrustedIssuanceTimeEstablished: true
          PreCompromiseOrRevocationEstablished: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - ISSUANCE_NOT_BEFORE_REVOCATION
          - SELF_DECLARED_SIGNING_TIME_IGNORED
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
      invariant: trusted time, not signer metadata, orders issuance against revocation

    - id: F-05
      name: valid_before_prospective_revocation
      threat: timeless revocation erases authentic history
      base: B0-valid-current-procedural
      mutation:
        - append authenticated prospective key revocation at t_r
        - retain trusted issuance evidence t_s where t_s < t_r
        - configure GY-N12 status to current as of t_q after t_r
        - make no compromise allegation applying before t_r
      execution:
        mode: online
      expected:
        top_level_outcome: VERIFIED_CURRENT_AS_OF
        predicates:
          SignatureValid: true
          PreCompromiseOrRevocationEstablished: true
          HistoricalAuthenticity: true
          CurrentAuthorityAtAsOf: true
        required_reason_codes:
          - KEY_REVOKED_AFTER_AUTHENTIC_ISSUANCE
        forbidden_outcomes:
          - TAMPERED_OR_SIGNATURE_INVALID
          - temporal_timeless_REVOKED_terminal
      invariant: prospective key revocation and record currentness are separate

    - id: F-06
      name: issuance_inside_uncertain_compromise_interval
      threat: optimistic treatment of unknown compromise time
      base: B0-valid-current-procedural
      mutation:
        - establish authenticated compromise interval [t_c_min, t_c_max]
        - provide trusted issuance bound t_s that lies within the interval
        - provide no independent evidence resolving ordering
      execution:
        mode: online
      expected:
        top_level_outcome: TEMPORAL_VALIDITY_INDETERMINATE
        predicates:
          SignatureValid: true
          TrustedIssuanceTimeEstablished: true
          PreCompromiseOrRevocationEstablished: false
          TemporalValidityIndeterminate: true
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - ISSUANCE_OVERLAPS_COMPROMISE_INTERVAL
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
      invariant: uncertainty is a terminal non-positive result, not a warning

    - id: F-07
      name: stale_gy_n12_epoch_certificate
      threat: authentic old epoch displayed as current
      base: B0-valid-current-procedural
      mutation:
        - retain authentic historical signature and epoch closure
        - append authenticated GY-N12 revision trigger and stale/revalidation-required status
        - omit any successful revalidation or successor current status
      execution:
        mode: online
      expected:
        top_level_outcome: AUTHENTIC_HISTORICAL_STALE
        predicates:
          HistoricalAuthenticity: true
          EpochHistoricallyAuthentic: true
          StaleAtAsOf: true
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - EPOCH_REVALIDATION_REQUIRED
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - stale_hidden_in_details_only
      invariant: historical authenticity never masks GY-N12 staleness

    - id: F-08
      name: split_view_transparency_server
      threat: equivocation despite locally valid Merkle proofs
      base: B0-valid-current-procedural
      mutation:
        - primary log serves checkpoint A to verifier group 1 and conflicting checkpoint B to verifier group 2
        - provide valid inclusion and internal consistency proofs inside each view
        - supply independent witness checkpoints that disagree or fail quorum
      execution:
        mode: online
      expected:
        top_level_outcome: COMMON_VIEW_NOT_ESTABLISHED
        predicates:
          LogIncluded: true
          LogAppendOnlyConsistent: true_within_presented_view
          WitnessPolicySatisfied: false
          CommonViewEstablished: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - WITNESS_CHECKPOINT_CONFLICT
          - SPLIT_VIEW_POSSIBLE
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
      invariant: Merkle consistency within one view is not common-view proof

    - id: F-09
      name: replay_under_wrong_audience
      threat: cross-purpose replay
      base: B0-valid-current-procedural
      mutation:
        - verify an otherwise valid citizen_public statement for a relying purpose requiring agency_adjudication audience
        - provide no authenticated audience-transfer policy
      execution:
        mode: online
      expected:
        top_level_outcome: AUTHORITY_NOT_ESTABLISHED
        predicates:
          SignatureValid: true
          AudienceBound: false
          AuthorityValidAtIssuance: false_for_requested_use
          HistoricalAuthenticity: false_for_requested_use
        required_reason_codes:
          - AUDIENCE_OR_PURPOSE_MISMATCH
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
      invariant: a signature is not replayable under an unbound relying purpose

    - id: F-10
      name: wrong_jurisdiction_or_authority_boundary
      threat: valid credential overclaims institutional competence
      base: B0-valid-current-procedural
      mutation:
        - request verification under jurisdiction J2 while statement and authority evidence are scoped to J1
        - or mutate claimed authority boundary without re-signing
        - provide no cross-jurisdiction recognition policy covering the use
      execution:
        mode: online
      expected:
        top_level_outcome: AUTHORITY_NOT_ESTABLISHED
        predicates:
          SignatureValid: true_if_statement_unmodified_otherwise_false
          JurisdictionBound: false
          AuthorityBoundaryBound: false_or_not_accepted
          AuthorityValidAtIssuance: false_for_requested_use
        required_reason_codes:
          - JURISDICTION_POLICY_MISMATCH
          - AUTHORITY_BOUNDARY_MISMATCH
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
      invariant: cryptographic identity does not create cross-jurisdiction competence

    - id: F-11
      name: delta_basis_stripped_or_substituted
      threat: semantic substitution of a bare probability
      base: B1-valid-current-delta
      mutation:
        - remove the declared obligation-set commitment from the presented statement, or substitute a smaller set
        - retain the same displayed delta
        - retain the original signature or create a signature over the incomplete statement with an otherwise authorized key
      execution:
        mode: online
      expected:
        top_level_outcome: BASIS_INCOMPLETE
        predicates:
          SignatureValid: false_if_original_signature_or_true_over_incomplete_statement
          BasisBound: false
          StatementComplete: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - DECLARED_OBLIGATION_SET_MISSING_OR_MISMATCHED
          - RELATIVE_BASIS_CLAIM_INCOMPLETE
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - numeric_delta_verified
      invariant: delta, declared set, assumptions, and rider are one signed proposition

    - id: F-12
      name: procedural_backdating_or_firstness_substitution
      threat: valid signature over a false chronology claim
      base: B0-valid-current-procedural
      mutation:
        - remove or contradict the trusted prospective seal
        - or insert an earlier candidate not covered by the firstness commitment
        - or append an unlogged prohibited substitution
        - keep a mathematically valid final statement signature
      execution:
        mode: online
      expected:
        top_level_outcome: PROCEDURAL_HISTORY_NOT_ESTABLISHED
        predicates:
          SignatureValid: true
          ProceduralHistoryBound: false
          StatementComplete: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - PROSPECTIVE_SEAL_OR_CHRONOLOGY_INVALID
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - probability_score_substitute
      invariant: signing a narrative does not prove prospectivity, chronology, or firstness

    - id: F-13
      name: compromised_single_signer_below_required_threshold
      threat: one insider creates an apparently valid record despite multi-party policy
      base: B0-valid-current-procedural
      mutation:
        - configure issuing policy to require threshold or multiple independent authorizations
        - compromise one signer/share below threshold
        - produce one valid partial or single-party signature
        - keep all other statement/evidence predicates valid
      execution:
        mode: online
      expected:
        top_level_outcome: AUTHORITY_NOT_ESTABLISHED
        predicates:
          SignatureValid: false_under_required_signature_policy
          AuthorityValidAtIssuance: false
          HistoricalAuthenticity: false
        required_reason_codes:
          - REQUIRED_SIGNER_QUORUM_NOT_SATISFIED
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
      invariant: configured multi-party authorization cannot be downgraded to one key

    - id: F-14
      name: archival_verification_after_rotation_and_algorithm_deprecation_with_timely_renewal
      threat: treating normal rotation or deprecated original algorithms as automatic historical failure
      base: B0-valid-current-procedural
      mutation:
        - normally retire and destroy original private key with evidence
        - deprecate original signature or hash for new use
        - before historical-validation cutoff, validate complete closure and append preservation renewal under an accepted successor suite
        - retain original bytes, original signature, old and new commitments, trusted time, log and witness evidence
      execution:
        mode: offline
        network: denied
        verification_time: after_original_algorithm_deprecation
      expected:
        top_level_outcome: VERIFIED_CURRENT_AS_OF
        predicates:
          SignatureValid: true_under_historical_policy_via_preservation_chain
          HistoricalAuthenticity: true
          PreservationChainValid: true
          AlgorithmPolicySatisfied: true
          CurrentAuthorityAtAsOf: true
          OfflineClosureComplete: true
        required_reason_codes:
          - HISTORICAL_ALGORITHM_PRESERVED_BY_TIMELY_RENEWAL
        forbidden_outcomes:
          - TAMPERED_OR_SIGNATURE_INVALID
          - original_key_must_still_be_active
        network_dependencies_contacted: []
      invariant: timely append-only renewal preserves history without silent re-signing

    - id: F-15
      name: archival_verification_after_algorithm_failure_without_timely_renewal
      threat: late re-signing launders a broken historical chain
      base: B0-valid-current-procedural
      mutation:
        - allow original hash/signature validation policy to expire or become practically broken
        - omit any renewal made while prior evidence was trustworthy
        - after failure, compute a new digest and sign the surviving bytes
      execution:
        mode: offline
        network: denied
      expected:
        top_level_outcome: PRESERVATION_CHAIN_BROKEN
        predicates:
          OriginalBytesRetained: true
          PreservationChainValid: false
          AlgorithmPolicySatisfied: false
          HistoricalAuthenticity: false
          CurrentAuthorityAtAsOf: false
        required_reason_codes:
          - RENEWAL_AFTER_TRUST_LOSS_CANNOT_REPAIR_HISTORY
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - AUTHENTIC_HISTORICAL_AS_OF
        network_dependencies_contacted: []
      invariant: later re-signing cannot retroactively restore lost authenticity

    - id: F-16
      name: complete_offline_verification_without_live_dependencies
      threat: nominal offline verifier silently relies on live PolicyOS, CA, OCSP, TSA, IdP, log, or witness endpoints
      base: B0-valid-current-procedural
      mutation:
        - none_to_record
        - block all network access
        - supply complete independently authenticated offline closure and status snapshot
      execution:
        mode: offline
        network: denied
      expected:
        top_level_outcome: VERIFIED_CURRENT_AS_OF
        predicates:
          OfflineClosureComplete: true
          HistoricalAuthenticity: true
          CurrentAuthorityAtAsOf: true
        required_reason_codes:
          - OFFLINE_VERIFIED_AS_OF_AUTHENTICATED_SNAPSHOT
        network_dependencies_contacted: []
        report_constraints:
          - outcome_text_contains_as_of
          - outcome_does_not_claim_current_now_beyond_snapshot
      invariant: offline verification is closed and explicitly time-bounded

    - id: F-17
      name: withdrawn_but_verifiable_record
      threat: withdrawal either erases history or remains hidden behind a valid signature
      base: B0-valid-current-procedural
      mutation:
        - append authenticated challenge and withdrawal event under canonical GY-N12/current-authority semantics
        - retain original bytes and full issuance/preservation evidence
        - include withdrawal in transparency history with witnessed checkpoint
      execution:
        mode: online
      expected:
        top_level_outcome: AUTHENTIC_HISTORICAL_WITHDRAWN
        predicates:
          HistoricalAuthenticity: true
          WithdrawnAtAsOf: true
          CurrentAuthorityAtAsOf: false
          CommonViewEstablished: true
        required_reason_codes:
          - HISTORICALLY_AUTHENTIC_CURRENT_AUTHORITY_WITHDRAWN
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - TAMPERED_OR_SIGNATURE_INVALID
        report_constraints:
          - original_record_remains_accessible
          - withdrawal_is_prominent
      invariant: append-only withdrawal preserves historical reproducibility and removes current authority

    - id: F-18
      name: successor_organization_identity_substitution
      threat: successor custodian rewrites predecessor issuer or uses custody to claim original authority
      base: B0-valid-current-procedural
      mutation:
        - reorganize or abolish predecessor organization
        - append a valid successor custody/preservation statement
        - replace displayed original issuer with successor, or replace predecessor trust material with successor key as if original
        - retain otherwise valid historical evidence
      execution:
        mode: offline
        network: denied
      expected:
        top_level_outcome: AUTHORITY_NOT_ESTABLISHED
        predicates:
          SignatureValid: true_for_successor_custody_statement
          AuthorityValidAtIssuance: false_if_successor_is_claimed_as_original_issuer
          HistoricalAuthenticity: false_for_substituted_attribution
          PreservationChainValid: true_only_if_successor_role_is_correctly_labeled
        required_reason_codes:
          - SUCCESSOR_CUSTODY_IS_NOT_PREDECESSOR_ISSUANCE
        forbidden_outcomes:
          - VERIFIED_CURRENT_AS_OF
          - successor_displayed_as_original_issuer
        network_dependencies_contacted: []
      invariant: organizational succession appends custody/status evidence and never rewrites original attribution
```

## 5. Required metamorphic extensions

For every case, the implementation test suite must generate at least these variants without changing the expected semantic class:

- alternate field order and benign serialization variation under the same canonical semantics;
- another supported locale and accessible rendering;
- online and offline execution where the necessary closure exists;
- direct file import and URL/QR retrieval;
- one sibling verifier consumer, so the fix is not isolated to the dashboard;
- malformed, missing, and contradictory versions of the same evidence class;
- policy-version mismatch and unknown algorithm identifier;
- cached/stale UI state before verification completes.

These variants enforce P33: a named probe is a witness, not the specification.

## 6. Harness assertions

A conformance runner must assert:

```text
for each case:
    result = verify_public_record(case.inputs)
    assert result.top_level_outcome == case.expected.top_level_outcome
    assert every listed predicate equals its expected value/class
    assert every required reason code is present
    assert no forbidden outcome or stronger human label appears
    assert machine and human semantics agree
    if mode == offline:
        assert result.network_dependencies_contacted == []
```

Additional structural assertions:

- the positive UI cannot consume the legacy FNV verifier;
- a server-provided `verified` Boolean is ignored as evidence;
- every public verifier routes through one canonical predicate evaluator;
- missing mandatory evidence cannot be demoted to warning-only success;
- historical/current statuses are independent fields/predicates;
- a preservation signature cannot populate the original-issuer field;
- INT-R8 proof failure cannot be overridden by signature success;
- GY-N12 stale/withdrawn/superseded status cannot be overridden by cached presentation state.

## 7. Exact expected suite result

A suite run is conformant only when:

```yaml
suite_id: INT-R7-PV-FALSIFIERS-v1
cases_total: 18
cases_passed: 18
cases_failed: 0
unexpected_positive_outcomes: 0
offline_network_contacts: 0
human_machine_semantic_mismatches: 0
legacy_fnv_positive_authority_paths: 0
```

Any nonzero failure keeps the first-public-signature gate closed.

## 8. Scope of passage

Passing this suite does not establish:

- legal compliance or signature sufficiency in a jurisdiction;
- institutional competence;
- content safety beyond the supplied INT-R8 fixtures;
- correctness for untested algorithms, profiles, environments, witnesses, or record classes;
- production readiness or permission to publish.

Under `S0-K16`, the passage report must name the implementation, commit, environment, evaluator version, trust/status fixtures, algorithm policies, and all 18 results.

## 9. Controlling amendment — `INT-R7-PV-FALSIFIERS-v2`

> **Remediation notice.** Section 10 controls the typed grammar, B0/B1 baseline pairs, and the six predicate overlays identified by `INT-R7-V-103` and `INT-R7-V-104`. The original §9 text remains visible as amendment history; where it conflicts with §10, it is not the executable v2 contract.

Suite v1 is preserved above as the audited history. It is **not executable as written** because conditional/disjunctive pseudo-values conflict with exact equality and several families combine distinct mutations. Suite v2 supersedes v1 for conformance while preserving `F-01` through `F-18` as immutable family IDs.

INT-R8 remains unaudited and GY-N12 remains planned. Positive dependency material in this suite is therefore a **fixture contract only**, not evidence that PolicyOS can currently produce the result.

### 9.1 Exact value model

Each expectation has this structure:

```yaml
SomePredicate:
  value: true | false | null | established | contradicted | not_established |
    latest_established_under_policy | supplied_snapshot_only | rollback_detected |
    public_available | records_process_available | competently_restricted
  evaluation_status: evaluated | short_circuited | not_applicable | dependency_unavailable
```

`value: null` is permitted only with `short_circuited`, `not_applicable`, or `dependency_unavailable`. Before comparison, the harness expands the named exact baseline; no relevant result may remain absent after expansion.

### 9.2 Static validator specification

A static suite validator rejects the suite before execution when:

1. a predicate/dimension slot contains a scalar outside the exact value set above;
2. any value contains `or`, `if`, `otherwise`, `under_`, `false_`, `true_`, whitespace prose, or another conditional fragment;
3. `evaluation_status: evaluated` is paired with `value: null`;
4. a subfixture lacks one exact top-level outcome;
5. a family alternative is expressed inside one mutation/expectation instead of a separately identified subfixture;
6. an offline subfixture omits an exact network-contact expectation;
7. expanded machine and human expected outcome/reason-code sets differ;
8. family or subfixture denominators differ from the frozen manifest;
9. an existing family ID is removed or weakened without a new suite version.

This is a static **specification**, not repository automation or an implementation script.

### 9.3 Exact baselines

```yaml
baselines:
  B0:
    dimensions:
      IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
      ProjectionFaithful: {value: established, evaluation_status: evaluated}
      PublicHistoryEstablished: {value: established, evaluation_status: evaluated}
      DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
      CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
      StatusSnapshotSelection: {value: latest_established_under_policy, evaluation_status: evaluated}
      EvidenceObtainability: {value: public_available, evaluation_status: evaluated}
    predicates:
      ContentBound: {value: true, evaluation_status: evaluated}
      SignatureValid: {value: true, evaluation_status: evaluated}
      SignaturePolicySatisfied: {value: true, evaluation_status: evaluated}
      BasisBound: {value: true, evaluation_status: not_applicable}
      ProceduralHistoryBound: {value: true, evaluation_status: evaluated}
      OfflineClosureComplete: {value: true, evaluation_status: evaluated}
  B1:
    inherit: B0
    predicates:
      BasisBound: {value: true, evaluation_status: evaluated}
```

### 9.4 Exact family/subfixture manifest

```yaml
suite:
  id: INT-R7-PV-FALSIFIERS-v2
  families_total: 23
  subfixtures_total: 29
  families:
    - family_id: F-01
      subfixtures:
        - id: F-01a
          base: legacy_publication_packet
          mutation: attacker_replaces_payload_and_recomputes_public_fnv
          expected:
            top_level_outcome: LEGACY_SELF_CONSISTENCY_NOT_AUTHORITY
            dimensions:
              IssuerIssuanceAuthentic: {value: not_established, evaluation_status: evaluated}
              ProjectionFaithful: {value: not_established, evaluation_status: evaluated}
              PublicHistoryEstablished: {value: not_established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: not_established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: not_established, evaluation_status: evaluated}
            predicates:
              SignatureValid: {value: false, evaluation_status: evaluated}
            required_reason_codes: [LEGACY_PUBLIC_HASH_NOT_CRYPTOGRAPHIC_PROOF]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-02
      subfixtures:
        - id: F-02a
          base: B0
          mutation: semantically_material_record_byte_changed_after_issuance
          expected:
            top_level_outcome: TAMPERED_OR_SIGNATURE_INVALID
            predicates:
              ContentBound: {value: false, evaluation_status: evaluated}
              SignatureValid: {value: null, evaluation_status: short_circuited}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [RECORD_COMMITMENT_MISMATCH]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-03
      subfixtures:
        - id: F-03a
          base: B0
          mutation: package_payload_signature_and_bundled_key_replaced
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: AUTHORITY_NOT_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              SignaturePolicySatisfied: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: not_established, evaluation_status: evaluated}
            required_reason_codes: [PACKAGE_KEY_NOT_IN_INDEPENDENT_TRUST]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-04
      subfixtures:
        - id: F-04a
          base: B0
          mutation: valid_signature_timestamped_at_or_after_effective_revocation
          expected:
            top_level_outcome: ISSUANCE_TEMPORALLY_UNAUTHORIZED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              TrustedIssuanceTimeEstablished: {value: true, evaluation_status: evaluated}
              PreCompromiseOrRevocationEstablished: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [ISSUANCE_NOT_BEFORE_REVOCATION, SELF_DECLARED_SIGNING_TIME_IGNORED]
            forbidden_outcomes: [TAMPERED_OR_SIGNATURE_INVALID, VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-05
      subfixtures:
        - id: F-05a
          base: B0
          mutation: prospective_key_revocation_after_trusted_authentic_issuance
          expected:
            top_level_outcome: VERIFIED_CURRENT_AS_OF
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              PreCompromiseOrRevocationEstablished: {value: true, evaluation_status: evaluated}
            required_reason_codes: [KEY_REVOKED_AFTER_AUTHENTIC_ISSUANCE]
            forbidden_outcomes: [TAMPERED_OR_SIGNATURE_INVALID]

    - family_id: F-06
      subfixtures:
        - id: F-06a
          base: B0
          mutation: trusted_issuance_bound_overlaps_uncertain_compromise_interval
          expected:
            top_level_outcome: TEMPORAL_VALIDITY_INDETERMINATE
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              TrustedIssuanceTimeEstablished: {value: true, evaluation_status: evaluated}
              PreCompromiseOrRevocationEstablished: {value: false, evaluation_status: evaluated}
              TemporalValidityIndeterminate: {value: true, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: not_established, evaluation_status: evaluated}
            required_reason_codes: [ISSUANCE_OVERLAPS_COMPROMISE_INTERVAL]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-07
      subfixtures:
        - id: F-07a
          base: B0
          mutation: authenticated_revision_trigger_marks_epoch_stale
          expected:
            top_level_outcome: AUTHENTIC_HISTORICAL_STALE
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: contradicted, evaluation_status: evaluated}
            predicates:
              StaleAtAsOf: {value: true, evaluation_status: evaluated}
            required_reason_codes: [EPOCH_REVALIDATION_REQUIRED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-08
      subfixtures:
        - id: F-08a
          base: B0
          mutation: log_serves_conflicting_internally_consistent_views
          expected:
            top_level_outcome: COMMON_VIEW_NOT_ESTABLISHED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              ProjectionFaithful: {value: established, evaluation_status: evaluated}
              PublicHistoryEstablished: {value: not_established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
            predicates:
              LogIncluded: {value: true, evaluation_status: evaluated}
              LogAppendOnlyConsistent: {value: true, evaluation_status: evaluated}
              WitnessPolicySatisfied: {value: false, evaluation_status: evaluated}
              CommonViewEstablished: {value: false, evaluation_status: evaluated}
            required_reason_codes: [WITNESS_CHECKPOINT_CONFLICT, SPLIT_VIEW_POSSIBLE]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-09
      subfixtures:
        - id: F-09a
          base: B0
          mutation: authentic_statement_replayed_for_unpermitted_relying_purpose
          expected:
            top_level_outcome: AUTHORITY_NOT_ESTABLISHED_FOR_REQUESTED_USE
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
            predicates:
              AudienceBound: {value: false, evaluation_status: evaluated}
            required_reason_codes: [AUDIENCE_OR_PURPOSE_MISMATCH]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-10
      subfixtures:
        - id: F-10a
          base: B0
          mutation: authentic_j1_statement_requested_for_unrecognized_j2_use
          expected:
            top_level_outcome: AUTHORITY_NOT_ESTABLISHED_FOR_REQUESTED_USE
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
            predicates:
              JurisdictionBound: {value: false, evaluation_status: evaluated}
            required_reason_codes: [JURISDICTION_POLICY_MISMATCH]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: F-10b
          base: B0
          mutation: signed_authority_boundary_bytes_changed_without_resigning
          expected:
            top_level_outcome: TAMPERED_OR_SIGNATURE_INVALID
            predicates:
              ContentBound: {value: false, evaluation_status: evaluated}
              SignatureValid: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [AUTHORITY_BOUNDARY_COMMITMENT_MISMATCH]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-11
      subfixtures:
        - id: F-11a
          base: B1
          mutation: obligation_basis_removed_while_original_signature_retained
          expected:
            top_level_outcome: TAMPERED_OR_SIGNATURE_INVALID
            predicates:
              BasisBound: {value: false, evaluation_status: evaluated}
              SignatureValid: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [DECLARED_OBLIGATION_SET_MISSING_OR_MISMATCHED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: F-11b
          base: B1
          mutation: authorized_key_signs_bare_delta_without_required_basis
          expected:
            top_level_outcome: BASIS_INCOMPLETE
            predicates:
              BasisBound: {value: false, evaluation_status: evaluated}
              SignatureValid: {value: true, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [RELATIVE_BASIS_CLAIM_INCOMPLETE]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-12
      subfixtures:
        - id: F-12a
          base: B0
          mutation: trusted_prospective_seal_absent
          expected:
            top_level_outcome: PROCEDURAL_HISTORY_NOT_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              ProceduralHistoryBound: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [PROSPECTIVE_SEAL_INVALID]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: F-12b
          base: B0
          mutation: earlier_candidate_outside_firstness_commitment
          expected:
            top_level_outcome: PROCEDURAL_HISTORY_NOT_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              ProceduralHistoryBound: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [FIRSTNESS_CONTRADICTED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: F-12c
          base: B0
          mutation: prohibited_substitution_not_appended_to_history
          expected:
            top_level_outcome: PROCEDURAL_HISTORY_NOT_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              ProceduralHistoryBound: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [PROHIBITED_SUBSTITUTION_UNLOGGED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-13
      subfixtures:
        - id: F-13a
          base: B0
          mutation: one_valid_signer_below_configured_multi_party_threshold
          expected:
            top_level_outcome: AUTHORITY_NOT_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              SignaturePolicySatisfied: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
            required_reason_codes: [REQUIRED_SIGNER_QUORUM_NOT_SATISFIED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: F-14
      subfixtures:
        - id: F-14a
          base: B0
          mutation: timely_complete_preservation_renewal_before_algorithm_cutoff
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: VERIFIED_CURRENT_AS_OF
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
            predicates:
              PreservationChainValid: {value: true, evaluation_status: evaluated}
              AlgorithmPolicySatisfied: {value: true, evaluation_status: evaluated}
            required_reason_codes: [HISTORICAL_ALGORITHM_PRESERVED_BY_TIMELY_RENEWAL]
            forbidden_outcomes: [TAMPERED_OR_SIGNATURE_INVALID]

    - family_id: F-15
      subfixtures:
        - id: F-15a
          base: B0
          mutation: renewal_created_only_after_prior_trust_loss
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: PRESERVATION_CHAIN_BROKEN
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: contradicted, evaluation_status: evaluated}
            predicates:
              PreservationChainValid: {value: false, evaluation_status: evaluated}
              AlgorithmPolicySatisfied: {value: false, evaluation_status: evaluated}
            required_reason_codes: [RENEWAL_AFTER_TRUST_LOSS_CANNOT_REPAIR_HISTORY]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: F-16
      subfixtures:
        - id: F-16a
          base: B0
          mutation: complete_independently_authenticated_closure_with_network_denied
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: VERIFIED_CURRENT_AS_OF
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              ProjectionFaithful: {value: established, evaluation_status: evaluated}
              PublicHistoryEstablished: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
              StatusSnapshotSelection: {value: latest_established_under_policy, evaluation_status: evaluated}
              EvidenceObtainability: {value: public_available, evaluation_status: evaluated}
            predicates:
              OfflineClosureComplete: {value: true, evaluation_status: evaluated}
            required_reason_codes: [OFFLINE_VERIFIED_AS_OF_AUTHENTICATED_SNAPSHOT]
            forbidden_outcomes: [unqualified_Verified]

    - family_id: F-17
      subfixtures:
        - id: F-17a
          base: B0
          mutation: authenticated_withdrawal_appended_with_original_closure_retained
          expected:
            top_level_outcome: AUTHENTIC_HISTORICAL_WITHDRAWN
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              ProjectionFaithful: {value: established, evaluation_status: evaluated}
              PublicHistoryEstablished: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: contradicted, evaluation_status: evaluated}
            predicates:
              WithdrawnAtAsOf: {value: true, evaluation_status: evaluated}
            required_reason_codes: [HISTORICALLY_AUTHENTIC_CURRENT_AUTHORITY_WITHDRAWN]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, TAMPERED_OR_SIGNATURE_INVALID]

    - family_id: F-18
      subfixtures:
        - id: F-18a
          base: B0
          mutation: successor_custody_signature_presented_as_predecessor_issuance
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: AUTHORITY_NOT_ESTABLISHED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
            predicates:
              PresentedOriginalIssuerAttributionValid: {value: false, evaluation_status: evaluated}
              SuccessorCustodyStatementValid: {value: true, evaluation_status: evaluated}
            required_reason_codes: [SUCCESSOR_CUSTODY_IS_NOT_PREDECESSOR_ISSUANCE]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: F-18b
          base: B0
          mutation: competent_successor_custody_statement_preserves_predecessor_attribution
          execution: {mode: offline, expected_network_contacts: 0}
          expected:
            top_level_outcome: AUTHENTIC_HISTORICAL_SUPERSEDED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: contradicted, evaluation_status: evaluated}
            predicates:
              PresentedOriginalIssuerAttributionValid: {value: true, evaluation_status: evaluated}
              SuccessorCustodyStatementValid: {value: true, evaluation_status: evaluated}
              SuccessorLinkValid: {value: true, evaluation_status: evaluated}
            required_reason_codes: [LAWFUL_SUCCESSOR_CUSTODY_PRESERVES_ORIGINAL_ISSUER]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: AX-01
      name: signer_and_timestamp_authority_collusion
      subfixtures:
        - id: AX-01a
          base: B0
          mutation: signer_and_tsa_backdate_together_without_independent_chronology
          expected:
            top_level_outcome: ISSUANCE_TIME_NOT_INDEPENDENTLY_ESTABLISHED
            predicates:
              SignatureValid: {value: true, evaluation_status: evaluated}
              TrustedIssuanceTimeEstablished: {value: false, evaluation_status: evaluated}
            dimensions:
              IssuerIssuanceAuthentic: {value: not_established, evaluation_status: evaluated}
            required_reason_codes: [SIGNER_TSA_COLLUSION_NOT_EXCLUDED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: AX-02
      name: authentic_status_snapshot_rollback
      subfixtures:
        - id: AX-02a
          base: B0
          mutation: older_authentic_snapshot_supplied_while_later_applicable_head_is_evidenced
          expected:
            top_level_outcome: STATUS_SNAPSHOT_ROLLBACK_DETECTED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              StatusSnapshotSelection: {value: rollback_detected, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: not_established, evaluation_status: evaluated}
            predicates:
              StatusSnapshotAuthentic: {value: true, evaluation_status: evaluated}
            required_reason_codes: [LATER_AUTHENTIC_STATUS_HEAD_EXISTS]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: AX-03
      name: conflicting_valid_succession_claims
      subfixtures:
        - id: AX-03a
          base: B0
          mutation: two_validly_signed_successor_claims_conflict_without_competent_adjudication
          expected:
            top_level_outcome: AUTHORITY_SUCCESSION_DISPUTED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: not_established, evaluation_status: evaluated}
            predicates:
              FirstSuccessionStatementValid: {value: true, evaluation_status: evaluated}
              SecondSuccessionStatementValid: {value: true, evaluation_status: evaluated}
              SuccessionResolutionEstablished: {value: false, evaluation_status: evaluated}
            required_reason_codes: [CONFLICTING_SUCCESSION_EVIDENCE]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]

    - family_id: AX-04
      name: parser_and_canonicalization_differential
      subfixtures:
        - id: AX-04a
          base: B0
          mutation: two_supported_consumers_derive_different_semantic_statements_from_same_bytes
          expected:
            top_level_outcome: PROFILE_OR_CANONICALIZATION_AMBIGUOUS
            dimensions:
              IssuerIssuanceAuthentic: {value: not_established, evaluation_status: evaluated}
            predicates:
              CanonicalStatementRecognized: {value: false, evaluation_status: evaluated}
              CrossVerifierSemanticParity: {value: false, evaluation_status: evaluated}
            required_reason_codes: [CANONICALIZATION_DIFFERENTIAL_DETECTED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF, AUTHENTIC_HISTORICAL_AS_OF]

    - family_id: AX-05
      name: selective_negative_terminal_withholding_and_evidence_access
      subfixtures:
        - id: AX-05a
          base: B0
          mutation: required_negative_or_refusal_terminal_withheld_from_release_history
          expected:
            top_level_outcome: PROCEDURAL_HISTORY_NOT_ESTABLISHED
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              ProjectionFaithful: {value: contradicted, evaluation_status: evaluated}
            predicates:
              ProceduralHistoryBound: {value: false, evaluation_status: evaluated}
              NegativeTerminalSetComplete: {value: false, evaluation_status: evaluated}
            required_reason_codes: [REQUIRED_NEGATIVE_TERMINAL_WITHHELD]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
        - id: AX-05b
          base: B0
          mutation: required_validation_evidence_is_competently_restricted_and_not_publicly_obtainable
          expected:
            top_level_outcome: EVIDENCE_NOT_OBTAINABLE
            dimensions:
              IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
              ProjectionFaithful: {value: established, evaluation_status: evaluated}
              PublicHistoryEstablished: {value: established, evaluation_status: evaluated}
              DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
              CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
              EvidenceObtainability: {value: competently_restricted, evaluation_status: evaluated}
            required_reason_codes: [EVIDENCE_ACCESS_COMPETENTLY_RESTRICTED]
            forbidden_outcomes: [VERIFIED_CURRENT_AS_OF]
```

### 9.5 Frozen v2 denominator and exact expected result

The complete set is **23 families / 23 total families** and **29 mandatory subfixtures / 29 total mandatory subfixtures**. No optional subfixture contributes to passage.

```yaml
suite_id: INT-R7-PV-FALSIFIERS-v2
families_total: 23
subfixtures_total: 29
subfixtures_passed: 29
subfixtures_failed: 0
unexpected_positive_outcomes: 0
offline_network_contacts: 0
human_machine_semantic_mismatches: 0
legacy_fnv_positive_authority_paths: 0
pseudo_value_validation_errors: 0
```

Any nonzero failure keeps the first-public-signature gate closed.

### 9.6 Harness requirements amended

A conforming harness must:

1. validate the static v2 specification before constructing fixtures;
2. expand exact baselines and compare exact values plus `evaluation_status`;
3. report all five dimensions, snapshot selection and evidence obtainability;
4. preserve issuer issuance when projection, public history or durable verification fails;
5. execute every offline case with process/sandbox network denial and zero contacts;
6. assert identical machine/human top outcomes and reason-code meaning;
7. identify implementation, revision, environment, evaluator, trust/status fixtures and algorithm policies;
8. treat INT-R8 and GY-N12 positives as fixture-only until their dependencies are independently admitted.

### 9.7 Scope of v2 passage

Under `S0-K16`, even 29/29 passage supports only that the named implementation, revision, environment, evaluator and fixture population satisfied these exact tested propositions. It does not establish legal sufficiency, institutional competence, content safety beyond admitted INT-R8 semantics, production readiness, a universal cryptographic theorem, or permission to publish.

### 9.8 Anti-wire-format warning

The YAML-like blocks are a static conformance specification, not a mandated API or wire format. Implementations may encode equivalent fixtures/results differently, but the immutable family IDs, exact semantic values, evaluation-status distinction, denominators and failure meanings must be preserved.

## 10. Bounded remediation after conformance verification

This section closes `INT-R7-V-103` and applies the predicate split required by `INT-R7-V-104`. It supersedes §§9.1–9.4 only for the typed value grammar, value/status pairing, B0/B1 baselines, and the six named fixture overlays. It does not add, delete, renumber, or weaken any family or subfixture.

### 10.1 Exact whole-token grammar

A validator parses each scalar as one complete token. It does **not** scan substrings.

```text
BooleanValue      := true | false
EvidenceValue     := established | contradicted | not_established
SelectionValue    := latest_established_under_policy | supplied_snapshot_only | rollback_detected
ObtainabilityValue:= public_available | records_process_available | competently_restricted
NoValue           := null
EvaluationStatus  := evaluated | short_circuited | not_applicable | dependency_unavailable
```

Each predicate/dimension slot declares which non-null value family it accepts. The pair grammar is:

```text
EvaluatedPair     := {value: <slot-permitted non-null token>, evaluation_status: evaluated}
UnevaluatedPair   := {value: null, evaluation_status: short_circuited | not_applicable | dependency_unavailable}
```

A conditional or free-prose pseudo-value fails because the complete scalar is not a member of the slot's grammar. A validator must never reject a permitted token because a character substring such as `or` or `if` appears inside that token.

### 10.2 Corrected static-validator rules

A static suite validator rejects the controlling v2 specification when:

1. a `value` token is not an exact member of the grammar declared for that slot;
2. an `evaluation_status` token is not an exact member of `EvaluationStatus`;
3. `evaluation_status: evaluated` is paired with `value: null`;
4. any unevaluated status is paired with a non-null value;
5. a subfixture lacks one exact top-level outcome;
6. a family alternative is expressed inside one mutation/expectation instead of a separately identified subfixture;
7. an offline subfixture omits an exact network-contact expectation;
8. expanded machine and human expected outcome/reason-code sets differ;
9. family or subfixture denominators differ from the frozen manifest; or
10. an existing family ID is removed or weakened without a new suite version.

### 10.3 Corrected exact baselines

```yaml
baselines:
  B0:
    dimensions:
      IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
      ProjectionFaithful: {value: established, evaluation_status: evaluated}
      PublicHistoryEstablished: {value: established, evaluation_status: evaluated}
      DurablyVerifiableAt: {value: established, evaluation_status: evaluated}
      CurrentAuthorityAsOf: {value: established, evaluation_status: evaluated}
      StatusSnapshotSelection: {value: latest_established_under_policy, evaluation_status: evaluated}
      EvidenceObtainability: {value: public_available, evaluation_status: evaluated}
    predicates:
      ContentBound: {value: true, evaluation_status: evaluated}
      SignatureValid: {value: true, evaluation_status: evaluated}
      SignaturePolicySatisfied: {value: true, evaluation_status: evaluated}
      BasisBound: {value: null, evaluation_status: not_applicable}
      IssuerAudienceDeclaredAndBound: {value: true, evaluation_status: evaluated}
      RequestedAudienceUsePermitted: {value: true, evaluation_status: evaluated}
      IssuerJurisdictionDeclaredAndBound: {value: true, evaluation_status: evaluated}
      RequestedJurisdictionUsePermitted: {value: true, evaluation_status: evaluated}
      IssuerProceduralHistoryBound: {value: true, evaluation_status: evaluated}
      ReleasedProceduralHistoryComplete: {value: true, evaluation_status: evaluated}
      OfflineClosureComplete: {value: true, evaluation_status: evaluated}
  B1:
    inherit: B0
    predicates:
      BasisBound: {value: true, evaluation_status: evaluated}
```

The complete value/status sweep covers **31 fixture records / 31 total fixture records**: B0, B1, and 29 mandatory subfixtures. B0's `BasisBound` pair was the only pair inconsistent with the declared not-applicable representation. F-02a's `{value: null, evaluation_status: short_circuited}` remains valid.

### 10.4 Corrected predicate overlays

These overlays replace only the listed predicate maps after baseline expansion.

```yaml
corrected_overlays:
  F-09a:
    dimensions:
      IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
    predicates:
      IssuerAudienceDeclaredAndBound: {value: true, evaluation_status: evaluated}
      RequestedAudienceUsePermitted: {value: false, evaluation_status: evaluated}

  F-10a:
    dimensions:
      IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
    predicates:
      IssuerJurisdictionDeclaredAndBound: {value: true, evaluation_status: evaluated}
      RequestedJurisdictionUsePermitted: {value: false, evaluation_status: evaluated}

  F-12a:
    dimensions:
      IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
    predicates:
      IssuerProceduralHistoryBound: {value: false, evaluation_status: evaluated}

  F-12b:
    dimensions:
      IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
    predicates:
      IssuerProceduralHistoryBound: {value: false, evaluation_status: evaluated}

  F-12c:
    dimensions:
      IssuerIssuanceAuthentic: {value: contradicted, evaluation_status: evaluated}
    predicates:
      IssuerProceduralHistoryBound: {value: false, evaluation_status: evaluated}

  AX-05a:
    dimensions:
      IssuerIssuanceAuthentic: {value: established, evaluation_status: evaluated}
      ProjectionFaithful: {value: contradicted, evaluation_status: evaluated}
    predicates:
      IssuerProceduralHistoryBound: {value: true, evaluation_status: evaluated}
      ReleasedProceduralHistoryComplete: {value: false, evaluation_status: evaluated}
      NegativeTerminalSetComplete: {value: false, evaluation_status: evaluated}
```

F-09a and F-10a are requested-use failures, not defects in the issuer's signed declaration. AX-05a is a released-history/projection failure, not evidence that the issuer omitted the negative-terminal-set commitment from the signed procedural statement.

### 10.5 Complete algebra-consistency sweep

The controlling v2 manifest remains **23 families / 23 total** and **29 subfixtures / 29 total**. A complete subfixture sweep against the remediated issuer formula found six overlays requiring the split vocabulary: F-09a, F-10a, F-12a, F-12b, F-12c, and AX-05a. After applying §10.4, no subfixture sets a necessary issuer-side predicate false while reporting `IssuerIssuanceAuthentic = established`.

The old `AudienceBound`, `JurisdictionBound`, and `ProceduralHistoryBound` entries in §9.4 remain visible as amendment history. They are not controlling v2 expectations after this remediation.

### 10.6 Denominator and passage boundary preserved

The exact expected result in §9.5 remains unchanged: 23 families, 29 mandatory subfixtures, and zero failures or unexpected positives for a conforming run. No run is claimed here. Passage remains bounded by `S0-K16`, and the first-public-signature gate remains closed.