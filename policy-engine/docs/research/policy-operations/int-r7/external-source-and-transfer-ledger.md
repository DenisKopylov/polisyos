---
title: INT-R7 — External Primary Source and Transfer Ledger
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
research_only: true
int_r8_seam: proof_only
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - permission to publish a governed result
  - automatic amendment of any plan or system-design decision
---

# External primary source and transfer ledger

## 1. Method and limits

This ledger records the external primary sources used by INT-R7 and the exact proposition imported from each. It is deliberately stricter than a bibliography:

1. every source has a stable identifier or an official standards/public-authority locator;
2. every imported proposition has a bounded transfer statement;
3. every row records what **does not** transfer to a governed PolicyOS public record;
4. standards are treated as technical constructions or interoperability profiles, not automatic legal sufficiency;
5. public-sector guidance is treated as evidence of institutional recordkeeping requirements in its issuing jurisdiction, not as a universal mandate; and
6. no source is used to appoint a vendor, certificate authority, trust service, archive, log operator or custodian.

The ledger was inspected on 2026-08-04. Versioned identifiers, not page titles or search-result snippets, are the citation anchors. A later implementation must re-check current standards, algorithm policy and jurisdiction-specific law before use.

## 2. Primary source ledger

| ID | Primary source and stable identifier | Official locator | Result used by INT-R7 |
| --- | --- | --- | --- |
| **EU-01** | Regulation (EU) No 910/2014 as consolidated 2024-10-18; CELEX `02014R0910-20241018`; ELI `reg/2014/910/2024-10-18` | https://eur-lex.europa.eu/eli/reg/2014/910/2024-10-18/eng | Validation is temporal: Articles 32/32a evaluate certificate and signature conditions at signing; Article 34 defines preservation beyond technological validity; Articles 24a, 27 and 42 demonstrate cross-border/public-service recognition and trusted-time concepts. |
| **EU-02** | Commission Implementing Regulation (EU) 2025/1946; ELI `reg_impl/2025/1946/oj` | https://eur-lex.europa.eu/eli/reg_impl/2025/1946/oj/eng | Qualified preservation is an operational service concerned with long-term integrity, authenticity, proof of existence and accessibility of preservation evidence, not merely storage of the original signature. |
| **ETSI-01** | ETSI TS 119 511 V1.2.1 (2025-10), *Policy and security requirements for trust service providers providing long-term preservation of digital signatures or general data using digital signature techniques* | https://www.etsi.org/deliver/etsi_ts/119500_119599/119511/01.02.01_60/ts_119511v010201p.pdf | Long-term preservation requires an operated policy, security controls and evidence-maintenance process. It supports the preservation-role and renewal-policy requirements. |
| **ETSI-02** | ETSI EN 319 102-1 V1.4.1 (2024-06), *Procedures for Creation and Validation of AdES Digital Signatures; Part 1* | https://www.etsi.org/deliver/etsi_en/319100_319199/31910201/01.04.01_60/en_31910201v010401p.pdf | Signature validation is a procedure under a validation policy and time context, producing determinate/indeterminate/invalid-style evidence rather than an unqualified Boolean. |
| **ETSI-03** | ETSI EN 319 122-1 V1.3.1 (2023-06), *CAdES digital signatures; Part 1* | https://www.etsi.org/deliver/etsi_en/319100_319199/31912201/01.03.01_60/en_31912201v010301p.pdf | CAdES baseline levels show how signed content, validation material and archival augmentation can be carried in a CMS family. |
| **ETSI-04** | ETSI EN 319 132-1 V1.3.1 (2024-07), *XAdES digital signatures; Part 1* | https://www.etsi.org/deliver/etsi_en/319100_319199/31913201/01.03.01_60/en_31913201v010301p.pdf | XAdES baseline levels show the corresponding XML family and the separation between base signature and later validation/preservation evidence. |
| **ETSI-05** | ETSI EN 319 142-1 V1.2.1 (2024-06), *PAdES digital signatures; Part 1* | https://www.etsi.org/deliver/etsi_EN/319100_319199/31914201/01.02.01_60/en_31914201v010201p.pdf | PAdES baseline levels show a PDF-oriented long-term validation family. It is a candidate container family, not the selected canonical PolicyOS wire format. |
| **IETF-01** | RFC 3161, *Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)*; DOI `10.17487/RFC3161` | https://www.rfc-editor.org/rfc/rfc3161 | A trusted timestamp can prove that a datum existed before a time and can support verification of a signature made before later certificate revocation. The time-stamp authority's policy and integrity remain assumptions. |
| **IETF-02** | RFC 5816, *ESSCertIDv2 Update for RFC 3161*; DOI `10.17487/RFC5816` | https://www.rfc-editor.org/rfc/rfc5816 | Timestamp profiles require algorithm agility in the certificate-binding hash and should not freeze a legacy digest. |
| **IETF-03** | RFC 4998, *Evidence Record Syntax (ERS)*; DOI `10.17487/RFC4998` | https://www.rfc-editor.org/rfc/rfc4998 | Long-term evidence may be renewed through timestamp and hash-tree renewal before the prior algorithms become unsuitable. Evidence records can remain separate from data while binding it. |
| **IETF-04** | RFC 9162, *Certificate Transparency Version 2.0*; DOI `10.17487/RFC9162` | https://www.rfc-editor.org/rfc/rfc9162 | Merkle inclusion and consistency proofs support efficient append-only auditing. A log exposes misissuance/equivocation risk but does not alone prevent split views; monitors and independent checkpoint comparison are required. |
| **IETF-05** | RFC 5280, *Internet X.509 PKI Certificate and CRL Profile*; DOI `10.17487/RFC5280` | https://www.rfc-editor.org/rfc/rfc5280 | Certificate-path, validity-window, key-usage and CRL semantics are available as an interoperable credential layer. Domain-specific authorization may need to supplement the generic profile. |
| **IETF-06** | RFC 6960, *X.509 Internet Public Key Infrastructure Online Certificate Status Protocol — OCSP*; DOI `10.17487/RFC6960` | https://www.rfc-editor.org/rfc/rfc6960 | Signed online status responses can reduce revocation-notification latency and, when preserved, contribute to signing-time status evidence. Live availability is not a 30-year preservation strategy. |
| **IETF-07** | RFC 9591, *The Flexible Round-Optimized Schnorr Threshold (FROST) Protocol for Two-Round Schnorr Signatures*; DOI `10.17487/RFC9591` | https://www.rfc-editor.org/rfc/rfc9591 | A concrete threshold-signature construction exists for separating signing power across participants under its stated assumptions. It does not provide authority, time, log or archive semantics. |
| **IETF-08** | RFC 8493, *The BagIt File Packaging Format (V1.0)*; DOI `10.17487/RFC8493` | https://www.rfc-editor.org/rfc/rfc8493 | A simple manifest-based transfer package can preserve fixity and support multiple hash algorithms. The specification explicitly is not protection against active substitution without an authenticated trust layer. |
| **IETF-09** | RFC 8785, *JSON Canonicalization Scheme (JCS)*; DOI `10.17487/RFC8785` | https://www.rfc-editor.org/rfc/rfc8785 | A real canonicalization construction exists for JSON-like data. INT-R7 imports the requirement for deterministic, versioned canonical bytes, not JCS as the final format. |
| **NIST-01** | NIST SP 800-57 Part 1 Rev. 5, *Recommendation for Key Management: Part 1 — General*; DOI `10.6028/NIST.SP.800-57pt1r5` | https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final | Key lifecycle, cryptoperiod, compromise, inventory, metadata protection, backup and split-knowledge concerns must be designed as a lifecycle rather than a key-generation function. |
| **NIST-02** | NIST SP 800-131A Rev. 2, *Transitioning the Use of Cryptographic Algorithms and Key Lengths*; DOI `10.6028/NIST.SP.800-131Ar2` | https://csrc.nist.gov/pubs/sp/800/131/a/r2/final | Algorithm acceptance changes over time; a preservation profile needs a monitored transition policy and renewal before disallowance, not a permanent algorithm constant. |
| **NIST-03** | FIPS 204, *Module-Lattice-Based Digital Signature Standard*; DOI `10.6028/NIST.FIPS.204` | https://csrc.nist.gov/pubs/fips/204/final | A standardized post-quantum signature family exists and should be represented in agility planning, without forcing immediate selection or declaring hybrid migration complete. |
| **NIST-04** | FIPS 205, *Stateless Hash-Based Digital Signature Standard*; DOI `10.6028/NIST.FIPS.205` | https://csrc.nist.gov/pubs/fips/205/final | A second standardized post-quantum signature family exists with different operational trade-offs; algorithm policy should support plural candidates and migration evidence. |
| **NIST-05** | NISTIR 8202, *Blockchain Technology Overview*; DOI `10.6028/NIST.IR.8202` | https://csrc.nist.gov/pubs/ir/8202/final | Distributed ledgers provide replicated commitment/order properties under their consensus and governance assumptions. They do not inherently establish off-chain identity, legal authority, accuracy or privacy. |
| **US-01** | U.S. National Archives and Records Administration, *Records Management Guidance for PKI Digital Signature Authenticated and Secured Transaction Records* | https://www.archives.gov/records-mgmt/policy/pki.html | A government transaction requires a retained “Trust Documentation Set”: transaction-specific signature/certificate/status/time evidence plus administrative policy, configuration, testing and operational records for the retention period. Lifecycle responsibility survives outsourcing. |
| **US-02** | U.S. Federal PKI, *Delegated Digital Signature Playbook*, Version 2.1 (2026-03-27) | https://www.idmanagement.gov/playbooks/dds/ | Public-sector delegated/role signing needs purpose-limited credential semantics, hardware/procedural controls and traceable delegation; a personal workforce identity alone is insufficient. |
| **CA-01** | Government of Canada, *Guidance on Using Electronic Signatures* | https://www.canada.ca/en/government/system/digital-government/online-security-privacy/identity-credential-access-management/government-canada-guidance-using-electronic-signatures.html | Long-term validation binds signing time, certificate chain and revocation status; recursive renewal supports decades; format conversion can invalidate the original signature; retrospective compromise needs a procedural adjudication path. |
| **ISO-01** | ISO 14721:2025, *Reference model for an Open Archival Information System (OAIS)* | https://www.iso.org/standard/87471.html | Long-term preservation is an organizational responsibility to a designated community under changing technology, formats and knowledge base; storage media alone are not an archive. |
| **LOC-01** | PREMIS Data Dictionary for Preservation Metadata, Version 3.0 | https://www.loc.gov/standards/premis/v3/ | Preservation needs structured metadata for Objects, Events, Rights and Agents, including migration/fixity/provenance events. PREMIS is a metadata model, not a signature verifier. |
| **SIG-01** | Sigstore, *Security Model* | https://docs.sigstore.dev/about/security/ | A distributed trust root can authenticate Fulcio and Rekor keys and rotate trust metadata. The construction is specific to its ecosystem and is not an institutional authority registry. |
| **SIG-02** | Sigstore, *Threat Model* | https://docs.sigstore.dev/about/threat-model/ | Keyless signing still depends on OIDC account/IdP, CA, log, monitors and trust-root security; identity monitoring and log consistency checking are required. A valid signature does not prove the artifact is substantively good or authorized. |
| **SIG-03** | Sigstore, *Transparency Log / Rekor Overview* | https://docs.sigstore.dev/logging/overview/ | Public inclusion in an append-only transparency service can make signing events discoverable and auditable. Transfer requires independent monitoring and privacy assessment. |
| **SIG-04** | Sigstore, *Verification of signatures and bundles* | https://docs.sigstore.dev/cosign/verifying/verify/ | Offline verification can use a self-contained bundle of certificate, inclusion proof, checkpoint and signed material if trust roots and policy are independently supplied. Package-contained keys are not self-authenticating. |

## 3. Transfer ledger

| Imported result | Source IDs | What transfers to a governed PolicyOS decision record | What does **not** transfer | Profile consequence |
| --- | --- | --- | --- | --- |
| Validation is evaluated at a historical time | EU-01, ETSI-02, IETF-01, CA-01 | Separate `signed-before-status-boundary` evidence from the verifier's present time; preserve the relevant status material | automatic conclusion that a record remains current, legally effective or substantively correct | `HistoricalAuthenticity` and `CurrentAuthority` remain separate predicates |
| Preservation extends trust beyond algorithm/certificate lifetime | EU-01, EU-02, ETSI-01, IETF-03, CA-01 | require renewal events, preserved validation material and migration lineage before first issuance | a claim that merely retaining the original bytes is sufficient | minimum preservation profile and scheduled evidence renewal |
| Trusted time can defeat simple backdating | IETF-01, EU-01 | bind the signature/statement commitment to independently authenticated time and retain TSA policy/status evidence | proof that the signer was authorized, that chronology content is true, or that a compromised TSA cannot lie | trusted-time layer plus separate authority and procedure-history evidence |
| AdES LTA families are proven long-term constructions | ETSI-03, ETSI-04, ETSI-05, ETSI-01 | use as concrete evidence that augmentable signature containers and archival validation levels exist | selection of PDF/XML/CMS as the final PolicyOS package, or legal sufficiency in any jurisdiction | owner-neutral format requirements; container remains open |
| PKI supplies credential/path/revocation primitives | IETF-05, IETF-06, EU-01 | retain chain, policy, usage, status-at-signing and trust-anchor evidence | public-administration delegation, competence, statutory mandate, organizational succession or current record authority | PKI is one authority-evidence layer, not the whole profile |
| Append-only Merkle logs support inclusion/consistency | IETF-04, SIG-03 | require inclusion proof, checkpoint and consistency path for publicly issued records | common-view proof from one log, prevention of malicious issuance, or record currentness | add independent witnesses/monitors and checkpoint comparison |
| Split view needs observation outside the log | IETF-04, SIG-02 | require multiple independently governed observations or witness quorum under a declared policy | a universal numeric quorum chosen by this research | `CommonView` is separate and policy-bound; consolidation must set governance |
| Keyless short-lived credentials reduce persistent-key exposure | SIG-01, SIG-02, SIG-04 | optional issuance pattern; preserve certificate, identity claims, log proof and trust-root metadata | transfer of OIDC/workforce identity into public authority, legal delegation or succession | Fulcio model is informative but not canonical for public records |
| Threshold signing can reduce single-custodian compromise | IETF-07, NIST-01 | optional/quorum control for high-consequence issuance, with participant and ceremony evidence | time, authority, transparency, archive, currentness, or protection from an authorized malicious quorum | threshold is a signing-control layer, not a verification profile |
| Distributed ledgers can be external anchors | NIST-05 | optional independent publication of a privacy-safe commitment/checkpoint | signer identity, off-chain accuracy, revocation semantics, content availability, legal recognition or migration-free permanence | blockchain rejected as canonical; may be an additional witness only |
| Canonicalization must be deterministic and versioned | IETF-09, ETSI-02 | sign unambiguous bytes and preserve canonicalization/verifier version | selection of JSON or JCS as the final wire format | semantic profile requires versioned canonical bytes, remains format-neutral |
| Transfer packages need authenticated manifests | IETF-08, SIG-04 | preserve an offline closure of record, proof and verification material with fixity manifests | trust in keys merely because they are inside the same package | offline trust anchors/status snapshots require independent authentication |
| Key metadata and lifecycle are protected assets | NIST-01 | inventory key/credential states, protect metadata, record compromise/rotation/recovery | a particular HSM, provider, ceremony, key lifetime or organizational owner | owner role and outcomes specified; mechanics deferred to implementation/OPS-R14 |
| Algorithm status changes | NIST-02, NIST-03, NIST-04, IETF-02 | maintain algorithm policy, plural identifiers, migration triggers and pre-deprecation renewal | a fixed migration date, immediate post-quantum mandate, or proof that a chosen hybrid is safe | algorithm-agile statement and preservation evidence; policy version is bound |
| Government records require administrative evidence | US-01, CA-01, ISO-01, LOC-01 | retain policy, procedures, configuration, validation, succession, preservation events and custody evidence with the record/proof family | treating technical signature validity as institutional competence or legal sufficiency | preservation profile includes verification closure and owner-role succession |
| Outsourcing does not remove records responsibility | US-01, ETSI-01, ISO-01 | contracts/service evidence must permit retention, export, verification and successor custody | appointment of a specific hosted service or transfer of public authority to a vendor | provider-neutral dependency and exit requirements |
| Human-readable purpose and time matter | US-01, CA-01 | citizen report shows signer/role purpose, bounded time result and transaction/record identity | replacement of machine-verifiable evidence by a textual summary | paired machine/human verification reports |
| Format conversion breaks embedded signatures | CA-01, LOC-01, ISO-01 | preserve original signed bytes; record derivative/migration events; bind new preservation attestations to originals | silent re-signing of converted content as if it were the original signature | original-authenticity chain plus derivative lineage |
| Retrospective compromise is not solved by syntax | CA-01, IETF-01 | represent `time validity not established`, affected interval, challenge/invalidation/reissue path | automatic assumption that every pre-revocation signature is valid or invalid | temporal validity may be indeterminate; append-only adjudication required |
| Archive responsibility outlives one organization/system | ISO-01, US-01 | require named owner **role**, succession package, designated verifier population and recovery drill | naming the current team/person as canonical or assuming one repository remains permanent | before-first-signature institutional commitment gate |
| Preservation events need structured provenance | LOC-01, IETF-03 | retain renewal, migration, validation, fixity, rights and agent events | adoption of PREMIS as the final database/schema | semantic event requirements only |
| Public-service cross-border recognition is institutional | EU-01 | audience/jurisdiction/credential-policy binding and cross-agency recognition must be explicit | global recognition of a PolicyOS signature or a declaration of eIDAS compliance | authority evidence is jurisdiction/purpose scoped; legal conclusion remains open |
| A valid signature does not prove a good/authorized artifact | SIG-02, IETF-05 | keep cryptographic authenticity, authority, content semantics and currentness as separate predicates | upgrading signature validity to policy correctness, compliance, competence or production readiness | vector verification output; no universal `Verified` Boolean |

## 4. Conflicts and adjudications

### 4.1 “Revoked now” versus “valid at signing”

RFC 5280/OCSP describe current certificate status mechanisms; eIDAS validation, RFC 3161 and Canadian LTV guidance require evaluation at the relevant signing time. The sources are not contradictory. They answer different predicates. INT-R7 therefore preserves both:

- whether the credential was valid and not disqualified at a proved issuance time; and
- whether the credential or record is trusted/current at the verifier's status cutoff.

A timeless revocation directory cannot answer both.

### 4.2 Transparency log consistency versus common view

RFC 9162 gives cryptographic consistency within a presented history and explicitly motivates external auditing. Sigstore's own threat model requires consistency monitoring and identity monitoring. The correct transfer is not “Merkle log prevents equivocation”; it is:

> inclusion + consistency + independently observed checkpoints under a declared witness policy provide evidence against split-view equivocation.

Failure of the witness layer yields `common_view_not_established`, not signature invalidity.

### 4.3 AdES format families versus owner-neutral research

PAdES, XAdES and CAdES demonstrate concrete long-term signature profiles. They differ in document/container semantics. The research question asks for a semantic lifecycle and prohibits a final wire/package contract. The sources therefore establish required capabilities—validation-material retention, timestamp augmentation, archival renewal—not a selected container.

### 4.4 Current guidance versus historical public-sector practice

US-01 is an official NARA guidance artifact with older technology references. INT-R7 uses its durable records-management result—the Trust Documentation Set and lifecycle responsibility—not obsolete assurance-level arithmetic or a claim that it is the latest whole-of-government signature policy. US-02 and CA-01 supply more recent public-sector practice. No row establishes legal sufficiency.

### 4.5 Supply-chain identity versus public authority

Sigstore's model is strong evidence for short-lived credentials, transparency, offline bundles and trust-root distribution. Its subject is software signing. A public decision record additionally requires competence, delegation, statutory/administrative authority, organizational succession, retention, challenge and current record status. Those properties are not inferred from OIDC or a transparency entry.

### 4.6 OAIS/PREMIS versus cryptographic proof

OAIS establishes organizational preservation responsibility; PREMIS establishes preservation metadata concepts. Neither authenticates a signature or log. Conversely, a valid signature does not establish that an archive can preserve and explain the evidence for decades. The selected profile composes the layers rather than substituting one for the other.

## 5. Source-backed minimum before a first public signature

The primary-source corpus supports a minimum institutional and technical profile, but not a declaration of jurisdictional legal compliance. Before issuance, the project must have:

1. an exact signed semantic statement and authenticated authority credential;
2. trusted issuance-time evidence plus retained certificate/status/trust material;
3. append-only inclusion and independently witnessed checkpoints;
4. an offline verification closure with independently authenticated trust inputs;
5. an algorithm/format monitoring and evidence-renewal policy;
6. retention of original bytes, proof, policy, verifier and preservation events;
7. an accountable custody-owner role and succession handoff;
8. a tested recovery drill; and
9. a separate currentness/epoch status path that never erases historical authenticity.

These requirements support the INT-R7 recommendation. They do **not** establish that PolicyOS presently possesses the capabilities, that a particular trust service is legally sufficient, or that publication is authorized.
