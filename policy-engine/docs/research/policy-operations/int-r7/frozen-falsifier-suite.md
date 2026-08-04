---
title: INT-R7 — Frozen Public Verification Falsifier Suite
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
suite_id: INT-R7-PV-FALSIFIERS-v1
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
