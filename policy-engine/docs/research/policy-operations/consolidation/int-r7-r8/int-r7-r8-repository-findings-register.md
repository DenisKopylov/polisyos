---
title: "INT-R7 / INT-R8 — Repository findings register"
status: delivered
kind: research-repository-findings-register
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r7-r8-consolidation
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
int_r7_controlling_head: 3883b45476aed138beface8c8ca817191c7e273e
int_r8_controlling_head: 286ade1057c9abb95bb1cf2c962479906f764667
inspection_date: 2026-08-05
research_only: true
authoritative_for:
  - repository defects capability gaps and deliberate absences established at the pinned baseline
  - classification of producer_missing bridge_missing contract_only institutional_dependency candidate_acceptance_gap and not_a_defect states
  - evidence-bounded closure signals for later independent verification
  - separation of repository facts from research propositions and implementation authorization
may_not_use_for:
  - authorizing or prescribing a repository fix
  - selecting a wire schema package database serialization enum status lattice API cryptographic suite or service
  - appointing an owner vendor operator custodian witness log archive timestamp service or certificate authority
  - claiming legal sufficiency institutional competence or jurisdictional compliance
  - permission to open either first-public gate or publish a governed result
  - issuing a numerical disclosure privacy leakage confidence or safety bound
  - claiming that an absent bridge producer verifier receipt currentness service or custody capability exists
  - automatic amendment of a plan backlog system-design decision failure-pattern register or AGENTS.md
execution_environment: connected_exact_ref_only_due_to_unavailable_ordinary_github_dns
---

# INT-R7 / INT-R8 repository findings register

## 1. Scope and classification vocabulary

This register contains repository defects, capability gaps, and deliberate non-capabilities. It does not restate the wave's mathematical or constitutional conclusions as source-code facts. Every repository observation is pinned to `02c5b8d23c757c92b9231e6e1e802d5701588908`.

Ordinary GitHub DNS was unavailable. Exact-ref connector reads and complete pinned enumerations were used. Set-level claims state the searched universe, unit, and denominator; matched lines, literal occurrences, and distinct files are not interchanged.

Classification vocabulary:

- **`live_defect`** — present behavior can support a false authority interpretation or cannot distinguish states the code purports to distinguish;
- **`producer_missing`** — an output producer required by an existing plan/research contract is absent from source;
- **`bridge_missing`** — a real producer and intended consumer/route are known, but the production connection is absent;
- **`contract_only`** — a plan or research contract exists without the source capability needed to issue its result;
- **`institutional_dependency`** — no repository edit alone can establish the required mandate, competence, independence, continuity, or access;
- **`candidate_acceptance_gap`** — no current admitted candidate exists, but every future candidate must discharge the named falsifier;
- **`not_a_defect`** — the absence is deliberate or correctly refused and must not trigger implementation by itself.

A closure signal identifies evidence a later independent verifier would require. It is not a design prescription or authorization.

## 2. Summary register

| ID | Finding | Classification | Current consequence | Existing destination |
| --- | --- | --- | --- | --- |
| `RFR-01` | `signed_at` and `signer_identity` are outside the signed statement while revocation is timeless | `live_defect` | genuine pre-compromise issuance cannot be distinguished from a post-compromise backdated forgery | DS12 / signing substrate |
| `RFR-02` | the real public-export bundle has no owner-issued public proof or governed verifier | `producer_missing` for proof/evaluator | export cannot carry INT-R7 public-verification authority | DS12 |
| `RFR-03` | a public-salt 32-bit FNV token is recomputed over attacker-selectable packet content and accepted as valid | `live_defect` | packet self-consistency can be mistaken for issuer verification | DS12 |
| `RFR-04` | the real public-export producer is not connected to an intended production public route | `bridge_missing` | existing producer must not be erased or duplicated, but the public path is absent | DS12 |
| `RFR-05` | `CompressionLossReceipt` and material-loss producer are absent | `producer_missing` | INT-R8 cannot yet gate or attest a public projection in source | GY-PA3 |
| `RFR-06` | controlled release-family transcript and exact/proved-conservative reconstruction execution are absent | `contract_only` | prefix discipline and reconstruction dispositions cannot yet be issued | GY-PA3 / custody lanes |
| `RFR-07` | epoch/currentness is planned but not delivered | `contract_only` | no governed `CurrentAuthorityAsOf` result | GY-N12 |
| `RFR-08` | durable replay, expiring authority, disconnected verification, and legal-hold resilience are undelivered | `contract_only` | long-horizon offline proof remains blocked | OPS-R14 |
| `RFR-09` | public proof metadata and topology can reconstruct protected content | `candidate_acceptance_gap` | no future proof candidate may be admitted without channel analysis | DS12 candidate evaluation |
| `RFR-10` | no numerical disclosure/composition/privacy budget owner exists | `not_a_defect` | no canonical number may be issued; no speculative service is implied | architect / future product trigger only |
| `RFR-11` | institutional authority, trust, witness, records access, preservation, and continuity are not established by source | `institutional_dependency` | technical validity cannot become institutional authority by code alone | competent governance |

## 3. Detailed findings

### RFR-01 — Signing-time, identity, and revocation semantics cannot distinguish historical legitimacy

**Classification:** `live_defect`.

**Pinned evidence**

- `SignatureStatement` contains type, version, algorithm, artifact ID, blob digest, manifest digest, and key ID. `DetachedSignature.signed_at` and `signer_identity` are sibling metadata outside that statement: `policy-engine/src/polisyos/core/artifacts/signing.py:53-94`.
- `canonical_statement_bytes()` serializes the statement and the signing operation covers those bytes: `signing.py:291-302,389-411`.
- Revocation is a set of key IDs loaded from a revoked-key directory and tested as timeless membership before signature verification: `signing.py:469-517,583-610`.
- The verifier has no effective-revocation time, compromise interval, authenticated signing-time status, or historical authority snapshot: `signing.py:539-683`.

**Complete-file lifecycle census**

Universe: all **768/768 physical lines** of `signing.py`. The retained exact-token/wildcard recipe in `int-r7/orientation-ledger.md:128-174` tests fifteen lifecycle labels: `rotat*`, `transparen*`, `equivocat*`, `split view`, `archiv*`, `algorithm_agility`, `offline`, `expiry`, `not_after`, `valid_until`, `chain`, `trust_root`, `anchor`, `countersign`, and `timestamp`. The controlling remediation reproduces **0 occurrences for each label**. This lexical result supports, but does not replace, the structural inspection above.

A separate complete source census finds **14/14 included Python paths** importing or using `cryptography`, `jwt`, or `hmac` under `policy-engine/src/polisyos/` (`int-r7/orientation-ledger.md:71-97`). Primitive availability does not close public-record lifecycle semantics. `core/security/rotation.py` rotates JWT trust anchors and deployment keys, not public-record signatures.

**Consequence**

An attacker holding a compromised private key can create a new valid signature and pair it with editable earlier `signed_at` metadata. The current verifier cannot distinguish that case from a genuine pre-compromise issuance. Timeless revocation also collapses historical authenticity and current trust into one present membership test.

**Closure signal**

Later independent verification must establish, without prescribing representation, that:

1. issuance time and institutional signer/role identity are authenticated inside the proved statement or an equally strong bound relation;
2. verification consumes authenticated status/authority history at an applicable cutoff, not timeless membership alone;
3. a post-compromise backdated forgery returns a non-positive terminal;
4. genuine pre-compromise issuance can remain historically authentic while current authority is separately non-positive; and
5. unknown, overlapping, stale, or unavailable status evidence cannot inherit a current positive.

**Not authorized:** no field, schema, key migration, certificate profile, timestamp service, or patch is selected.

### RFR-02 — Public export is a real producer but has no governed proof producer or evaluator

**Classification:** `producer_missing` for public proof/evaluator; the export producer itself is present.

**Pinned evidence**

- `policy-engine/src/polisyos/runtime/quality/public_export.py` is a real **2,103-line** bundle producer.
- It emits a redacted projection-only bundle without an INT-R7 owner-issued proof, trusted issuance-time/status evidence, transparency/common-view evidence, preservation evidence, currentness result, or vector verifier gate.
- Universe: all **2,103/2,103 physical lines**. The complete controlling inspection found no public-record Ed25519 integration, detached proof issuance, certificate/status/timestamp/log package, or public-verification gate. The `sign`-family matches are substrings of design-record identifiers, not public signing capability.
- `core/audit/verifier.py` (**981 lines**) and `core/audit/standalone_verifier_template.py` (**559 lines**) are nearby execution substrates. Their package-relative trust does not establish independently authenticated public authority (`int-r7/orientation-ledger.md:41-47,112-126`).

**Consequence**

The bundle may carry projection semantics, but it cannot be represented as an INT-R7 public-verification result. Projection cannot mint signing, custody, or institutional authority under `S0-K07`.

**Closure signal**

A later path must independently show that the exact public object and semantic/projection package are bound to owner-issued evidence; the verifier reports each INT-R7 dimension and typed non-positive outcomes; package-supplied trust cannot self-authenticate; and forged, stale, superseded, unavailable-history, projection-failure, and currentness-unknown fixtures cannot render a positive composite.

**Not authorized:** no proof format, signing subsystem, verifier package, trust root, route, or owner is selected.

### RFR-03 — The public packet's FNV token is forgeable by construction

**Classification:** `live_defect`.

**Pinned evidence**

- `publicationPacket.ts:240-247` defines a source-visible `SIGNATURE_SALT`.
- `publicationPacket.ts:357-371` implements a 32-bit FNV-1a-style `stableHash` and returns eight hexadecimal characters.
- `publicationPacket.ts:1053-1063` computes `sig:${stableHash(SIGNATURE_SALT + stableJson(payload))}`.
- `publicationPacket.ts:1112-1186` serializes the packet and token into `signedId`, then parses attacker-supplied payload content, recomputes the same token, and returns `valid: true` when they agree.
- The controlling INT-R7 repository orientation and audit chain records that the public viewer consumes this predecessor as a `Verified` presentation (`int-r7-public-verification-lifecycle.md:105-123`). Atlas DS12 records it as forgeable and declares the first negative control: a forged packet must stop rendering as verified (`POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:197-218,1194-1250`).

**Consequence**

The adversary chooses replacement JSON and can compute its matching token directly. No secret, collision search, or issuer key is required. Browser recomputation establishes only internal agreement with attacker-selected data; it does not establish issuance authenticity, projection faithfulness, public history, currentness, or durable verification.

**Closure signal**

The exact Atlas negative control must pass: an attacker-created or modified packet with a recomputed legacy token cannot render or serialize any governed positive-verification claim. Any retained checksum must be visibly and mechanically non-authoritative and incapable of satisfying the proof gate.

**Not authorized:** no replacement cryptographic mechanism, packet format, or UI wording is selected.

### RFR-04 — The existing export producer has no production bridge to the intended public route

**Classification:** `bridge_missing`.

**Pinned complete-set evidence**

Two denominators are intentionally distinct:

1. Universe: every Python file below `policy-engine/src`; unit: distinct files containing exact symbol text `build_public_export_bundle`. Result: **2 files** — the definition in `runtime/quality/public_export.py` and a re-export in `runtime/quality/__init__.py`.
2. Universe: every Python file in the complete repository tree; unit: distinct files containing exact invocation/definition token `build_public_export_bundle(`. Result: **5 files** — the definition plus `tools/ops_runners/runtime/canary_evidence.py`, `tools/quality/validation/check_layer3_workflow_failure_authority.py`, `tests/unit/runtime/quality/test_public_export.py`, and `tests/unit/runtime/quality/test_multi_tenant_shared_cas.py`.

Therefore there are **4 caller files outside the definition**. `runtime/quality/__init__.py` is a re-export, not a caller. The exact set is recorded at `int-r8/orientation-ledger.md:99-131`. There is no production caller outside the defining module and no HTTP route.

**Consequence**

Calling the producer absent would erase real capability and invite duplicate implementation. Calling the public path delivered would overclaim. The exact state is producer present, intended production bridge absent.

**Closure signal**

Later evidence must show an end-to-end production invocation from the intended public route to the existing producer, consumption of governed proof/loss/currentness outputs, and negative-control behavior. A second competing export producer is not closure.

**Not authorized:** no route, controller, service, or deployment topology is selected.

### RFR-05 — Compression-loss receipt and material-loss producer are absent

**Classification:** `producer_missing`.

**Pinned complete-file token census**

Universe: all **2,103/2,103 physical lines** of `public_export.py`. Units are both matched lines and literal occurrences:

| Exact token | Matched lines | Literal occurrences |
| --- | ---: | ---: |
| `omitted_claim` | 8 | 9 |
| `projection_faithfulness` | 13 | 13 |
| `redaction_reason` | 2 | 2 |
| `omissions_manifested` | 2 | 2 |
| `lossy` | 0 | 0 |
| `blocked_material` | 0 | 0 |
| `compression` | 0 | 0 |
| `retained_limitation` | 0 | 0 |

Source: `int-r8/orientation-ledger.md:45-70`.

A second exact-token census over **all files below `policy-engine/src`** finds **0 source files** for each of `disclosure_budget`, `composition_budget`, `privacy_budget`, `compression_loss`, and `CompressionLoss` (`int-r8/orientation-ledger.md:133-153`). Planning and research mentions are not capability.

The repository already has the owners the receipt should extend: `_omission_manifest`, `_normalize_omission`, `_dedupe_omissions`, `_redaction_summary`, `_projection_gaps`, `_closeout_limitations`, `_deficit_register`, `_contested_records`, `_recourse_projection`, `_participation_surface`, `_audience_visibility`, `_invariant_summary`, `_audit_refs`, `assert_policy_design_projection_not_authority`, four canonical audiences at `projection_semantics.py:651-655`, and S9-S14 `*_authority_laundered` checks. A complete Python-file census finds `may_not_use_for` in **106 distinct token-containing files**, partitioned **67 runtime + 12 scientist + 27 remainder**.

**Consequence**

Existing projection semantics provide omission, redaction, gap, limitation, contest, recourse, audience, denied-use, and no-authority-laundering substrate. They do not produce controlling `lossy_but_safe` / `blocked_material_omission` dispositions or a `CompressionLossReceipt`.

**Closure signal**

A later producer must extend those existing owners; bind the controlling semantic contract and rule/model versions; preserve denied uses, negative terminals, contest, recourse, and currentness limitations; return typed positive or blocking outcomes; and pass the **78-row** suite with **0/78** unsafe-approximation passes. It must not create a parallel confidence, currentness, or status ledger.

**Not authorized:** no receipt schema, storage location, enum, endpoint, or API is selected.

### RFR-06 — Release-family custody and reconstruction execution are contract-only

**Classification:** `contract_only`.

**Pinned evidence**

INT-R8 defines controlled release-family membership, chronology, predecessor/current heads, exact model inputs, consistency-set results, and typed verifier dispositions at `int-r8-compression-loss-and-disclosure.md:201-315` and `int-r8/semantic-contract-and-loss-boundary.md:429-459`. The channel registry is explicitly open. No pinned source path establishes a custody transcript that can prove controlled membership, completeness, correction non-rewrite, model/rule versions, and historical dispositions for this release family.

**Consequence**

The repository cannot yet issue prefix discipline or an executable reconstruction/non-reconstruction result. A solver status without retained exact inputs, model/rule identity, transcript, evaluator context, and completeness disposition does not satisfy offline proof.

**Closure signal**

Independent evidence must reproduce controlled membership and chronology; bind protected predicates, coalition/delegation model, auxiliary assumptions, channel registry, and evaluator inputs; return exact/proved-conservative or typed non-establishment dispositions; preserve historical results append-only; and make each historical evaluation replayable or challengeable offline under OPS-R14-grade custody.

**Not authorized:** no transcript store, solver, abstraction, time limit, model owner, or channel list is selected.

### RFR-07 — Epoch/currentness capability is absent

**Classification:** `contract_only`.

**Pinned evidence**

GY-N12 is the canonical plan/research owner of epoch identity, stale/revalidation semantics, append-only reissue, and open-world currentness risk. INT-R7 consumes that output and explicitly does not create a second epoch manager or status lattice (`int-r7/public-verification-profile.md:360-399`; `int-r7/orientation-ledger.md:71-83`). No currentness capability is claimed by the pinned source census.

**Consequence**

The repository cannot issue `CurrentAuthorityAsOf(t_q)` or reliably distinguish current, stale, superseded, withdrawn, and unknown states. Historical authenticity alone must not be displayed as current authority.

**Closure signal**

GY-N12's eventual evidence must bind epoch identity, authenticated latest-applicable snapshot selection, rollback resistance, predecessor/successor relation, stale/unknown outcomes, and append-only history, and must integrate without creating a second currentness owner.

**Not authorized:** no status schema, expiry interval, event format, or GY-N12 implementation is selected.

### RFR-08 — Long-horizon independently authenticated offline closure is undelivered

**Classification:** `contract_only` under the existing OPS-R14 dependency.

**Pinned evidence**

The nearest offline substrates are `core/audit/verifier.py` (**981 lines**) and `core/audit/standalone_verifier_template.py` (**559 lines**). They do not provide independently authenticated public trust, signing-time revocation history, public common-view evidence, archival renewal, release-family evidence, or currentness. OPS-R14 already owns custody-grade resilience, expiring authority, long-term replay of signed records, and legal-hold override. INT-R7 requires long-term preservation/re-anchoring and independently authenticated disconnected verification; it does not invent the missing mechanics.

**Consequence**

A result may be locally or package-relatively replayable without proving that its trust, status, model, transcript, and preservation evidence remain independently authentic years later. The first-public-signature gate remains closed.

**Closure signal**

OPS-R14 or a later architect-routed implementation must demonstrate authenticated evidence retention, timely renewal before algorithm/evidence expiry, recoverable current/superseded history, compromised-primary behavior, legal-hold interaction, and real-path connected and disconnected replay with negative controls. Package-supplied keys alone may not self-anchor trust.

**Not authorized:** no archive, LTA/ERS profile, retention period, timestamp provider, recovery topology, or legal-hold policy is selected.

### RFR-09 — Proof metadata is an unresolved candidate-acceptance channel

**Classification:** `candidate_acceptance_gap`, not a present implementation defect.

**Pinned evidence**

INT-R8 constructs a cross-view attack over key identifiers, certificate/credential paths, commitment identifiers, transparency-log positions, witness sets, proof-object sizes, and linkage patterns: `int-r8-compression-loss-and-disclosure.md:318-355`; `int-r8/reconstruction-composition-and-threat-model.md:425-436`. INT-R7 requires privacy-safe addressing and prohibits proof metadata from becoming a protected-value oracle: `int-r7/public-verification-profile.md:649-670`.

**Consequence**

A proof can be cryptographically correct while violating the semantic-loss boundary through topology or auxiliary fields. No candidate public-proof implementation exists in the pinned repository, so no mitigation can be declared conforming or defective.

**Closure signal**

Every future DS12 proof candidate must include all public proof metadata in the declared channel, coalition, and auxiliary-information model and pass exact or proved-conservative reconstruction tests for protected predicates. An omitted metadata class, unknown external join, incomplete history, or unproved approximation remains blocking or `not_established`.

**Not authorized:** no padding, batching, encryption, identifier, credential, log, witness, or proof-size mitigation is selected.

### RFR-10 — Absence of a numerical disclosure budget owner is deliberate

**Classification:** `not_a_defect`.

**Pinned evidence**

The all-source exact-token census records **0 files** for `disclosure_budget`, `composition_budget`, and `privacy_budget`. The controlling INT-R8 analysis also finds no admitted secret/channel/support or prior/gain model, locally valid measure, applicable composition theorem, selection-valid adaptive conditions, prospectively enforced custody, canonical owner, or named protected consumer.

**Consequence**

No canonical numerical disclosure, privacy, leakage, remaining-budget, or cumulative-risk claim is justified. The absence must not be converted into a speculative owner, second ledger, or implementation task. The accepted current authority claim is no-number prefix discipline.

**Closure signal**

This state changes only after a named product use establishes all `INT-K04`/`INT-K07` premises and a competent architect assigns one canonical owner and protected consumer, followed by independent verification.

**Not authorized:** no epsilon, score, threshold, budget service, owner, or numerical research commission is created.

### RFR-11 — Institutional authority and continuity are outside repository capability

**Classification:** `institutional_dependency`.

**Pinned evidence**

INT-R7's profile requires independently evidenced issuer mandate, audience/jurisdiction/claim-class authority, key/status governance, common-view witnesses, preservation, succession, and public evidence access. Source can encode and verify evidence but cannot appoint or fund a competent issuer, legal authority, witness community, log operator, records custodian, archive, timestamp authority, or successor. Findings `S0-K05` and `S0-K07` prevent cryptographic possession or projection from minting those roles.

**Consequence**

Even a technically conforming implementation cannot assert institutional or legal sufficiency without separate competent evidence and governance. Institutional conditions can remain blocking after engineering is complete.

**Closure signal**

A competent architecture/governance act must establish the applicable authority relationships, delegation and succession evidence, public access and retention commitments, independence criteria, operating continuity, funding, challenge process, and explicit limitations. Legal sufficiency remains jurisdiction-specific and outside this register.

**Not authorized:** no institution, owner, vendor, custodian, log operator, witness, archive, timestamp authority, or certificate authority is appointed.

## 4. States that must not be collapsed

| Distinct states | Why the distinction matters |
| --- | --- |
| export producer present vs proof producer absent | prevents erasing and reimplementing `public_export.py` |
| proof producer absent vs production bridge absent | a producer may exist without being wired, and a bridge requires known endpoints |
| research contract present vs source capability present | Markdown and plans cannot satisfy a public gate |
| present defect vs future candidate falsifier | proof-metadata leakage is mandatory to test, but no current candidate can be patched or condemned |
| deliberate numerical refusal vs missing implementation | absence of a budget owner is currently correct, not technical debt |
| source capability vs institutional authority | code cannot appoint, delegate, or establish legal competence |
| historical authenticity vs current authority | revocation or withdrawal must not erase history, and history must not imply currency |
| checksum self-consistency vs owner-issued proof | recomputation over public data does not establish issuer authority |

## 5. Gate and standing effects

- `RFR-01` through `RFR-08` and `RFR-11` are sufficient to keep both first-public gates closed regardless of research-input closure.
- `RFR-09` is a mandatory future candidate-acceptance test.
- `RFR-10` confirms that DS12 and the present release path neither need nor possess a numerical disclosure number.
- None of these findings changes the registered standing of `GY-GAP1`, `GY-GAP2`, `INT-GAP-01`, `INT-GAP-02`, `OPS-R14`, or `S0-GAP-02`.

## 6. Register boundary

This register identifies what the pinned repository does and does not establish. It does not authorize a fix, route edit, owner appointment, implementation, release, promotion, or publication.
