---
title: INT-R7 — Bounded Remediation Ledger
research_id: INT-R7
status: remediated_pending_delta_verification
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
amendment_commit: 2d922813ef542f3eebd21d2a189c017b15512803
verification_commit: 5225f8bf6cc995f0d3a9cb622454c1af9432745d
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
remediation_branch: research/int-r7-remediation
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
remediated_after_verification: research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d
authoritative_for:
  - bounded closure evidence for INT-R7-V-102, INT-R7-V-103, and INT-R7-V-104
  - correction of amendment-ledger evidence-path precision
  - complete supersession-reachability check across the eleven amendment artifacts
  - regression evidence for the twelve already-conforming revisions and twenty surviving audit commendations
  - updated standing after bounded remediation
may_not_use_for:
  - re-audit or re-adjudication of INT-R7 or INT-R8
  - new research, attack families, or implementation design
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, key custodian, trust service, log, witness, archive, institution, team, person, or vendor appointment
  - authority grant or capability claim
  - benchmark, recovery-drill, or falsifier-suite passage claim
  - legal compliance, legal sufficiency, admissibility, or institutional competence conclusion
  - permission to publish a governed record or open the first-public-signature gate
research_only: true
---

# INT-R7 bounded remediation ledger

## 1. Scope and method

This is a delta-only remediation of three conformance findings and one evidence-path precision defect. It does not reopen the research, audit, amendment, INT-R8 seam, three honest variations, twelve already-conforming revisions, or twenty audit commendations.

Ordinary GitHub access was unavailable: direct clone/remote access could not resolve or connect to GitHub. Exact-ref reads, ordinary Markdown commits and post-write reads used the connected GitHub interface. No CI workflow, upload fragment, staging directory, base64 repository payload, binary file, or self-executing automation was committed.

The source amendment remains `research/int-r7-amendment@2d922813ef542f3eebd21d2a189c017b15512803`. This remediation branch was created from that exact head. Every set-level statement below names its complete denominator.

## 2. `INT-R7-V-102` — supersession is reachable

### 2.1 Primary-report repair

The primary report now carries all three required layers:

| Layer | Exact evidence | Closure effect |
| --- | --- | --- |
| machine-readable frontmatter | `int-r7-public-verification-lifecycle.md:14-15` | binds this remediation verification and names §21 as the controlling post-audit amendment |
| executive entry notice | `int-r7-public-verification-lifecycle.md:43` | tells every entry-point reader that conflicting earlier text is audited history before any affected proposition appears |
| executive dependency/suite point marker | `:60` | directs old INT-R8/GY-N12 availability and 18-case wording to §§21.3, 21.5 and 21.6 |
| capability-label point marker | `:125` | directs old downstream labels to §21.4 and the corrected repository handoff |
| aggregate-algebra point marker | `:204` | directs `HistoricalAuthenticity`/current algebra to §21.2 and threat-model §15 |
| US-01 point marker | `:554` | directs present-tense US-01 use to §21.7 and the source ledger §6 |
| suite-v1 point marker | `:679` | labels the 18-case denominator audited history and directs to v2 |
| N-01–N-07 label point marker | `:733` | labels old labels audited history and preserves only the real `bridge_missing` route |
| recovery/suite gate point marker | `:858` | directs the generic drill and 18/18 gate to §§21.5–21.6 |
| independence point marker | `:886` | directs the word “independent” to the separately-reportable §21.2 model |
| controlling amendment | `:926-1053` | preserves the post-audit model and records bounded remediation status |

The earlier propositions are not deleted. They are reachable only with an immediately preceding direction to the governing text.

### 2.2 Complete eleven-artifact supersession check

The complete set is **11 amendment artifacts / 11 total**:

| Artifact | Result after remediation | Evidence |
| --- | --- | --- |
| primary report | repaired | frontmatter/executive/point markers above |
| orientation ledger | already conforming; unchanged | §7 explicitly controls O-18 and static outputs; no earlier row asserted the false four-day fact |
| threat model | conforming; bounded new supersession explicit | §15 supersedes §§7–8; §15.10 at `:948-1024` explicitly supersedes overloaded names in §§7.1 and 15.2 |
| comparative models | already conforming; unchanged | §14 controls the comparative conclusion after named findings |
| public-verification profile | already conforming; unchanged | §18 explicitly supersedes named earlier sections where dimensions collapse |
| lifecycle/preservation | already conforming; unchanged | §11 explicitly supersedes named earlier sections and states preservation does not edit past occurrence |
| citizen UX | already conforming; unchanged | §13 explicitly supersedes the two-question/aggregate/capability text |
| falsifier suite | repaired for new defects | §9 begins with a remediation notice before old §9.1; §10 at `:1243-1375` controls grammar, baseline pairs and overlays |
| repository/dependencies | already conforming; unchanged | §11 explicitly supersedes §§2, 4 and 6 missing-state labels |
| external-source ledger | already conforming; unchanged | §6 explicitly controls source use after the named findings |
| amendment ledger | new accountability artifact, not a carrier of an older governing proposition | remediation index and tightened paths point to the exact controlling text |

Result: **11 checked / 11 total; 2 repaired, 8 already conforming and unchanged, 1 not applicable as a new accountability artifact**.

### 2.3 Revisions closed through the common root repair

The reachable-supersession repair closes the shared gap for exactly **9 revisions / 9 total affected revisions**:

```text
R1 R3 R4 R5 R6 R8 R10 R12 R16
```

R9's remaining gap was V-104 rather than primary reachability and is closed in §4 below.

## 3. `INT-R7-V-103` — typed grammar and value/status consistency

### 3.1 Exact-token validator

`int-r7/frozen-falsifier-suite.md:1243-1282` replaces substring rejection with a typed whole-token grammar. A validator now:

- parses the entire scalar token;
- checks exact membership in the value family declared for the slot;
- checks exact membership in the evaluation-status vocabulary;
- requires non-null for `evaluated`;
- requires null for `short_circuited`, `not_applicable`, or `dependency_unavailable`; and
- rejects conditional/free-prose pseudo-values because the whole scalar is not a grammar member, not because a substring happens to occur inside it.

Therefore the permitted token `short_circuited` is not rejected merely because it contains the letters `or`.

### 3.2 Baseline correction

The controlling B0/B1 definitions are at `int-r7/frozen-falsifier-suite.md:1284-1315`:

- B0 `BasisBound` is `{value: null, evaluation_status: not_applicable}`;
- B1 overrides it with `{value: true, evaluation_status: evaluated}`; and
- F-02a's null/short-circuited result remains a valid unevaluated pair.

### 3.3 Complete value/status sweep

The complete fixture-record denominator is **31 records / 31 total**:

```text
B0 B1
F-01a F-02a F-03a F-04a F-05a F-06a F-07a F-08a F-09a
F-10a F-10b F-11a F-11b F-12a F-12b F-12c F-13a F-14a
F-15a F-16a F-17a F-18a F-18b AX-01a AX-02a AX-03a AX-04a
AX-05a AX-05b
```

The amendment's B0 `BasisBound` was the only value/status mismatch. After the controlling §10 baseline is applied, **31/31 pairs are grammar-consistent**. This is a specification sweep, not a claim that a runtime validator has executed.

## 4. `INT-R7-V-104` — predicate collision diagnosed and resolved

### 4.1 Diagnosis

The defect was a name collision, not three unrelated expected-value errors:

- F-09a's signed statement still declares its citizen audience; the requested agency-adjudication use is not permitted.
- F-10a's signed statement still declares J1; the requested J2 recognition/use is not permitted.
- AX-05a's signed procedural statement still commits to the required negative-terminal set; the released projection/history withholds a required terminal.

Issuer-side statement completeness, requested-use authorization and released-history completeness are separate propositions.

### 4.2 Controlling predicate split

`int-r7/threat-model-and-verification-predicates.md:948-1024` defines:

- `IssuerAudienceDeclaredAndBound` versus `RequestedAudienceUsePermitted`;
- `IssuerJurisdictionDeclaredAndBound` versus `RequestedJurisdictionUsePermitted`; and
- `IssuerProceduralHistoryBound` versus `ReleasedProceduralHistoryComplete`.

The controlling issuer formula uses only issuer-side predicates. Requested-use mismatch blocks reliance for the request; released-history withholding blocks projection/public-history reliance. Neither rewrites an established issuer occurrence.

### 4.3 Exact suite overlays

The six controlling overlays are at `int-r7/frozen-falsifier-suite.md:1322-1365`:

| Subfixture | Issuer-side result | Separate failing proposition |
| --- | --- | --- |
| F-09a | issuer issuance established; issuer audience binding true | requested audience use false |
| F-10a | issuer issuance established; issuer jurisdiction binding true | requested jurisdiction use false |
| F-12a | issuer issuance contradicted | issuer procedural history binding false |
| F-12b | issuer issuance contradicted | issuer procedural history binding false |
| F-12c | issuer issuance contradicted | issuer procedural history binding false |
| AX-05a | issuer issuance established; issuer procedural history binding true | released procedural history completeness false; projection contradicted |

### 4.4 Complete algebra sweep

The complete controlling v2 denominator remains **29 subfixtures / 29 total**. Six require the split vocabulary; the other 23 do not change. After the overlays, no subfixture reports `IssuerIssuanceAuthentic = established` while setting a necessary issuer-side predicate false. No family, subfixture, attack, reason code, or denominator is added or removed.

## 5. Evidence-path precision repair

The amendment ledger now lands on the changed proposition rather than the beginning of a later section:

| Row | Old imprecise anchor | Tightened evidence |
| --- | --- | --- |
| R12 | source `:153`; lifecycle `:552` | source `:163,166,210-217`; lifecycle `:653-657`; primary `:554-556,1010-1021` |
| R15 | lifecycle `:552` | lifecycle `:659-669`, with threat/profile/UX exact ranges |
| R17 | source `:153` | source `:161-167`; comparative `:410-416` |
| INT-R7-II-003 | lifecycle `:552` | source `:163`; lifecycle `:653-657`; primary `:554-556` |

The rest of the remediation index likewise points to the controlling formulas, grammar, overlays, or point markers.

## 6. Regression statement — twelve already-conforming revisions

The complete protected set is **12 revisions / 12 total**. None was reopened or semantically changed by the bounded repair.

| Revision | Regression evidence | Result |
| --- | --- | --- |
| R2 | snapshot-selection algebra at threat `:851-873`; lifecycle `:595-612`; AX-02 unchanged | intact |
| R7 | threat `:794-811`; UX `:705-718`; F-04a suite `:793-807` | intact |
| R11 | lifecycle anti-rollback/cross-custody `:595-637` | intact |
| R13 | source `:164,213-217`; comparative `:410-416` | intact |
| R14 | orientation O-18 `:212-218` | intact |
| R15 | obtainability at threat `:874-884`, profile `:675-685`, UX `:734-745`, lifecycle `:659-669`, AX-05b unchanged | intact |
| R17 | source metadata/attribution `:161-167`; comparative `:410-416` | intact |
| R18 | anti-wire warnings in repository/profile/UX/primary/suite | intact |
| R19 | profile `:701-708`; lifecycle `:639-651`; UX `:758-764`; F-18b suite `:1087-1102` | intact |
| R20 | orientation static outputs/reservations `:220-258` | intact |
| R21 | F-03a suite `:780-791`; F-13a `:984-997` | intact |
| R22 | source currentness/recheck `:169-225` | intact |

## 7. Regression statement — twenty audit commendations

The complete protected set is **20 commendations / 20 total**. All remain intact or strengthened.

| Finding ID | Strength preserved | Post-remediation evidence |
| --- | --- | --- |
| `INT-R7-I-001` | exact branch geometry and bounded scope | complete compare/read-back record in §9 |
| `INT-R7-I-002` | signing-time/revocation implementation defect precisely bounded | primary `:932-937`; no source conclusion weakened |
| `INT-R7-I-003` | O-09 correction and real producer preserved | orientation `:231-255`; repository `:365-368` |
| `INT-R7-I-004` | honest O-02/O-08 reservations | orientation `:256-258` |
| `INT-R7-II-001` | primary-heavy, transfer-limited source corpus | source ledger `:153-225`; no source removed |
| `INT-R7-III-001` | signature does not equal a worldly fact | five dimensions and predicate split at threat `:761-919,948-1024` |
| `INT-R7-IV-001` | nine real comparative constructions with eliminating properties | comparative artifact unchanged |
| `INT-R7-IV-002` | GY-N12 and INT-R8 ownership not duplicated | repository `:387-414` |
| `INT-R7-V-004` | F-05/F-17/F-18 protect history, withdrawal and succession | suite F-05a `:809-823`, F-17a `:1054-1070`, F-18a/b `:1072-1102` |
| `INT-R7-VI-001` | first-signature gate respects candidate/authority bands | lifecycle `:570-594`; primary marker `:858` |
| `INT-R7-VI-004` | preservation never launders issuer identity or late trust loss | lifecycle `:552-568,639-657`; F-15/F-18 unchanged |
| `INT-R7-VII-001` | INT-K06 chronology remains security-critical | threat `:921-931,948-1024`; AX-05a corrected rather than removed |
| `INT-R7-VII-002` | INT-K02 basis completeness remains statement integrity | threat issuer formula; F-11 unchanged |
| `INT-R7-VII-003` | withdrawn-but-verifiable remains first-class | threat §15.6; F-17 unchanged |
| `INT-R7-VII-004` | S0-K16 bounds suite passage | suite `:1221-1237,1373-1375` |
| `INT-R7-VII-005` | no second authority/status/projection owner | repository `:387-414`; anti-wire warnings intact |
| `INT-R7-VIII-001` | proof/content seam remains explicit and disciplined | repository `:387-407`; no INT-R8 change |
| `INT-R7-IX-001` | effective research prohibitions | all touched artifacts retain non-empty `may_not_use_for` and `research_only: true` |
| `INT-R7-IX-003` | `GO_WITH_REVISIONS` remains the correct target | primary `:1029-1053`; first-public-signature gate closed |
| `INT-R7-X-002` | real public-export producer not erased | repository `:365-368`; primary point markers preserve the correct route-only `bridge_missing` result |

Result: **20 intact or strengthened / 20 total; 0 weakened; 0 lost**.

## 8. Updated standing

**Standing: `GO_WITH_REVISIONS`, retained pending independent delta-only re-verification.**

The authoring-level definition of done is met:

- V-102 has machine-readable, executive and point-of-use supersession in the primary plus an eleven-artifact check;
- V-103 has a self-consistent whole-token grammar and 31/31 value/status sweep;
- V-104 has an explicit diagnosis, split predicates and a 29/29 algebra sweep;
- evidence paths are tightened; and
- the twelve conforming revisions and twenty commendations remain intact.

This ledger does not claim independent conformance, suite passage, production capability, legal sufficiency, or publication permission. INT-R8 remains untouched. The first-public-signature gate remains closed.

## 9. Post-write verification record

This section is completed after all writes by reading every touched file back from `research/int-r7-remediation` and comparing the branch to amendment head `2d922813ef542f3eebd21d2a189c017b15512803`. Until that final read-back is recorded, repository geometry beyond the source head is not asserted here.