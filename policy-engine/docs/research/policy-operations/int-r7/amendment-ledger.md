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

This ledger records amendment of INT-R7 after hostile audit `research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db`. It is not a rewrite or defence:

- the audited ten files remain in place;
- the original audited text remains visible where a later controlling amendment supersedes it;
- every commendation-backed position is retained;
- capability was not deleted to close a classification defect;
- no implementation, schema, wire format, owner, service, vendor, legal conclusion, or publication authorization is selected.

Ordinary GitHub clone/codeload access remained unavailable because outbound GitHub DNS/egress was denied. Exact immutable blobs, exact-ref reads, ordinary branch creation, ordinary Markdown commits and post-write reads used the connected GitHub interface. No workflow, CI bootstrap, base64 upload fragment, staging directory, binary payload, or self-executing automation was added.

Every repository-state claim below was checked by reading the amended branch after writing. Exact lexical counts that could not be freshly rerun remain `not_established` or are explicitly labelled retained static outputs.

## 2. Updated standing

**Standing after amendment: `GO_WITH_REVISIONS`, retained pending independent conformance verification.**

`R1`–`R15` are executed. `R16`–`R22` are also executed; `R20` is executed with an environment variation because the original complete-set outputs are preserved but a fresh local AST rerun was unavailable.

The result does not become `CONFORMS`: INT-R8 is delivered but unaudited for this seam; GY-N12 and OPS-R14 remain unresolved; proposed public-proof capabilities are absent/unallocated at the pinned commit; suite v2 and the recovery drills have not run; institutional roles, trust policies, retention rules and jurisdiction-specific mappings remain unresolved; and no present publication capability or permission is established.

Controlling standing: `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:1006`.

## 3. Revision-register dispositions

| Revision | Disposition | Exact amended-text evidence | Change / variation |
| --- | --- | --- | --- |
| R1 | **executed** | `int-r7/threat-model-and-verification-predicates.md:760`; `int-r7/public-verification-profile.md:622`; `int-r7/lifecycle-migration-preservation.md:552`; `int-r7/citizen-verification-ux.md:668`; `int-r7/frozen-falsifier-suite.md:670`; `int-r7-public-verification-lifecycle.md:904` | Decomposed issuer issuance, projection, public history, durable verification and current authority. Later evidentiary failure no longer edits issuer-side issuance. |
| R2 | **executed** | `int-r7/threat-model-and-verification-predicates.md:850`; `int-r7/public-verification-profile.md:664`; `int-r7/lifecycle-migration-preservation.md:595`; suite v2 AX-02 under `int-r7/frozen-falsifier-suite.md:732` | Added authentic-snapshot selection and rollback detection; current authority requires the latest-applicable authenticated snapshot. |
| R3 | **executed with variation** | `int-r7/repository-integration-and-dependencies.md:387`; `int-r7/threat-model-and-verification-predicates.md:812`; `int-r7/public-verification-profile.md:646`; `int-r7-public-verification-lifecycle.md:939` | INT-R8 is now delivered but unaudited. Positives remain hypothetical/unsatisfied. Added a provisional item-by-item interface comparison without importing INT-R8 conclusions. |
| R4 | **executed** | `int-r7/repository-integration-and-dependencies.md:408`; `int-r7/threat-model-and-verification-predicates.md:850`; `int-r7-public-verification-lifecycle.md:951` | GY-N12 remains contract-only/planned; no current-authority positive is established. |
| R5 | **executed** | `int-r7/repository-integration-and-dependencies.md:356`; `int-r7/public-verification-profile.md:718`; `int-r7/citizen-verification-ux.md:776`; `int-r7-public-verification-lifecycle.md:953` | Reclassified N-01–N-07 and proposed public capabilities as absent/unallocated. Retained `bridge_missing` only for the real export producer and absent production route. |
| R6 | **executed** | `int-r7/frozen-falsifier-suite.md:670`; static validator at `:690`; exact baselines at `:706`; exact manifest at `:732` | Versioned to v2; preserved F-01–F-18 as immutable families; split alternatives into 29 exact subfixtures; added exact values and evaluation status. |
| R7 | **executed** | `int-r7/threat-model-and-verification-predicates.md:793`; `int-r7/citizen-verification-ux.md:705`; `int-r7/frozen-falsifier-suite.md:789` | F-04 now returns `ISSUANCE_TEMPORALLY_UNAUTHORIZED`; signature mathematics remains true. |
| R8 | **executed** | `int-r7/threat-model-and-verification-predicates.md:932`; `int-r7/citizen-verification-ux.md:733`; suite v2 F-08a under `int-r7/frozen-falsifier-suite.md:732` | Split-view failure preserves issuer issuance and blocks public-current reliance through the public-history dimension. |
| R9 | **executed** | `int-r7/threat-model-and-verification-predicates.md:920`; suite v2 AX-01–AX-05 under `int-r7/frozen-falsifier-suite.md:732` | Added signer+TSA collusion, snapshot rollback, conflicting succession, parser/canonicalization differential and selective negative-terminal withholding. |
| R10 | **executed** | `int-r7/lifecycle-migration-preservation.md:570`; `int-r7/public-verification-profile.md:712`; `int-r7-public-verification-lifecycle.md:981` | Added real-path pre-live ceremonial drill and bounded first-live-record drill; paper/tabletop/mock Boolean is insufficient. |
| R11 | **executed** | `int-r7/lifecycle-migration-preservation.md:595`; cross-custody subsection at `:613` | Added anti-rollback and compromised-primary/cross-custody recovery outcomes. |
| R12 | **executed with variation** | `int-r7/external-source-and-transfer-ledger.md:153`; `int-r7/lifecycle-migration-preservation.md:552` | US-01 is historical-only/superseded. Added current-status-limited US-03 as supplemental evidence; no universal applicability inferred. |
| R13 | **executed** | `int-r7/external-source-and-transfer-ledger.md:164` | Narrowed US-02 to a nonbinding Federal Register submission playbook. |
| R14 | **executed** | `int-r7/orientation-ledger.md:212` | Recorded the missed same-day correction: ratification, pin and inspection were all 2026-08-04. |
| R15 | **executed** | `int-r7/threat-model-and-verification-predicates.md:873`; `int-r7/public-verification-profile.md:675`; `int-r7/citizen-verification-ux.md:739`; `int-r7/lifecycle-migration-preservation.md:552` | Added explicit evidence obtainability and competent restriction outcomes. |
| R16 | **executed** | `int-r7/threat-model-and-verification-predicates.md:764`; `int-r7/comparative-models.md:396` | Replaced “independent predicates” with “separately reportable dimensions.” |
| R17 | **executed** | `int-r7/external-source-and-transfer-ledger.md:153` | Corrected ETSI-05 date, narrowed RFC 9162 transfer, and added SIG-05 exact bundle-format source. |
| R18 | **executed** | `int-r7/repository-integration-and-dependencies.md:412`; `int-r7/public-verification-profile.md:722`; `int-r7/citizen-verification-ux.md:780`; `int-r7-public-verification-lifecycle.md:1024` | Added anti-wire/API/schema/enum warnings. |
| R19 | **executed** | `int-r7/public-verification-profile.md:701`; `int-r7/lifecycle-migration-preservation.md:639`; `int-r7/citizen-verification-ux.md:760`; suite v2 F-18b under `int-r7/frozen-falsifier-suite.md:732` | Added positive lawful succession preserving predecessor attribution. |
| R20 | **executed with variation** | `int-r7/orientation-ledger.md:220`; O-09 record at `:231` | Preserved O-05 14/14 and O-09 5/5 static complete-set outputs. Fresh local rerun remained unavailable; O-02/O-08 stay `not_established`. |
| R21 | **executed** | `int-r7/frozen-falsifier-suite.md:708`; exact F-03a/F-13a under `:732` | Separated local `SignatureValid` from configured `SignaturePolicySatisfied` and quorum satisfaction. |
| R22 | **executed** | `int-r7/external-source-and-transfer-ledger.md:169` | Added per-source currentness/recheck metadata and manual revalidation trigger. |

### Revision count reconciliation

**22 revisions / 22 total:** 19 `executed`, 3 `executed with variation`, 0 `declined`. All R1–R15 standing revisions are executed; no improvement is silently skipped.

## 4. Complete audit-finding disposition register

| Finding ID | Severity | Disposition and exact preservation/repair evidence |
| --- | --- | --- |
| INT-R7-I-001 | commendation | **preserved** — audited head remains merge base; complete branch comparison is recorded in §6. |
| INT-R7-I-002 | commendation | **preserved** — source defect remains explicit in primary controlling amendment at `int-r7-public-verification-lifecycle.md:908`. |
| INT-R7-I-003 | commendation | **preserved/strengthened** — O-09 static record at `int-r7/orientation-ledger.md:231`; producer retained and route remains `bridge_missing`. |
| INT-R7-I-004 | commendation | **preserved** — O-02/O-08 reservations remain controlling at `int-r7/orientation-ledger.md:245`. |
| INT-R7-I-005 | material | **corrected** — same-day error at `int-r7/orientation-ledger.md:212`. |
| INT-R7-I-006 | minor | **bounded** — retained 14/14 record and rerun limitation at `int-r7/orientation-ledger.md:220`. |
| INT-R7-II-001 | commendation | **preserved** — original 30/30 corpus retained; amended source section at `int-r7/external-source-and-transfer-ledger.md:153`. |
| INT-R7-II-002 | minor | **corrected** — ETSI-05 date at `int-r7/external-source-and-transfer-ledger.md:161`. |
| INT-R7-II-003 | material | **corrected** — US-01 historical-only at `int-r7/external-source-and-transfer-ledger.md:163`; preservation use superseded under `int-r7/lifecycle-migration-preservation.md:552`. |
| INT-R7-II-004 | material | **corrected** — US-02 narrowed at `int-r7/external-source-and-transfer-ledger.md:164`. |
| INT-R7-II-005 | minor | **corrected** — RFC 9162 witness transfer narrowed at `int-r7/external-source-and-transfer-ledger.md:162`. |
| INT-R7-II-006 | minor | **corrected** — SIG-05 added at `int-r7/external-source-and-transfer-ledger.md:166`. |
| INT-R7-III-001 | commendation | **preserved** — five-dimension model continues to reject “signature equals fact” at `int-r7/threat-model-and-verification-predicates.md:760`. |
| INT-R7-III-002 | material | **corrected** — aggregate conflation superseded at `int-r7/threat-model-and-verification-predicates.md:776`. |
| INT-R7-III-003 | minor | **corrected** — separately reportable wording at `int-r7/threat-model-and-verification-predicates.md:764`. |
| INT-R7-III-004 | material | **corrected** — rollback/selection at `int-r7/threat-model-and-verification-predicates.md:850`. |
| INT-R7-IV-001 | commendation | **preserved** — all nine comparative models and eliminating properties survive; clarification at `int-r7/comparative-models.md:392`. |
| INT-R7-IV-002 | commendation | **preserved** — GY-N12/INT-R8 ownership remains consumed, not duplicated, at `int-r7/repository-integration-and-dependencies.md:387`. |
| INT-R7-IV-003 | material | **updated, still open** — INT-R8 delivered but unaudited; positives remain unsatisfied at `int-r7/repository-integration-and-dependencies.md:387`. |
| INT-R7-IV-004 | material | **preserved as open dependency** — GY-N12 remains planned at `int-r7/repository-integration-and-dependencies.md:408`. |
| INT-R7-V-001 | material | **corrected** — exact value/evaluation-status model and validator at `int-r7/frozen-falsifier-suite.md:670`. |
| INT-R7-V-002 | material | **corrected** — F-04 temporal terminal at `int-r7/frozen-falsifier-suite.md:789`. |
| INT-R7-V-003 | material | **corrected** — F-08 issuer issuance preserved at `int-r7/threat-model-and-verification-predicates.md:932`. |
| INT-R7-V-004 | commendation | **preserved/expanded** — F-05/F-17 remain; positive F-18b added under suite v2 at `int-r7/frozen-falsifier-suite.md:732`. |
| INT-R7-V-005 | material | **corrected** — five attacks at `int-r7/threat-model-and-verification-predicates.md:920` and suite AX-01–AX-05. |
| INT-R7-VI-001 | commendation | **preserved/clarified** — gate binds live authority-bearing issuance, not candidate/test work, at `int-r7/lifecycle-migration-preservation.md:570`. |
| INT-R7-VI-002 | material | **corrected** — non-circular drill phases at `int-r7/lifecycle-migration-preservation.md:570`. |
| INT-R7-VI-003 | material | **corrected** — anti-rollback/cross-custody at `int-r7/lifecycle-migration-preservation.md:595`. |
| INT-R7-VI-004 | commendation | **preserved** — late renewal cannot repair history and custody cannot launder issuer at `int-r7/lifecycle-migration-preservation.md:552`. |
| INT-R7-VII-001 | commendation | **preserved/strengthened** — INT-K06 remains primary; negative-terminal withholding at `int-r7/threat-model-and-verification-predicates.md:920`. |
| INT-R7-VII-002 | commendation | **preserved** — INT-K02 basis remains issuer-statement integrity at `int-r7/threat-model-and-verification-predicates.md:776`. |
| INT-R7-VII-003 | commendation | **preserved** — withdrawn-but-verifiable vector at `int-r7/threat-model-and-verification-predicates.md:904`. |
| INT-R7-VII-004 | commendation | **preserved** — v2 passage remains S0-K16-bounded at `int-r7/frozen-falsifier-suite.md:670`. |
| INT-R7-VII-005 | commendation | **preserved** — no second authority/status/projection owner at `int-r7/repository-integration-and-dependencies.md:387`. |
| INT-R7-VIII-001 | commendation | **preserved** — proof/content seam and provisional comparison at `int-r7/repository-integration-and-dependencies.md:387`. |
| INT-R7-VIII-002 | material | **updated, still unsatisfied** — delivered-but-unaudited INT-R8 at `int-r7/repository-integration-and-dependencies.md:387`. |
| INT-R7-VIII-003 | material | **corrected** — INT-R8 failure affects projection, not issuance, at `int-r7/threat-model-and-verification-predicates.md:812`. |
| INT-R7-IX-001 | commendation | **preserved** — complete 11/11 frontmatter read-back in §6. |
| INT-R7-IX-002 | minor | **corrected** — anti-wire warnings at `int-r7/repository-integration-and-dependencies.md:412` and sibling amended artifacts. |
| INT-R7-IX-003 | commendation | **preserved** — `GO_WITH_REVISIONS` retained at `int-r7-public-verification-lifecycle.md:1006`. |
| INT-R7-X-001 | blocking | **corrected** — capability reclassification at `int-r7/repository-integration-and-dependencies.md:356`. |
| INT-R7-X-002 | commendation | **preserved** — real export producer and `bridge_missing` route retained at `int-r7/repository-integration-and-dependencies.md:365`. |

### Finding-count reconciliation

**42 findings / 42 total:** 1 blocking, 15 material, 6 minor, 20 commendations. Every negative finding is repaired, explicitly retained as open, or updated for a changed fact. Every commendation states how it survives.

## 5. Dependency and capability boundary after amendment

- **INT-R8:** delivered at `90b372964d29a9e97605a6ef733ef03ffe7938d2`, standing `accepted_narrow_scope`, but unaudited for this use. Interface comparison is provisional; projection positives remain hypothetical and unsatisfied.
- **GY-N12:** contract-only/planned; current-authority positives remain hypothetical and unsatisfied.
- **OPS-R14/institutions:** durability mechanics, legal hold, continuity, role assignment, funding and jurisdictional recognition remain unresolved.
- **Pinned capability reality:** the real export producer exists and its intended production route remains `bridge_missing`; proposed public proof lifecycle capabilities are otherwise absent/unallocated.

## 6. Post-write verification record

Complete branch comparison from audited head `f5671253b51554dde2dd22a6aef2ef827c5bd9dd` found **11 changed paths / 11 total changed paths**:

- **10 modified Markdown files** — exactly the audited artifacts;
- **1 added Markdown file** — this amendment ledger;
- **0 deleted files**;
- **0 non-Markdown files**;
- merge base exactly the audited head.

Complete frontmatter read-back covered **11 artifacts / 11 total amendment artifacts**. Every one contains:

- the exact `amended_after_audit` binding;
- `research_only: true`;
- a non-empty `may_not_use_for` block.

The eleven read-back paths are:

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

No pull request is opened by this work. The audit branch is not modified. The first-public-signature gate remains closed.