---
title: INT-R7 — Bounded-Remediation Conformance Ledger
verified_commit: 92c05323ed4c13c8f9eadb586d4e627c8d33a409
verified_branch: research/int-r7-remediation
prior_verification_commit: 5225f8bf6cc995f0d3a9cb622454c1af9432745d
audited_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
remediation_base_commit: 2d922813ef542f3eebd21d2a189c017b15512803
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
verification_branch: research/int-r7-remediation-verification
authoritative_for:
  - independently checkable working evidence for INT-R7-V-102 through INT-R7-V-105
  - complete primary and 11-artifact supersession-reachability evidence
  - complete 31-record value/status and 29-subfixture issuer-algebra evidence
  - deletion and evidence-path reconciliation
  - delta-only regression evidence for twelve revisions and twenty commendations
may_not_use_for:
  - re-audit or substantive re-adjudication of INT-R7
  - audit, adoption, or seam adjudication of INT-R8
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, key custodian, trust service, log, witness, archive, institution, team, person, or vendor appointment
  - authority grant or capability claim
  - benchmark, recovery-drill, or falsifier-suite passage claim
  - legal compliance, legal sufficiency, admissibility, or institutional competence conclusion
  - permission to publish a governed record or open the first-public-signature gate
research_only: true
---

# INT-R7 bounded-remediation conformance ledger

## 1. Evidence discipline

This ledger records direct inspection of the remediated source at
`92c05323ed4c13c8f9eadb586d4e627c8d33a409`. The remediation ledger was used only to identify
claimed evidence; it was not accepted as proof of closure.

Set-level facts use complete denominators:

- 5 changed remediation paths / 5 total;
- 7 named primary propositions / 7 total;
- 9 primary-report affected revisions / 9 total;
- 11 amendment artifacts / 11 total;
- 31 fixture records / 31 total;
- 23 families / 23 total;
- 29 subfixtures / 29 total;
- 12 regression revisions / 12 total; and
- 20 regression commendations / 20 total.

Ordinary GitHub DNS/egress was unavailable. Exact-ref connector reads and ordinary Markdown
commits were used. No automation was added.

## 2. Geometry and deletion ledger

### 2.1 Complete path denominator

| Exact path | Status | `+` | `-` | Inspected consequence |
| --- | --- | ---: | ---: | --- |
| `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md` | modified | 28 | 2 | local supersession markers and final status appended; old propositions remain |
| `policy-engine/docs/research/policy-operations/int-r7/amendment-ledger.md` | modified | 88 | 106 | evidence rows rewritten; 22 revision and 42 finding rows remain |
| `policy-engine/docs/research/policy-operations/int-r7/frozen-falsifier-suite.md` | modified | 139 | 1 | §10 appended; old §9 remains |
| `policy-engine/docs/research/policy-operations/int-r7/remediation-ledger.md` | added | 272 | 0 | accountability record |
| `policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md` | modified | 80 | 1 | §15.10 appended; old §15.2 remains |
| **total** | **4 modified + 1 added** | **607** | **110** | **0 non-Markdown paths** |

Arithmetic:

```text
28 + 88 + 139 + 272 + 80 = 607
2 + 106 + 1 + 0 + 1 = 110
```

### 2.2 Deletion classification

| File | Deleted lines | Classification | Audited proposition removed? |
| --- | ---: | --- | --- |
| primary | 2 | one sentence split before local marker; one retained EOF sentence replaced by itself plus §21.11 | no |
| amendment ledger | 106 | old evidence/prose lines replaced by 88 tighter lines | no; 22/22 and 42/42 rows remain |
| suite | 1 | retained EOF anti-wire sentence replaced by itself plus §10 | no |
| threat model | 1 | retained EOF anti-wire sentence replaced by itself plus §15.10 | no |
| remediation ledger | 0 | added file | not applicable |

The comparison API reports **lines**, not semantic rows. “106 rows replaced by 88” is therefore
not the precise unit; the correct statement is 106 deleted lines and 88 added lines in the
amendment ledger.

## 3. `INT-R7-V-102` working evidence

### 3.1 Frontmatter and executive entry

| Evidence | Exact location | Direct finding |
| --- | --- | --- |
| remediation binding | primary `:14` | exact prior-verification commit recorded |
| machine-readable controller | primary `:15` | names §21 as controlling post-audit amendment |
| executive notice | primary `:43` | says conflicting earlier text is audited history before affected propositions appear |

### 3.2 Seven stale propositions

| # | Stale proposition inspected | Advance notice | Specific controller named | Verdict |
| ---: | --- | --- | --- | --- |
| 1 | executive: INT-R8 contract “is available” gate and 18 falsifiers, primary `:62-71` | `:60` | §§21.3, 21.5, 21.6 | pass |
| 2 | §2.3 capability labels, primary `:129-134` | `:125` | §21.4 + repository §11 | pass |
| 3 | §4.2 aggregate formula, primary `:206-250` | `:204` | §21.2 + threat §15 | pass |
| 4 | §12.2 US-01 current transfer, primary `:556-558` | `:554` | §21.7 + source §6 | pass |
| 5 | §15 v1 suite/18 denominator, primary `:681-712` | `:679` | §21.5 + suite §9 as remediated | pass |
| 6 | §16.2 capability labels, primary `:735-746` | `:733` | §21.4 + repository §11 | pass |
| 7 | §19 generic drill/18-of-18 and §20 “independent,” primary `:860-890` | `:858`, `:886` | §§21.5–21.6; §21.2 | pass |

Result: **7/7 propositions have an actionable signal before the proposition**.

### 3.3 Nine revision reachability rows

| Revision | Primary evidence | Primary result | Remaining delta issue |
| --- | --- | --- | --- |
| R1 | `:204`, §21.2 `:945-959` | pass | threat §15.2/§15.10 reachability |
| R3 | `:60`, §21.3 `:961-973` | pass | none in primary |
| R4 | `:204,60`, §21.3 | pass | none in primary |
| R5 | `:125,733`, §21.4 `:975-986` | pass | none |
| R6 | `:60,679,858`, §21.5 `:988-1002` | pass | none |
| R8 | `:204`, §21.2 | pass | none in primary |
| R10 | `:858`, §21.6 `:1004-1008` | pass | none |
| R12 | `:554`, §21.7 `:1010-1021` | pass | none |
| R16 | `:886`, §21.2 | pass | none |

Primary denominator: **9 passes / 9 total**.

### 3.4 Complete 11-artifact sweep

| Artifact | Superseded region | Control clause | One-pass verdict |
| --- | --- | --- | --- |
| primary | executive; §§2.3, 4.2, 12.2, 15, 16.2, 19, 20 | frontmatter `:15`; executive `:43`; local markers | pass |
| orientation | missed-date and static-output claims | §7 `:208-258` controls R14/R20 | pass |
| threat | §§7–8 aggregate; §15.2 overloaded formula | §15 `:761`; §15.10 `:948` | **gap at §15.2** |
| comparative | comparative conclusion/source transfers | §14 `:392-425` | pass |
| profile | §§2, 10, 13, 15–17 collapse | §18 `:622-728` | pass |
| lifecycle | §§3, 5, 6, 9, 10 historical/preservation wording | §11 `:552-672` | pass |
| UX | UX-T03; §§3, 5, 10–12 aggregate/capabilities | §13 `:668-784` | pass |
| suite | v1; §9.1–9.4 stale grammar/baseline/overlays | §9 notice `:670`; §10 `:1243-1375` | pass |
| repository/dependencies | §§2, 4, 6 missing-state labels | §11 `:356-414` | pass |
| external source ledger | old source rows/transfers | §6 `:153-225` | pass |
| amendment ledger | accountability record | not a prior semantic proposition owner | not applicable |

Count: **9 applicable passes, 1 applicable gap, 1 not applicable; 11/11 inspected**.

The remediation ledger's “8 already conforming and unchanged” phrase is accurate only as a
V-102 semantic classification. Raw file geometry has seven unchanged conforming research files;
the threat model changed for V-104, and the amendment ledger changed for evidence precision.

## 4. `INT-R7-V-103` working evidence

### 4.1 Scoped supersession

| Old §9 content | §10 controlling category | Coverage verdict |
| --- | --- | --- |
| §9.1 scalar value list | typed whole-token grammar, §10.1 `:1248-1269` | covered |
| §9.2 substring rule and incomplete pair rules | value/status grammar and §10.2 `:1271-1282` | covered |
| §9.3 B0/B1 | corrected baselines, §10.3 `:1284-1315` | covered |
| six inconsistent predicate maps in §9.4 | corrected overlays, §10.4 `:1317-1365` | covered |

The §9 remediation notice appears before §9.1 at `frozen-falsifier-suite.md:670-672`, so a reader
knows which later section governs before encountering the stale rule.

No required correction falls outside the four scoped categories. Denominators, outcomes, reason
codes, S0-K16 scope and anti-wire warnings remain controlled by §§9.4–9.8/10.6 and do not conflict
with §10.

### 4.2 Complete 31-record value/status sweep

| Record | Source | Pair pattern after §10 | Verdict |
| --- | --- | --- | --- |
| B0 | §10.3 | one `null/not_applicable`; all others non-null/evaluated | pass |
| B1 | §10.3 | `BasisBound=true/evaluated` override | pass |
| F-01a | §9.4 | all non-null/evaluated | pass |
| F-02a | §9.4 | `SignatureValid=null/short_circuited`; others non-null/evaluated | pass |
| F-03a | §9.4 | all non-null/evaluated | pass |
| F-04a | §9.4 | all non-null/evaluated | pass |
| F-05a | §9.4 | all non-null/evaluated | pass |
| F-06a | §9.4 | all non-null/evaluated | pass |
| F-07a | §9.4 | all non-null/evaluated | pass |
| F-08a | §9.4 | all non-null/evaluated | pass |
| F-09a | §10.4 overlay | all non-null/evaluated | pass |
| F-10a | §10.4 overlay | all non-null/evaluated | pass |
| F-10b | §9.4 | all non-null/evaluated | pass |
| F-11a | §9.4 | all non-null/evaluated | pass |
| F-11b | §9.4 | all non-null/evaluated | pass |
| F-12a | §10.4 overlay | all non-null/evaluated | pass |
| F-12b | §10.4 overlay | all non-null/evaluated | pass |
| F-12c | §10.4 overlay | all non-null/evaluated | pass |
| F-13a | §9.4 | all non-null/evaluated | pass |
| F-14a | §9.4 | all non-null/evaluated | pass |
| F-15a | §9.4 | all non-null/evaluated | pass |
| F-16a | §9.4 | all non-null/evaluated | pass |
| F-17a | §9.4 | all non-null/evaluated | pass |
| F-18a | §9.4 | all non-null/evaluated | pass |
| F-18b | §9.4 | all non-null/evaluated | pass |
| AX-01a | §9.4 | all non-null/evaluated | pass |
| AX-02a | §9.4 | all non-null/evaluated | pass |
| AX-03a | §9.4 | all non-null/evaluated | pass |
| AX-04a | §9.4 | all non-null/evaluated | pass |
| AX-05a | §10.4 overlay | all non-null/evaluated | pass |
| AX-05b | §9.4 | all non-null/evaluated | pass |

Count: **31 passes / 31 total**. The only stale mismatch in §9 was B0
`BasisBound=true/not_applicable`; §10.3 corrects it. `short_circuited` is accepted as a whole
status token.

## 5. `INT-R7-V-104` working evidence

### 5.1 Formula expansion

Controlling §15.10 formula, threat `:981-1009`:

```text
IssuerStatementComplete :=
  CanonicalStatementRecognized
  and ContentBound
  and ClaimClassBound
  and IssuerAudienceDeclaredAndBound
  and IssuerJurisdictionDeclaredAndBound
  and AuthorityBoundaryBound
  and EpochBound
  and (not delta or BasisBound)
  and (not procedural or IssuerProceduralHistoryBound)

IssuerIssuanceAuthentic :=
  IssuerStatementComplete
  and SignatureValid
  and SignerCredentialValidAtIssuance
  and AuthorityValidAtIssuance
  and TrustedIssuanceTimeEstablished
  and PreCompromiseOrRevocationEstablished
```

Requested-use predicates occur only in `RequestedUseAuthorized`. Released-history completeness
occurs only in procedural projection faithfulness. The formula is semantically correct.

### 5.2 Six overlay checks

| Fixture | Baseline-expanded issuer predicates | Separate failing predicate | Expected issuer result | Verdict |
| --- | --- | --- | --- | --- |
| F-09a | issuer audience true | requested audience use false | established | pass |
| F-10a | issuer jurisdiction true | requested jurisdiction use false | established | pass |
| F-12a | issuer procedural history false | none | contradicted | pass |
| F-12b | issuer procedural history false | none | contradicted | pass |
| F-12c | issuer procedural history false | none | contradicted | pass |
| AX-05a | issuer procedural history true | released history false; projection contradicted | established | pass |

### 5.3 Complete 29-subfixture issuer-algebra sweep

| ID | Necessary issuer-side false? | Issuer result | Consistency |
| --- | --- | --- | --- |
| F-01a | legacy/no admitted issuer closure | not established | pass |
| F-02a | `ContentBound=false` | contradicted | pass |
| F-03a | independent trust/signature policy unavailable | not established | pass |
| F-04a | pre-revocation predicate false | contradicted | pass |
| F-05a | none | established | pass |
| F-06a | pre-compromise ordering false/indeterminate | not established | pass |
| F-07a | none; currentness fails separately | established | pass |
| F-08a | none; public history fails separately | established | pass |
| F-09a | none; requested audience fails separately | established | pass |
| F-10a | none; requested jurisdiction fails separately | established | pass |
| F-10b | `ContentBound=false` | contradicted | pass |
| F-11a | delta `BasisBound=false` | contradicted | pass |
| F-11b | delta `BasisBound=false` | contradicted | pass |
| F-12a | issuer procedural history false | contradicted | pass |
| F-12b | issuer procedural history false | contradicted | pass |
| F-12c | issuer procedural history false | contradicted | pass |
| F-13a | configured signature/quorum policy false | contradicted | pass |
| F-14a | none | established | pass |
| F-15a | none; durability fails separately | established | pass |
| F-16a | none | established | pass |
| F-17a | none; current authority withdrawn separately | established | pass |
| F-18a | none; presented attribution fails separately | established | pass |
| F-18b | none | established | pass |
| AX-01a | trusted issuance time false | not established | pass |
| AX-02a | none; snapshot selection/currentness fails separately | established | pass |
| AX-03a | none; succession/currentness dispute separately | established | pass |
| AX-04a | canonical statement false | not established | pass |
| AX-05a | none; released history/projection fails separately | established | pass |
| AX-05b | none; obtainability fails separately | established | pass |

Count: **29 algebra-consistent / 29 total**. Family denominator remains **23/23**.

### 5.4 Reachability inspection

| Reader position | Text encountered | Advance supersession signal? |
| --- | --- | --- |
| threat §15 heading, `:761` | calls §15 the post-audit controlling decomposition | no signal about later §15.10 |
| threat §15.2, `:777-809` | old overloaded issuer formula | no |
| threat §15.10, `:948-1024` | says §15.2 meanings are superseded and supplies corrected formula | arrives later |

This is a one-pass reachability gap even though the algebra is correct.

## 6. `INT-R7-V-105` working evidence

| Row checked | Remediated ledger citation | Target proposition inspected | Verdict |
| --- | --- | --- | --- |
| R12 | source `:163,166,210-217`; lifecycle `:653-657`; primary `:554-556,1010-1021` | historical-only US-01, bounded US-03 and primary marker | exact |
| R15 | threat `:874-884`; profile `:675-685`; UX `:734-745`; lifecycle `:659-669` | four obtainability states and consequence | exact |
| R17 | source `:161-167`; comparative `:410-416` | ETSI date, RFC transfer and SIG-05 | exact |
| `INT-R7-II-003` | source `:163`; lifecycle `:653-657`; primary `:554-556` | NARA historical-only correction | exact |

Complete amendment-ledger rows retained:

- revisions: R1 through R22 exactly once — **22/22**;
- findings: INT-R7-I-001 through INT-R7-X-002 — **42/42**.

## 7. Repair-created defect ledger

| Finding ID | Severity | Exact evidence | Determination |
| --- | --- | --- | --- |
| `INT-R7-RV-001` | blocking | threat `:761-809,948-1024` | §15.2 is reachable as controlling text before §15.10 replaces its predicate names; V-102's 11-artifact claim and V-104 reachability remain incomplete. |

No analogous issue exists in the suite because the §9 notice precedes §9.1 and identifies the
exact §10 categories. No analogous issue exists in the primary because each stale proposition has
a local signal.

## 8. Regression ledger — 12 revisions

| Revision | Evidence resolved at remediation head | Touched by remediation? | Result |
| --- | --- | --- | --- |
| R2 | threat `:851-873`; lifecycle `:595-612`; AX-02 | threat appended only after relevant section | intact |
| R7 | threat `:794-811`; UX `:705-718`; F-04a `:793-807` | threat/suite touched outside fixture/formula | intact |
| R11 | lifecycle `:595-637` | no | intact |
| R13 | source `:164,213-217`; comparative `:410-416` | no | intact |
| R14 | orientation `:212-218` | no | intact |
| R15 | threat `:874-884`; profile `:675-685`; UX `:734-745`; lifecycle `:659-669`; AX-05b | threat/suite touched; cited propositions remain | intact |
| R17 | source `:161-167`; comparative `:410-416` | no | intact |
| R18 | repository `:412-414`; profile `:726-728`; UX `:782-784`; primary `:1047-1049`; suite `:1238-1241` | primary/suite touched; warnings remain | intact |
| R19 | profile `:701-708`; lifecycle `:639-651`; UX `:758-764`; F-18b `:1087-1102` | suite touched outside F-18b | intact |
| R20 | orientation `:220-258` | no | intact |
| R21 | F-03a `:780-791`; F-13a `:984-997` | suite touched outside those cases | intact |
| R22 | source `:169-225` | no | intact |

Count: **12 intact / 12 total**.

## 9. Regression ledger — 20 commendations

| Finding ID | Evidence resolved | Result |
| --- | --- | --- |
| `INT-R7-I-001` | complete remediation compare and five-path denominator | intact |
| `INT-R7-I-002` | primary §21.1 `:932-937` | intact |
| `INT-R7-I-003` | orientation `:231-255`; repository `:365-368` | intact/strengthened |
| `INT-R7-I-004` | orientation `:256-258` | intact |
| `INT-R7-II-001` | source `:153-225` | intact |
| `INT-R7-III-001` | threat five dimensions `:761-919`; corrected split `:948-1024` | intact despite reachability gap |
| `INT-R7-IV-001` | comparative artifact unchanged; §14 `:392-425` | intact |
| `INT-R7-IV-002` | repository `:387-414` | intact |
| `INT-R7-V-004` | F-05a `:809-823`; F-17a `:1054-1070`; F-18a/b `:1072-1102` | intact/expanded |
| `INT-R7-VI-001` | lifecycle `:570-594`; primary `:858` | intact |
| `INT-R7-VI-004` | lifecycle `:552-568,639-657`; F-15/F-18 | intact |
| `INT-R7-VII-001` | threat `:921-931,948-1024`; AX-05a overlay | intact/strengthened |
| `INT-R7-VII-002` | issuer formula; F-11a/b | intact |
| `INT-R7-VII-003` | threat §15.6; F-17a | intact |
| `INT-R7-VII-004` | suite `:1221-1237,1373-1375` | intact |
| `INT-R7-VII-005` | repository `:387-414`; anti-wire warnings | intact |
| `INT-R7-VIII-001` | repository `:387-407` | intact |
| `INT-R7-IX-001` | frontmatter of all five touched paths | intact |
| `INT-R7-IX-003` | primary `:1029-1053`; first-signature gate closed | intact |
| `INT-R7-X-002` | repository `:365-368` | intact |

Count: **20 intact or strengthened / 20 total; 0 weakened; 0 lost**.

The complete remediation diff has no INT-R8 path.

## 10. Conformance and standing ledger

| Item | Result |
| --- | --- |
| V-102 primary seven propositions | 7/7 pass |
| V-102 11-artifact sweep | 9 pass, 1 gap, 1 N/A |
| V-103 scoped grammar/pairing | pass |
| V-103 fixture records | 31/31 pass |
| V-104 overlays | 6/6 algebraically consistent |
| V-104 complete subfixtures | 29/29 algebraically consistent |
| V-104 reachability | gap |
| V-105 evidence paths | pass |
| regression revisions | 12/12 intact |
| regression commendations | 20/20 intact or strengthened |
| new findings | 1 blocking |
| final verdict | `CONFORMS_WITH_GAPS` |
| R1–R15 independent standing gate | not met |
| first-public-signature gate | closed |
