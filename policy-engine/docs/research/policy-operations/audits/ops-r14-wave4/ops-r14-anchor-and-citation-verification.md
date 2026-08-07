---
title: "OPS-R14 Anchor and Citation Verification"
audit_id: OPS-R14-WAVE4-INDEPENDENT-AUDIT
status: completed
verified_commit: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent_internal_anchor_verification_for_ops_r14
  - external_primary_source_resolution_status
  - transfer_limit_audit_for_ops_r14
may_not_use_for:
  - production_implementation_authorization
  - production_capability_claim
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_vendor_custodian_archive_service_or_escrow_appointment
  - authority_or_delegation_grant
  - legal_sufficiency_or_jurisdictional_conclusion
  - permission_to_publish_sign_or_open_a_gate
  - creation_or_amendment_of_a_status_lattice
  - automatic_amendment_of_any_plan_backlog_or_system_design_decision
  - assessment_or_adoption_of_pao_r36_quality
research_only: true
---

# OPS-R14 anchor and citation verification

## 1. Method

Every internal repository citation was resolved at either the audited head or the pinned baseline.
Every external row was checked against the cited official source or, where the cited page did not
respond, an official publication/mirror carrying the same stable legal or standards identifier. A
source can pass identity and substance while still fail citation precision: a catalogue or rules
landing page is not as stable as the exact document or section.

The audit asks two separate questions:

1. **Does the source say the proposition for which it is cited?**
2. **Does the report import only what transfers to custody of PolicyOS's own signed records?**

A valid source does not cure an over-broad transfer.

## 2. Internal anchors

| Anchor | Resolution | Audit verdict |
| --- | --- | --- |
| `AGENTS.md:27-28` delivery/read-back and behavioral-gate rules | Exact pin read. | **Verified.** The audited branch uses Markdown-only ordinary commits and makes no branch-state claim inside the research. |
| `policy-design-case-failure-patterns.md` P35/P36 and capability labels | Exact pin read. | **Verified.** OPS-R14 applies denominator and label prerequisites unusually carefully, except the custom documentation label noted in `OPS-R14-IX-001`. |
| `stage0-custody-kernel-ratification.md` `S0-K08` | Exact pin read at disposition and controlling text. | **Verified.** RP, WD, hold and drill semantics append and preserve prior history. |
| same, `S0-K10` | Exact pin read. | **Verified.** F-03 and WD-08 make wake a candidate followed by re-evaluation. |
| `int-wave-claim-semantics-ratification.md` `INT-K05` | Exact pin read. | **Verified.** OPS-R14 does not create a parallel currentness/chronology owner. |
| `int-r7-r8-public-verification-and-disclosure-ratification.md` `PV-K01` | Exact pin read. | **Verified.** `Restored` retains a separate signed-record closure and dimension report. |
| same, `PV-K02` | Exact pin read. | **Verified.** Present failure never changes the earlier issuer-side occurrence. |
| `GY-engine-subordination.md` GY-N12 | Exact pin read of the build-new task and riders. | **Verified.** It owns epoch/currentness/stale/reissue/release chronology and is undelivered. |
| INT-R7 primary and lifecycle controlling amendments | Exact pin read of terminal controlling sections. | **Verified.** Phase A requires a non-authoritative ceremonial corpus before first live issuance; Phase B follows first issuance and is not retroactive authorization. |
| five in-scope runbooks | Exact pin reads. | **Verified.** They contain real operational procedures; no one of them is drill evidence. |
| `platform-acceptance.md` and manual evidence | Exact pin reads. | **Verified with qualification.** They pass documentation/posture/tabletop rows; they do not expressly claim custody-grade restoration or `DurablyVerifiableAt`. |
| `fabric/security/retention.py`, `world/store/snapshots.py`, tests | Exact pin reads. | **Verified.** Narrow snapshot legal-hold classification, encryption requirement and GC protection are real. |
| `runtime/http/services/control_worker.py` | Exact pin read. | **Verified.** Renewal means processing-lease renewal only. |
| OPS-R14/PAO-R36 backlog seam | Exact pin read. | **Verified.** Mechanics versus correction meaning are allocated as the brief states. |
| PAO-R36 F11 and handoff at `1bccc012b` | Exact parallel-head reads for seam comparison only. | **Resolved, not adopted.** PAO-R36 asks OPS-R14 to prevent recovery from un-correcting and lists five interfaces. OPS-R14 answers them at package level. |

## 3. United States sources

| Source identifier | Resolution status | Does the source support the import? | Transfer-limit verdict |
| --- | --- | --- | --- |
| **44 U.S.C. § 3101** | Official OLRC URL timed out during this audit; identifier and text resolved through the official GovInfo U.S. Code publication. | Yes: adequate/proper documentation of organization, functions, policies, decisions, procedures and essential transactions. | **Honest.** It supports evidence preservation, not PolicyOS legal status, RPO/RTO or architecture. |
| **44 U.S.C. § 3105** | Stable official identifier resolved; NARA implementing material also cites §§3105–3106. | Yes: safeguards against removal/loss and notification duties. | **Honest.** OPS-R14 imports detectability/incident evidence, not sanctions or universal jurisdiction. |
| **36 C.F.R. Part 1226** | Exact eCFR source resolved; current page was up to date as of 2026-07-09 and amended 2026-06-05. | Yes: approved schedules are mandatory; disposition authority can be withdrawn; special circumstances may temporarily extend retention; storage facilities must be notified. | **Honest.** No retention number or universal hold authority is imported. |
| **NARA FRC Freeze Process Overview/FAQ** | Exact NARA page resolved; last reviewed 2024-01-29. It still cites superseded Part 1228 numbering. | Yes for the operational distinction between an agency hold and an FRC freeze and for preserving records outside physical custody. | **Honest and self-correcting.** The ledger expressly says current eCFR wins over historical numbering. |
| **Fed. R. Civ. P. 37(e)** | Official U.S. Courts current-rules landing resolved; stable rule identifier exists, but the URL is a collection page rather than an exact Rule 37(e) anchor. | Yes: ESI that should have been preserved, reasonable steps, loss and remedies. | **Substantively honest; citation should be made document-specific.** See `OPS-R14-II-002`. |
| **5 U.S.C. § 552** | Official OLRC identifier resolved. | Yes for access to existing agency records subject to statute/exemptions. | **Honest.** The report correctly refuses to turn FOIA into an indefinite retention rule or automatic publication authority. |
| **FAR 4.805**, FAC 2026-01, effective 2026-03-13 | Exact Acquisition.gov page resolved with the stated FAC and effective date. | Yes: all media, complete/accurate/clear reproduction including signatures, protection from alteration, and longer retention for investigations/litigation. | **Mostly honest.** The format-migration transfer is strong. Contract survival/audit-right propositions are contract-specific inferences, not universal consequences of 4.805. See `OPS-R14-II-001`. |
| **FEMA FCD-1 (2017)** | FEMA guidance catalogue resolved; FCD-1 remains listed, but the cited URL is the catalogue rather than an exact document/PDF anchor. | Yes for continuity planning, training, testing, assessment and engagement at the federal executive level. | **Honest transfer; citation precision should improve.** No universal applicability or OPS-R12 absorption is claimed. |
| **NIST SP 800-34 Rev. 1**, DOI `10.6028/NIST.SP.800-34r1` | DOI and official NIST publication resolved. | Yes: impact-derived priorities, contingency strategies, testing/training/exercises. | **Honest.** It is used as an engineering pattern, not public-record law. |
| **NIST SP 800-184**, DOI `10.6028/NIST.SP.800-184` | DOI and official NIST publication resolved. | Yes: playbooks, testing, metrics, recovery improvement and coordination. | **Honest.** No legal hold, signed-record semantics or mandate is imported. |

## 4. United Kingdom sources

| Source identifier | Resolution status | Does the source support the import? | Transfer-limit verdict |
| --- | --- | --- | --- |
| **Public Records Act 1958 c.51 s.3** | Stable legislation.gov.uk identifier resolved; official archival guidance corroborates the section. | Yes for selection, preservation, transfer and authorized disposal within scope. | **Honest.** It does not appoint TNA or establish universal applicability/periods. |
| **FOIA 2000 s.46 Code of Practice (2021)**, ISBN `978-1-5286-2517-3` | Exact GOV.UK publication resolved. | Yes for reliable creation, keeping, management, access and disposal practice. | **Honest.** It remains guidance, not proof of compliance or a universal schedule. |
| **FOIA 2000 s.77** plus ICO guidance | Legislation.gov.uk section resolved. The exact ICO path cited in the ledger is not the clearest current live anchor; current ICO request-handling guidance still states the offence. | Yes for intentional alteration/erasure/destruction/concealment after a request within scope. | **Honest, but update the ICO URL/access anchor.** It correctly refuses a pre-request blanket hold. |
| **CPR PD 57AD paras. 3–4** | Exact Ministry of Justice practice-direction page resolved. | Yes for preservation notices, suspension of deletion processes, employees/former employees and agents/third parties in the Business and Property Courts scope. | **Honest and carefully scoped.** |
| **Procurement Act 2023 c.54 s.98** | Stable legislation.gov.uk identifier resolved; official explanatory material corroborates decision/communication records. | Yes for records sufficient to explain material decisions and communications in the statutory scheme. | **Partially over-transferred in synthesis.** It does not itself establish audit-right, exit or survival-clause continuation. See `OPS-R14-II-001`. |
| **Civil Contingencies Act 2004 s.2** and **Emergency Preparedness Ch.6** | Stable statute and GOV.UK guidance resolved. The 2026 Call for Views, published 2026-07-14, confirms a 2027 post-implementation review process. | Yes for continuity plans, prioritized functions, training and exercise within scope. | **Honest.** The work imports exercised continuity, not universal duties or its RTO numbers. |

## 5. Archival and cryptographic sources

| Source identifier | Resolution status | Does the source support the import? | Transfer-limit verdict |
| --- | --- | --- | --- |
| **ISO 14721:2025**, Edition 3, official ISO record | Exact standard metadata resolved. | Yes for OAIS responsibilities across ingest, storage, data management, access, migration and designated-community change. | **Honest.** No certification, vendor, retention period or “open means public” inference. |
| **PREMIS Data Dictionary 3.0**, Library of Congress | Exact LOC standard page resolved. | Yes for objects, events, rights and agents as preservation evidence concepts. | **Honest.** It is not adopted as the PolicyOS schema. |
| **RFC 4998**, DOI `10.17487/RFC4998` | Exact RFC Editor identifier resolved. | Yes for evidence-record syntax, archive timestamps and renewal processing. | **Honest.** It is an option/pattern and does not establish public authority or a selected wire. |
| **RFC 6283**, DOI `10.17487/RFC6283` | Exact RFC Editor identifier resolved. | Yes for XML representation of evidence-record concepts. | **Honest.** No XML/serialization choice follows. |

## 6. Findings

### OPS-R14-II-001 — material — procurement synthesis exceeds its sources

The cross-jurisdiction synthesis says procurement rights expire and records, audit rights, exit duties
and survival clauses can outlive service. The records proposition is supported. The latter three are
possible and often material **contract provisions**, but neither FAR 4.805 nor Procurement Act s.98
makes them universal. Mark this as a design inference contingent on the admitted contract/statute and
preserve the WatchedDependency requirement to inspect the actual instrument.

### OPS-R14-II-002 — minor — three citations are indirect or unstable anchors

Replace or supplement:

- the U.S. Courts current-rules landing with an exact Rule 37(e) text/PDF anchor;
- the FEMA guidance catalogue with the exact FCD-1 document/catalogue record; and
- the older ICO retention/destruction path with the current section-77 request-handling guidance.

No substantive conclusion changes.

### OPS-R14-II-003 — commendation — unusually disciplined transfer ledger

Every row distinguishes imported operating principle from legal applicability, retention period,
owner appointment, architecture and legal sufficiency. NIST/FEMA IT/continuity results are narrowed to
failure analysis, exercises, metrics and after-action closure; they are not laundered into a public-
records mandate. This strength should survive consolidation.

## 7. Resolution summary

- **20 source rows / 20 total rows** were audited.
- **23 cited external URLs / 23 total URLs** were attempted or resolved through their official stable
  identifier/publication.
- **0 sources were fabricated.**
- **1 material transfer overreach** was found.
- **3 indirect/unstable citation anchors** are grouped in one minor finding.
- The external corpus supports public-administration grounding in at least the United States and
  United Kingdom without establishing jurisdictional legal sufficiency.
