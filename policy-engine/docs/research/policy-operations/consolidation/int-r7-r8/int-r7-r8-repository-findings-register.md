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
  - classification of producer_missing bridge_missing contract_only institutional_dependency and not_a_defect states
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

This register contains repository defects and capability gaps, not the wave's mathematical or constitutional research results. Every repository observation is pinned to `02c5b8d23c757c92b9231e6e1e802d5701588908`.

Ordinary GitHub DNS was unavailable. Exact-ref reads and complete connected searches were used. Set-level claims state their denominators and distinguish lines, occurrences and files.

Classification vocabulary:

- **live_defect** — present behavior can support a false authority interpretation or cannot distinguish states the current code purports to distinguish;
- **producer_missing** — the governed output producer named by an existing plan/research contract is absent from source;
- **bridge_missing** — both a real producer and an intended consumer/route are identifiable, but the production connection is absent;
- **contract_only** — a plan or research contract exists without source capability;
- **institutional_dependency** — no repository edit alone can establish the required authority, competence, continuity or access;
- **candidate_acceptance_gap** — no current admitted candidate exists, but every future candidate must discharge the stated falsifier;
- **not_a_defect** — an absence is deliberate or correctly refused and must not trigger implementation by itself.

A closure signal states what future independent evidence would have to establish. It is not a design prescription or authorization.

## 2. Summary register

| ID | Finding | Classification | Current consequence | Primary existing destination |
| --- | --- | --- | --- | --- |
| `RFR-01` | signed time and signer identity are outside the signed statement; revocation is timeless | `live_defect` | historical legitimacy cannot be distinguished from post-compromise backdating | DS12 / signing substrate |
| `RFR-02` | real public-export bundle has no public proof issuance or governed verification | `producer_missing` for proof/evaluator | export cannot carry INT-R7 public-verification authority | DS12 |
| `RFR-03` | browser-recomputed public-salt 32-bit FNV token can render `Verified` | `live_defect` | attacker-chosen replacement packet can reproduce its own accepted token | DS12 |
| `RFR-04` | real public-export producer is not wired to an intended production public route | `bridge_missing` | existing producer must not be erased or duplicated, but production path is absent | DS12 |
| `RFR-05` | `CompressionLossReceipt` and material-loss producer are absent | `producer_missing` | INT-R8 contract cannot yet gate or attest a public projection | GY-PA3 |
| `RFR-06` | controlled release-family transcript and exact/proved-conservative reconstruction execution are absent | `contract_only` | prefix discipline and reconstruction dispositions cannot yet be issued | GY-PA3 / custody lanes |
| `RFR-07` | epoch/currentness is planned but not delivered | `contract_only` | no governed `CurrentAuthorityAsOf` result | GY-N12 |
| `RFR-08` | durable replay, expiring authority and legal-hold resilience are undelivered | `contract_only` | long-horizon independently authenticated offline closure remains blocked | OPS-R14 |
| `RFR-09` | proof metadata can reconstruct protected values | `candidate_acceptance_gap` | no future proof candidate may be admitted without channel analysis | DS12 candidate evaluation |
| `RFR-10` | no numerical disclosure/composition/privacy budget owner exists | `not_a_defect` | no canonical number may be issued; no implementation is implied | architect / future product trigger only |
| `RFR-11` | institutional authority, trust, witness, records access and preservation competence are not established by source | `institutional_dependency` | technically valid evidence cannot become institutional authority by code alone | competent governance |

## 3. Detailed findings

### RFR-01 — Signing-time, identity and revocation semantics cannot distinguish historical legitimacy

**Classification:** `live_defect`.

**Pinned evidence**

- The signed `SignatureStatement` contains type, version, algorithm, artifact ID, blob digest, manifest digest and key ID; `DetachedSignature.signed_at` and `signer_identity` are sibling metadata outside that statement: `policy-engine/src/polisyos/core/artifacts/signing.py:53-94`.
- `canonical_statement_bytes()` serializes only the statement, and signing covers those bytes: `signing.py:291-302,389-411`.
- Revocation is a set of key IDs loaded from a directory and tested as timeless membership before signature verification: `signing.py:469-517,583-610`.
- The verifier has no effective revocation time, compromise interval, signing-time status evidence or authenticated historical authority snapshot: `signing.py:539-683`.

**Complete-file lifecycle census**

Denominator: all **768/768 physical lines** of `signing.py`, using the retained exact-token/wildcard recipe in `int-r7/orientation-ledger.md:128-174`. The 15 tested labels are `rotat*`, `transparen*`, `equivocat*`, `split view`, `archiv*`, `algorithm_agility`, `offline`, `expiry`, `not_after`, `valid_until`, `chain`, `trust_root`, `anchor`, `countersign`, and `timestamp`. The controlling remediation reproduces **0 occurrences for each label**. This lexical result is supporting evidence only; the structural finding above is independently visible in the signed model and verifier flow.

A separate complete source census finds **14/14 included Python paths** importing or using `cryptography`, `jwt` or `hmac` under `policy-engine/src/polisyos/` (`int-r7/orientation-ledger.md:71-97`). Primitive availability does not close lifecycle semantics.

**Consequence**

A genuine signature made before compromise and an attacker-created signature made after compromise but accompanied by an earlier editable `signed_at` value cannot be distinguished by the current verification model. Conversely, timeless revocation can erase the distinction between historically authentic issuance and current trust. The current `VALID`/`REVOKED` result therefore cannot support INT-R7's historical/current vector.

**Closure signal**

Future independent verification would need to show, without prescribing representation, that:

1. the issuance-time proposition and the institutional signer/role proposition are authenticated within the proved statement or an equally strong bound evidence relation;
2. verification consumes authenticated status/authority history with an applicable cutoff rather than timeless membership alone;
3. a post-compromise backdated forgery returns a non-positive terminal;
4. a genuine pre-compromise issuance can remain historically authentic while current authority is separately non-positive; and
5. unknown, overlapping or unavailable status evidence cannot inherit a current positive.

**Not authorized:** no field addition, schema change, key migration, certificate profile, timestamp service or patch is selected here.

### RFR-02 — The public-export producer is unsigned and has no governed proof/evaluator

**Classification:** `producer_missing` for the public proof producer and evaluator; the export producer itself is present.

**Pinned evidence**

- `policy-engine/src/polisyos/runtime/quality/public_export.py` is a real **2,103-line** producer: `:1-850,1400-2103`.
- It builds a redacted, projection-only public bundle and returns it without the INT-R7 proof, trusted issuance-time/status evidence, transparency/common-view evidence, preservation evidence or currentness result.
- Complete-file denominator: **2,103/2,103 lines**. The exact inspection found no `Ed25519Signer` integration, detached public-record signature, certificate/status/timestamp/log evidence or public-verifier gate. The earlier `sign`-substring number is not needed to establish the structural absence.
- `core/audit/verifier.py` and `standalone_verifier_template.py` are reusable execution substrates, but their package-relative trust does not establish independently authenticated public authority (`int-r7/orientation-ledger.md:41-47,112-126`).

**Consequence**

The existing bundle may carry projection semantics but cannot be represented as an INT-R7 public-verification result. Projection cannot mint signing, custody or institutional authority under `S0-K07`.

**Closure signal**

A future independently verified path would have to demonstrate that the exact public object and its semantic/projection package are bound to owner-issued evidence; the verifier reports the separate INT-R7 dimensions and typed non-positive outcomes; package-supplied trust cannot self-authenticate; and forged, stale, superseded, unavailable-history and projection-failure fixtures cannot render a positive composite.

**Not authorized:** this finding does not select the proof format, signing subsystem, verifier package, trust root, route or owner.

### RFR-03 — Browser FNV token is forgeable and is consumed as `Verified`

**Classification:** `live_defect`.

**Pinned evidence**

- Public salt: `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:240-247`.
- 32-bit FNV-1a function: `publicationPacket.ts:357-369`.
- Packet token creation and browser recomputation: `publicationPacket.ts:1050-1188`.
- Positive badge consumption: `policy-engine/apps/runtime-dashboard/src/features/runs/pages/PublicDecisionViewerPage.tsx:1-53`.
- Atlas records the predecessor as forgeable and DS12's first negative control requires a forged packet to stop rendering as verified: `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:197-218,1194-1250`.

**Consequence**

The adversary chooses replacement JSON and can compute the matching eight-hex-character value directly; no secret or collision search is required. Browser recomputation demonstrates only internal agreement with attacker-supplied data, not issuer authenticity, projection faithfulness, history, currentness or durable verification.

**Closure signal**

The exact Atlas negative control must pass: an attacker-generated or modified packet with a recomputed legacy token cannot render or serialize any governed positive-verification claim. Any retained checksum must be explicitly non-authoritative and incapable of satisfying a proof gate.

**Not authorized:** no replacement cryptographic mechanism or UI wording is selected.

### RFR-04 — Existing public-export producer has no production bridge to the intended public path

**Classification:** `bridge_missing`.

**Pinned complete-set evidence**

Two different denominators are required:

1. Search universe: every Python file below `policy-engine/src`; unit: distinct files containing the exact symbol text `build_public_export_bundle`. Result: **2 files** — the definition in `runtime/quality/public_export.py` and a re-export in `runtime/quality/__init__.py`.
2. Search universe: every Python file in the complete repository tree; unit: distinct files containing the exact invocation/definition token `build_public_export_bundle(`. Result: **5 files** — the definition plus two tool callers and two unit-test callers. Therefore there are **4 caller files outside the definition**. The `__init__.py` re-export is not a caller.

The exact five-file set is recorded at `int-r8/orientation-ledger.md:99-131`. No file below `policy-engine/src/polisyos/runtime/http/` calls the producer.

**Consequence**

Calling the bundle producer absent would erase existing capability and risk a duplicate implementation. Calling the public path delivered would overclaim. The precise state is: producer present, intended production bridge absent.

**Closure signal**

Future evidence must show an end-to-end production invocation from the intended public route to the existing producer, consumption of the governed proof/loss/currentness results, and negative-control behavior. A second competing export producer is not a closure.

**Not authorized:** no route, controller, service or deployment topology is selected.

### RFR-05 — Compression-loss receipt and material-loss producer are absent

**Classification:** `producer_missing`.

**Pinned complete-file token census**

Denominator: all **2,103/2,103 lines** of `public_export.py`. Units are both matched lines and literal occurrences:

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

A second exact-token source census over **all files below `policy-engine/src`** finds **0 source files** for each of `disclosure_budget`, `composition_budget`, `privacy_budget`, `compression_loss`, and `CompressionLoss` (`int-r8/orientation-ledger.md:133-153`). Planning/research mentions are not capability.

**Consequence**

Existing projection owners provide omission, redaction, gaps, contest, recourse, denied-use, limitation and authority-boundary substrate, but no controlling `lossy_but_safe` / `blocked_material_omission` producer or `CompressionLossReceipt`. A public projection therefore cannot yet demonstrate INT-R8 conformance.

**Closure signal**

A future producer must extend the existing projection/omission owners, bind the controlling semantic contract and rule/model versions, return typed positive or blocking dispositions, preserve denied uses and negative terminals, and pass the 78-row suite with **0/78** unsafe approximation paths. It must not create a parallel confidence/currentness/status ledger.

**Not authorized:** no receipt schema, storage location, enum or API is selected.

### RFR-06 — Release-family custody and reconstruction execution are contract-only

**Classification:** `contract_only`.

**Pinned evidence**

INT-R8 defines the required controlled transcript, release-family versions, exact model inputs, consistency-set results and typed dispositions at `int-r8-compression-loss-and-disclosure.md:201-315` and `semantic-contract-and-loss-boundary.md:429-459`. The repository contains no source owner named by the complete exact-token census for disclosure/composition budgets or compression loss, and the channel registry is explicitly open. No pinned source path establishes a custody transcript that can prove controlled membership, chronology, predecessor/current heads, completeness and correction non-rewrite for this release family.

**Consequence**

The repository cannot yet issue prefix discipline or an executable reconstruction/non-reconstruction result. A solver invocation without the exact retained inputs, model/rule versions, transcript and evaluator disposition would not close the offline-proof requirement.

**Closure signal**

Independent evidence must reproduce the controlled family membership and chronology; bind model, protected-predicate, coalition, auxiliary-information and channel assumptions; return exact/proved-conservative or typed non-establishment dispositions; preserve historical results append-only; and make every historical result replayable or challengeable offline under OPS-R14-grade custody.

**Not authorized:** no transcript store, solver, abstraction, time limit, model owner or channel list is selected.

### RFR-07 — Epoch/currentness capability is absent from the delivered source path

**Classification:** `contract_only`.

**Pinned evidence**

GY-N12 is the canonical plan/research owner of epoch identity, stale/revalidation semantics, append-only reissue and open-world risk. INT-R7 consumes it and explicitly does not create a second epoch manager or status lattice (`int-r7/orientation-ledger.md:71-83`; `int-r7/public-verification-profile.md:360-399`). No currentness capability is claimed by the pinned source census.

**Consequence**

The repository cannot issue `CurrentAuthorityAsOf(t_q)` or reliably distinguish current, stale, superseded, withdrawn and unknown states. Historical authenticity alone must not be displayed as current authority.

**Closure signal**

GY-N12's eventual evidence must bind epoch identity, authenticated latest-applicable snapshot selection, rollback resistance, predecessor/successor relation, stale/unknown outcomes and append-only history, and must integrate without creating a second currentness owner.

**Not authorized:** no status schema, expiry interval, event format or GY-N12 implementation is selected.

### RFR-08 — Long-horizon independently authenticated offline closure is undelivered

**Classification:** `contract_only` under the already declared OPS-R14 dependency.

**Pinned evidence**

The nearest offline substrates are `core/audit/verifier.py` (**981 lines**) and `core/audit/standalone_verifier_template.py` (**559 lines**), but they do not supply independently authenticated public trust, signing-time revocation, public common-view evidence, archival renewal or currentness. OPS-R14 already owns custody-grade resilience, expiring authority, long-term replay of signed records and legal-hold override. INT-R7 requires long-term preservation/re-anchoring and independently authenticated disconnected verification; it does not invent the missing mechanics.

**Consequence**

A result may be locally or package-relatively replayable without proving that its trust/status/model/transcript evidence remains independently authentic years later. The first-public-signature gate remains closed.

**Closure signal**

OPS-R14 or a later architect-routed implementation must demonstrate authenticated evidence retention, renewal before algorithm/evidence expiry, recoverable current/superseded history, compromised-primary behavior, legal-hold interaction, and real-path disconnected replay with negative controls. Package-supplied keys alone may not self-anchor trust.

**Not authorized:** no archive, LTA/ERS profile, retention period, timestamp provider, recovery topology or legal-hold policy is selected.

### RFR-09 — Proof metadata is an unresolved candidate acceptance channel

**Classification:** `candidate_acceptance_gap`, not a present implementation defect.

**Pinned evidence**

INT-R8 constructs a cross-view attack over key identifiers, certificate/credential paths, commitment identifiers, transparency-log positions, witness sets, proof-object sizes and linkage patterns: `int-r8-compression-loss-and-disclosure.md:318-355`; `int-r8/reconstruction-composition-and-threat-model.md:425-436`. INT-R7 requires privacy-safe addressing and prohibits proof metadata from becoming a protected-value oracle: `int-r7/public-verification-profile.md:649-670`.

**Consequence**

A proof can be cryptographically correct and still violate the semantic-loss boundary through its topology or auxiliary fields. No candidate proof exists in the pinned repository, so there is no implementation to declare defective and no mitigation to endorse.

**Closure signal**

Every future DS12 proof candidate must include all public proof metadata in the declared channel/coalition/auxiliary-information model and pass exact or proved-conservative reconstruction tests for protected predicates. An omitted metadata class, unproved approximation or unknown external join remains blocking/not established.

**Not authorized:** no padding, batching, encryption, identifier, credential, log or witness mitigation is selected.

### RFR-10 — Absence of a numerical disclosure budget owner is deliberate, not a defect

**Classification:** `not_a_defect`.

**Pinned evidence**

The all-source exact-token census records 0 files for `disclosure_budget`, `composition_budget` and `privacy_budget`. The controlling INT-R8 analysis also establishes that the repository lacks the necessary secret/channel/support or prior/gain model, prospectively valid local bounds, applicable composition theorem, selection-valid adaptive conditions, canonical owner and named protected consumer.

**Consequence**

No canonical numerical disclosure, leakage, privacy or remaining-budget claim is justified. The absence must not be converted into a speculative owner, second ledger or implementation task without a concrete product/model trigger.

**Closure signal**

This state changes only after a named use establishes all `INT-K04`/`INT-K07` premises and a competent architect assigns one canonical owner and consumer. Until then, the accepted authority-band claim is no-number prefix discipline.

**Not authorized:** no numerical research program, epsilon, score, threshold, owner or budget service is commissioned here.

### RFR-11 — Institutional authority and continuity are outside repository capability

**Classification:** `institutional_dependency`.

**Pinned evidence**

INT-R7's profile requires independently evidenced issuer mandate, audience/jurisdiction/claim-class authority, key/status governance, common-view witnesses, preservation, succession and public evidence access. Source can encode and verify evidence but cannot appoint or fund a competent issuer, legal authority, log/witness community, records custodian, archive, timestamp authority or successor. The ratified `S0-K05` and `S0-K07` rules prevent cryptographic possession or projection from minting those roles.

**Consequence**

Even a technically conforming implementation cannot assert institutional or legal sufficiency without separate competent evidence and governance. These conditions may block first publication after engineering is complete.

**Closure signal**

A competent architecture/governance act must identify the applicable authority relationships, delegation/succession evidence, public access and retention commitments, independence requirements, operating continuity and limitation disclosures. Legal sufficiency remains jurisdiction-specific and outside this register.

**Not authorized:** no institution, owner, vendor, custodian, log operator, witness, archive or certificate authority is appointed.

## 4. Findings that must not be collapsed

| Distinct states | Why the distinction matters |
| --- | --- |
| export producer present vs proof producer absent | prevents erasing and reimplementing `public_export.py` |
| proof producer absent vs production bridge absent | a producer can exist without being wired, and a bridge can exist only between known endpoints |
| research contract present vs source capability present | planning or Markdown cannot satisfy a public gate |
| present defect vs future candidate falsifier | proof-metadata leakage is mandatory to test, but no current candidate can be condemned or fixed |
| deliberate numerical refusal vs missing implementation | absence of a budget owner is currently correct, not technical debt |
| source capability vs institutional authority | code cannot appoint, delegate or establish legal competence |
| historical authenticity vs current authority | revocation or withdrawal must not erase history, and history must not imply currency |

## 5. Gate and standing effects

- `RFR-01` through `RFR-08` and `RFR-11` are sufficient to keep both first-public gates closed regardless of the research-input closure.
- `RFR-09` is a mandatory future candidate acceptance test.
- `RFR-10` confirms that DS12 and the present release path do not need or possess a numerical disclosure number.
- None of these findings changes the registered standing of `GY-GAP1`, `GY-GAP2`, `INT-GAP-01`, `INT-GAP-02`, `OPS-R14` or `S0-GAP-02`.

## 6. Register boundary

This register identifies what the pinned repository does and does not establish. It does not authorize any fix, route edit, owner appointment, implementation, release or publication.
