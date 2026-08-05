---
title: INT-R7 — Reachability Invariant Closure Ledger
research_id: INT-R7
status: reachability_closed_pending_independent_verification
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
remediation_commit: 92c05323ed4c13c8f9eadb586d4e627c8d33a409
remediation_verification_commit: f705c4a7c92511c63541addffd6af2eb870a12bd
prior_verification_commit: 5225f8bf6cc995f0d3a9cb622454c1af9432745d
audit_commit: 54e8f41d790cb257a616c5bb5f96d996fbe3e9db
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
closure_branch: research/int-r7-reachability-closure
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
remediated_after_verification: research/int-r7-amendment-verification@5225f8bf6cc995f0d3a9cb622454c1af9432745d
reachability_closed_after: research/int-r7-remediation-verification@f705c4a7c92511c63541addffd6af2eb870a12bd
authoritative_for:
  - authoring-level closure evidence for INT-R7-RV-001
  - the supersession reachability invariant for the INT-R7 artifact set
  - the complete ordered-pair register across the eleven amendment artifacts
  - the exact change that makes threat-model section 15.2 subordinate to section 15.10 in one pass
  - regression evidence for findings and revisions closed before this pass
  - updated standing pending independent bounded conformance verification
may_not_use_for:
  - re-audit or substantive re-adjudication of INT-R7 or INT-R8
  - new research, attack families, sources, fixtures, algorithms, owners, or implementation design
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, key custodian, trust service, log, witness, archive, institution, team, person, or vendor appointment
  - authority grant or capability claim
  - benchmark, recovery-drill, or falsifier-suite passage claim
  - legal compliance, legal sufficiency, admissibility, or institutional competence conclusion
  - permission to publish a governed record or open the first-public-signature gate
research_only: true
---

# INT-R7 reachability invariant closure ledger

## 1. Scope and method

This is a bounded authoring pass for blocking finding `INT-R7-RV-001`. It changes no cryptographic algebra, fixture outcome, source conclusion, capability disposition, standing class, or dependency seam. It adds an invariant, one advance map, and one point-of-use signal to the threat-model artifact, then records the complete supersession-pair denominator.

Ordinary GitHub DNS/egress remained unavailable. Exact-ref reads, branch creation, ordinary Markdown commits, comparisons, and post-write reads used the connected GitHub interface. No workflow, upload fragment, base64 repository payload, staging directory, binary, or self-executing automation was added.

### 1.1 Complete artifact denominator

The pair walk covers these **11 artifacts / 11 total amendment artifacts** at remediation head `92c05323ed4c13c8f9eadb586d4e627c8d33a409`:

1. `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md`;
2. `policy-engine/docs/research/policy-operations/int-r7/orientation-ledger.md`;
3. `policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md`;
4. `policy-engine/docs/research/policy-operations/int-r7/comparative-models.md`;
5. `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md`;
6. `policy-engine/docs/research/policy-operations/int-r7/lifecycle-migration-preservation.md`;
7. `policy-engine/docs/research/policy-operations/int-r7/citizen-verification-ux.md`;
8. `policy-engine/docs/research/policy-operations/int-r7/frozen-falsifier-suite.md`;
9. `policy-engine/docs/research/policy-operations/int-r7/repository-integration-and-dependencies.md`;
10. `policy-engine/docs/research/policy-operations/int-r7/external-source-and-transfer-ledger.md`;
11. `policy-engine/docs/research/policy-operations/int-r7/amendment-ledger.md`.

The new closure ledger is not included in that historical denominator; it records the walk.

### 1.2 Pair-construction rule

The complete line walk searched each artifact for propositions displaced by terms or effects including `supersedes`, `controls`, `corrected`, `amended`, `remediation`, `historical_only`, `not executable`, `no longer`, and explicit replacement of an earlier vocabulary or formula.

One pair is counted for one contiguous source section or named subsection `E` and one controlling section or bounded controlling range `S`. If one source section contains independently displaced proposition classes governed by different targets, it contributes more than one pair. Multiple corrected rows in one contiguous table governed by one correction block contribute one pair. Pure additions that do not displace an earlier in-document proposition contribute no pair.

### 1.3 Adequate signal classes

A pair passes only when a reader can determine the controller before relying on the displaced proposition:

- **direct** — an advance map or point-of-use notice before `E` names `S` and the proposition class;
- **singleton document controller** — the exact `amended_after_audit` binding appears in frontmatter before `E`, the document has exactly one uniquely titled post-audit controller, and that controller's opening clause names `E`; the binding alone would not pass;
- **versioned controller** — frontmatter identifies old and amended suite IDs and a notice before the stale subsection names the exact controlling later section;
- **nested/same-change** — always requires a direct advance map or point-of-use signal; a document-level amendment binding is insufficient.

This is why the prior document-level corrections can remain unambiguous while the nested §15.2 → §15.10 relation failed before this pass.

## 2. Supersession reachability invariant

For every ordered pair `(E, S)` where section `S` supersedes, corrects, narrows, or otherwise displaces a proposition in section `E`, a reader travelling the affected document in order must encounter, at or before the first displaced proposition in `E`, an actionable signal that identifies `S` specifically enough to navigate to it and identifies the proposition class that `S` controls.

The invariant applies to:

- document-level supersession;
- a subsection superseding an earlier subsection inside the same controlling section;
- cross-layer versioning inside one artifact; and
- a supersession introduced in the same change.

The change that creates or changes `S` must create or update the signal and this pair register in the same commit. Displaced text may remain as history, but a generic “amended” status or unqualified “see later” is not sufficient.

The invariant now lives in the artifact set at `int-r7/threat-model-and-verification-predicates.md:29-43`, before every semantic section of that artifact. It directs future editors to this complete register.

## 3. Complete `(E, S)` register

### 3.1 Denominator reconciliation

| Artifact | Pair rows |
| --- | ---: |
| primary report | 11 |
| orientation ledger | 0 |
| threat model | 3 |
| comparative models | 3 |
| public-verification profile | 6 |
| lifecycle/preservation | 6 |
| citizen UX | 6 |
| falsifier suite | 5 |
| repository/dependencies | 3 |
| external-source ledger | 4 |
| amendment ledger | 0 |
| **total** | **47** |

Result after this closure: **47 invariant-satisfying pairs / 47 total pairs; 0 failing pairs**.

### 3.2 Primary report — 11 pairs

| ID | Superseded `E` | Controller `S` | Signal encountered before `E` | Result |
| --- | --- | --- | --- | --- |
| PR-01 | executive INT-R8 “becomes available” dependency state, `:62-63` | §21.3, `:961-973` | `:60` names §21.3 | pass |
| PR-02 | executive GY-N12 availability wording, `:64` | §21.3, `:961-973` | `:60` names §21.3 | pass |
| PR-03 | executive 18-case suite snapshot, `:69-71` | §21.5, `:988-1002` | `:60` names §21.5 | pass |
| PR-04 | §2.3 downstream capability labels, `:129-134` | §21.4, `:975-986` | `:125` names §21.4 and repository §11 | pass |
| PR-05 | §4.2 aggregate `HistoricalAuthenticity`/current algebra, `:206-250` | §21.2, `:945-959` | `:204` names §21.2 and threat §15 | pass |
| PR-06 | §12.2 current-sounding US-01 transfer, `:556-558` | §21.7, `:1010-1021` | `:554` names §21.7 and source §6 | pass |
| PR-07 | §15 v1/18-case suite, `:681-712` | §21.5, `:988-1002` | `:679` names §21.5 and suite §9/§10 | pass |
| PR-08 | §16.2 downstream capability labels, `:735-746` | §21.4, `:975-986` | `:733` names §21.4 and repository §11 | pass |
| PR-09 | §19 generic disconnected-recovery wording, `:860-879` | §21.6, `:1004-1008` | `:858` names §21.6 | pass |
| PR-10 | §19 18/18 suite gate, `:860-879` | §21.5, `:988-1002` | `:858` names §21.5 | pass |
| PR-11 | §20 “historical authenticity and current authority are independent,” `:888-891` | §21.2, `:945-959` | `:886` names §21.2 | pass |

The primary's entry signal remains in frontmatter `:14-15` and the executive notice at `:43`; each row above also has the accepted point-of-use signal.

### 3.3 Orientation ledger — 0 pairs

Section 7 adds the previously omitted briefing-date correction and preserves static O-05/O-09 evidence. No earlier section in this artifact asserts the false four-day interval, and the static records do not displace the earlier O-05/O-09 conclusions. Therefore the complete walk found **0 in-document supersession pairs / 0 total**. External briefing correction O-18 is not converted into a fictitious section pair.

### 3.4 Threat model — 3 pairs

| ID | Superseded `E` | Controller `S` | Signal encountered before `E` | Result |
| --- | --- | --- | --- | --- |
| TH-01 | §§7–8 and later uses of `HistoricalAuthenticity` as one conjunction | §15, beginning `:775` | artifact advance map `:37-40` names §15 before §7; §15 opening enumerates §§7–8 | pass |
| TH-02 | §7.1 overloaded audience/jurisdiction/procedural predicate meanings | §15.10, beginning `:966` | artifact advance map `:39` names §15.10 before §7.1 | pass |
| TH-03 | §15.2 overloaded issuer formula, `:793-823` | §15.10, `:966-1046` | §15 opening `:779` and point-of-use notice `:795` name §15.10 before the formula | pass |

`TH-03` was the sole failing pair identified by `INT-R7-RV-001`. It now has both an advance signal at the start of the controlling section and a point-of-use signal immediately before the old formula. The old predicate names remain visible as history.

### 3.5 Comparative models — 3 pairs

| ID | Superseded `E` | Controller `S` | Entry/controller signal | Result |
| --- | --- | --- | --- | --- |
| CM-01 | §13 recommendation/conclusion using the pre-decomposition framing | §14.1 and §14.3, `:396-422` | exact audit binding in frontmatter `:9`; unique §14 controller at `:392` names the affected findings and conclusion | pass |
| CM-02 | §6 RFC 9162/common-view transfer | §14.2, `:410-416` | same singleton-controller signal; §14.2 names RFC 9162 and the narrowed inference | pass |
| CM-03 | §7 Sigstore/general-bundle attribution | §14.2, `:410-416` | same singleton-controller signal; §14.2 names SIG-05 and bounded transfer | pass |

The ETSI date and NARA/Federal-PKI statements in §14.2 point to the source ledger; they do not displace a contradictory earlier comparative-model proposition and therefore do not create additional pairs here.

### 3.6 Public-verification profile — 6 pairs

The exact audit binding is in frontmatter `:9`; the artifact has one unique controller, §18 at `:622`, whose opening clause names the affected source sections.

| ID | Superseded `E` | Controller `S` | Result |
| --- | --- | --- | --- |
| PF-01 | §2 profile proposition | §18 | pass |
| PF-02 | §10 offline closure/result wording | §18 | pass |
| PF-03 | §13 aggregate outcome table | §18 | pass |
| PF-04 | §15 pre-issuance gate/result composition | §18 | pass |
| PF-05 | §16 dependency contract where composition collapses | §18 | pass |
| PF-06 | §17 profile conclusion | §18 | pass |

### 3.7 Lifecycle and preservation — 6 pairs

The exact audit binding is in frontmatter; the artifact has one unique controller, §11 at `:552`, whose opening clause names §§3, 5, 6, 9, and 10.

| ID | Superseded `E` | Controller `S` | Result |
| --- | --- | --- | --- |
| LC-01 | §3 lifecycle state wording that can collapse occurrence and proof | §11 | pass |
| LC-02 | §5 preservation/source wording | §11 | pass |
| LC-03 | §6 migration/preservation result wording | §11 | pass |
| LC-04 | §9 hard-failure wording | §11 | pass |
| LC-05 | §10 preservation conclusion | §11 | pass |
| LC-06 | §5.2 present-tense US-01 transfer | §11.6, `:653-657` | pass |

For LC-06, the singleton §11 controller names §5 at entry and §11.6 explicitly says the §5.2 sentence is superseded.

### 3.8 Citizen UX — 6 pairs

The exact audit binding is in frontmatter `:9`; the artifact has one unique controller, §13 at `:668`, whose opening clause names UX-T03 and §§3, 5, 10–12.

| ID | Superseded `E` | Controller `S` | Result |
| --- | --- | --- | --- |
| UX-01 | §2 UX-T03 two-question model | §13 | pass |
| UX-02 | §3 aggregate information hierarchy | §13 | pass |
| UX-03 | §5 aggregate outcome behavior | §13 | pass |
| UX-04 | §10 aggregate/offline behavior | §13 | pass |
| UX-05 | §11 prohibited-state wording affected by the split | §13 | pass |
| UX-06 | §12 aggregate capability/result standing | §13 | pass |

### 3.9 Falsifier suite — 5 pairs

The version signal is in frontmatter through `suite_id` and `amended_suite_id`; §9 at `:670` declares v1 historical, and the remediation notice before §9.1 names §10 and its scope.

| ID | Superseded `E` | Controller `S` | Signal encountered before `E` | Result |
| --- | --- | --- | --- | --- |
| FS-01 | §§1–8 v1 executable claim/case contract | §9 v2 controller | suite IDs in frontmatter and §9 heading before v2 semantics | pass |
| FS-02 | §9.1 scalar grammar | §10.1, `:1248-1269` | remediation notice `:670-672` names typed grammar | pass |
| FS-03 | §9.2 substring validator and pair rules | §§10.1–10.2, `:1248-1282` | remediation notice `:670-672` names typed grammar | pass |
| FS-04 | §9.3 B0/B1 baseline pairs | §10.3, `:1284-1315` | remediation notice `:670-672` names baseline pairs | pass |
| FS-05 | §9.4 six predicate overlays | §10.4, `:1317-1365` | remediation notice `:670-672` names the six overlays | pass |

The §10 scope does not displace denominators, top-level outcomes, reason codes, S0-K16 limits, or anti-wire warnings; those remain controlled by §§9.4–9.8 and §10.6.

### 3.10 Repository integration and dependencies — 3 pairs

The exact audit binding is in frontmatter; the artifact has one unique controller, §11 at `:356`, whose opening clause explicitly supersedes missing-state labels in §§2, 4, and 6.

| ID | Superseded `E` | Controller `S` | Result |
| --- | --- | --- | --- |
| RI-01 | §2 capability reality/missing-state labels | §11 | pass |
| RI-02 | §4 N-01–N-07 labels | §11 | pass |
| RI-03 | §6 summary/handoff labels | §11 | pass |

### 3.11 External source and transfer ledger — 4 pairs

The exact audit binding is in frontmatter; the artifact has one unique controller, §6 at `:153`, whose opening clause names the audit findings and revisions governing source correction/currentness.

| ID | Superseded `E` | Controller `S` | Result |
| --- | --- | --- | --- |
| ES-01 | §2 primary-source rows affected by ETSI-05, IETF-04, US-01, US-02, and SIG-04 corrections | §§6.1–6.2 | pass |
| ES-02 | §3 transfer-ledger propositions affected by those corrections | §6.4 | pass |
| ES-03 | §§4.2–4.5 source adjudication for RFC 9162, AdES, NARA/Federal PKI, and Sigstore | §§6.1 and 6.4 | pass |
| ES-04 | §5 source-backed minimum insofar as US-01 was current support | §6.4 | pass |

### 3.12 Amendment ledger — 0 pairs

The amendment ledger is an accountability record. At the remediation head its evidence table was rewritten to tighter paths rather than retaining an older visible governing table plus a later controller. The complete walk therefore found **0 supersession pairs / 0 total** in this artifact. Its 22 revision rows and 42 finding rows remain subject to the closed evidence-path verification, not a new reachability layer.

## 4. Change made for `INT-R7-RV-001`

The defect was confirmed by reading §15 in order: a reader met the title “Post-audit controlling decomposition,” then the §15.2 formula using overloaded names, and only later encountered §15.10. The later formula was mathematically correct but not reachable as controlling before the earlier formula.

The threat-model artifact now contains:

1. the artifact-set invariant and editing rule before §1, `int-r7/threat-model-and-verification-predicates.md:29-43`;
2. an advance map before §7 naming §15 and §15.10, `:37-40`;
3. a sentence at the start of §15 naming the nested §15.2 → §15.10 relation, `:779`;
4. a point-of-use notice immediately before the §15.2 formula, `:795`; and
5. unchanged corrected algebra in §15.10, `:966-1046`.

A notice alone is sufficient here because §15.10 already contains the correct formula and complete diagnosis. Marking the old predicate names inside the formula as deleted or rewriting the formula would spend append-only history without improving reachability. The point-of-use notice names the three old and three replacement issuer-side predicates, and states that requested-use and released-history results remain separate.

## 5. Editing-discipline placement

The invariant is not confined to this ledger. It is placed at the start of the threat-model artifact, which is the formal owner of result algebra and the document most likely to receive future controlling predicates. It also requires any future superseding change to update this register in the same commit.

The primary report remains the worked example for direct point-of-use signals. The suite remains the worked example for a scoped versioned controller. The new threat-model signal is the worked example for a controlling subsection that supersedes an earlier subsection of the same controlling section.

## 6. Regression statement — closed items remain closed

### 6.1 Closed verification findings

| Closed item | Complete regression evidence at the closure head | Result |
| --- | --- | --- |
| `INT-R7-V-103` | suite file unchanged from remediation blob `d308fde3f56545bca58ad2ac70ab842bbad148d7`; §§9–10 grammar, B0/B1, and 31/31 sweep untouched | intact |
| `INT-R7-V-105` | amendment ledger unchanged from remediation blob `3d1d696f4b2d6c546b61a11c078418496f3d997b`; 22/22 revision and 42/42 finding rows untouched | intact |
| `INT-R7-V-104` algebra | §15.10 formula and diagnosis preserved byte-for-byte in proposition content; suite overlays unchanged; 29/29 algebra denominator unchanged | intact |
| primary-report portion of `INT-R7-V-102` | primary report unchanged from remediation blob `6af28e4c5f1b991d3265fbc652f48e9cbdcd5f7f`; 9/9 affected revision signals remain | intact |
| `INT-R7-RV-001` | TH-03 now has advance and point-of-use signals before §15.2; 47/47 pair register passes | authoring-level closure |

### 6.2 Twelve conforming revisions

Only the threat-model artifact and this new ledger are changed. The threat-model change adds reachability metadata and signals; it does not alter the propositions supporting these revisions.

| Revision | Evidence retained | Result |
| --- | --- | --- |
| R2 | threat snapshot-selection algebra remains in §15.4; suite AX-02 unchanged | intact |
| R7 | threat temporal terminal remains; UX and F-04a unchanged | intact |
| R11 | lifecycle anti-rollback/cross-custody text unchanged | intact |
| R13 | source and comparative narrowing unchanged | intact |
| R14 | orientation O-18 unchanged | intact |
| R15 | evidence-obtainability semantics in threat §15.5 and sibling artifacts unchanged | intact |
| R17 | source metadata/attribution corrections unchanged | intact |
| R18 | all anti-wire-format warnings unchanged | intact |
| R19 | lawful-succession profile/lifecycle/UX/F-18b unchanged | intact |
| R20 | orientation static outputs and reservations unchanged | intact |
| R21 | F-03a/F-13a signature-policy separation unchanged | intact |
| R22 | 32-source currentness/recheck ledger unchanged | intact |

Result: **12 intact / 12 total; 0 weakened; 0 lost**.

### 6.3 Twenty audit commendations

| Finding ID | Preserved strength | Result |
| --- | --- | --- |
| `INT-R7-I-001` | exact branch/scope discipline | intact |
| `INT-R7-I-002` | signing-time/revocation defect remains precisely bounded | intact |
| `INT-R7-I-003` | O-09 and real producer preservation | intact |
| `INT-R7-I-004` | O-02/O-08 reservations | intact |
| `INT-R7-II-001` | primary-heavy, transfer-limited source corpus | intact |
| `INT-R7-III-001` | signature does not equal a worldly fact | intact |
| `INT-R7-IV-001` | nine real comparative constructions | intact |
| `INT-R7-IV-002` | GY-N12/INT-R8 ownership not duplicated | intact |
| `INT-R7-V-004` | F-05/F-17/F-18 history/withdrawal/succession cases | intact |
| `INT-R7-VI-001` | candidate/authority-band first-signature gate | intact |
| `INT-R7-VI-004` | preservation does not launder issuer or late trust loss | intact |
| `INT-R7-VII-001` | INT-K06 chronology remains security-critical | intact |
| `INT-R7-VII-002` | INT-K02 basis completeness remains statement integrity | intact |
| `INT-R7-VII-003` | withdrawn-but-verifiable remains first-class | intact |
| `INT-R7-VII-004` | S0-K16 bounds suite passage | intact |
| `INT-R7-VII-005` | no second authority/status/projection owner | intact |
| `INT-R7-VIII-001` | proof/content seam remains explicit | intact |
| `INT-R7-IX-001` | effective research prohibitions remain | intact |
| `INT-R7-IX-003` | `GO_WITH_REVISIONS` remains the target standing | intact |
| `INT-R7-X-002` | real `public_export.py` producer remains recognized; only its production route is `bridge_missing` | intact |

Result: **20 intact / 20 total; 0 weakened; 0 lost**.

### 6.4 Frozen denominators and untouched dependencies

- suite grammar/value-status result remains **31/31**;
- suite manifest/algebra result remains **23 families / 29 subfixtures**, with the independent **29/29** consistency sweep unchanged;
- primary reachability remains **9/9 affected revisions**;
- the revision/finding ledgers remain **22/22** and **42/42**;
- INT-R8 is untouched; and
- the first-public-signature gate remains closed.

## 7. Updated standing

**Standing: `GO_WITH_REVISIONS`, retained at the authoring level pending independent bounded conformance verification of this closure.**

`INT-R7-RV-001` is closed in the authored artifacts because the formerly unreachable §15.2 → §15.10 controller now has an advance map and a point-of-use signal, and the complete register records **47 passing pairs / 47 total**. This ledger does not self-certify independent conformance, open the first-public-signature gate, establish suite passage, or authorize consolidation by itself.

## 8. Post-write verification record

A complete comparison from remediation head `92c05323ed4c13c8f9eadb586d4e627c8d33a409` to this closure branch, taken after the threat-model update and initial ledger write, found exactly **2 changed Markdown paths / 2 total**:

| Path | Status at comparison | Additions | Deletions |
| --- | --- | ---: | ---: |
| `int-r7/threat-model-and-verification-predicates.md` | modified | 18 | 0 |
| `int-r7/reachability-closure-ledger.md` | added | 334 | 0 |

The merge base was exactly the remediation head; the branch was 2 commits ahead and 0 behind; no non-Markdown file was present. This final ledger-only update changes no path membership, merge base, threat-model diff, or deletion count.

Post-write reads established:

- threat-model blob `7b19c8790c62c76242fec51387d978321facd03a`, including the exact closure binding, invariant, advance map, §15 signal, and §15.2 point-of-use notice;
- closure-ledger pre-final blob `cda71b09f9c576b16851664f9488e3c28c61ed0c`, including `research_only: true`, a non-empty `may_not_use_for`, and all three existing bindings plus `reachability_closed_after`.

The final ledger version is read back after this commit and its final branch head/blob are reported in the delivery response. No pull request is opened, no other branch is written, and the first-public-signature gate remains closed.
