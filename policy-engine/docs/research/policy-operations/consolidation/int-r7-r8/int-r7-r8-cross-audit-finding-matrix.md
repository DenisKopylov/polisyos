---
title: "INT-R7 / INT-R8 — Cross-audit finding matrix"
status: delivered
kind: research-cross-audit-matrix
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r7-r8-consolidation
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
int_r7_controlling_head: 3883b45476aed138beface8c8ca817191c7e273e
int_r8_controlling_head: 286ade1057c9abb95bb1cf2c962479906f764667
inspection_date: 2026-08-05
research_only: true
authoritative_for:
  - stage-qualified reconciliation of every finding in the pinned INT-R7 and INT-R8 correction chains
  - severity and disposition count reconciliation across six independent registers
  - determination of which findings survive as ratification candidates research evidence repository defects deferred dependencies or rejected propositions
may_not_use_for:
  - treating a disposition as architect ratification or implementation authorization
  - reopening an independently closed finding without new evidence
  - extending a finding beyond its pinned artifact and finding ID
  - final wire schema package database serialization enum status lattice or API contract
  - owner vendor operator custodian witness log archive timestamp service or certificate-authority appointment
  - permission to publish or open either first-public gate
  - numerical disclosure privacy leakage confidence or safety bound
  - automatic amendment of any plan backlog system-design decision failure-pattern register or AGENTS.md
execution_environment: connected_exact_ref_only_due_to_unavailable_ordinary_github_dns
---

# INT-R7 / INT-R8 cross-audit finding matrix

## 1. Method and namespace rule

The denominator is every row in six independent finding registers:

1. INT-R7 independent audit at `54e8f41d790cb257a616c5bb5f96d996fbe3e9db`;
2. INT-R7 amendment verification at `5225f8bf6cc995f0d3a9cb622454c1af9432745d`;
3. INT-R7 remediation verification at `f705c4a7c92511c63541addffd6af2eb870a12bd`;
4. INT-R8 independent audit at `f45f338f9d9b0de94edc16efbc334789e70e34e2`;
5. INT-R8 amendment verification at `ead4aca36f94d6014879c9f70b1074800c4ffabf`;
6. INT-R8 remediation verification at `8a0847ffd4de6664727d025aee5b1bcbfbfcdbc6`.

The INT-R8 audit uses `INT-R8-V-001` through `INT-R8-V-005` for its section-V findings, and the later amendment verification independently reuses those same five IDs inside a new `INT-R8-V-001` through `INT-R8-V-012` register. Therefore the qualified key is **stage/head + finding ID**. An unqualified INT-R8 `V-001`–`V-005` citation is ambiguous and must not be used.

Disposition vocabulary is exactly:

- `ratify_now` — the finding supports an authority-band candidate in `int-r7-r8-ratification-candidates.md`;
- `retain_as_research` — preserve as method, evidence, limitation or commendation without ratification;
- `revise` — the finding was a valid defect closed by the later controlling correction chain;
- `defer` — the proposition belongs to an already-declared undelivered dependency;
- `repository_fix_separate` — a live repository defect/gap, not a research-result defect;
- `additional_research` — a new research task is required now;
- `reject` — the proposition named by the finding is refuted and must not be carried.

No row requires `additional_research`: remaining live work is engineering, institutional, architect decision, or already owned by OPS-R14/GY-N12/GY-PA3/S0-GAP-02.

## 2. Count reconciliation

### 2.1 Per-register reconciliation

| Register | Blocking | Material | Minor | Commendation | Total | Disposition reconciliation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| INT-R7 audit | 1 | 15 | 6 | 20 | **42** | 12 retain + 2 repository fix + 1 reject + 19 revise + 7 ratify + 1 defer = **42** |
| INT-R7 amendment verification | 1 | 2 | 1 | 4 | **8** | 4 retain + 4 revise = **8** |
| INT-R7 remediation verification | 1 | 0 | 0 | 0 | **1** | 1 revise = **1** |
| INT-R8 audit | 1 | 11 | 4 | 19 | **35** | 15 retain + 15 revise + 1 reject + 4 ratify = **35** |
| INT-R8 amendment verification | 0 | 4 | 0 | 8 | **12** | 7 retain + 4 revise + 1 ratify = **12** |
| INT-R8 remediation verification | 0 | 0 | 0 | 8 | **8** | 8 retain = **8** |
| **All registers** | **4** | **32** | **11** | **59** | **106** | **46 retain + 43 revise + 12 ratify + 2 repository fix + 2 reject + 1 defer = 106** |

### 2.2 Arithmetic checks

- Severity arithmetic: `4 + 32 + 11 + 59 = 106`.
- Register arithmetic: `42 + 8 + 1 + 35 + 12 + 8 = 106`.
- Disposition arithmetic: `46 + 43 + 12 + 2 + 2 + 1 + 0 = 106`.
- INT-R7 chain: `42 + 8 + 1 = 51`.
- INT-R8 chain: `35 + 12 + 8 = 55`.
- Wave: `51 + 55 = 106`.

The prose, tables and row registers below use the same denominators.

## 3. INT-R7 independent audit — 42/42

Qualified stage: `R7-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R7-I-001` | commendation | branch geometry and complete audit scope are reproducible | `retain_as_research` | Preserved as correction-chain method evidence. |
| `INT-R7-I-002` | commendation | `signed_at`/`signer_identity` are outside the signed statement and revocation is timeless | `repository_fix_separate` | Live repository defect; routed to the repository findings register with a closure signal. |
| `INT-R7-I-003` | commendation | orientation correction preserves the real public-export producer and narrows the missing bridge | `repository_fix_separate` | Producer is present; unsigned proof/evaluator/route connection remains a separate repository gap. |
| `INT-R7-I-004` | commendation | unavailable exact lexical counts were honestly left `not_established` | `retain_as_research` | Preserved as P35/P36-compatible method discipline. |
| `INT-R7-I-005` | material | false relative-date statement about the baseline | `reject` | Date proposition is not carried; exact commits/dates control. |
| `INT-R7-I-006` | minor | claimed 14/14 import census lacked a retained rerun at the audited stage | `revise` | Later orientation/remediation preserves complete roots, inclusion rule and exact-ref rerun method. |
| `INT-R7-II-001` | commendation | source corpus breadth and primary-source orientation are strong | `retain_as_research` | Preserved with transfer limitations and currentness checks. |
| `INT-R7-II-002` | minor | ETSI-05 date was wrong | `revise` | Corrected to 2024-01 in the controlling source ledger. |
| `INT-R7-II-003` | material | NARA transfer was presented as current despite supersession | `revise` | US-01 is historical-only; later current source is jurisdiction-bounded. |
| `INT-R7-II-004` | material | Federal PKI proposition was overbroad | `revise` | Narrowed to the evidenced submission/delegation-control pattern. |
| `INT-R7-II-005` | minor | RFC 9162 does not itself establish an independent witness quorum | `revise` | Quorum transfer is explicitly an INT-R7 inference, not an RFC claim. |
| `INT-R7-II-006` | minor | Sigstore bundle citation lacked the exact format anchor | `revise` | Exact bundle-format source anchor added. |
| `INT-R7-III-001` | commendation | public verification should be a vector rather than a signature bit | `ratify_now` | Supports RC-01 and RC-02. |
| `INT-R7-III-002` | material | `HistoricalAuthenticity` overloaded issuer, projection, history and durability | `revise` | Controlling five-way decomposition and §15.10 split remove the aggregate. |
| `INT-R7-III-003` | minor | “independent predicates” overstated logical independence | `revise` | Replaced by “separately reportable” with explicit dependency relations. |
| `INT-R7-III-004` | material | currentness snapshot selection lacked anti-rollback semantics | `revise` | Authenticity and latest-applicable selection are separated with exact non-current outcomes. |
| `INT-R7-IV-001` | commendation | ten-element composite profile is coherent and construction-neutral | `retain_as_research` | Preserved as the research composition; candidate mechanisms remain open. |
| `INT-R7-IV-002` | commendation | GY-N12 owns currentness and INT-R8 owns content/projection | `ratify_now` | Supports RC-03 and prevents a second lattice/owner. |
| `INT-R7-IV-003` | material | the then-absent INT-R8 contract was treated too close to an available dependency | `revise` | Final R8 contract now exists; seam is adjudicated item by item in preflight. |
| `INT-R7-IV-004` | material | GY-N12 is planned/undelivered | `defer` | Correctly left with GY-N12; no local currentness capability is claimed. |
| `INT-R7-V-001` | material | suite's exact-equality rule conflicted with typed status values | `revise` | Whole-token grammar and value/status pairing corrected; 31/31 sweep passes. |
| `INT-R7-V-002` | material | F-04 erased valid signature mathematics for post-revocation issuance | `revise` | Exact terminal preserves signature validity and reports temporal unauthorized issuance. |
| `INT-R7-V-003` | material | F-08 collapsed split-view/public-history failure into issuer failure | `revise` | Issuer issuance remains established while public history/common view is non-positive. |
| `INT-R7-V-004` | commendation | withdrawn/superseded records remain historically verifiable | `ratify_now` | Supports RC-02. |
| `INT-R7-V-005` | material | required adversarial cases were missing | `revise` | AX families and later v2 suite cover the omitted attacks with exact terminals. |
| `INT-R7-VI-001` | commendation | first-signature gate respects authority/candidate bands | `ratify_now` | Supports RC-01/RC-03; gate remains closed. |
| `INT-R7-VI-002` | material | “disconnected recovery drill” was ambiguous and potentially ceremonial | `revise` | Controlling lifecycle requires real-path non-authoritative and bounded first-live phases. |
| `INT-R7-VI-003` | material | anti-rollback and restored-state behavior were absent | `revise` | Authentic snapshot rollback and compromised-primary outcomes are explicit. |
| `INT-R7-VI-004` | commendation | preservation cannot become original issuer authority | `ratify_now` | Supports RC-03 and RC-02. |
| `INT-R7-VII-001` | commendation | `INT-K06` requires prospectivity and chronology rather than a probability | `retain_as_research` | Preserved as the procedural-claim basis for the profile and prefix result. |
| `INT-R7-VII-002` | commendation | `INT-K02` basis completeness must be signed atomically with `delta` | `retain_as_research` | Preserved and consumed by RC-05. |
| `INT-R7-VII-003` | commendation | withdrawn-but-verifiable is a legitimate completed result | `ratify_now` | Supports RC-02. |
| `INT-R7-VII-004` | commendation | passage claims remain bounded under `S0-K16` | `retain_as_research` | Preserved as a limitation on suite and recovery evidence. |
| `INT-R7-VII-005` | commendation | no second confidence/currentness ledger should be created | `retain_as_research` | Preserved in routing and rejection tables. |
| `INT-R7-VIII-001` | commendation | proof binds semantic content but remains on the proof side | `ratify_now` | Supports RC-03. |
| `INT-R7-VIII-002` | material | no delivered R8 interface existed at the audited stage | `revise` | Superseded by the controlling R8 contract and bidirectional seam adjudication. |
| `INT-R7-VIII-003` | material | projection failure could retroactively erase authentic issuance | `revise` | Issuance, projection, history, durability and current authority are separately reportable. |
| `INT-R7-IX-001` | commendation | research-only frontmatter and prohibitions are effective | `retain_as_research` | Preserved across the wave and this consolidation. |
| `INT-R7-IX-002` | minor | code-shaped lists risked being mistaken for schema | `retain_as_research` | Anti-wire warnings now explicit; stylistic hazard retained as research discipline. |
| `INT-R7-IX-003` | commendation | `GO_WITH_REVISIONS` is the honest substantive standing | `retain_as_research` | Retained, now with the closure gate independently met. |
| `INT-R7-X-001` | blocking | capability labels erased existing producers and inflated absent chains | `revise` | Controlling map preserves real producers and uses `bridge_missing` only where both sides exist. |
| `INT-R7-X-002` | commendation | existing public export must not be erased or duplicated | `retain_as_research` | Regression preserved; routed as an integration constraint. |

**Register reconciliation:** 42 rows = 1 blocking + 15 material + 6 minor + 20 commendation. Dispositions = 19 revise + 12 retain + 7 ratify + 2 repository fix + 1 reject + 1 defer.

## 4. INT-R7 amendment verification — 8/8

Qualified stage: `R7-amend-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R7-V-101` | commendation | geometry, 11/11 frontmatter and complete denominators reproduce | `retain_as_research` | Preserved as conformance-method evidence. |
| `INT-R7-V-102` | blocking | primary-report supersession was not reachable before stale propositions | `revise` | Seven point-of-use repairs and 9/9 primary revision closure landed; later threat-model nested reachability was separately closed. |
| `INT-R7-V-103` | material | suite grammar rejected permitted values and B0 paired value/status inconsistently | `revise` | §10 whole-token grammar and 31/31 value/status sweep close it. |
| `INT-R7-V-104` | material | suite vectors contradicted overloaded issuer-completeness algebra | `revise` | Predicate split and 29/29 algebra sweep close the mathematics; nested reachability later closed. |
| `INT-R7-V-105` | minor | ledger evidence sometimes cited section entries rather than exact propositions | `revise` | R12/R15/R17 and finding anchors were tightened without losing rows. |
| `INT-R7-V-106` | commendation | the three amendment variations were honestly labelled | `retain_as_research` | Preserved as correction-chain honesty evidence. |
| `INT-R7-V-107` | commendation | all 20 original audit commendations survived | `retain_as_research` | Preserved and rechecked after remediation. |
| `INT-R7-V-108` | commendation | suite/source/revision/finding arithmetic reconciles | `retain_as_research` | Preserved; later 23/29, 31/31 and 29/29 counts remain consistent. |

**Register reconciliation:** 8 rows = 1 blocking + 2 material + 1 minor + 4 commendation. Dispositions = 4 revise + 4 retain.

## 5. INT-R7 remediation verification — 1/1

Qualified stage: `R7-remediation-verification@f705c4a7c92511c63541addffd6af2eb870a12bd`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R7-RV-001` | blocking | threat-model §15.2 presented overloaded controlling algebra before §15.10 silently replaced it | `revise` | Closure adds artifact-level, section-opening and point-of-use signals; this consolidation independently confirms all three and reproduces 47/47 displacement pairs. |

**Register reconciliation:** 1 row = 1 blocking. Dispositions = 1 revise.

## 6. INT-R8 independent audit — 35/35

Qualified stage: `R8-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R8-I-001` | commendation | branch geometry, audience and source orientation are exact | `retain_as_research` | Preserved through rewrite and remediation. |
| `INT-R8-I-002` | material | `omitted_claim` count confused matched lines with literal occurrences | `revise` | Controlling census states 8 matched lines / 9 literal occurrences. |
| `INT-R8-I-003` | commendation | 106 denied-use files partition cleanly as 67/12/27 | `retain_as_research` | Preserved with stated distinct-file denominator. |
| `INT-R8-I-004` | minor | public-export caller count mixed definition, callers and re-export | `revise` | Five invocation-containing files, four callers outside definition; `__init__` is re-export only. |
| `INT-R8-I-005` | commendation | no disclosure/composition/privacy/compression budget owner exists | `retain_as_research` | Supports the current numerical refusal without manufacturing a missing capability. |
| `INT-R8-II-001` | commendation | public-administration source transfer is broadly sound and bounded | `retain_as_research` | Preserved with jurisdiction and currentness limitations. |
| `INT-R8-II-002` | minor | ONS source was historical/unpinned | `revise` | Reclassified as historical with living-as-of current use. |
| `INT-R8-II-003` | minor | NSW proposition lacked a stable pin and was too broad | `revise` | Narrowed to retrievable official evidence and explicit limits. |
| `INT-R8-II-004` | commendation | differential privacy was not imported by analogy | `retain_as_research` | Preserved and sharpened into a model-premise analysis. |
| `INT-R8-III-001` | commendation | refusing a current canonical number is justified | `retain_as_research` | Preserved as premise-relative refusal and offered in RC-08. |
| `INT-R8-III-002` | material | determinism was wrongly treated as a universal bar to quantitative analysis | `reject` | Refuted; deterministic-channel QIF families remain legitimate future model families. |
| `INT-R8-III-003` | commendation | exact Boolean non-uniqueness test uses no implicit budget | `ratify_now` | Supports RC-06. |
| `INT-R8-III-004` | material | approximate reconstruction branch lacked an owned safety direction | `revise` | Only exact or proved no-false-safe abstraction can support a pass; others block. |
| `INT-R8-III-005` | commendation | actual-prefix induction handles adaptive next-release choice | `retain_as_research` | Preserved as the mathematical core of prefix discipline. |
| `INT-R8-III-006` | material | release transcript universe was not scoped | `revise` | Controlled, observed-external and unknown/uncontrolled channel classes are separated. |
| `INT-R8-IV-001` | commendation | `C(T)` and strict-coalition reconstruction are valid under declared premises | `ratify_now` | Supports RC-06. |
| `INT-R8-IV-002` | material | general decidability/tractability was not established | `revise` | Executable claim is bounded to finite/enumerable, declared-decidable or proved-conservative models. |
| `INT-R8-IV-003` | material | threat model omitted proof metadata, delivery, print/screenshot and auxiliary channels | `revise` | Open channel registry and five new families added; proof-metadata attack retained. |
| `INT-R8-IV-004` | commendation | threat analysis already exceeded body-text-only review | `retain_as_research` | Preserved and expanded. |
| `INT-R8-V-001` | commendation | bare `delta` and hidden negative terminals are categorical blockers | `retain_as_research` | Preserved and offered through RC-05. |
| `INT-R8-V-002` | material | materiality and condensation were free-text rather than operational | `revise` | Versioned effect, basis, affected-claim and condensation relations now fail closed. |
| `INT-R8-V-003` | material | transformation/redaction reason semantics were not reconciled | `revise` | One canonical reason relation now maps transformation to class, claims, effects and safe explanation. |
| `INT-R8-V-004` | minor | one universal limitations field was claimed but not present | `revise` | Contract consumes concrete limitation carriers without claiming a universal top-level field. |
| `INT-R8-V-005` | commendation | receipt should extend existing owners and create no status lattice | `ratify_now` | Supports RC-03/RC-04 and repository reuse constraints. |
| `INT-R8-VI-001` | material | suite equality/atomicity was insufficiently executable | `revise` | Controlling v2 has typed exact rows; remediation reaches 71/71 red atomic rows. |
| `INT-R8-VI-002` | commendation | strongest red cases and five green purposes are discriminating | `retain_as_research` | Preserved; green controls expanded to seven. |
| `INT-R8-VI-003` | material | attack families and exact cases were missing | `revise` | F26-F30 and bounded-remediation fixtures added. |
| `INT-R8-VII-001` | commendation | directions from K02/K06/K08/S0-K07/K05 are correct | `retain_as_research` | Preserved as binding-architecture alignment. |
| `INT-R8-VII-002` | commendation | exact adaptive discipline respects K04/K07 without claiming a number | `retain_as_research` | Preserved as prefix discipline. |
| `INT-R8-VIII-001` | commendation | content/proof authority boundary is correct | `ratify_now` | Supports RC-03 and RC-09. |
| `INT-R8-VIII-002` | material | required INT-R7 proof-binding interface was omitted | `revise` | Eighteen-item construction-neutral interface now explicit and seam-adjudicated. |
| `INT-R8-IX-001` | blocking | capability labels erased existing producers and mislabeled absent chains | `revise` | Producer preserved; route is `bridge_missing`; undeclared chains are absent/unallocated. |
| `INT-R8-IX-002` | commendation | existing projection/export producers must remain visible | `retain_as_research` | Preserved through rewrite and routing. |
| `INT-R8-X-001` | commendation | research-only prohibitions are effective | `retain_as_research` | Preserved across all controlling artifacts. |
| `INT-R8-X-002` | commendation | `accepted_narrow_scope` is the correct target | `retain_as_research` | Final independent verification permits it to be carried. |

**Register reconciliation:** 35 rows = 1 blocking + 11 material + 4 minor + 19 commendation. Dispositions = 15 revise + 15 retain + 4 ratify + 1 reject.

## 7. INT-R8 amendment verification — 12/12

Qualified stage: `R8-amend-verification@ead4aca36f94d6014879c9f70b1074800c4ffabf`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R8-V-001` | commendation | geometry, bindings, Markdown-only scope and immutable refs reproduce | `retain_as_research` | Preserved as verification-method evidence. |
| `INT-R8-V-002` | commendation | complete deletion audit found no lost commended/required substance | `retain_as_research` | Preserved as rewrite-in-place integrity evidence. |
| `INT-R8-V-003` | material | R4 lacked atomic empty-consistency and unsafe-heuristic fixtures | `revise` | F21-D/E added; 0/78 unsafe-pass sweep. |
| `INT-R8-V-004` | material | R5 lacked an unknown-external-history limiting fixture | `revise` | G05-B added with bounded-family limitation and non-universal claim. |
| `INT-R8-V-005` | material | R7 lacked a positive two-event faithful-condensation fixture | `revise` | G04-B added with both event references, effects and order edges. |
| `INT-R8-V-006` | material | F09-A bundled three mutations; only 66/67 red rows atomic | `revise` | F09 split; 71/71 red rows atomic. |
| `INT-R8-V-007` | commendation | capability-map rewrite closes the original blocking defect | `retain_as_research` | Preserved in repository/capability conclusions. |
| `INT-R8-V-008` | commendation | narrowed theorem and deterministic-QIF path landed | `retain_as_research` | Preserved in numerical refusal and rejected-proposition record. |
| `INT-R8-V-009` | commendation | all 19 original audit commendations survive | `retain_as_research` | Confirmed again after remediation. |
| `INT-R8-V-010` | commendation | open channels and F26-F30 are real, with no self-rejecting vocabulary | `retain_as_research` | Preserved in RC-06/RC-09 limitations. |
| `INT-R8-V-011` | commendation | census and call-site corrections reproduce | `retain_as_research` | Preserved with matched-line/occurrence/caller denominators. |
| `INT-R8-V-012` | commendation | R10 proof interface is complete and construction-neutral | `ratify_now` | Supports RC-03 and seam-hold determination. |

**Register reconciliation:** 12 rows = 4 material + 8 commendation. Dispositions = 4 revise + 7 retain + 1 ratify.

## 8. INT-R8 remediation verification — 8/8

Qualified stage: `R8-remediation-verification@8a0847ffd4de6664727d025aee5b1bcbfbfcdbc6`.

| Finding ID | Severity | Finding carried by ID | Disposition | Consolidated resolution |
| --- | --- | --- | --- | --- |
| `INT-R8-RV-001` | commendation | geometry, Markdown-only scope, merge base and remediation bindings reproduce | `retain_as_research` | Preserved as final-verification method evidence. |
| `INT-R8-RV-002` | commendation | R4 closed; F21-D/E exact and no unsafe approximation inherits safety | `retain_as_research` | Supports RC-06; no residual gap. |
| `INT-R8-RV-003` | commendation | R5 closed; G05-B is limiting, non-complete and non-blocking | `retain_as_research` | Preserves bounded declared-family semantics. |
| `INT-R8-RV-004` | commendation | R7 closed; G04-B is a discriminating faithful-condensation witness | `retain_as_research` | Demonstrates the contract is not reject-all. |
| `INT-R8-RV-005` | commendation | R9 closed; F09 split and all red rows atomic | `retain_as_research` | Preserves executable suite discipline. |
| `INT-R8-RV-006` | commendation | 30/71/5/7/78 denominators reconcile and 67/12/27 census is untouched | `retain_as_research` | Final controlling count set. |
| `INT-R8-RV-007` | commendation | all 34 deletions are replacements; no superseding-section defect introduced | `retain_as_research` | Confirms rewrite-in-place discipline. |
| `INT-R8-RV-008` | commendation | regression resolves 9/9 conforming revisions and 19/19 commendations | `retain_as_research` | Final gate evidence; `accepted_narrow_scope` carried. |

**Register reconciliation:** 8 rows = 8 commendations. Dispositions = 8 retain.

## 9. Cross-chain adjudication

### 9.1 Findings proposed for authority-band ratification — 12/106

The twelve `ratify_now` rows do not each create a separate ruling. They support the nine consolidated candidates in `int-r7-r8-ratification-candidates.md`:

- verification vector and historical/current separation;
- proof/content non-laundering seam;
- use-relative conservative parity and categorical anchors;
- exact/proved-conservative reconstruction;
- prefix discipline and numerical refusal; and
- proof metadata as channel.

### 9.2 Repository fixes kept separate — 2/106

Only `INT-R7-I-002` and `INT-R7-I-003` are assigned `repository_fix_separate`. They concern live code/surface defects, not defects in the final research result. The detailed register does not authorize a fix.

### 9.3 Rejected propositions — 2/106

- `INT-R7-I-005`: the false relative-date proposition is discarded in favor of exact pins.
- `INT-R8-III-002`: determinism as a universal impossibility argument is refuted.

### 9.4 Deferred dependency — 1/106

`INT-R7-IV-004` remains with GY-N12. The wave neither absorbs nor solves epoch/currentness implementation.

### 9.5 No active additional-research row

The proof-metadata attack is real but already has an authority-band requirement and a candidate-specific falsifier. Additional research becomes active only if a concrete admitted construction cannot satisfy it without choosing content or leaking protected values. No such candidate exists in the pinned wave.

## 10. Matrix boundary

A matrix disposition records what consolidation should do with a finding. It does not ratify, implement, appoint, publish, or amend any destination. Finding IDs remain authoritative only at their pinned stage-qualified sources.
