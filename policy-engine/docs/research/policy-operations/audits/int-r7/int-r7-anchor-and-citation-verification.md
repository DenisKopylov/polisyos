---
title: INT-R7 — Anchor and Citation Verification
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent resolution of load-bearing internal anchors used by INT-R7
  - independent Pass II verification of all thirty external primary-source identifiers
  - source-transfer findings INT-R7-II-001 through INT-R7-II-006
may_not_use_for:
  - legal sufficiency or jurisdictional compliance conclusion
  - certification that any source remains current after 2026-08-04
  - production implementation authorization
  - final schema, wire, package, serialization, database, or API contract
  - canonical vendor, authority, trust service, log, witness, archive, or custodian selection
  - claim that a cited standard alone establishes administrative competence or currentness
research_only: true
---

# INT-R7 anchor and citation verification

## 1. Verification method

Every external identifier in the audited 30-row source ledger was opened through an official
or primary-source locator. For PDF standards, the relevant pages were visually inspected as
rendered pages rather than relying only on extracted text. An official catalogue page was used
where the normative full text is paywalled. The audit checked three questions:

1. does the exact identifier exist;
2. does it support the proposition attributed to it; and
3. is the transfer to a governed public-administration record honestly narrowed?

Verdicts:

- `supported` — identifier and proposition match;
- `supported_with_transfer_limit` — technical/institutional result is real but narrower than
  the PolicyOS conclusion;
- `metadata_correction` — result stands but citation metadata is wrong;
- `historical_only` — official source is superseded/non-current;
- `partial` — official edition/scope confirmed, but full normative text was not independently
  available;
- `unsupported` — source does not support the proposition.

No external row was `unsupported`. Two require material transfer corrections and three require
minor citation/attribution corrections.

## 2. Internal anchor resolution

| Internal anchor at pinned baseline | Resolution | Audit result |
| --- | --- | --- |
| `src/polisyos/core/artifacts/signing.py` | exact statement, sidecar, signing, trust, identity and revoked-key logic read | supports the mutable-time/identity and timeless-revocation defect |
| `src/polisyos/core/security/rotation.py` | runtime/JWT/local Ed25519 rotation owner read | supports nearby owner; not a public proof lifecycle |
| `src/polisyos/core/audit/verifier.py` | package/CAS/provenance/signature verifier substrate exists | supports reuse, not independently authenticated public trust |
| `src/polisyos/core/audit/standalone_verifier_template.py` | archive, checksum, CAS and package-key logic read | supports offline substrate and package-relative trust warning |
| `src/polisyos/core/security/slsa/fulcio.py` | OIDC, ephemeral P-256, short certificate and local mode read | supports supply-chain identity pattern only |
| `src/polisyos/runtime/quality/public_export.py` | real projection producer read | supports producer-present/proof-and-production-bridge-absent distinction |
| `src/polisyos/runtime/quality/__init__.py` | symbol is re-exported | supports O-09 re-export classification |
| `tools/ops_runners/runtime/canary_evidence.py` | caller corroborated | non-production tool caller |
| `tools/quality/validation/check_layer3_workflow_failure_authority.py` | caller corroborated | validation tool caller |
| `tests/unit/runtime/quality/test_multi_tenant_shared_cas.py` | caller corroborated | test caller |
| `tests/unit/runtime/quality/test_public_export.py` | caller corroborated | test caller |
| `apps/runtime-dashboard/.../publicationPacket.ts` | public salt, FNV-1a, packet signing and browser verification read | supports constructive forgery finding |
| `apps/runtime-dashboard/.../PublicDecisionViewerPage.tsx` | positive badge consumes verifier Boolean | supports legacy positive-authority-path finding |
| `docs/system-design-decisions/stage0-custody-kernel-ratification.md` | binding acceptance record exists | `S0-K07`, `S0-K08`, `S0-K16` resolved by ID |
| `docs/system-design-decisions/int-wave-claim-semantics-ratification.md` | binding acceptance record exists, dated 2026-08-04 | `INT-K01`, `INT-K02`, `INT-K05`, `INT-K06` resolved by ID; disproves “four days before” |
| `docs/reference/policy-design-case-failure-patterns.md` | P35, P36 and missing-state vocabulary read | canonical method/capability-label owner |
| `docs/plans/active/layer3-slices/GY-engine-subordination.md` | N12 epoch/currentness plan read | supports planned canonical ownership, not implementation |
| `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | DS12/DS13 and FNV-strangle plan read | supports plan boundary, not capability |
| `docs/research/policy-operations-and-real-world-runtime-backlog.md` | OPS-R14 row read | supports resilience dependency ownership |
| `docs/reference/operations/retention-and-recovery.md` | operations reference exists | background/runbook evidence, not proof that INT-R7 preservation is implemented |
| `docs/adr/0010-cas-artifact-signing-ed25519.md` | artifact-signing ADR exists | historical signing design, not the proposed public profile |
| `pyproject.toml` | cryptographic dependencies exist | dependency presence does not establish public-verification capability |

Exact full-tree lexical denominators in O-05 and O-09 are not independently promoted because a
local checkout/AST walk was unavailable. Named anchors and the semantic classification were
resolved individually.

## 3. External primary-source verification — 30/30

### 3.1 European Union and ETSI — 7/7

| ID | Exact source | Resolution and supported proposition | Transfer limit or correction |
| --- | --- | --- | --- |
| EU-01 | Regulation (EU) No 910/2014, consolidated 2024-10-18, CELEX `02014R0910-20241018` | **supported_with_transfer_limit** for signing-time validation conditions, trusted time, qualified preservation, and member-state public-service recognition concepts | does not establish PolicyOS competence, universal cross-border recognition, or legal sufficiency for a specific record |
| EU-02 | Commission Implementing Regulation (EU) 2025/1946 | **supported_with_transfer_limit** for operational qualified-preservation requirements and long-term integrity/authenticity/accessibility | applies within the eIDAS implementing framework; not an owner-neutral mandate for PolicyOS |
| ETSI-01 | ETSI TS 119 511 V1.2.1 (2025-10) | **supported_with_transfer_limit** for preservation-service policy, security controls, evidence maintenance and operated service requirements | does not select a provider, container, jurisdiction, or legal outcome |
| ETSI-02 | ETSI EN 319 102-1 V1.4.1 (2024-06) | **supported** for validation under a named policy/time context with determinate/indeterminate/invalid-style results | technical validation does not decide administrative competence or record currentness |
| ETSI-03 | ETSI EN 319 122-1 V1.3.1 (2023-06), CAdES | **supported_with_transfer_limit** for a concrete CMS signature family with validation-material/archival augmentation semantics | candidate construction, not selected PolicyOS wire format |
| ETSI-04 | ETSI EN 319 132-1 V1.3.1 (2024-07), XAdES | **supported_with_transfer_limit** for an XML signature family and later evidence augmentation | candidate construction, not selected PolicyOS wire format |
| ETSI-05 | ETSI EN 319 142-1 V1.2.1, PAdES | **metadata_correction**: the official PDF cover gives **2024-01**, while the ledger says 2024-06; long-term baseline proposition is supported | download-directory date does not replace the edition date printed in the standard; no PDF container is selected |

### 3.2 IETF — 9/9

| ID | Exact source | Resolution and supported proposition | Transfer limit or correction |
| --- | --- | --- | --- |
| IETF-01 | RFC 3161, DOI `10.17487/RFC3161` | **supported** for proving a message imprint existed no later than trusted time and ordering it against later revocation | TSA key, clock, policy and status remain assumptions; no authority or truth proof |
| IETF-02 | RFC 5816, DOI `10.17487/RFC5816` | **supported** for ESSCertIDv2 and hash agility in timestamp certificate binding | narrow protocol update, not general archive migration policy |
| IETF-03 | RFC 4998, DOI `10.17487/RFC4998` | **supported** for Evidence Record Syntax, hash trees, and timely renewal | does not establish original administrative authority or currentness |
| IETF-04 | RFC 9162, DOI `10.17487/RFC9162` | **supported_with_transfer_limit** for Merkle inclusion/consistency and the need for external comparison/monitoring against inconsistent views | does not standardize INT-R7's independent witness quorum or governance policy; that is a design inference |
| IETF-05 | RFC 5280, DOI `10.17487/RFC5280` | **supported_with_transfer_limit** for path validation, validity, key usage, constraints and CRL semantics | generic certificate validation does not prove mandate, delegation, succession or current record authority |
| IETF-06 | RFC 6960, DOI `10.17487/RFC6960` | **supported** for signed online certificate-status responses and response-time metadata | live OCSP is neither proof of unknown compromise nor a 30-year preservation strategy |
| IETF-07 | RFC 9591, DOI `10.17487/RFC9591` | **supported_with_transfer_limit** for a concrete two-round FROST construction under its assumptions | no time, authority, log, archive, or honest-authorized-quorum guarantee |
| IETF-08 | RFC 8493, DOI `10.17487/RFC8493` | **supported** for manifest-based transfer/fixity and explicit absence of active-substitution protection | requires independently authenticated trust |
| IETF-09 | RFC 8785, DOI `10.17487/RFC8785` | **supported_with_transfer_limit** as proof that deterministic JSON canonicalization is a real construction | does not select JSON/JCS for PolicyOS |

### 3.3 NIST and United States public-sector sources — 7/7

| ID | Exact source | Resolution and supported proposition | Transfer limit or correction |
| --- | --- | --- | --- |
| NIST-01 | NIST SP 800-57 Part 1 Rev. 5, DOI `10.6028/NIST.SP.800-57pt1r5` | **supported_with_transfer_limit** for key lifecycle, cryptoperiod, compromise, metadata, backup, split knowledge, and controls | general security guidance, not public-record competence or owner assignment |
| NIST-02 | NIST SP 800-131A Rev. 2, DOI `10.6028/NIST.SP.800-131Ar2` | **supported** for changing algorithm acceptability and transition planning | no fixed PolicyOS deadline/profile follows automatically |
| NIST-03 | FIPS 204, DOI `10.6028/NIST.FIPS.204` | **supported** for existence of standardized ML-DSA | does not mandate immediate adoption or prove hybrid/archive interoperability |
| NIST-04 | FIPS 205, DOI `10.6028/NIST.FIPS.205` | **supported** for existence of standardized SLH-DSA | same transfer limit; operational selection remains open |
| NIST-05 | NISTIR 8202, DOI `10.6028/NIST.IR.8202` | **supported_with_transfer_limit** for distributed-ledger commitment/order properties and off-chain/governance limits | no signer authority, source truth, revocation/currentness, privacy, or legal custody |
| US-01 | NARA, *Records Management Guidance for PKI Digital Signature Authenticated and Secured Transaction Records* (2005) | **historical_only**: official page says superseded, no longer accurate, retained as technical/historical reference | Trust Documentation Set is useful historical precedent, not current NARA mandate; present-tense normative reliance must be replaced or labelled |
| US-02 | Federal PKI, *Delegated Digital Signature Playbook* V2.1 (2026-03-27) | **supported_with_transfer_limit** for a concrete Federal Register delegated-signing process, purpose-limited credentials, per-use authorization, and controls | source says it is not official policy, mandated action, or authoritative terminology and is specific to Federal Register submissions |

### 3.4 Canada, OAIS, PREMIS, and Sigstore — 7/7

| ID | Exact source | Resolution and supported proposition | Transfer limit or correction |
| --- | --- | --- | --- |
| CA-01 | Government of Canada, *Guidance on Using Electronic Signatures* | **supported_with_transfer_limit** for risk-based signature selection, long-term validation, signing-time certificate/status evidence, recursive renewal, format-conversion risk, and compromise handling | Canadian government guidance, not universal law or automatic PolicyOS legal sufficiency |
| ISO-01 | ISO 14721:2025, OAIS | **partial but adequate for the imported high-level proposition**: official ISO locator confirms current edition and OAIS scope | use organizational preservation/designated-community concepts only; no unverified clause wording |
| LOC-01 | PREMIS Data Dictionary for Preservation Metadata V3.0 | **supported_with_transfer_limit** for Objects, Events, Rights, Agents, fixity, migration, and provenance | preservation metadata model, not signature verifier or required PolicyOS schema |
| SIG-01 | Sigstore, *Security Model* | **supported_with_transfer_limit** for distributed trust-root authentication/rotation and ecosystem assumptions | software-signing ecosystem, not institutional authority registry |
| SIG-02 | Sigstore, *Threat Model* | **supported_with_transfer_limit** for IdP/CA/log/monitor/trust-root dependencies and limits of signature validity | does not decide government competence, record currentness, or content safety |
| SIG-03 | Sigstore, *Transparency Log / Rekor Overview* | **supported_with_transfer_limit** for public discoverability/auditability through append-only logging | common view and privacy need external controls |
| SIG-04 | Sigstore, *Verification of signatures and bundles* | **supported in substance; locator incomplete for exact bundle fields** | use the official *Sigstore Bundle Format* page for certificate, timestamp, transparency entry, inclusion proof, and checkpoint structure; retain verification page for behavior |

**Denominator:** 30 verified source identifiers / 30 identifiers in the audited ledger.

## 4. Transfer adjudication by model family

### 4.1 PKI and qualified/advanced signatures

PKI can establish a credential/path/status proposition under a trust policy. eIDAS/ETSI
profiles can add regulated signature-validation and preservation effects in their scope. None
of those results alone establishes the complete PolicyOS administrative mandate, a disputed
succession, GY-N12 currentness, or an INT-R8 projection relation. The audited conclusion is
correct as a **non-sufficiency** claim; it would be overreach only if phrased as “these regimes
can never contribute to legal or administrative validity.”

### 4.2 Blockchain/public anchoring

NISTIR 8202 supports commitment/order properties under consensus and governance assumptions.
It does not support off-chain truth, authority, disclosure safety, revocation semantics, or
long-term legal custody. “Optional additional witness, not canonical profile” is supported.

### 4.3 Sigstore

Sigstore supports short-lived identity credentials, transparency, bundles, and distributed
trust roots for software signing. Its own threat/security model retains IdP, CA, log, monitor,
and root assumptions. Importing those constructions while refusing to infer public
administrative competence is correct.

### 4.4 Archival regimes

OAIS/PREMIS provide organizational and metadata semantics; ETSI/RFC 4998 provide cryptographic
preservation constructions. Neither substitutes for the other. The audited composite use is
correct, subject to the NARA currentness correction.

## 5. Pass II findings

### INT-R7-II-001 — commendation — the 30-source corpus is primary-source heavy and usually transfer-limited

**Evidence:** 30/30 table above and the audited source ledger.

### INT-R7-II-002 — minor — PAdES edition metadata is wrong

**Evidence:** ETSI EN 319 142-1 V1.2.1 official cover: 2024-01; audited row: 2024-06.

### INT-R7-II-003 — material — NARA guidance is officially superseded

**Evidence:** official NARA page notice stating the guidance is superseded/no longer accurate
and retained for technical/historical reference.

Reclassify as historical precedent and add current authority wherever a present requirement is
claimed.

### INT-R7-II-004 — material — Federal PKI playbook scope and legal status are understated

**Evidence:** official V2.1 disclaimer and Federal Register use-case scope.

Preserve the concrete control pattern, but state that it is nonbinding and use-case-specific.

### INT-R7-II-005 — minor — RFC 9162 does not define the proposed witness quorum

**Evidence:** RFC monitor/auditor/common-view limitations versus INT-R7's policy choice.

Label quorum/non-collusion as an INT-R7 design inference.

### INT-R7-II-006 — minor — Sigstore bundle-field support needs the exact bundle-format anchor

**Evidence:** official verification page and official Bundle Format documentation.

Keep both locators; do not attribute every field to the general verification page.
