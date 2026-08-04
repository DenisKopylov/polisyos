---
title: "INT-R8 — Compression Loss and Disclosure Composition"
research_id: INT-R8
result_standing: accepted_narrow_scope
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
research_branch: research/int-r8-compression-loss-and-disclosure
prepared_at: 2026-08-04
composition_result: procedural_no_number
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 — Compression Loss and Disclosure Composition

## Executive decision

### Result standing: `accepted_narrow_scope`

INT-R8 settles:

1. the semantic contract of a `CompressionLossReceipt` as an extension of the existing projection/omission/redaction substrate;
2. a checkable definition of semantic parity for legitimately shorter records;
3. the minimum semantic set a summary must retain;
4. the boundary between `lossy_but_safe` and `blocked_material_omission`;
5. a formal, distribution-free treatment of cross-view and temporal reconstruction;
6. screenshot, deep-link, diff, hash, ordering, timing, provenance and export threats;
7. a red-first falsifier suite and repository integration handoff.

INT-R8 **does not establish a numeric repeated-disclosure budget**. The present release mechanism is a curated deterministic/editorial projection, not an established randomized privacy mechanism with a declared adjacency relation, prospectively enforced local guarantees, adaptive composition theorem and canonical accountant. Issuing a number would violate the premises ratified by `INT-K04` and `INT-K07` (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:143-218`).

The accepted composition result is instead an `INT-K06` **no-number procedural custody claim**:

> Every actual candidate disclosure prefix is checked prospectively against a declared semantic-loss and reconstruction rule family; release membership, chronology, current heads, assumptions and verifier versions remain reproducible; no post-hoc narrowing or silent history deletion manufactures a pass.

That claim is falsifiable and useful. It is not differential privacy, a probability of confidentiality, legal compliance, competence or publication authority.

## 1. Answer to the research question

### What is lost in summary and compression?

A summary can lose more than text. It can lose:

- a claim's declared basis, scope, assumptions or conditionality;
- the limitation that changes who or when the result applies to;
- an active denied use (`may_not_use_for`);
- an attack, counterexample, conflict or counterevidence considered by the decision-maker;
- dissent or minority reasoning on a material issue;
- contest/dispute status and a real recourse route;
- the negative fact that a governed process ended in refusal, void, no-attempt or exhaustion;
- a load-bearing step in a no-number procedural history;
- currentness, supersession or correction lineage;
- privacy, when the combination of releases determines protected information.

A fluent short sentence can therefore be lexically accurate yet institutionally false: conditional becomes unconditional, majority becomes consensus, refusal becomes absence, a bounded custody history becomes “the process was proper,” and an old version appears current.

### What can be reconstructed by combining the four views and side channels?

Anything whose possible values collapse to one after intersecting the constraints carried by PUBLIC, REVIEWER, EXPERT and MACHINE releases — including their historical versions, diffs, hashes, ordering, timestamps, provenance identifiers, URLs, screenshots and exports.

The formal test is not “did one view display the secret?” It is:

> After observing the complete obtainable transcript, do at least two full records with different protected values remain observationally possible?

If not, the protected predicate has been reconstructed. Two individually safe projections may therefore be jointly unsafe.

## 2. Repository orientation and measured delta

Pass I independently verified the commission against exact Git object `02c5b8d23c757c92b9231e6e1e802d5701588908`. The full ledger and reproduction recipe are in [`int-r8/orientation-ledger.md`](int-r8/orientation-ledger.md).

### 2.1 Existing substrate to extend

`projection_semantics.py` already builds one truth into the four canonical audiences and carries:

- `closeout_truth`;
- `projection_gaps`;
- `omission_manifest`;
- `contested_records`;
- `recourse_pointer`;
- `deficit_register`;
- participation requirements;
- invariant summary;
- `redaction_summary`;
- source/audit references;
- `may_not_be_used_for`;
- an explicit `projection_only` authority role.

It then calls `assert_policy_design_projection_not_authority` (`policy-engine/src/polisyos/runtime/quality/projection_semantics.py:275-575`). The four audiences are exactly PUBLIC, REVIEWER, EXPERT and MACHINE (`projection_semantics.py:648-655`). Existing S9-S14 contracts already check per-view faithfulness and authority laundering; S14 includes a hidden/gold-payload guard.

`public_export.py` already:

- builds the public export bundle;
- consumes projection semantics;
- runs S9-S14 gates;
- requires omitted claim IDs to occur in the omission manifest;
- runs candidate and replay-drift firewalls;
- emits canonical scanner redaction reasons;
- preserves a projection-only authority boundary (`policy-engine/src/polisyos/runtime/quality/public_export.py:1540-1995`).

The exact 2,103-line literal census confirmed:

| Literal | Count |
|---|---:|
| `omitted_claim` | 8 |
| `projection_faithfulness` | 13 |
| `redaction_reason` | 2 |
| `omissions_manifested` | 2 |
| `lossy` | 0 |
| `blocked_material` | 0 |
| `compression` | 0 |
| `retained_limitation` | 0 |

The gap is therefore not “discover omissions.” It is:

- classify what semantic class was retained/dropped;
- decide whether loss is materially safe;
- preserve limitations, denied uses, counterevidence, dissent and negative outcomes;
- evaluate the union and history of releases;
- issue a checkable verdict.

### 2.2 Capability reality

- `build_public_export_bundle` producer: **present**.
- HTTP/public-surface binding: **`bridge_missing`**. In `policy-engine/src`, the complete token-containing set is the definition plus `runtime/quality/__init__.py` re-export; no `runtime/http` caller exists.
- Compression-loss receipt producer: **`producer_missing`**.
- Material-loss/transcript verifier: **`verification_missing`**.
- Screenshot/export/cross-view red-first suite: **`semantic_test_missing`**.
- GY-PA3: plan entry only, not capability. It expressly plans a producer reusing G6 ledgers, `projection_semantics` and `public_export` (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2278-2330`).

The complete exact-token census also confirmed 106 Python files using `may_not_use_for`; denied use is a live mechanism, not documentation convention.

### 2.3 Current frontend compression point

The Atlas packet is explicitly a rendering view model, never authority. It nevertheless shows the practical loss gap:

- `publicRef` truncates after masking to 96 characters;
- `publicText` truncates after masking to 320 characters (`publicationPacket.ts:389-434`);
- deterministic explanation rendering keeps only the first four metrics (`publicationPacket.ts:632-724`);
- `buildProjectionSemantics` carries a narrow subset and omits the canonical omission/gap/contest/recourse/deficit/audit structures (`publicationPacket.ts:913-956`);
- the packet itself is serialized and base64url-encoded into the deep-link path (`publicationPacket.ts:1019-1174`);
- the private-context heuristic searches only five literal needles (`publicationPacket.ts:1194-1214`).

These are not findings that the frontend should own materiality. They show why loss must be classified upstream and rendered downstream.

## 3. Binding ratified constraints

The decision applies the ratified kernel by finding ID, not by adjacency:

- **S0-K07:** projection cannot mint authority.
- **INT-K02:** every `delta` claim must retain declared obligation set, maintained assumptions and visible relative-basis rider. A bare `delta` is a different false claim and always `blocked_material_omission`.
- **INT-K04:** a composed bound requires prospectively fixed/enforced local bounds and canonical reproduction of membership, chronology, current heads and assumptions. Prose is not an invariant.
- **INT-K05:** do not create a second confidence/risk ledger or parent scope.
- **INT-K06:** a binding falsifiable procedural custody claim may carry no probability.
- **INT-K07:** adaptive selection needs a guarantee valid for the actual history-selected procedure and a pathwise aggregate bound before any number is allowed.
- **INT-K08:** refusal, void, dispute, terminal no-attempt and exhaustion are completed governed results; compression may not hide them (`int-wave-claim-semantics-ratification.md:77-245`).

The Atlas DS12 gate already treats INT-R8 as a pre-publication research input, keeps the current packet only as rendering, consumes a no-number custody claim, requires the `delta` declared-set rider and forbids hiding negative completion (`POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1203-1300`). DS13 then owns public dispute/history surfaces, and DS14 is the intended receipt-rendering consumer (`:1301-1345`).

## 4. Comparative model selection

The full primary-source and transfer analysis is in [`int-r8/external-source-and-transfer-ledger.md`](int-r8/external-source-and-transfer-ledger.md).

| Model | Decision | Eliminating property / retained role |
|---|---|---|
| National-statistical-institute disclosure control | **Adopt as release-discipline layer** | Suppression, thresholds, output checking and differencing are valuable, but cell rules do not preserve policy reasons, dissent, denied uses or authority scope. |
| Differential privacy | **Reject as current general composition theorem** | Editorial projections have no established adjacency, randomization, local DP guarantee or accountant. Retain only as future narrow option for defined statistical mechanisms. |
| Information-theoretic leakage | **Adopt as formal diagnostic, not budget** | Exact consistency-set reconstruction works now. A scalar needs a justified secret, distribution, channel and gain function. |
| Access-control / need-to-know | **Adopt as perimeter only** | Roles overlap and content is copyable; authorized views can be joined. It cannot establish parity or prevent coalition leakage. |
| Redaction with manifest | **Adopt as canonical base** | Closest to current substrate; insufficient alone because manifest/diff/hash/history can reconstruct information and IDs do not classify materiality. |
| Provenance completeness | **Adopt as binding/currentness layer** | A full-record pointer supports audit but does not cure a materially misleading visible summary. |
| Administrative-law reasons-giving | **Adopt as materiality/contestability layer** | Material findings, reasons, evidence and dissent identify what government cannot casually drop; exact duties remain jurisdiction-specific. |
| Unstructured editorial summary without receipt | **Reject** | Silent loss is undetectable; no inventory, parity test, denied-use monotonicity, transcript or fail-closed verdict. |

### Selected layered answer

1. Administrative reasons/dissent practice identifies load-bearing public-administration semantics.
2. Existing omission/redaction machinery records typed removal.
3. `CompressionLossReceipt` classifies safe versus material loss.
4. Existing access controls constrain ordinary audience access.
5. SDC-style output checking treats every view/version/export as a disclosure event.
6. Consistency-set analysis tests joint and temporal reconstruction.
7. Provenance/currentness connects summary to the authoritative revision.
8. INT-R7 binds the content and history cryptographically.
9. Composition presently remains a no-number procedural prefix claim.

## 5. `CompressionLossReceipt` semantic contract

The detailed contract is in [`int-r8/semantic-contract-and-loss-boundary.md`](int-r8/semantic-contract-and-loss-boundary.md).

### 5.1 What is reused

The receipt reuses, by reference and identifier:

- canonical audience and projection source revision;
- `omission_manifest` and normalization/deduplication;
- `redaction_summary` and approved reason vocabulary;
- projection gaps, limitations, deficit register;
- contested records, recourse and participation surface;
- audit/provenance references;
- current `may_not_use_for` semantics;
- S9-S14 verification and projection-only authority boundary.

### 5.2 What is new

For each semantic source item the receipt adds:

- retained / dropped-manifested / not-applicable disposition;
- item class: claim, basis, assumption, limitation, attack, denied use, counterevidence, dissent, negative terminal, chronology, provenance or protected detail;
- affected claim IDs;
- canonical reason;
- semantic effect on truth, scope, authority/status, use, contestability, history or privacy;
- declared use/predicate version;
- actual transcript predecessor/current head;
- verifier finding and issue code;
- one of the two loss verdicts.

This is a semantic inventory, not a final schema or package decision.

### 5.3 Receipt outcomes

- **`lossy_but_safe`** — information was removed, but every mandatory semantic invariant is retained or faithfully condensed, every drop is manifested, the summary is no broader/more authoritative than the full record, and the complete actual transcript passes declared reconstruction checks.
- **`blocked_material_omission`** — any mandatory semantic, parity, reason, completeness, contestability, currentness or reconstruction test fails or is unresolved.

No “unknown but safe,” “editor approved,” “privacy score” or local publication status is added. Missing verification fails closed through the existing gate.

## 6. Semantic parity and minimum retained set

### 6.1 Parity definition

Semantic parity is **use-relative conservative observational equivalence**, not byte equality.

For full record `R`, summary+receipt `S`, declared use set `U` and versioned decision predicates `D_U`, parity holds only when:

1. every surfaced claim in `S` resolves to `R`;
2. claim type, basis, scope, assumptions, material conditions and limitations are preserved;
3. for every `d ∈ D_U`, the conclusion from `S` equals the conclusion from `R` or is more conservative — never broader, more favorable, more certain or more authoritative;
4. denied uses are monotone: `may_not_use_for(S) ⊇ may_not_use_for(R)`;
5. negative states, contest, dissent and recourse remain visible when material;
6. all drops are manifested;
7. the accumulated transcript remains non-reconstructing under the declared model.

This permits duplicate wording, repeated citations and low-level paths to disappear. It does not permit a truth-changing rider to disappear.

### 6.2 Derived minimum retained set

The minimum is derived by asking whether removal can change truth, scope, authority, use, contestability, history/currentness or privacy. The mandatory set is:

1. source record/revision, release version and current/superseded state;
2. actual outcome and existing status, without local proxies;
3. claim ID and claim type (`delta`, refusal/negative, or no-number custody);
4. subject/jurisdiction/time/envelope and declared basis;
5. for `delta`: obligation set, maintained assumptions and relative-basis rider;
6. for procedural custody: load-bearing ordered history, sealing, firstness, substitutions/deviations, adjudication, dissent, negative and correction state;
7. material limitations and conditionality;
8. all active denied uses;
9. material counterevidence, attacks and dissent — existence, affected claim and disposition, with protected detail safely redacted;
10. contest/dispute and competent recourse/correction pointer;
11. typed omission/redaction notice and reason;
12. public-safe provenance/full-record binding/current-head pointer;
13. receipt verdict, issue codes and verifier reference.

A deep link to the full record is necessary but not sufficient.

## 7. Loss-typing boundary

### 7.1 Decision procedure

A conforming verifier evaluates, in order:

1. source/revision/use/inventory completeness;
2. categorical mandatory semantics;
3. conservative parity over governed predicates;
4. canonical reason/affected-claim integrity;
5. joint and temporal transcript reconstruction;
6. final two-valued verdict.

Any unknown materiality, missing history, unresolved source item or unavailable check blocks.

### 7.2 Categorical anchors

#### Bare `delta`

Keeping the number while dropping its declared set, assumptions or rider broadens a conditional statement into a false general one. Always `blocked_material_omission`.

#### Hidden refusal/void/dispute/exhaustion

Replacing a completed negative with blank/“unavailable” turns outcome into ambiguity and enables deadline/success-pressure laundering. Always blocked.

#### No-number procedural custody

“The process was properly followed” is not a safe compression of a bounded history claim. If a step such as pre-result sealing, first qualifying attempt, no prohibited substitution, dissent or correction is load-bearing, dropping it broadens the claim. Blocked.

A shorter sentence that explicitly preserves those bounded steps and disclaims compliance/competence/efficacy can be `lossy_but_safe`.

### 7.3 Safe examples

Potentially safe after transcript verification:

- five duplicate references become one while support/conflict/independence semantics remain;
- protected personal name becomes a role while material dissent, mandate and conflict facts remain;
- low-level artifact paths become public-safe references;
- raw cells become an approved aggregate while population/time, uncertainty, contributor rule, conditionality, disclosure reason and denied uses remain;
- repetitive procedural event prose is normalized without removing unique chronology, firstness or substitution facts.

## 8. Cross-view reconstruction

The formal analysis is in [`int-r8/reconstruction-composition-and-threat-model.md`](int-r8/reconstruction-composition-and-threat-model.md).

### 8.1 Consistency-set definition

Let `T` be the complete obtainable disclosure transcript and `𝓡` the declared set of compatible full records:

`C(T) = { r ∈ 𝓡 : the release process for r is observationally consistent with T }`.

A protected predicate `q` is exactly reconstructed when:

`| { q(r) : r ∈ C(T) } | = 1`.

Strict cross-view reconstruction occurs when `q` is not determined by any single obtainable projection but is determined by their union. Temporal reconstruction is the same condition over successive versions.

This formalism applies to deterministic editorial projection and does not require an invented prior.

### 8.2 Transcript denominator

The verifier includes:

- all obtainable canonical audience projections;
- historical versions and corrections;
- diffs and counts;
- hashes, ETags and stable fingerprints;
- ordering, rank, gaps and pagination;
- timing and update cadence;
- provenance and join keys;
- deep-link representation;
- screenshot, print, clipboard and downloadable artifacts;
- hidden DOM/accessibility/embedded metadata;
- caches, logs, analytics/referrer and error channels;
- current/superseded state.

Per-view safety is necessary and insufficient.

## 9. Composition: refusal of a number and accepted alternative

### 9.1 Why differential-privacy composition does not currently transfer

DP composition theorems combine mechanisms that already satisfy explicit local privacy guarantees under a defined neighboring-input relation and randomized output law. The current projection has none of those established premises. Later editorial choices are normally adaptive.

NIST SP 800-226, the Kairouz–Oh–Viswanath composition theorem and maximal-leakage literature therefore supply a premise/audit vocabulary, not a current PolicyOS scalar. The external ledger records exact identifiers and transfer limits.

### 9.2 No-number prefix discipline

Define `Safe_F(T)` as a deterministic predicate over the complete transcript under a fixed versioned check family `F`. If:

1. the base transcript passes;
2. before each release the actual candidate prefix is built with all known channels;
3. release occurs only after the full prefix passes;
4. history is append-only logically, with correction/supersession instead of deletion;
5. membership, chronology, heads, inputs and verifier version are reproducible;

then every released prefix passed `Safe_F` when released. This follows by induction.

The claim is intentionally bounded: it proves enforcement of declared checks, not completeness of attacks or a probability of secrecy. Adaptation is allowed because the actual history-selected candidate is checked; it does not create a numeric adaptive guarantee.

## 10. Screenshot, deep-link and export threat model

### 10.1 Deep links

The current frontend encodes the packet into the path. The URL is therefore itself a release copy, potentially present in browser history, referrers, logs, analytics, previews and support tickets. INT-R8 requires analysis of the decoded URL representation, not merely visible DOM. An opaque-handle architecture may later be chosen, but route/proof design is outside this research.

### 10.2 Screenshot/print

A detached capture must visibly preserve:

- identity/version/currentness;
- claim type/outcome and negative terminal;
- material basis/rider and limitations;
- denied uses;
- material contest/dissent indicator;
- omission notice;
- current-status/full-record reference.

Hover-only, collapsed, off-viewport or print-hidden caveats do not count.

### 10.3 Exports

Every PDF/DOCX/HTML/JSON/CSV/clipboard export is a separate disclosure event. The exact rendered bytes and metadata must be checked for:

- dropped minimum semantics;
- hidden comments/revisions/attachments/source JSON;
- private author/path/reference metadata;
- formulas/raw cells;
- differences from prior releases;
- stale/superseded presentation.

Format conversion is not presumed semantically neutral.

### 10.4 Named no-reconstruction channels

- **Diff:** no raw before/after disclosure of protected content.
- **Hash:** no low-entropy secret membership/persistence oracle; INT-R7 must supply any safe proof binding.
- **Ordering:** no hidden score/rank/gap leakage.
- **Timing:** disclose minimum chronology needed for custody; coarsen non-material precision where necessary.
- **Provenance:** no unauthorized cross-audience join key.
- **Manifest:** enough to prevent misleading silence, not enough to identify the protected value.

## 11. Falsifier suite

The executable behavioral specification is in [`int-r8/falsifier-suite-and-integration-handoff.md`](int-r8/falsifier-suite-and-integration-handoff.md).

Required red cases include:

1. retained limitation dropped;
2. bare `delta` without declared set/rider;
3. hidden refusal/negative terminal;
4. two locally safe projections jointly reconstruct a withheld claim;
5. absent/non-canonical/self-disclosing redaction reason;
6. procedural custody step omitted;
7. denied use narrowed;
8. material dissent/counterevidence rendered as consensus;
9. low-entropy hash oracle;
10. diff/order/timing/provenance reconstruction;
11. screenshot/print drops minimum semantics;
12. export/deep-link contains unrendered protected field;
13. stale record appears current;
14. unknown materiality coerced to safe;
15. receipt mints authority;
16. adaptive release checked locally rather than against the full prefix;
17. prior transcript member removed post hoc;
18. unjustified numeric budget attached.

Positive controls prevent a reject-everything implementation: duplicate references, non-material identity replacement, correctly disclosure-controlled aggregate, faithful no-number history condensation and added conservative caution can pass.

## 12. Repository integration handoff

| Capability | Existing owner/surface to extend | Pinned label | Required behavior |
|---|---|---|---|
| Projection semantics | `runtime/quality/projection_semantics.py` | substrate `implemented`; receipt `producer_missing` | Reuse four audiences, IDs, omissions, limitations, denied uses, contest, recourse, audit refs and authority boundary. |
| Public export | `runtime/quality/public_export.py` | loss `verification_missing`; HTTP `bridge_missing` | Consume exact-revision verified receipt; reject blocked/missing/unknown; do not improvise materiality. |
| Planned loss producer | GY-PA3 runtime-quality plan entry | `producer_missing` | Emit retained/dropped authority delta and receipt only after approved implementation; `authoritative_for = ∅`. |
| Frontend packet/viewer | Atlas DS12/DS14 rendering | receipt `bridge_missing`; capture/export `semantic_test_missing` | Render owner result/minimum set; no client-side safe-loss or authority decision. |
| Release transcript | Existing competent custody/history boundary to be selected by architecture | `producer_missing`, `verification_missing` | Reproduce all releases/channels/heads; no new confidence ledger. |
| INT-R7 proof | Parallel research dependency | `contract_only` until closed | Bind source revision, retained set, omission classes/reasons, verdict and transcript head without exposing drops. |
| Numeric accountant | None | `producer_missing`; research gap | Not authorized. Use no-number discipline. |

This names reuse directions, not canonical owner appointments.

## 13. INT-R7 seam

INT-R8 owns content. It requires INT-R7 to bind:

- source revision;
- audience/surface;
- retained semantic-item set;
- omission classes, affected claims and canonical reasons;
- loss verdict and rule version;
- predecessor/current transcript head and current/superseded state.

Redaction must be a well-defined operation on the proof-bound object, and proof material must not become a hash/identifier oracle for protected content. Signature algorithms, key policy, rotation, revocation, long-term verification and anti-equivocation construction remain with INT-R7.

## 14. Open questions for consolidation

### Engineering

- Which existing custody/history owner can reproduce deep links, screenshots and exports without becoming a second confidence ledger?
- How is the heterogeneous semantic inventory derived without prematurely fixing package/schema cardinality?
- Which renderer/metadata harness will test PDF/DOCX/print/accessibility outputs?
- How will audience-safe provenance remain authorized-resolvable but non-joinable?
- What is fail-closed behavior when historical bytes or metadata are unavailable?

### Institutional

- Which competent office defines “material issue,” canonical reason classes and when dissent identity is material?
- Which audience coalitions/auxiliary sources must be assumed under delegation, FOI, litigation, insider access and copying?
- What recourse/full-record access must an affected person receive when detail is withheld?
- What plain-language, translation and accessibility review establishes comprehensibility without semantic loss?
- What retention/correction obligations govern cached/exported predecessors?

### Additional research

- Can a narrow statistical release class be made genuinely DP with defined adjacency, randomized mechanism and adaptive accountant?
- Which secret predicates/gain functions justify maximal-leakage analysis for policy records?
- Can semantic entailment/materiality checking be made sound enough to admit useful condensation?
- What auxiliary-information model is conservative and testable?
- How should multilingual compression preserve legal qualifiers?
- How do later appeal, incident, retraction, law change or bias findings invalidate prior receipts while preserving history?

## 15. External grounding summary

Primary sources cover at least four jurisdictions/practice systems:

- United States: 5 U.S.C. §§ 552 and 557; Plain Writing Act, Pub. L. 111-274;
- Australia: ADJR Act 1977, s 13, Federal Register `C2004A01697`; FOI Act 1982 `C2004A02562`; NSW MHRT dissent practice; ABS DataLab clearance/output rules;
- European Union: Directive (EU) 2016/2102, CELEX `32016L2102`; EUIPO official summary/full-decision practice;
- United Kingdom: ONS statistical disclosure control and SRS Output Checking Guidance.

Privacy-theoretic anchors are NIST SP 800-226, DOI `10.6028/NIST.SP.800-226`; Kairouz, Oh & Viswanath, PMLR 37 / arXiv `1311.0776`; and Issa, Wagner & Kamath, DOI `10.1109/TIT.2019.2962804` / arXiv `1807.07878`.

The transfer ledger states explicitly what each source does **not** establish.

## 16. Supporting artifacts

- [`int-r8/orientation-ledger.md`](int-r8/orientation-ledger.md) — exact-ref Pass I, censuses, caller/reality audit and reproduction recipe.
- [`int-r8/semantic-contract-and-loss-boundary.md`](int-r8/semantic-contract-and-loss-boundary.md) — full receipt semantics, parity, minimum set, decision procedure and examples.
- [`int-r8/reconstruction-composition-and-threat-model.md`](int-r8/reconstruction-composition-and-threat-model.md) — consistency-set formalism, composition refusal, no-number proposition and release-channel threat model.
- [`int-r8/falsifier-suite-and-integration-handoff.md`](int-r8/falsifier-suite-and-integration-handoff.md) — red/green fixtures, properties, missing-state labels and typed open questions.
- [`int-r8/external-source-and-transfer-ledger.md`](int-r8/external-source-and-transfer-ledger.md) — primary sources, comparative models, selected layers and transfer/non-transfer limits.

## 17. Final ruling

INT-R8 authorizes one narrow research conclusion:

> PolicyOS can define safe compression only as a conservative, use-relative, receipt-bearing transformation of the canonical projection, checked against the complete cross-view and temporal release transcript. A summary is blocked whenever it loses a truth-changing basis, material limitation, denied use, counterposition, dissent, negative outcome, procedural step or currentness fact, or when combined releases reconstruct protected information.

It does not authorize implementation or publication. It does not establish a scalar disclosure budget. The honest current composition result is the no-number procedural discipline described above.
