---
title: INT-R7 — Delta-Only Bounded-Remediation Verification
verified_commit: 92c05323ed4c13c8f9eadb586d4e627c8d33a409
verified_branch: research/int-r7-remediation
prior_verification_commit: 5225f8bf6cc995f0d3a9cb622454c1af9432745d
audited_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
remediation_base_commit: 2d922813ef542f3eebd21d2a189c017b15512803
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
verification_branch: research/int-r7-remediation-verification
verdict: CONFORMS_WITH_GAPS
authoritative_for:
  - delta-only closure determination for INT-R7-V-102, INT-R7-V-103, INT-R7-V-104, and INT-R7-V-105
  - independent nine-revision primary-report reachability check
  - independent 11-artifact supersession check
  - independent 31-record value/status and 29-subfixture issuer-algebra sweeps
  - regression verification for the twelve closed revisions and twenty audit commendations
  - standing-gate determination after bounded remediation
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

# INT-R7 delta-only bounded-remediation verification

## 1. Executive verdict

**Verdict: `CONFORMS_WITH_GAPS`.**

The bounded remediation makes real, correctly scoped changes:

- the seven stale propositions in the primary report are each preceded by an actionable supersession signal;
- the suite's §10 whole-token grammar no longer rejects its own permitted status values;
- the corrected B0/B1 baselines and all 29 subfixtures have consistent value/status pairs;
- the issuer/request/release predicate collision is correctly diagnosed and the six fixture overlays are algebraically consistent;
- the 23-family/29-subfixture denominator is unchanged;
- the amendment-ledger evidence paths now land on the changed propositions; and
- the twelve previously conforming revisions and all twenty audit commendations remain intact.

One repair-created reachability defect remains. In
`policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md`,
§15.2 at lines 777–809 presents `IssuerStatementComplete` and `IssuerIssuanceAuthentic` as the
post-audit controlling formula using the overloaded `AudienceBound`, `JurisdictionBound`, and
`ProceduralHistoryBound` names. The reader receives no advance signal that §15.10 at lines
948–1024 later supersedes that same formula. This is the exact append-only layering hazard the
primary-report remediation was designed to remove.

Consequently:

- `INT-R7-V-103` and `INT-R7-V-105` close;
- the original seven-proposition primary defect in `INT-R7-V-102` closes, but its claimed
  complete 11-artifact supersession sweep remains incomplete;
- `INT-R7-V-104` has correct mathematics and fixtures but remains `conforms_with_gap` because the
  corrected formula is not reachable before the superseded intermediate formula; and
- standing-required revisions `R1` and `R9` are not yet independently verified in a one-pass,
  unambiguous form.

The audit's standing gate—`R1`–`R15` executed **and independently verified**—is therefore **not
met**. `GO_WITH_REVISIONS` remains the substantive target, but it may not yet be retained for
consolidation under that gate. The first-public-signature gate remains closed.

## 2. Scope and method

This verification did not re-open the research, the audit, the three honest variations, the
twelve closed revisions, the twenty commendations, or the INT-R8 seam. It inspected only:

1. `INT-R7-V-102` supersession reachability;
2. `INT-R7-V-103` validator and value/status consistency;
3. `INT-R7-V-104` predicate separation and fixture algebra;
4. `INT-R7-V-105` evidence-path precision;
5. repair-created layering defects;
6. the stated deletion geometry; and
7. the remediation ledger's bounded regression statement.

Ordinary GitHub DNS/egress was unavailable. Exact-ref reads, comparisons, output-branch commits
and post-write reads used the connected GitHub interface. No workflow, upload fragment, staging
directory, binary, base64 repository payload, or self-executing automation was added.

## 3. Branch and deletion geometry

A complete comparison from amendment head
`2d922813ef542f3eebd21d2a189c017b15512803` to remediation head
`92c05323ed4c13c8f9eadb586d4e627c8d33a409` reproduced:

| Path | Status | Additions | Deletions |
| --- | --- | ---: | ---: |
| `int-r7-public-verification-lifecycle.md` | modified Markdown | 28 | 2 |
| `int-r7/amendment-ledger.md` | modified Markdown | 88 | 106 |
| `int-r7/frozen-falsifier-suite.md` | modified Markdown | 139 | 1 |
| `int-r7/remediation-ledger.md` | added Markdown | 272 | 0 |
| `int-r7/threat-model-and-verification-predicates.md` | modified Markdown | 80 | 1 |
| **total** | **4 modified + 1 added** | **607** | **110** |

The branch is 6 commits ahead, 0 behind, with merge base exactly the amendment head. All five
changed paths are Markdown.

The deletion explanation is substantially correct, with one terminology correction:

- `106` is the number of **deleted lines**, not table rows, in the amendment ledger;
- the revised ledger still contains all **22/22 revision rows** and **42/42 finding rows**;
- the primary's two deleted lines are a sentence split around the local supersession marker and
  an end-of-file replacement that retains the prior sentence;
- the suite's one deletion and the threat model's one deletion are end-of-file replacements that
  retain the prior final sentence before appending the remediation section; and
- the old primary formulas, v1 suite, defective §9 grammar/baseline, and old threat formula all
  remain visible as history.

No audited research proposition was deleted.

## 4. Per-finding closure determination

| Prior finding | Verdict | Determination |
| --- | --- | --- |
| `INT-R7-V-102` | `conforms_with_gap` | All seven named stale propositions in the primary now have specific advance signals, and all nine primary-report revision gaps are repaired. The broader 11-artifact sweep finds one new reachability gap in threat-model §15.2/§15.10. |
| `INT-R7-V-103` | `conforms` | §9 warns before the stale grammar; §10 precisely supersedes grammar, value/status pairing, baselines and the six overlays. Whole-token grammar and all 31 fixture-record pairings are consistent. |
| `INT-R7-V-104` | `conforms_with_gap` | The split predicates and six overlays are mathematically consistent, and the complete 29-subfixture sweep finds no residual contradiction. The corrected formula is nevertheless encountered only after the superseded §15.2 formula. |
| `INT-R7-V-105` | `conforms` | The tightened R12, R15, R17 and `INT-R7-II-003` anchors land on the exact propositions; all 22 revision and 42 finding rows remain present. |

## 5. `INT-R7-V-102` — primary reachability

### 5.1 Seven named propositions

| Superseded proposition | Signal encountered first | Governing target identified | Result |
| --- | --- | --- | --- |
| Executive says INT-R8 must “become available” and advertises 18 cases | primary `:60` | §§21.3, 21.5 and 21.6 | pass |
| §2.3 downstream capability labels | primary `:125` | §21.4 and repository handoff §11 | pass |
| §4.2 aggregate `HistoricalAuthenticity` and current algebra | primary `:204` | §21.2 and threat-model §15 | pass |
| §12.2 US-01 as strong current transfer | primary `:554` | §21.7 and source ledger §6 | pass |
| §15 v1/18-case suite | primary `:679` | §21.5 and suite §9 as remediated | pass |
| §16.2 downstream capability labels | primary `:733` | §21.4 and repository handoff §11 | pass |
| §19 generic recovery/18-of-18 gate and §20 “are independent” | primary `:858` and `:886` | §§21.5–21.6 and §21.2 | pass |

The frontmatter at `:14-15` names §21 as controlling, and the executive notice at `:43` states
before any affected proposition that conflicting earlier text is audited history. Each local
notice names the relevant §21 subsection rather than merely saying “see §21.”

### 5.2 Nine affected revisions

| Revision | Primary reachability after remediation | Delta verdict |
| --- | --- | --- |
| `R1` | aggregate marker precedes §4.2 and points to §21.2 | primary pass; threat-model gap remains |
| `R3` | dependency marker precedes stale INT-R8 availability statement | pass |
| `R4` | aggregate/dependency markers identify admitted-interface condition | pass |
| `R5` | both old capability-label locations have §21.4 markers | pass |
| `R6` | v1 suite and 18-case gate have §21.5 markers | pass |
| `R8` | §4.2 marker points to the split issuer/public-history model | pass |
| `R10` | generic drill marker points to §21.6 | pass |
| `R12` | US-01 marker points to §21.7 | pass |
| `R16` | independence marker points to §21.2 | pass |

Thus **9/9 primary-report reachability repairs are present**, but `R1` is not fully closed because
the referenced threat-model formula has a later intermediate supersession.

### 5.3 Complete 11-artifact sweep

The complete denominator is the eleven amendment artifacts, excluding the later remediation
ledger:

| Artifact | One-pass supersession result |
| --- | --- |
| primary report | pass — frontmatter, executive and point-of-use signals |
| orientation ledger | pass — §7 explicitly controls O-18/R14/R20 and no earlier row states the false interval |
| threat model | **gap** — §15.2 is presented as controlling before §15.10 replaces its predicate names |
| comparative models | pass — §14 names the findings and controls the comparative conclusion |
| public-verification profile | pass — §18 names the exact earlier sections and collapse condition |
| lifecycle/preservation | pass — §11 names the exact sections and affected historical-verification wording |
| citizen UX | pass — §13 names the two-question, aggregate and capability text it supersedes |
| falsifier suite | pass — §9's pre-§9.1 notice directs grammar/baseline/overlay conflicts to §10 |
| repository/dependencies | pass — §11 explicitly supersedes missing-state labels in §§2, 4 and 6 |
| external-source ledger | pass — §6 explicitly controls source use for the named findings/revisions |
| amendment ledger | not applicable — accountability artifact, not an earlier governing research proposition |

Functional result: **9 unambiguous carriers / 9 applicable passes, 1 applicable gap, 1 not
applicable; 11/11 inspected**.

The remediation's `2 repaired / 8 already conforming / 1 not applicable` classification is
reasonable as a V-102 semantic classification, but it is not a literal raw-file-change
classification: the threat model was modified for V-104 and the amendment ledger was modified for
evidence precision.

## 6. `INT-R7-V-103` — scoped suite supersession

The stale §9.2 substring rule and stale B0 pair remain visible, but the remediation notice appears
before §9.1 and says §10 controls the typed grammar, B0/B1 pairs and six named overlays. Section
10 then says it supersedes §§9.1–9.4 only for:

1. typed value grammar;
2. value/status pairing;
3. B0/B1 baselines; and
4. the six named overlays.

That scope covers every proposition that needed correction. No stale §9 proposition outside those
four categories is required to close `INT-R7-V-103` or `INT-R7-V-104`:

- family IDs and denominators remain controlled by §9.4/§9.5;
- top-level outcomes and reason codes remain unchanged;
- S0-K16 passage scope remains controlled by §§9.7 and 10.6; and
- the anti-wire warning remains controlled by §9.8.

### 6.1 Pair sweep

The complete fixture-record denominator is **31/31**:

```text
B0 B1
F-01a F-02a F-03a F-04a F-05a F-06a F-07a F-08a F-09a
F-10a F-10b F-11a F-11b F-12a F-12b F-12c F-13a F-14a
F-15a F-16a F-17a F-18a F-18b AX-01a AX-02a AX-03a AX-04a
AX-05a AX-05b
```

After applying §10:

- B0 has one valid unevaluated pair: `BasisBound=null/not_applicable`;
- B1 overrides that slot with `true/evaluated`;
- F-02a has the one valid short-circuit pair: `SignatureValid=null/short_circuited`;
- every other explicit pair in all 28 remaining subfixtures is non-null/evaluated; and
- every §10.4 overlay pair is non-null/evaluated.

The amendment's B0 `BasisBound=true/not_applicable` was the only inconsistent pair. The
whole-token grammar does not reject `short_circuited` merely because it contains the letters
`or`.

`INT-R7-V-103`: **closed**.

## 7. `INT-R7-V-104` — formula and complete fixture sweep

### 7.1 Algebra

Section 15.10 correctly separates:

- `IssuerAudienceDeclaredAndBound` from `RequestedAudienceUsePermitted`;
- `IssuerJurisdictionDeclaredAndBound` from `RequestedJurisdictionUsePermitted`; and
- `IssuerProceduralHistoryBound` from `ReleasedProceduralHistoryComplete`.

The remediated `IssuerStatementComplete` uses only issuer-side predicates. Requested-use
mismatch is evaluated by `RequestedUseAuthorized`; released procedural-history completeness is
added to procedural projection faithfulness. The mathematical separation is correct.

### 7.2 Six corrected overlays

| Subfixture | Expanded issuer-side interpretation | Result |
| --- | --- | --- |
| F-09a | issuer audience declaration true; requested audience use false | consistent |
| F-10a | issuer jurisdiction declaration true; requested jurisdiction use false | consistent |
| F-12a | issuer procedural history false; issuance contradicted | consistent |
| F-12b | issuer procedural history false; issuance contradicted | consistent |
| F-12c | issuer procedural history false; issuance contradicted | consistent |
| AX-05a | issuer procedural history true; released history false; projection contradicted | consistent |

### 7.3 Complete 29-subfixture sweep

The manifest contains **29/29 subfixtures**. Expanding the issuer formula gives:

| Fixture class | Members | Consistency result |
| --- | --- | --- |
| necessary issuer predicate false and issuer non-positive | F-02a, F-04a, F-06a, F-10b, F-11a, F-11b, F-12a, F-12b, F-12c, AX-01a, AX-04a | pass |
| requested-use/release/presentation/currentness/durability failure with issuer preserved | F-07a, F-08a, F-09a, F-10a, F-15a, F-17a, F-18a, AX-02a, AX-03a, AX-05a, AX-05b | pass |
| all issuer-side requirements positive | F-05a, F-14a, F-16a, F-18b | pass |
| legacy/non-baseline authority not established | F-01a, F-03a | pass |
| signature-policy/quorum failure with issuer contradicted | F-13a | pass |

No fixture reports `IssuerIssuanceAuthentic=established` while setting a necessary issuer-side
predicate false after baseline expansion and §10.4 overlays. The denominator remains 23 families
and 29 subfixtures; nothing is added, removed, renumbered or weakened.

### 7.4 Reachability gap

The corrected algebra is not one-pass reachable. Section 15.2 at lines 777–809 is headed as part
of the “Post-audit controlling decomposition” and uses the old overloaded names. Neither the
frontmatter nor the start of §15 warns that §15.10 will replace that formula. A reader can
therefore stop at the intermediate formula, exactly as a reader could previously stop at the
primary's stale §4.2 formula.

`INT-R7-V-104`: **mathematics and fixtures conform; reachability conforms with gap**.

## 8. `INT-R7-V-105` — evidence-path precision

Spot checks land on the affected propositions:

| Ledger row | Tightened evidence | Result |
| --- | --- | --- |
| R12 | source `:163,166,210-217`; lifecycle `:653-657`; primary `:554-556,1010-1021` | exact |
| R15 | threat `:874-884`; profile `:675-685`; UX `:734-745`; lifecycle `:659-669` | exact |
| R17 | source `:161-167`; comparative `:410-416` | exact |
| `INT-R7-II-003` | source `:163`; lifecycle `:653-657`; primary `:554-556` | exact |

The amended ledger still contains **22/22 revision rows** and **42/42 finding rows**. No finding,
revision disposition, severity, or count reconciliation was lost when 106 old lines were replaced
by 88 new lines.

`INT-R7-V-105`: **closed**.

## 9. Repair-created new-defect check

### `INT-R7-RV-001` — blocking — threat-model remediation repeats the supersession-reachability defect

**Evidence:**
`policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md:761-809,948-1024`
@ `92c05323ed4c13c8f9eadb586d4e627c8d33a409`.

Section 15.2 is encountered first and presents the old names as the controlling issuer formula.
Section 15.10 later says those meanings are superseded. Unlike the suite, the threat model has no
advance remediation notice; unlike the primary, it has no point-of-use marker before the stale
formula. The reader must resolve two successive supersessions and can stop at the intermediate
one.

This finding does not dispute the corrected formula. It requires only the same bounded closure
already used successfully elsewhere: signal before §15.2 that the issuer formula is controlled by
§15.10, without deleting the retained history.

No other repair-created layering defect was found:

- primary: frontmatter, executive and local notices precede stale text;
- suite: §9 notice precedes §§9.1–9.4 and names the exact §10 categories;
- unchanged supporting artifacts retain one explicit post-audit control clause; and
- the amendment/remediation ledgers are accountability records rather than semantic formula
  owners.

## 10. Regression verification

### 10.1 Twelve closed revisions

The remediation ledger lists **12 revisions / 12 total**:

```text
R2 R7 R11 R13 R14 R15 R17 R18 R19 R20 R21 R22
```

All 12 cited evidence paths resolve at the remediation head and retain the prior proposition.
Touched-file dependencies were checked directly:

- threat model: R2, R7 and R15 remain intact;
- suite: R7, R18, R19 and R21 remain intact;
- primary: R18's anti-wire warning remains intact.

Unchanged-file paths were spot-checked for R11, R13, R14, R17, R20 and R22. Result:
**12 intact / 12 total; 0 weakened; 0 lost**.

### 10.2 Twenty commendations

The remediation ledger lists **20 commendations / 20 total**:

```text
INT-R7-I-001 INT-R7-I-002 INT-R7-I-003 INT-R7-I-004 INT-R7-II-001
INT-R7-III-001 INT-R7-IV-001 INT-R7-IV-002 INT-R7-V-004
INT-R7-VI-001 INT-R7-VI-004 INT-R7-VII-001 INT-R7-VII-002
INT-R7-VII-003 INT-R7-VII-004 INT-R7-VII-005 INT-R7-VIII-001
INT-R7-IX-001 INT-R7-IX-003 INT-R7-X-002
```

Every cited path resolves and the named strength remains. In particular:

- the real `runtime/quality/public_export.py` producer remains recognized;
- only the real producer-to-public-route connection remains `bridge_missing`;
- the signing-time/revocation defect remains explicit;
- F-05, F-17 and F-18 remain present;
- the first-signature authority/candidate distinction remains intact;
- S0-K16 still bounds passage;
- no second authority/projection owner is created;
- all touched artifacts retain `research_only: true`, non-empty `may_not_use_for`, the original
  audit binding where applicable and the remediation-verification binding; and
- the first-public-signature gate remains closed.

Result: **20 intact or strengthened / 20 total; 0 weakened; 0 lost**.

INT-R8 is untouched: the complete five-path remediation diff contains no INT-R8 path.

## 11. Finding register and count reconciliation

This verification records **1 new finding / 1 total**:

| Finding ID | Severity | Determination |
| --- | --- | --- |
| `INT-R7-RV-001` | blocking | Threat-model §15.2 remains reachable as controlling text before §15.10 supersedes its predicate names, leaving V-102's 11-artifact claim and V-104 reachability incomplete. |

Per-prior-finding result:

| Result | Count |
| --- | ---: |
| `conforms` | 2 |
| `conforms_with_gap` | 2 |
| `not_executed` | 0 |
| **total prior findings checked** | **4** |

Regression result:

| Protected set | Intact | Weakened/lost | Total |
| --- | ---: | ---: | ---: |
| previously conforming revisions | 12 | 0 | 12 |
| audit commendations | 20 | 0 | 20 |

## 12. Standing gate

The audit required `R1`–`R15` to be executed and independently verified. The remediation fixes
are real, but the gate is **not met** because `R1` and `R9` still depend on a corrected threat
formula that is not reachable before the superseded §15.2 formula.

Therefore:

- conformance verdict: **`CONFORMS_WITH_GAPS`**;
- `GO_WITH_REVISIONS` remains the correct substantive target but is **not yet independently
  retained for consolidation**;
- no implementation or publication authority follows; and
- the first-public-signature gate remains closed.
