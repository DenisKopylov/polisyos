---
title: INT-R7 — Independent Orientation Error Ledger
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass I disposition of every O-01 through O-17 orientation entry
  - explicit record of the missed same-day ratification error
  - repository-orientation findings INT-R7-I-001 through INT-R7-I-006
may_not_use_for:
  - production implementation authorization
  - amendment of the audited research or binding architecture
  - final schema, wire, package, serialization, database, or API contract
  - owner, operator, vendor, trust-service, witness, archive, or key-custodian appointment
  - legal sufficiency or jurisdictional compliance conclusion
  - capability or benchmark passage claim
research_only: true
---

# INT-R7 independent orientation error ledger

## 1. Method boundary

This pass independently re-derived every entry in the audited orientation ledger at
`f5671253b51554dde2dd22a6aef2ef827c5bd9dd` against repository objects pinned to
`02c5b8d23c757c92b9231e6e1e802d5701588908`.

The exact baseline-to-head comparison is reproducible through the connected GitHub interface:
**10 commits ahead, 0 behind, 10 added Markdown files, 5,250 additions, 0 deletions, and no
modified or renamed files**. The merge base is the pinned baseline.

An ordinary clone and codeload archive were unavailable because outbound GitHub DNS/egress
failed. The audit therefore does not promote a global lexical count unless the connected
interface returned a complete bounded set whose denominator could be retained. Named source
matches were opened individually. This distinction is important for O-05 and O-09.

Verdicts:

- `confirmed` — independently established at the pinned object;
- `confirmed_with_narrowing` — core conclusion stands after a stated scope correction;
- `corrected` — supplied assertion was false and is replaced below;
- `not_established` — exact assertion cannot be warranted from the retained evidence;
- `not_applicable` — design interpretation rather than a repository fact.

## 2. Entry-by-entry re-derivation

| Entry | Audited assertion | Independent verdict | Evidence and reasoning |
| --- | --- | --- | --- |
| O-01 | `core/artifacts/signing.py` is a 768-line Ed25519 detached-signature module with key IDs, canonical statement bytes, trust/revocation directories, verification states, and bulk reports. | **confirmed** | `policy-engine/src/polisyos/core/artifacts/signing.py:1-768 @ 02c5b8d`. `SignatureStatement`, `DetachedSignature`, Ed25519 signer/verifier, `VALID/UNSIGNED/INVALID/UNTRUSTED/REVOKED/ERROR`, local trust and revoked-key directories, and report types are present. |
| O-02 | The supplied full-file lifecycle vocabulary census is exactly zero for every term. | **not_established for the lexical zero table; semantic conclusion confirmed** | Exact-ref reading establishes no represented certificate path, trusted timestamp token, effective revocation time, compromise interval, transparency receipt, witness/common-view proof, archival renewal, or historical/current record split in this owner. The researcher supplies a complete-file reproduction script. Without executing it against a checkout, repeating the exact zero denominator would violate P35. |
| O-03 | `core/security/rotation.py` rotates the wrong asset class for INT-R7. | **confirmed_with_narrowing** | `policy-engine/src/polisyos/core/security/rotation.py:1-237 @ 02c5b8d` manages JWT trust-anchor manifests and local Ed25519 key files with active/next/retired/revoked sets. It is a reusable control owner, not a public-record credential, signing-time status, log, succession, or currentness proof. “Wrong asset class” means insufficient semantics, not irrelevant code. |
| O-04 | `core/audit/verifier.py` and `standalone_verifier_template.py` are the closest offline-verifier substrates. | **confirmed_with_narrowing** | The files provide archive traversal, checksum/CAS/provenance, detached-signature, and portable-report logic. The standalone template loads package-contained public keys (`standalone_verifier_template.py:180-360 @ 02c5b8d`), so it is package-relative unless trust is authenticated independently. It is a substrate, not a public authority verifier. |
| O-05 | Exactly 14 production Python modules import/use `cryptography`, `jwt`, or `hmac`, and the list is complete. | **not_established for the exact 14/14 denominator; substantive orientation confirmed** | The audited ledger lists 14 concrete production paths, and opened examples (`signing.py`, `rotation.py`, `fulcio.py`, verifier files) support the conclusion that primitive use is distributed but no public-verification lifecycle exists. The connected code-search response available to this audit was not a retained complete AST walk and returned unrelated textual matches for broader queries. The exact denominator requires the ledger's script on the pinned tree. |
| O-06 | `core/security/slsa/fulcio.py` is a supply-chain identity path. | **confirmed** | `policy-engine/src/polisyos/core/security/slsa/fulcio.py:1-400 @ 02c5b8d` obtains verified OIDC claims, generates an ephemeral P-256 key, requests a short-lived Fulcio-style certificate, and signs payloads; local self-signed mode also exists. The transfer is a credential pattern, not administrative competence. |
| O-07 | `runtime/quality/public_export.py` is a real 2,103-line public projection producer and is not a public proof producer. | **confirmed** | `policy-engine/src/polisyos/runtime/quality/public_export.py:1-2103 @ 02c5b8d` emits projection-only records and authority-boundary prohibitions. No public-record signing, trusted timestamp, signing-time status, transparency receipt, witness result, or canonical public verifier gate was found. |
| O-08 | The public-export file has exactly 36 incidental `sign`-family lexical hits. | **not_established for the number; absence of proof integration confirmed** | Exact source reading establishes that the file does not integrate the canonical Ed25519 signer or the proposed proof lifecycle. The count is feasible to reproduce from the pinned file, but no retained command output accompanied the audited artifact; the researcher correctly declined to promote it. |
| O-09 | The supplied briefing said `build_public_export_bundle` occurs in exactly two Python files; the ledger corrects this to five call/definition files and one separate re-export. | **confirmed in classification and named matches; exact global five-expression denominator not independently promoted** | Individually corroborated: definition in `src/polisyos/runtime/quality/public_export.py`; callers in `tools/ops_runners/runtime/canary_evidence.py`, `tools/quality/validation/check_layer3_workflow_failure_authority.py`, `tests/unit/runtime/quality/test_multi_tenant_shared_cas.py`, and `tests/unit/runtime/quality/test_public_export.py`; `runtime/quality/__init__.py` re-exports the symbol. No production `src` caller outside the defining module or HTTP route was found in the audited evidence. Thus projection producer exists and production publication remains `bridge_missing`, not `producer_missing`. A local AST walk is still required before quoting the set as exhaustive outside this audit. |
| O-10 | The dashboard's “signature” is a source-visible salt plus 32-bit FNV recomputed in the browser. | **confirmed** | `publicationPacket.ts:240-247, 357-369, 1050-1188 @ 02c5b8d` defines the public salt, FNV-1a hash, signing and verification. `PublicDecisionViewerPage.tsx:1-53` maps the resulting Boolean to a positive translated `Verified` badge. An attacker can choose replacement JSON and recompute the token; no collision search is needed. |
| O-11 | Atlas identifies the predecessor as forgeable and requires DS12 to strangle it. | **confirmed as plan obligation, not implementation** | `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:197-218, 1194-1250 @ 02c5b8d` records the missing server-side proof chain and forged-packet negative control. It does not establish that the strangle is implemented. |
| O-12 | DS12 consumes INT-R7/INT-R8 before first publication and DS13 later owns richer accountability surfaces. | **confirmed as plan ownership** | `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1194-1250, 1293-1310 @ 02c5b8d`. INT-R7 may require minimum common-view evidence before first issuance without implementing the later DS13 product surface. |
| O-13 | Stage-0 custody kernel ratification is binding and includes append-only correction, authority bands, and S0-K16. | **confirmed by finding IDs** | `stage0-custody-kernel-ratification.md` is the acceptance record. The audited work relies on `S0-K07`, `S0-K08`, and `S0-K16`; this audit evaluates those IDs rather than adjacent explanatory prose. |
| O-14 | INT-wave claim-semantics ratification is binding and changes the first signed-claim target. | **confirmed, with one missed briefing error** | `int-wave-claim-semantics-ratification.md` ratifies `INT-K01`–`INT-K08`. `INT-K06` makes the first likely public claim procedural and non-probabilistic; `INT-K02` binds `delta` to declared obligations and assumptions. However, the document's `created`, `last_reviewed`, principal decision date, pinned commit, and inspection date are all **2026-08-04**, so the briefing's “four days before you start” assertion was false and the audited ledger did not record it. |
| O-15 | GY-N12 is the canonical epoch/currentness seam and must not be duplicated. | **confirmed as planned canonical ownership** | `docs/plans/active/layer3-slices/GY-engine-subordination.md` names N12 epoch/currentness and append-only reissue semantics. INT-R7 consumes authenticated outputs and does not create a second status lattice. The planned interface is not an implemented capability. |
| O-16 | P35 and P36 bind the method. | **confirmed** | `policy-design-case-failure-patterns.md:83-135 @ 02c5b8d` defines sampled-denominator generalization and authority-by-adjacency failures. This audit follows the owner vocabulary and marks unreproduced exact counts `not_established`. |
| O-17 | OPS-R14 is active and undelivered, so INT-R7 must declare resilience outcomes without inventing storage/DR mechanics. | **confirmed** | `policy-operations-and-real-world-runtime-backlog.md:400-510 @ 02c5b8d` assigns custody-grade durability, replay, expiring authority, legal-hold effects, and disaster fixtures to OPS-R14. INT-R7 stays at proof-outcome and drill requirements. |

## 3. Source defect re-verification

### 3.1 Mutable signing time and identity

`SignatureStatement` binds only type, version, algorithm, artifact ID, blob digest, manifest
digest, and key ID (`signing.py:62-75`). `DetachedSignature` places `signed_at` and
`signer_identity` beside, not inside, that statement (`:77-94`). `canonical_statement_bytes`
serializes only the `SignatureStatement` (`:291-302`), and `Ed25519Signer.sign()` signs those
bytes before attaching the two metadata fields (`:409-441`).

**Result:** changing displayed signing time or identity does not necessarily invalidate the
Ed25519 signature. The sidecar does not establish trusted time or institutional identity at
issuance.

### 3.2 Timeless revocation

`Ed25519Verifier` stores revoked key IDs in a set, loads them from `*.pub` files, and returns
`REVOKED` on membership (`signing.py:444-517, 583-610`). There is no effective time, reason,
normal-retirement distinction, compromise interval, or retained signing-time status.

**Result:** the current verifier cannot distinguish an authentic pre-revocation issuance from
a post-compromise forgery whose mutable `signed_at` claims an earlier date. The audited defect
is true and registrable.

## 4. Pass I findings

### INT-R7-I-001 — commendation — branch geometry and audit scope are exact

**Evidence:** complete GitHub comparison from baseline to audited head: 10 commits, 10 added
Markdown files, 5,250 additions, 0 deletions, merge base equal to the pinned baseline.

### INT-R7-I-002 — commendation — the signing-time/revocation defect is real and precisely bounded

**Evidence:** `signing.py:62-94, 291-302, 409-517, 583-610 @ 02c5b8d`.

The research does not overstate the defect as an Ed25519 break. It correctly identifies a
statement/temporal-evidence failure.

### INT-R7-I-003 — commendation — O-09 corrects the briefing without erasing the existing producer

**Evidence:** the five named definition/caller files and the separate `__init__.py` re-export.

The classification `bridge_missing`, rather than `producer_missing`, survives. Exact global
exhaustiveness remains bounded by the unavailable local AST rerun.

### INT-R7-I-004 — commendation — O-02 and O-08 use `not_established` honestly

**Evidence:** both rows state the semantic conclusion, refuse the unretained lexical number,
and provide reproducible complete-file scripts. This is the correct use of
`not_established`, not avoidance.

### INT-R7-I-005 — material — the ledger missed the same-day ratification error

**Evidence:** `int-wave-claim-semantics-ratification.md` frontmatter and decision text date the
ratification to 2026-08-04; the pinned commit and research inspection date are also
2026-08-04. The ledger confirms O-14 but never corrects the briefing's “four days before”
claim.

### INT-R7-I-006 — minor — O-05's exact 14/14 denominator is not independently retained by this audit

**Evidence:** the audited ledger's list and reproduction script versus the connected search
limitations described above.

The semantic conclusion is unaffected. Consolidation should not quote `14/14` as independently
audited until the script output is retained at the pinned commit.
