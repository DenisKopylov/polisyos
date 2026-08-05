---
title: INT-R7 — Post-Audit Amendment Ledger
research_id: INT-R7
status: remediated_pending_delta_verification
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
audited_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
amendment_branch: research/int-r7-amendment
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
remediated_after_verification: research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d
authoritative_for:
  - disposition of revision register R1 through R22
  - disposition of all forty-two independent-audit findings
  - exact amended and remediated text evidence map and updated research standing
  - post-amendment and bounded-remediation delivery limitations
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

This ledger records amendment of INT-R7 after hostile audit `research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db` and tightens its evidence paths after verification `research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d`. It is not a rewrite or defence:

- the audited ten files remain in place;
- the original audited text remains visible where a later controlling amendment or remediation supersedes it;
- every commendation-backed position is retained;
- capability was not deleted to close a classification defect;
- no implementation, schema, wire format, owner, service, vendor, legal conclusion, or publication authorization is selected.

Ordinary GitHub clone/codeload access remained unavailable because outbound GitHub DNS/egress was denied. Exact immutable blobs, exact-ref reads, ordinary branch creation, ordinary Markdown commits and post-write reads used the connected GitHub interface. No workflow, CI bootstrap, base64 upload fragment, staging directory, binary payload, or self-executing automation was added.

The bounded remediation and its regression evidence are recorded in `int-r7/remediation-ledger.md`. Exact lexical counts that could not be freshly rerun remain `not_established` or are explicitly labelled retained static outputs.

## 2. Updated standing

**Standing after bounded remediation: `GO_WITH_REVISIONS`, retained pending independent delta-only re-verification.**

All `R1`–`R22` remain executed as recorded below. The three conformance defects are repaired at the authoring level, but this ledger does not self-certify their independent closure. The first-public-signature gate remains closed.

Controlling standing: `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:1051-1053`.

## 3. Revision-register dispositions

| Revision | Disposition | Exact amended/remediated-text evidence | Change / variation |
| --- | --- | --- | --- |
| R1 | **executed and remediated** | `int-r7/threat-model-and-verification-predicates.md:761-919,948-1024`; `int-r7/public-verification-profile.md:622-700`; `int-r7/lifecycle-migration-preservation.md:552-568`; `int-r7/citizen-verification-ux.md:668-718`; `int-r7/frozen-falsifier-suite.md:1243-1375`; `int-r7-public-verification-lifecycle.md:43,204,926-1053` | Five dimensions remain separate; primary supersession is reachable and the issuer/request/release predicate collision is resolved. |
| R2 | **executed** | `int-r7/threat-model-and-verification-predicates.md:851-873`; `int-r7/public-verification-profile.md:664-674`; `int-r7/lifecycle-migration-preservation.md:595-612`; suite v2 AX-02 in `int-r7/frozen-falsifier-suite.md` §9.4 | Added authentic-snapshot selection and rollback detection; current authority requires the latest-applicable authenticated snapshot. |
| R3 | **executed with variation and remediated** | `int-r7/repository-integration-and-dependencies.md:387-407`; `int-r7/threat-model-and-verification-predicates.md:813-850`; `int-r7/public-verification-profile.md:646-663`; `int-r7-public-verification-lifecycle.md:60,961-973` | INT-R8 is delivered but unaudited; positives remain hypothetical/unsatisfied; the primary's old “become available” wording is now locally marked as history. |
| R4 | **executed and remediated** | `int-r7/repository-integration-and-dependencies.md:408-410`; `int-r7/threat-model-and-verification-predicates.md:851-873`; `int-r7-public-verification-lifecycle.md:204,961-973` | GY-N12 remains contract-only/planned; no current-authority positive is established and old algebra is locally superseded. |
| R5 | **executed and remediated** | `int-r7/repository-integration-and-dependencies.md:356-385`; `int-r7/public-verification-profile.md:718-724`; `int-r7/citizen-verification-ux.md:776-780`; `int-r7-public-verification-lifecycle.md:125,733,975-986` | N-01–N-07 remain absent/unallocated; the real export producer and its `bridge_missing` route survive; old labels are locally marked as history. |
| R6 | **executed and remediated** | `int-r7/frozen-falsifier-suite.md:1243-1375` | v2 remains 23 families/29 subfixtures; the controlling grammar is whole-token, B0 uses null/not-applicable, and no family is added, removed, or weakened. |
| R7 | **executed** | `int-r7/threat-model-and-verification-predicates.md:794-811`; `int-r7/citizen-verification-ux.md:705-718`; `int-r7/frozen-falsifier-suite.md:793-807` | F-04 returns `ISSUANCE_TEMPORALLY_UNAUTHORIZED`; signature mathematics remains true. |
| R8 | **executed and remediated** | `int-r7/threat-model-and-verification-predicates.md:933-943`; `int-r7/citizen-verification-ux.md:733-752`; `int-r7/frozen-falsifier-suite.md:857-875`; `int-r7-public-verification-lifecycle.md:204` | Split-view failure preserves issuer issuance and blocks public-current reliance through the public-history dimension. |
| R9 | **executed and remediated** | `int-r7/threat-model-and-verification-predicates.md:921-931,948-1024`; `int-r7/frozen-falsifier-suite.md:1322-1375` | The five attack families remain; requested-use and released-history predicates are separated from issuer-side predicates. |
| R10 | **executed and remediated** | `int-r7/lifecycle-migration-preservation.md:570-594`; `int-r7/public-verification-profile.md:709-714`; `int-r7-public-verification-lifecycle.md:858-878,1004-1008` | The real-path pre-live ceremonial drill and bounded first-live-record drill remain; the old generic gate is locally marked as history. |
| R11 | **executed** | `int-r7/lifecycle-migration-preservation.md:595-637` | Added anti-rollback and compromised-primary/cross-custody recovery outcomes. |
| R12 | **executed with variation and remediated** | `int-r7/external-source-and-transfer-ledger.md:163,166,210-217`; `int-r7/lifecycle-migration-preservation.md:653-657`; `int-r7-public-verification-lifecycle.md:554-556,1010-1021` | US-01 is historical-only/superseded; US-03 is supplemental and jurisdiction-limited; the primary's old transfer is locally marked as history. |
| R13 | **executed** | `int-r7/external-source-and-transfer-ledger.md:164,213-217`; `int-r7/comparative-models.md:410-416` | US-02 is limited to a nonbinding Federal Register submission playbook. |
| R14 | **executed** | `int-r7/orientation-ledger.md:212-218` | Recorded the missed same-day correction: ratification, pin and inspection were all 2026-08-04. |
| R15 | **executed** | `int-r7/threat-model-and-verification-predicates.md:874-884`; `int-r7/public-verification-profile.md:675-685`; `int-r7/citizen-verification-ux.md:734-745`; `int-r7/lifecycle-migration-preservation.md:659-669` | Added explicit evidence obtainability and competent restriction outcomes. |
| R16 | **executed and remediated** | `int-r7/threat-model-and-verification-predicates.md:765-776`; `int-r7/comparative-models.md:396-408`; `int-r7-public-verification-lifecycle.md:886-891,945-959` | “Separately reportable” remains controlling; the primary's old “independent” wording is locally marked as history. |
| R17 | **executed** | `int-r7/external-source-and-transfer-ledger.md:161-167`; `int-r7/comparative-models.md:410-416` | Corrected ETSI-05 date, narrowed RFC 9162 transfer, and added SIG-05 exact bundle-format source. |
| R18 | **executed** | `int-r7/repository-integration-and-dependencies.md:412-414`; `int-r7/public-verification-profile.md:726-728`; `int-r7/citizen-verification-ux.md:782-784`; `int-r7-public-verification-lifecycle.md:1047-1049`; `int-r7/frozen-falsifier-suite.md:1238-1241` | Anti-wire/API/schema/enum warnings remain intact. |
| R19 | **executed** | `int-r7/public-verification-profile.md:701-708`; `int-r7/lifecycle-migration-preservation.md:639-651`; `int-r7/citizen-verification-ux.md:758-764`; suite F-18b at `int-r7/frozen-falsifier-suite.md:1087-1102` | Positive lawful succession preserves predecessor attribution. |
| R20 | **executed with variation** | `int-r7/orientation-ledger.md:220-258` | O-05 14/14 and O-09 5/5 static outputs remain; fresh local rerun remains unavailable; O-02/O-08 stay `not_established`. |
| R21 | **executed** | suite F-03a at `int-r7/frozen-falsifier-suite.md:780-791`; F-13a at `:984-997` | Local `SignatureValid` remains separate from `SignaturePolicySatisfied` and quorum satisfaction. |
| R22 | **executed** | `int-r7/external-source-and-transfer-ledger.md:169-225` | Per-source currentness/recheck metadata and manual revalidation trigger remain intact. |

### Revision count reconciliation

**22 revisions / 22 total:** 19 originally `executed`, 3 originally `executed with variation`, 0 `declined`. Bounded remediation does not alter those amendment dispositions; it closes verification gaps in R1, R3, R4, R5, R6, R8, R9, R10, R12, and R16.

## 4. Complete audit-finding disposition register

| Finding ID | Severity | Disposition and exact preservation/repair evidence |
| --- | --- | --- |
| INT-R7-I-001 | commendation | **preserved** — audited head remains the amendment merge base; remediation geometry is recorded in `int-r7/remediation-ledger.md`. |
| INT-R7-I-002 | commendation | **preserved** — mutable `signed_at`/identity and timeless revocation remain explicit at `int-r7-public-verification-lifecycle.md:932-937`. |
| INT-R7-I-003 | commendation | **preserved/strengthened** — O-09 static record at `int-r7/orientation-ledger.md:231-255`; producer retained at `int-r7/repository-integration-and-dependencies.md:365-368`. |
| INT-R7-I-004 | commendation | **preserved** — O-02/O-08 reservations remain at `int-r7/orientation-ledger.md:256-258`. |
| INT-R7-I-005 | material | **corrected** — same-day error at `int-r7/orientation-ledger.md:212-218`. |
| INT-R7-I-006 | minor | **bounded** — retained 14/14 record and rerun limitation at `int-r7/orientation-ledger.md:220-230`. |
| INT-R7-II-001 | commendation | **preserved** — original 30/30 corpus and amended currentness controls at `int-r7/external-source-and-transfer-ledger.md:153-225`. |
| INT-R7-II-002 | minor | **corrected** — ETSI-05 date at `int-r7/external-source-and-transfer-ledger.md:161`. |
| INT-R7-II-003 | material | **corrected** — US-01 historical-only at `int-r7/external-source-and-transfer-ledger.md:163`; present-tense lifecycle use superseded at `int-r7/lifecycle-migration-preservation.md:653-657`; primary point marker at `int-r7-public-verification-lifecycle.md:554-556`. |
| INT-R7-II-004 | material | **corrected** — US-02 narrowed at `int-r7/external-source-and-transfer-ledger.md:164,213-217`. |
| INT-R7-II-005 | minor | **corrected** — RFC 9162 transfer narrowed at `int-r7/external-source-and-transfer-ledger.md:162`. |
| INT-R7-II-006 | minor | **corrected** — SIG-05 added at `int-r7/external-source-and-transfer-ledger.md:166`. |
| INT-R7-III-001 | commendation | **preserved** — the five-dimension model and predicate split remain at `int-r7/threat-model-and-verification-predicates.md:761-919,948-1024`. |
| INT-R7-III-002 | material | **corrected** — aggregate conflation is superseded at `int-r7/threat-model-and-verification-predicates.md:777-919`; primary point marker at `int-r7-public-verification-lifecycle.md:204`. |
| INT-R7-III-003 | minor | **corrected** — separately reportable wording at `int-r7/threat-model-and-verification-predicates.md:765-776`; primary marker at `int-r7-public-verification-lifecycle.md:886-891`. |
| INT-R7-III-004 | material | **corrected** — rollback/selection at `int-r7/threat-model-and-verification-predicates.md:851-873`. |
| INT-R7-IV-001 | commendation | **preserved** — all nine comparative models and eliminating properties survive at `int-r7/comparative-models.md:1-425`. |
| INT-R7-IV-002 | commendation | **preserved** — GY-N12/INT-R8 ownership remains consumed, not duplicated, at `int-r7/repository-integration-and-dependencies.md:387-414`. |
| INT-R7-IV-003 | material | **updated, still open** — INT-R8 delivered but unaudited; positives remain unsatisfied at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-IV-004 | material | **preserved as open dependency** — GY-N12 remains planned at `int-r7/repository-integration-and-dependencies.md:408-410`. |
| INT-R7-V-001 | material | **corrected and remediated** — exact whole-token grammar and value/status pairing at `int-r7/frozen-falsifier-suite.md:1243-1315`. |
| INT-R7-V-002 | material | **corrected** — F-04 temporal terminal at `int-r7/frozen-falsifier-suite.md:793-807`. |
| INT-R7-V-003 | material | **corrected** — F-08 issuer issuance preserved at `int-r7/threat-model-and-verification-predicates.md:933-943` and suite `:857-875`. |
| INT-R7-V-004 | commendation | **preserved/expanded** — F-05 at suite `:809-823`, F-17 at `:1054-1070`, and F-18a/F-18b at `:1072-1102`. |
| INT-R7-V-005 | material | **corrected and remediated** — five attacks remain at threat `:921-931`; predicate-consistent overlays at suite `:1322-1375`. |
| INT-R7-VI-001 | commendation | **preserved/clarified** — gate binds live authority-bearing issuance, not candidate/test work, at `int-r7/lifecycle-migration-preservation.md:570-594`. |
| INT-R7-VI-002 | material | **corrected** — non-circular drill phases at `int-r7/lifecycle-migration-preservation.md:570-594`; primary marker at `int-r7-public-verification-lifecycle.md:858`. |
| INT-R7-VI-003 | material | **corrected** — anti-rollback/cross-custody at `int-r7/lifecycle-migration-preservation.md:595-637`. |
| INT-R7-VI-004 | commendation | **preserved** — late renewal cannot repair history and custody cannot launder issuer at `int-r7/lifecycle-migration-preservation.md:552-568,639-657`. |
| INT-R7-VII-001 | commendation | **preserved/strengthened** — INT-K06 remains primary; negative-terminal withholding is separated at threat `:948-1024` and suite `:1355-1365`. |
| INT-R7-VII-002 | commendation | **preserved** — INT-K02 basis remains issuer-statement integrity at threat `:777-809`; suite F-11 remains unchanged. |
| INT-R7-VII-003 | commendation | **preserved** — withdrawn-but-verifiable vector remains in threat §15.6 and suite F-17 at `:1054-1070`. |
| INT-R7-VII-004 | commendation | **preserved** — v2 passage remains S0-K16-bounded at suite `:1221-1237,1373-1375`. |
| INT-R7-VII-005 | commendation | **preserved** — no second authority/status/projection owner at `int-r7/repository-integration-and-dependencies.md:387-414`. |
| INT-R7-VIII-001 | commendation | **preserved** — proof/content seam and provisional comparison at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-VIII-002 | material | **updated, still unsatisfied** — delivered-but-unaudited INT-R8 at `int-r7/repository-integration-and-dependencies.md:387-407`. |
| INT-R7-VIII-003 | material | **corrected** — INT-R8 failure affects projection, not issuance, at threat `:813-850`; requested/release split at `:948-1024`. |
| INT-R7-IX-001 | commendation | **preserved** — amendment prohibitions remain; touched remediation artifacts also retain frontmatter prohibitions and the exact remediation binding. |
| INT-R7-IX-002 | minor | **corrected** — anti-wire warnings remain at repository `:412-414`, profile `:726-728`, UX `:782-784`, primary `:1047-1049`, and suite `:1238-1241`. |
| INT-R7-IX-003 | commendation | **preserved** — `GO_WITH_REVISIONS` remains at primary `:1029-1053`; first-public-signature gate stays closed. |
| INT-R7-X-001 | blocking | **corrected** — capability reclassification at `int-r7/repository-integration-and-dependencies.md:356-385`; primary old labels are marked at `:125,733`. |
| INT-R7-X-002 | commendation | **preserved** — real export producer and `bridge_missing` route remain at `int-r7/repository-integration-and-dependencies.md:365-368`. |

### Finding-count reconciliation

**42 findings / 42 total:** 1 blocking, 15 material, 6 minor, 20 commendations. Bounded remediation changes no audit severity or audit disposition count.

## 5. Dependency and capability boundary after remediation

- **INT-R8:** delivered at `90b372964d29a9e97605a6ef733ef03ffe7938d2`, standing `accepted_narrow_scope`, but unaudited for this use. Interface comparison remains provisional; projection positives remain hypothetical and unsatisfied.
- **GY-N12:** contract-only/planned; current-authority positives remain hypothetical and unsatisfied.
- **OPS-R14/institutions:** durability mechanics, legal hold, continuity, role assignment, funding and jurisdictional recognition remain unresolved.
- **Pinned capability reality:** the real export producer exists and its intended production route remains `bridge_missing`; proposed public-proof lifecycle capabilities are otherwise absent/unallocated.

## 6. Amendment delivery record retained as history

The amendment head `2d922813ef542f3eebd21d2a189c017b15512803` was independently verified as 12 commits ahead of the audited head, with 11 changed Markdown paths, 1,600 insertions, and 0 deletions. Those are facts about the amendment delivery, not the remediation branch. Current remediation geometry is recorded in `int-r7/remediation-ledger.md` after complete compare and read-back.

## 7. Bounded remediation index

| Verification finding | Controlling repair |
| --- | --- |
| `INT-R7-V-102` | primary frontmatter `:14-15`, executive notice `:43`, and point markers `:60,125,204,554,679,733,858,886`; full eleven-artifact reachability check in `int-r7/remediation-ledger.md` |
| `INT-R7-V-103` | suite whole-token grammar and pair rules `:1243-1315` |
| `INT-R7-V-104` | threat diagnosis/formulas `:948-1024`; suite corrected overlays `:1322-1375` |
| evidence-path precision | R12, R15, R17 and corresponding finding rows above now land on the exact propositions rather than section starts |

The standing remains **`GO_WITH_REVISIONS` pending independent delta-only re-verification**. No suite passage, publication capability, or permission to open the first-public-signature gate is claimed.