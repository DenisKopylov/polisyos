---
title: "INT-R8 — Claim-evidence and capability-honesty ledger"
audit_id: INT-R8-INDEPENDENT-AUDIT
verified_commit: 90b372964d29a9e97605a6ef733ef03ffe7938d2
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent mapping of INT-R8 load-bearing claims to offered evidence
  - Pass IX capability-honesty adjudication
  - findings INT-R8-IX-001 and INT-R8-IX-002
may_not_use_for:
  - adoption amendment or ratification of INT-R8
  - production implementation authorization
  - final wire schema package database serialization or API contract
  - canonical owner appointment
  - authority grant capability claim benchmark passage or permission to publish
  - legal sufficiency compliance or institutional competence conclusion
  - automatic amendment of any plan or system-design decision
  - signature algorithm key policy or numeric disclosure-bound selection
research_only: true
---

# INT-R8 claim-evidence ledger

## 1. Verdict vocabulary

- `supported` — offered evidence establishes the claim at the stated scope.
- `supported_after_narrowing` — core conclusion survives, but one premise or scope statement must
  be narrowed.
- `partially_supported` — evidence supports only part of the statement.
- `not_established` — the evidence does not make the claim decidable or reproducible.
- `refuted_as_stated` — a feasible independent check contradicts the statement as worded.
- `research_contract_only` — coherent semantic requirement, not present repository capability.
- `capability_mislabelled` — missing-state label asserts prerequisites not present at the pin.

This ledger does not convert a supported research claim into implementation or authority.

## 2. Orientation and repository claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-001 | Audited branch is 6 commits ahead, adds 6 Markdown files/2,207 lines, changes nothing else. | Git history and delivered-file list. | `supported` | Exact compare reproduces 6/0 commits, 6 added files, no modify/delete, 2,207 additions. |
| C-002 | `projection_semantics.py` is 3,763 lines. | End-line anchor. | `supported` | Exact end read closes at 3,763. |
| C-003 | `public_export.py` is 2,103 lines. | End-line anchor. | `supported` | Exact end read closes at 2,103. |
| C-004 | Four canonical audiences are PUBLIC/REVIEWER/EXPERT/MACHINE; INT-R8 adds no fifth. | Projection fixture plus 6-file audit. | `supported` | Exact source and 6/6 audited files agree. |
| C-005 | `may_not_use_for` occurs in 106 Python files partitioned 67/12/27. | Orientation census and recipe. | `supported` | Three complete disjoint path searches reproduce 67 runtime, 12 scientist, 27 remainder. This is a file count. |
| C-006 | `omitted_claim` appears 8 times in `public_export.py`. | Literal-occurrence table and `text.count` recipe. | `refuted_as_stated` | Eight matched lines contain nine literal occurrences; the recipe returns 9. |
| C-007 | Other seven public-export census rows are exact. | Complete file and recipe. | `supported` | `projection_faithfulness` 13/13 lines/occurrences; `redaction_reason` 2/2; `omissions_manifested` 2/2; four loss terms 0/0. |
| C-008 | No named disclosure/composition/privacy/compression-loss owner exists in source. | Complete source token searches. | `supported_after_narrowing` | Five exact tokens return zero source files. This establishes named-token absence, not absence of every adaptable differently named component. |
| C-009 | `CompressionLoss` exists in planning prose including GY-PA3 but in zero source files. | Whole-tree and source searches. | `supported` | Four planning/research files; zero source. |
| C-010 | `build_public_export_bundle` source token set is definition+re-export and no HTTP binding. | `src` and `runtime/http` searches. | `supported` | Exactly two `src` token files, no HTTP caller. |
| C-011 | Tooling/tests contain invocations. | Whole-tree search. | `partially_supported` | Four caller files exist: two tools and two tests. Ledger mentions only one operations runner and later calls definition/re-export “two callers.” |

## 3. Central composition claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-012 | No current canonical numerical disclosure-composition guarantee is justified. | Repository absence, DP premise audit, ratified K04/K07. | `supported` | No local guarantee, model, prospective allocation or adaptive accountant exists. |
| C-013 | A numerical disclosure theorem requires a randomized mechanism. | DP/NIST/Kairouz survey and editorial determinism. | `refuted_as_stated` | Randomization is a DP premise, not a universal numeric-leakage premise; deterministic quantitative-information-flow channels exist. |
| C-014 | Differential-privacy composition does not transfer by analogy to the current editorial path. | NIST SP 800-226 and Kairouz et al. | `supported` | Local DP mechanism/adjacency/parameters are absent. |
| C-015 | Maximal leakage is useful diagnostically but no canonical value can presently be issued. | Issa et al. plus absent channel/distribution/gain owner. | `supported_after_narrowing` | No current value is justified, but deterministic leakage and weak composition possibilities must be acknowledged. |
| C-016 | Exact prefix discipline is genuinely number-free. | Boolean `Safe_F(T)` and singleton consistency test. | `supported` for finite/decidable models | It is a repeated predicate, not an expenditure or remaining quantity. |
| C-017 | Prefix discipline handles adaptive next-release selection. | Actual-prefix induction. | `supported` | A fixed versioned Boolean family is evaluated on the history-selected candidate. |
| C-018 | Prefix discipline covers the complete actual history. | Transcript model and reproducible-membership prose. | `partially_supported` | Only a declared controlled release universe can be complete; uncontrolled external copies and unknown auxiliary releases cannot be reproduced. |
| C-019 | Approximation/conservative solving preserves the no-number theorem. | Symbolic/over-approximation implementation discussion. | `not_established` | Soundness direction, termination, timeout and heuristic-substitution rules are not specified. |

## 4. Formal reconstruction claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-020 | `C(T)` exact reconstruction criterion is mathematically well-defined. | Set definition and hidden predicate `q`. | `supported` conditionally | Correct when model class, observation relation and total predicate are supplied and consistency set is meaningful. |
| C-021 | Strict cross-view reconstruction is correctly defined. | Single-view non-uniqueness plus coalition uniqueness. | `supported` | Correctly captures synergistic reconstruction. |
| C-022 | The reconstruction check is executable in general. | Enumeration, SAT/SMT and over-approximation sketch. | `not_established` | Finiteness, decidability, empty-set behavior, abstraction soundness and realistic scale are not closed. |
| C-023 | The transcript channel enumeration is comprehensive enough for the claimed threat model. | Long channel list. | `partially_supported` | Strong breadth, but locale/translation, notifications/syndication, network compression, discovery/index and proof metadata are missing. |
| C-024 | The model is distribution-free. | Consistency sets rather than probabilities. | `supported` for exact predicates | No probability is needed; unknown auxiliary facts remain an explicit limitation. |

## 5. Domain and loss-boundary claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-025 | Minimum retained set tracks public-administration materiality rather than generic token retention. | APA/ADJR reasons, FOI deletion, dissent, accessibility, SDC/ABS. | `supported` | Sources and transfer limits support reasons, contestability, dissent, denied-use, negative outcome and visible caveat classes. |
| C-026 | Bare `delta` without set/assumptions/rider is always blocked. | INT-K02, boundary and F02. | `supported` | No exception path exists. |
| C-027 | Hidden refusal/void/dispute/no-attempt/exhaustion is always blocked. | INT-K08, boundary and F03. | `supported` | Correct categorical semantic rule. |
| C-028 | Removing a constitutive procedural step is mechanically checkable. | Named history classes and F06. | `not_established` | “Constitutive/load-bearing” relation, condensation equivalence and decisive mutation are not operationalized. |
| C-029 | `lossy_but_safe`/`blocked_material_omission` form a total decision procedure. | Six-gate procedure; unknown/missing maps to blocked. | `partially_supported` | Outcome surface is two-valued, but general termination/materiality/faithful-condensation predicates remain open. |
| C-030 | Pointer-only cure is insufficient. | Administrative reasons and F10. | `supported` | A pointer cannot make misleading visible prose semantically conservative. |
| C-031 | Denied uses must be monotone under compression. | Live `may_not_use_for` substrate and P2. | `supported` | Correct and checkable once claim IDs are bound. |
| C-032 | Receipt is a real extension, not a parallel projection owner. | Reuse table and source anchors. | `supported_after_narrowing` | Core reuse points exist, but scanner/projection/receipt reason vocabularies need one canonical relation. |
| C-033 | Existing source has a universal `limitations` field to reuse. | Generic reuse prose. | `refuted_as_stated` | Existing carriers are limitation codes, gaps, deficits and surface-specific fields; no universal base list. |
| C-034 | Receipt outcomes are not a new global status lattice and do not mint authority. | Explicit disclaimers, authority boundary, F22. | `supported` | Outcomes are verifier dispositions feeding existing gates. |

## 6. Falsifier and interface claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-035 | Suite contains 25 red and 5 green cases. | F01-F25/G01-G05 headings. | `supported` | Exact heading census is 25/5. |
| C-036 | Suite is executable as written by an equality harness. | Logical result shape and case prose. | `refuted_as_stated` | At least 13 cases use alternatives, multiple mutations, “red,” `and/or` or unbound materiality. |
| C-037 | Suite prevents reject-all passage. | Five green controls. | `supported` | Positive controls cover duplicate condensation, role substitution, controlled aggregate, history condensation and extra caution. |
| C-038 | Suite covers the major enumerated channels. | F11-F20. | `supported` for listed channels | Diff, hash, order, timing, provenance, manifest, screenshot, export, deep-link and currentness cases exist. |
| C-039 | Suite covers the full declared threat channel. | F01-F25. | `refuted_as_stated` | Five independently constructed channel attacks lack cases. |
| C-040 | INT-R7 seam keeps content and proof separate. | Primary §13 and handoff. | `supported` | No algorithm/key lifecycle/proof format is selected by INT-R8. |
| C-041 | INT-R7 seam binds everything needed to prove the formal relation. | Source/audience/retained set/reasons/verdict/rule/head list. | `partially_supported` | Missing use/predicate/model/channel/coalition/background/render/timeout/completeness identities. |
| C-042 | Projection failure has a correctly bounded effect on authenticity. | Currentness/history prose. | `partially_supported` | INT-R8 should explicitly prohibit interpreting projection failure as erasure of source issuer authenticity, consistent with `INT-R7-VIII-003`. |

## 7. Pass IX — capability-honesty audit

### 7.1 Missing-state prerequisite rule

The repository vocabulary is directional:

- `producer_missing` presupposes a real admitted consumer;
- `bridge_missing` presupposes both endpoints;
- `verification_missing` presupposes a wired producer→bridge→consumer chain whose verifier is the
  missing link;
- `semantic_test_missing` identifies a missing semantic negative only when the underlying
  surface/behavior being tested exists;
- `contract_only` is appropriate for a research/typed contract without the rest of the chain;
- `artifact_missing`, `consumer_missing` and `surface_missing` state earlier absences without
  pretending downstream maturity.

### 7.2 Handoff-row adjudication

| Handoff capability | Audited label | Independent reality | Verdict |
| --- | --- | --- | --- |
| Existing four-audience projection substrate | `implemented` | Source producer, contracts and tests exist. | Correct. |
| Compression receipt on projection substrate | `producer_missing` | Research semantic contract exists; no admitted receipt consumer contract is wired. | `capability_mislabelled`. `producer_missing` prerequisite absent. |
| Existing public-export bundle | present | Source producer and tests/tools exist; no HTTP surface. | Correctly preserved as existing. |
| Public-export loss gate | `verification_missing` | No receipt producer, bridge or consumer chain exists. | `capability_mislabelled`. Not yet a verifier-only gap. |
| HTTP binding for public export | `bridge_missing` | Producer exists, but no HTTP endpoint/consumer endpoint for this chain exists. | `capability_mislabelled`. Two endpoints are not present. |
| GY-PA3 loss producer | `producer_missing` | Plan entry only; DS12/DS14 are plans, not admitted live consumers. | `capability_mislabelled`. |
| Cross-view transcript owner/verifier | `producer_missing`, `verification_missing` | No approved owner, artifact, consumer or wired chain. | `capability_mislabelled`. |
| Frontend receipt integration | `bridge_missing` | Frontend packet exists, but owner-issued receipt endpoint/artifact does not. | `capability_mislabelled`. |
| Screenshot/print/export semantic checks | `semantic_test_missing` | Real packet/viewer/render/export behaviors exist; INT-R8 semantic cases do not. | Correct at the scoped surface level. |
| INT-R7 proof binding | `contract_only` | Parallel research contract exists; implementation is not claimed. | Correct. |
| Numeric composition accountant | `producer_missing`; research gap | No authorized contract or admitted consumer; accepted result says the capability is not currently required. | **Capability mislabel plus scope error.** It should not be represented as an owed downstream producer. |

### 7.3 Why this is blocking

The mislabels are not cosmetic. They place absent research sketches later in the capability
ratchet than their evidence allows:

- `verification_missing` implies a chain that does not exist;
- `bridge_missing` implies endpoints that do not exist;
- `producer_missing` implies a consumer that does not exist; and
- the accountant row makes a deliberately refused number look like pending engineering.

A downstream planner could therefore treat implementation as local gap closure rather than a
new architecture/consumer decision. That is precisely the capability inflation prohibited by
the repository's vocabulary and independently found as `INT-R7-X-001` in the parallel audit.

### INT-R8-IX-001 — blocking — capability labels upgrade research sketches beyond their prerequisites

Recompute every new handoff row from the pinned chain. Preserve `implemented` for the real
projection substrate and present producer for public export. Do not use `producer_missing`,
`bridge_missing` or `verification_missing` until their prerequisite consumer/endpoints/chain are
independently evidenced. Remove the numeric accountant from the maturity ratchet unless a later
architecture decision creates a real consumer and research contract.

### INT-R8-IX-002 — commendation — existing public-export and projection capability is not erased

Unlike a common gap-analysis failure, INT-R8 correctly says the substrate and export producer
exist and need extension. Screenshot/export semantic-test debt is also honestly identified on
real surfaces.

## 8. Prohibition and standing claims

| Claim ID | Load-bearing claim | Offered evidence | Independent verdict | Reason |
| --- | --- | --- | --- | --- |
| C-043 | All six artifacts carry `research_only: true` and `may_not_use_for`. | 6/6 frontmatter census. | `supported` | Complete audited-file read. |
| C-044 | No artifact appoints an owner or fixes wire/package/schema/API. | 6/6 text search/read. | `supported` | Directional integration only; no appointment or serialization contract. |
| C-045 | No second confidence ledger, fifth audience or global status lattice is created. | Prohibitions and semantic contract. | `supported` | Explicitly refused; outcomes are local verifier dispositions. |
| C-046 | Repository can currently emit a `CompressionLossReceipt`. | Capability map and disclaimers. | `refuted by INT-R8 itself` | Work consistently says producer/verification absent; no source symbol exists. |
| C-047 | `accepted_narrow_scope` is substantively justified. | Formal/domain/reuse results. | `supported_after_required_revisions` | Core no-number/semantic result survives; capability labels and eleven material defects require revision. |

## 9. Claim-evidence conclusion

The strongest claims are supported:

- existing substrate orientation;
- public-administration minimum semantics;
- categorical bare-delta and negative-outcome rules;
- exact cross-view reconstruction definition;
- exact number-free prefix discipline; and
- proof/content ownership separation.

The weakest claims are precisely where the work crosses from semantic research into operational
or maturity language:

- universal randomization premise;
- general executability of `C(T)`;
- mechanically total materiality/constitutive-step classification;
- equality-ready falsifier suite; and
- capability missing-state labels.

The blocking capability-label defect does not erase the research result. It prevents the
integration handoff from being consumed as a trustworthy capability map until revised.