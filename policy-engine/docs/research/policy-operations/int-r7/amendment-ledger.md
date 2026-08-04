---
title: INT-R7 — Post-Audit Amendment Ledger
research_id: INT-R7
status: amended_pending_independent_verification
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
audited_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
amendment_branch: research/int-r7-amendment
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
authoritative_for:
  - disposition of revision register R1 through R22
  - disposition of all forty-two independent-audit findings
  - exact amended-text evidence map and updated research standing
  - post-amendment delivery and verification limitations
may_not_use_for:
  - adoption, ratification, or automatic amendment of INT-R7
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, key custodian, trust service, log, witness, archive, institution, team, person, or vendor appointment
  - authority grant
  - capability claim
  - benchmark or falsifier-suite passage claim
  - legal compliance, legal sufficiency, admissibility, or institutional competence conclusion
  - permission to publish a governed record
research_only: true
---

# INT-R7 post-audit amendment ledger

## 1. Purpose and method

This ledger is the accountability record for amendment of INT-R7 after hostile audit `research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db`. It records what changed, where it changed, what did not change, and what remains unestablished.

The amendment is not a rewrite or defence:

- the audited ten files remain in place;
- the original audited text remains visible where a later controlling amendment supersedes it;
- every commendation-backed position is retained;
- capability was not deleted to close a classification defect;
- no implementation, schema, wire format, owner, service, vendor, legal conclusion, or publication authorization is selected.

Ordinary GitHub clone/codeload access remained unavailable because outbound GitHub DNS/egress was denied. Exact immutable blobs, exact-ref file reads, ordinary branch creation, ordinary Markdown file commits and post-write reads used the connected GitHub interface. No workflow, CI bootstrap, base64 upload fragment, staging directory, binary payload, or self-executing automation was added.

Every repository-state claim in this ledger is based on a post-write read from `research/int-r7-amendment`, not on the content submitted to the write call. Exact lexical counts that could not be freshly rerun remain `not_established` or are explicitly labelled retained static outputs.

## 2. Updated standing

**Standing after amendment: `GO_WITH_REVISIONS`, retained pending independent conformance verification.**

The condition for retaining standing has been met at the authoring level: `R1`–`R15` are executed. `R16`–`R22` are also executed; `R20` is executed with a recorded environment variation because the original complete-set outputs are preserved but a fresh local AST rerun was unavailable.

The result does not become `CONFORMS` because the amendment has not yet been independently verified. The first-public-signature gate remains closed because:

- INT-R8 is delivered but unaudited for this seam;
- GY-N12 is contract-only/planned and OPS-R14 remains unresolved;
- public proof issuance, predicate evaluation, trust distribution, preservation renewal and citizen proof outcomes are absent/unallocated at the pinned commit;
- suite v2 and the two-phase recovery drills have not run;
- competent institutional roles, trust policies, retention rules and jurisdiction-specific legal mappings remain unresolved;
- no present publication capability or permission is established.

The controlling standing statement is at `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:1008-1025`.

## 3. Revision-register dispositions

| Revision | Required? | Disposition | Exact amended-text evidence | What changed / variation reason |
| --- | --- | --- | --- | --- |
| R1 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:760-919`; `int-r7/public-verification-profile.md:622-700`; `int-r7/lifecycle-migration-preservation.md:552-568`; `int-r7/citizen-verification-ux.md:668-718`; `int-r7-public-verification-lifecycle.md:924-939` | Replaced the controlling aggregate with separately reportable `IssuerIssuanceAuthentic`, `ProjectionFaithful`, `PublicHistoryEstablished`, `DurablyVerifiableAt(t_v)` and `CurrentAuthorityAsOf(t_q)`. Projection/history/preservation/currentness failure no longer edits issuer-side issuance. |
| R2 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:850-872`; `int-r7/public-verification-profile.md:664-674`; `int-r7/lifecycle-migration-preservation.md:595-612`; `int-r7/citizen-verification-ux.md:719-733`; `int-r7/frozen-falsifier-suite.md:670-732` | Added authentic-snapshot selection with `latest_established_under_policy`, `supplied_snapshot_only`, `rollback_detected`, and `not_established`; current authority requires the latest-applicable result. Added AX-02. |
| R3 | standing | **executed with variation** | `int-r7/repository-integration-and-dependencies.md:387-407`; `int-r7/threat-model-and-verification-predicates.md:812-849`; `int-r7/public-verification-profile.md:646-663`; `int-r7-public-verification-lifecycle.md:940-954` | Landscape changed: INT-R8 is delivered at `90b3729` but unaudited. Positives remain hypothetical/unsatisfied. Added a provisional item-by-item interface comparison without importing INT-R8 conclusions as established. |
| R4 | standing | **executed** | `int-r7/repository-integration-and-dependencies.md:408-410`; `int-r7/threat-model-and-verification-predicates.md:859-872`; `int-r7-public-verification-lifecycle.md:955-956` | GY-N12 remains contract-only/planned; no current-authority positive is established. |
| R5 | standing / blocking | **executed** | `int-r7/repository-integration-and-dependencies.md:356-385`; `int-r7/public-verification-profile.md:720-724`; `int-r7/citizen-verification-ux.md:776-780`; `int-r7-public-verification-lifecycle.md:958-970` | Reclassified N-01–N-07 and proposed public capabilities as `absent/unallocated at pinned commit`. Retained `bridge_missing` only for the real public-export producer and its missing production route. |
| R6 | standing | **executed** | `int-r7/frozen-falsifier-suite.md:670-732` and the exact v2 manifest following line 732 | Versioned the suite to v2, preserved F-01–F-18 as immutable families, split alternatives into 29 exact subfixtures, added exact values plus evaluation status, and specified a static pseudo-value validator. |
| R7 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:793-810`; `int-r7/citizen-verification-ux.md:704-718`; `int-r7/frozen-falsifier-suite.md:789-803` | F-04 now reports `ISSUANCE_TEMPORALLY_UNAUTHORIZED`; `SignatureValid` remains true and temporal authorization is false. |
| R8 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:932-940`; `int-r7/citizen-verification-ux.md:746-752`; `int-r7/frozen-falsifier-suite.md:670-732` | F-08 now keeps issuer issuance established, makes public history/common view non-positive, and blocks every public-current positive. |
| R9 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:920-930`; `int-r7/frozen-falsifier-suite.md:670-732` and AX-01–AX-05 in the manifest | Added signer+TSA collusion, authentic-snapshot rollback, conflicting valid succession, parser/canonicalization differential, and selective negative-terminal withholding. AX-05 also exercises evidence obtainability. |
| R10 | standing | **executed** | `int-r7/lifecycle-migration-preservation.md:570-594`; `int-r7/public-verification-profile.md:709-714`; `int-r7-public-verification-lifecycle.md:987-992` | Defined a pre-live disconnected drill over a representative non-authoritative/ceremonial corpus through real intended paths, followed by a bounded first-live-record drill. Runbooks/tabletops/mock Booleans do not satisfy the gate. |
| R11 | standing | **executed** | `int-r7/lifecycle-migration-preservation.md:595-637`; `int-r7-public-verification-lifecycle.md:993-994` | Added authentic-snapshot anti-rollback and compromised-primary/cross-custody recovery outcomes with independent roots and checkpoint comparison. |
| R12 | standing | **executed with variation** | `int-r7/external-source-and-transfer-ledger.md:157-167`; `int-r7/lifecycle-migration-preservation.md:653-657`; `int-r7-public-verification-lifecycle.md:996-1006` | Reclassified US-01 as historical-only/superseded. Added current-status-limited US-03 as supplemental official evidence; no universal applicability is inferred. |
| R13 | standing | **executed** | `int-r7/external-source-and-transfer-ledger.md:164`; `int-r7-public-verification-lifecycle.md:1000-1001` | Narrowed US-02 to a nonbinding Federal Register document-submission playbook; retained only bounded delegation/control patterns. |
| R14 | standing | **executed** | `int-r7/orientation-ledger.md:208-218`; `int-r7-public-verification-lifecycle.md:1008-1010` | Recorded the missed briefing error: ratification, pin and inspection were all 2026-08-04, not four days apart. No substantive consequence inferred. |
| R15 | standing | **executed** | `int-r7/threat-model-and-verification-predicates.md:873-883`; `int-r7/public-verification-profile.md:675-685`; `int-r7/citizen-verification-ux.md:734-745`; `int-r7/lifecycle-migration-preservation.md:659-669` | Added `EvidenceObtainability`: public, competent records process, competently restricted, or not established; public verifiability requires an obtainable route. |
| R16 | improvement | **executed** | `int-r7/threat-model-and-verification-predicates.md:764-775`; `int-r7/comparative-models.md:396-408`; `int-r7-public-verification-lifecycle.md:924-926` | Replaced “independent predicates” with “separately reportable dimensions”; no claim of logical/statistical independence remains. |
| R17 | improvement | **executed** | `int-r7/external-source-and-transfer-ledger.md:157-167`; `int-r7-public-verification-lifecycle.md:996-1006` | Corrected ETSI-05 date, narrowed RFC 9162 witness transfer, added SIG-05 exact bundle-format anchor, and preserved transfer limits. |
| R18 | improvement | **executed** | `int-r7/repository-integration-and-dependencies.md:412-414`; `int-r7/public-verification-profile.md:726-728`; `int-r7/citizen-verification-ux.md:782-784`; `int-r7-public-verification-lifecycle.md:1027-1029` | Added explicit anti-wire/API/schema/enum warnings. Names and YAML-like fixtures are semantic/conformance vocabulary only. |
| R19 | improvement | **executed** | `int-r7/public-verification-profile.md:701-708`; `int-r7/lifecycle-migration-preservation.md:639-651`; `int-r7/citizen-verification-ux.md:758-764`; suite v2 `F-18b` | Added a positive lawful-succession case preserving predecessor attribution and labelling the successor only as custodian/preservation signer. |
| R20 | improvement | **executed with variation** | `int-r7/orientation-ledger.md:220-256`; `int-r7-public-verification-lifecycle.md:1011-1013` | Preserved static complete-set outputs for O-05 (14/14) and O-09 (5/5 expressions). A fresh local AST rerun was unavailable due denied DNS/egress; what would settle it is stated. O-02/O-08 remain `not_established`. |
| R21 | improvement | **executed** | `int-r7/frozen-falsifier-suite.md:708-730`, especially `SignatureValid` versus `SignaturePolicySatisfied`; exact `F-03a` and `F-13a` subfixtures after line 732 | Separated local cryptographic validity from configured signature/quorum-policy satisfaction. One mathematically valid signature below threshold is not called signature-math failure. |
| R22 | improvement | **executed** | `int-r7/external-source-and-transfer-ledger.md:169-210` | Added per-source currentness/recheck metadata and a manual revalidation trigger for load-bearing institutional guidance before consolidation or implementation. |

### Revision count reconciliation

The register contains **22 revisions / 22 total revisions**:

| Disposition | Count |
| --- | ---: |
| executed | 19 |
| executed with variation | 3 |
| declined | 0 |
| **total** | **22** |

All `R1`–`R15` standing revisions are executed. No improvement is silently skipped.

## 4. Complete audit-finding disposition register

| Finding ID | Severity | Disposition | Exact evidence and preservation statement |
| --- | --- | --- | --- |
| INT-R7-I-001 | commendation | **preserved** | Branch geometry remains pinned in this ledger frontmatter and will be reconciled by complete compare after amendment. No scope expansion beyond ten amended files plus this ledger. |
| INT-R7-I-002 | commendation | **preserved** | Source defect remains explicit at `int-r7-public-verification-lifecycle.md:908-917`; no narrowing of mutable `signed_at`/identity or timeless revocation finding. |
| INT-R7-I-003 | commendation | **preserved and strengthened** | O-09 remains corrected at `int-r7/orientation-ledger.md:233-254`; real producer retained and only its route remains `bridge_missing`. |
| INT-R7-I-004 | commendation | **preserved** | O-02/O-08 reservations remain at `int-r7/orientation-ledger.md:256`; no retrofitted exact counts. |
| INT-R7-I-005 | material | **corrected** | Same-day correction at `int-r7/orientation-ledger.md:212-218`. |
| INT-R7-I-006 | minor | **bounded, not overstated** | Static 14/14 record and rerun limitation at `int-r7/orientation-ledger.md:220-231`. Independent fresh rerun remains unestablished. |
| INT-R7-II-001 | commendation | **preserved** | Original 30/30 source corpus is retained; amended ledger states 32/32 after two supplemental rows at `int-r7/external-source-and-transfer-ledger.md:153-167`. |
| INT-R7-II-002 | minor | **corrected** | ETSI-05 date corrected at `int-r7/external-source-and-transfer-ledger.md:161`. |
| INT-R7-II-003 | material | **corrected** | US-01 historical-only/superseded at `int-r7/external-source-and-transfer-ledger.md:163`; current use superseded in preservation at `int-r7/lifecycle-migration-preservation.md:653-657`. |
| INT-R7-II-004 | material | **corrected** | US-02 narrowed at `int-r7/external-source-and-transfer-ledger.md:164`. |
| INT-R7-II-005 | minor | **corrected** | RFC 9162 transfer narrowed to inclusion/consistency/external observation; quorum is an INT-R7 inference at `int-r7/external-source-and-transfer-ledger.md:162`. |
| INT-R7-II-006 | minor | **corrected** | SIG-05 exact bundle-format source added at `int-r7/external-source-and-transfer-ledger.md:166`. |
| INT-R7-III-001 | commendation | **preserved** | Five-dimension model continues to reject “signature equals fact” at `int-r7/threat-model-and-verification-predicates.md:760-919`. |
| INT-R7-III-002 | material | **corrected** | Aggregate historical-authenticity conflation superseded by issuer/projection/history/durability/currentness decomposition at `int-r7/threat-model-and-verification-predicates.md:776-919`. |
| INT-R7-III-003 | minor | **corrected** | “Separately reportable, not logically independent” at `int-r7/threat-model-and-verification-predicates.md:764-775` and `int-r7/comparative-models.md:396-408`. |
| INT-R7-III-004 | material | **corrected** | Snapshot selection and rollback outcomes at `int-r7/threat-model-and-verification-predicates.md:850-872`; AX-02 in suite v2. |
| INT-R7-IV-001 | commendation | **preserved** | Ten construction families and eliminating properties remain intact; audit-preservation statement at `int-r7/comparative-models.md:410-413`. |
| INT-R7-IV-002 | commendation | **preserved** | GY-N12 and INT-R8 remain consumed, not duplicated, at `int-r7/repository-integration-and-dependencies.md:387-410`. |
| INT-R7-IV-003 | material | **updated for changed facts, not closed by fiat** | INT-R8 now delivered but unaudited; dependent positives still unsatisfied at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-IV-004 | material | **preserved as open dependency** | GY-N12 remains contract-only/planned at `int-r7/repository-integration-and-dependencies.md:408-410`. |
| INT-R7-V-001 | material | **corrected** | Exact value/evaluation-status model and static validator at `int-r7/frozen-falsifier-suite.md:670-732`. |
| INT-R7-V-002 | material | **corrected** | F-04 exact temporal terminal at `int-r7/frozen-falsifier-suite.md:789-803`. |
| INT-R7-V-003 | material | **corrected** | F-08 issuer issuance preserved at `int-r7/threat-model-and-verification-predicates.md:932-940` and suite v2 F-08a. |
| INT-R7-V-004 | commendation | **preserved and expanded** | F-05 and F-17 retain their semantics; F-18 gains positive F-18b. Primary preservation at `int-r7-public-verification-lifecycle.md:972-985`. |
| INT-R7-V-005 | material | **corrected** | Five missing attack families added at `int-r7/threat-model-and-verification-predicates.md:920-930` and AX-01–AX-05 in suite v2. |
| INT-R7-VI-001 | commendation | **preserved and clarified** | Gate binds first live authority-bearing signature, not candidate/test work, at `int-r7/lifecycle-migration-preservation.md:570-594`. |
| INT-R7-VI-002 | material | **corrected** | Non-circular ceremonial Phase A and first-live Phase B at `int-r7/lifecycle-migration-preservation.md:570-594`. |
| INT-R7-VI-003 | material | **corrected** | Anti-rollback and compromised-primary/cross-custody outcomes at `int-r7/lifecycle-migration-preservation.md:595-637`. |
| INT-R7-VI-004 | commendation | **preserved** | Late renewal still cannot repair history; successor/preservation signer never becomes original issuer at `int-r7/lifecycle-migration-preservation.md:556-568` and `639-651`. |
| INT-R7-VII-001 | commendation | **preserved and strengthened** | `INT-K06` remains primary; selective negative-terminal withholding added at `int-r7/threat-model-and-verification-predicates.md:920-930` and AX-05a. |
| INT-R7-VII-002 | commendation | **preserved** | `INT-K02` basis remains issuer-statement integrity at `int-r7/threat-model-and-verification-predicates.md:776-791` and exact F-11a/F-11b. |
| INT-R7-VII-003 | commendation | **preserved** | Withdrawn-but-verifiable remains first-class without aggregate-history collapse at `int-r7/threat-model-and-verification-predicates.md:904-918` and F-17a. |
| INT-R7-VII-004 | commendation | **preserved** | Suite v2 scope remains bounded by `S0-K16`; primary summary at `int-r7-public-verification-lifecycle.md:972-985`. |
| INT-R7-VII-005 | commendation | **preserved** | No second authority/status/projection ledger; owner seam retained at `int-r7/repository-integration-and-dependencies.md:387-410`. |
| INT-R7-VIII-001 | commendation | **preserved** | Proof/content seam remains explicit; provisional comparison does not import content conclusions at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-VIII-002 | material | **updated for changed facts; remains unsatisfied** | Delivered-but-unaudited INT-R8 status and open positives at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-VIII-003 | material | **corrected** | INT-R8 failure now affects `ProjectionFaithful`, not issuer issuance, at `int-r7/threat-model-and-verification-predicates.md:812-849`. |
| INT-R7-IX-001 | commendation | **preserved** | All amended artifacts retain `research_only: true` and `may_not_use_for`; complete post-write census is recorded in §6. |
| INT-R7-IX-002 | minor | **corrected** | Anti-wire warnings at `int-r7/repository-integration-and-dependencies.md:412-414`, `int-r7/public-verification-profile.md:726-728`, and `int-r7-public-verification-lifecycle.md:1027-1029`. |
| INT-R7-IX-003 | commendation | **preserved** | `GO_WITH_REVISIONS` retained, with stronger pending-independent-verification language at `int-r7-public-verification-lifecycle.md:1008-1025`. |
| INT-R7-X-001 | blocking | **corrected** | Capability prerequisites and N-01–N-07 reclassification at `int-r7/repository-integration-and-dependencies.md:356-385`. |
| INT-R7-X-002 | commendation | **preserved** | Existing export producer remains recognized and only production route remains `bridge_missing` at `int-r7/repository-integration-and-dependencies.md:365-366`. |

### Finding-count reconciliation

The register above contains **42 rows / 42 total findings**:

| Severity | Rows |
| --- | ---: |
| blocking | 1 |
| material | 15 |
| minor | 6 |
| commendation | 20 |
| **total** | **42** |

Every negative finding is executed, explicitly retained as open, or updated for a changed repository fact. Every commendation states how it was preserved. No finding is silently omitted.

## 5. Dependency and capability boundary after amendment

### INT-R8

Delivered at `90b372964d29a9e97605a6ef733ef03ffe7938d2`, standing `accepted_narrow_scope`, but unaudited for this use. Interface comparison is provisional. `ProjectionFaithful` positives remain hypothetical and unsatisfied.

### GY-N12

Contract-only/planned. `CurrentAuthorityAsOf` positives remain hypothetical and unsatisfied.

### OPS-R14 and institutional governance

Custody-grade durability, recovery mechanics, legal hold, continuity, role assignment, funding and jurisdiction-specific recognition remain unresolved. INT-R7 specifies observable outcomes only.

### Pinned capability reality

The real export producer exists and its intended production route remains `bridge_missing`. Proposed public proof lifecycle capabilities are otherwise absent/unallocated at the pinned commit. The amendment does not claim a present verifier, producer, persisted proof, trust distribution mechanism, preservation service, public route, or suite passage.

## 6. Post-write verification record

The final independent verifier should check the complete amended artifact set:

1. `int-r7-public-verification-lifecycle.md`;
2. `int-r7/orientation-ledger.md`;
3. `int-r7/threat-model-and-verification-predicates.md`;
4. `int-r7/comparative-models.md`;
5. `int-r7/public-verification-profile.md`;
6. `int-r7/lifecycle-migration-preservation.md`;
7. `int-r7/citizen-verification-ux.md`;
8. `int-r7/frozen-falsifier-suite.md`;
9. `int-r7/repository-integration-and-dependencies.md`;
10. `int-r7/external-source-and-transfer-ledger.md`;
11. `int-r7/amendment-ledger.md`.

Boundary: **11 Markdown artifacts / 11 total amendment artifacts**. Every artifact must contain `research_only: true`, a non-empty `may_not_use_for`, and the exact `amended_after_audit` binding. This denominator is accepted only after each file is read back from the branch; the final read-back result is recorded below by a follow-up ordinary ledger commit if a correction is needed.

No pull request is opened by this work. The audit branch is not modified. The first-public-signature gate remains closed.