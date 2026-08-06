---
id: OPS-R14-EXTERNAL-LEDGER
artifact_kind: research_source_and_transfer_ledger
status: research_only
standing: NO_GO
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
source_review_date: 2026-08-06
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner, vendor, custodian, archive, or service appointment
  - escrow agent appointment
  - authority grant
  - delegation grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - permission to sign
  - automatic amendment of any plan, backlog, or system-design decision
  - automatic amendment of the status lattice
  - proof that any retention period is legally sufficient
  - absorption of OPS-R12 institutional-scale continuity scope
  - design of PAO-R36 correction, notice, subscriber fan-out, or correction-feed semantics
---

# External primary-source and transfer ledger

## 1. Use rule

This ledger imports operating principles, failure modes, and checkable evidence duties. It does not
import a jurisdiction's retention period, appoint an archive or official, decide legal sufficiency,
or assert that PolicyOS is within any source's legal scope. Applicability must be re-established by
competent institutional and legal review before implementation or use in a real matter.

The review date is 2026-08-06. A source is rechecked on amendment, supersession, material guidance
update, jurisdiction change, contract change, or before any implementation relies on it.

## 2. United States federal sources

| Stable identifier and official source | Imported result | What transfers to government-record custody | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **44 U.S.C. 3101**, Records management by agency heads. Office of the Law Revision Counsel, U.S. House of Representatives. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title44-section3101&num=0&edition=prelim> | Agency heads must make and preserve adequate and proper documentation of organization, functions, policies, decisions, procedures, and essential transactions. | Custody must preserve the evidence needed to reconstruct an authority-bearing act, not only its final display. Decision chronology, source, role, and supporting evidence are part of the recovery closure. | It does not establish that PolicyOS is a U.S. federal agency, set this project's retention periods, or specify a software architecture. | Amendment to Title 44 or change in deployment jurisdiction. |
| **44 U.S.C. 3105**, Safeguards. Office of the Law Revision Counsel. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title44-section3105&num=0&edition=prelim> | Agencies establish safeguards against removal or loss and notify the Archivist of unlawful removal or destruction. | Recovery must detect missing evidence and preserve a durable incident trail; silent data loss is not acceptable closeout. | It does not define the project's incident roles, sanctions, or cross-border duties. | Statutory amendment or relevant NARA implementing-rule change. |
| **36 C.F.R. Part 1226**, Implementing disposition. Electronic Code of Federal Regulations. <https://www.ecfr.gov/current/title-36/chapter-XII/subchapter-B/part-1226> | Current federal rules govern authorized disposition, withdrawal of disposal authority, and temporary extension of retention under special circumstances. | A hold/freeze is modeled as a suspension of disposition, while the underlying schedule and passed deadline remain facts. Release requires renewed disposal evaluation. | No Part 1226 retention term is adopted. The rule does not supply PolicyOS hold authority, schema, or a universal litigation rule. | eCFR amendment, NARA rulemaking, or deployment outside U.S. federal scope. |
| **NARA Federal Records Centers Program Freeze Process Overview / FAQ**. <https://www.archives.gov/frc/arcis/freeze-faq> | Distinguishes an agency litigation hold from an FRC freeze and explains that normal disposition is suspended for covered records, including records outside the agency's physical custody. | A hold must reach third-party or separate custody domains; tagging only the primary store is insufficient. Release must identify the covered freeze/hold. | The FAQ is operational guidance, not a universal legal-hold rule. It cites historical regulatory numbering; where wording conflicts, current eCFR controls. | NARA page revision, regulatory renumbering, or change in records-center arrangement. |
| **Fed. R. Civ. P. 37(e)**, Failure to preserve electronically stored information. U.S. Courts current rules page. <https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-civil-procedure> | Preservation duties and consequences turn on ESI that should have been preserved in anticipation or conduct of litigation and on reasonable preservation steps. | Drill evidence must show that deletion/GC/crypto-erasure was suspended for in-scope material and that loss is detected, scoped, and reported. | It does not make every record subject to indefinite hold, decide when litigation is anticipated, or apply outside its procedural scope. | Rule amendment, controlling case law, or matter-specific litigation advice. |
| **5 U.S.C. 552**, Freedom of Information Act. Office of the Law Revision Counsel. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section552&num=0&edition=prelim> | Federal agencies provide access to existing agency records subject to the statute and exemptions. | Evidence obtainability is a custody dimension: records may need a competent access route even when not openly published. | FOIA is not a blanket retention schedule and does not authorize public release of restricted material. Applicability and exemptions are not decided here. | Statutory amendment, agency-specific FOIA rule, or matter-specific disclosure decision. |
| **FAR 4.805**, Storage, handling, and contract files, current FAC 2026-01 effective 2026-03-13. Acquisition.gov. <https://www.acquisition.gov/far/4.805> | Contract files cover all media; alternate-media conversion must reproduce originals completely, accurately, and clearly and protect data from alteration. Investigations/litigation can extend retention. | Format migration must preserve signatures and graphic/written evidence, record transformation provenance, verify completeness, and keep litigation/hold interactions visible. Procurement records and expiring contract/audit rights require their own watches. | FAR table retention periods are not imported. The rule does not appoint a vendor/custodian or prove a migrated PolicyOS record legally sufficient. | FAC update, NARA schedule change, contract regime change, or non-U.S.-federal procurement. |
| **FEMA FCD-1 (2017)**, Federal Executive Branch National Continuity Program and Requirements, FEA `FCD-1`. FEMA guidance catalogue. <https://www.fema.gov/about/reports-and-data/guidance> | Establishes a continuity framework and plan elements for federal executive departments and agencies; FEMA continuity materials emphasize planning, training, testing, assessment, and engagement. | Recovery objectives must be exercised and measured; continuity evidence includes tests, exercises, after-action findings, and improvement closure rather than a plan alone. | It does not apply automatically to every public body or define PolicyOS custody classes. Institutional-scale continuity remains OPS-R12. | Replacement FCD, FEMA continuity-policy update, or deployment-scope change. |
| **NIST SP 800-34 Rev. 1**, Contingency Planning Guide for Federal Information Systems, DOI `10.6028/NIST.SP.800-34r1`. <https://doi.org/10.6028/NIST.SP.800-34r1> | Contingency planning derives recovery priorities and strategies from system impact and requires plan testing, training, and exercises. | Custody classes need different measured objectives and exercised restoration paths. A configured backup is not recovery evidence. | The publication does not set legal retention, public authority, or this report's numerical RPO/RTO as binding federal requirements. | NIST revision/supersession or material architecture change. |
| **NIST SP 800-184**, Guide for Cybersecurity Event Recovery, DOI `10.6028/NIST.SP.800-184`. <https://doi.org/10.6028/NIST.SP.800-184> | Recovery planning includes playbooks, testing, metrics, improvement, and coordination across preparation and recovery. | Retain measurable recovery outcomes, failure injections, playbook execution, lessons, remediation, and retest. | It does not establish legal-hold authority, signed-record semantics, or a government continuity mandate for PolicyOS. | NIST revision or threat/architecture change. |

## 3. United Kingdom sources

| Stable identifier and official source | Imported result | What transfers to government-record custody | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **Public Records Act 1958 c. 51, s.3**, selection and preservation of public records. Legislation.gov.uk. <https://www.legislation.gov.uk/ukpga/1958/51/section/3> | Public-record bodies have duties around selection, preservation, transfer, and authorized disposal within the Act's scope. | Custody design must distinguish preservation, transfer, and disposal authority; organizational change must not orphan records or erase provenance. | It does not establish that every PolicyOS deployment is a public-record body, set a universal transfer period, or appoint The National Archives as this project's custodian. | Legislative amendment, transfer-policy change, or deployment outside the Act's scope. |
| **Freedom of Information Act 2000 c. 36, s.46 Code of Practice**, 2021, ISBN `978-1-5286-2517-3`. Lord Chancellor / UK Government. <https://www.gov.uk/government/publications/code-of-practice-on-the-management-of-records-issued-under-section-46-the-freedom-of-information-act-2000> | Provides public-authority records-management practice supporting reliable creation, keeping, access, and disposal. | A public access regime depends on trustworthy records management, metadata, disposal control, and continuity, not only a request endpoint. | The Code is guidance, not a universal retention schedule or a finding that a particular design complies. | New Code, statutory amendment, ICO/TNA guidance change, or deployment-scope change. |
| **Freedom of Information Act 2000 c. 36, s.77**, alteration etc. of records with intent to prevent disclosure. Legislation.gov.uk. <https://www.legislation.gov.uk/ukpga/2000/36/section/77> and ICO official guidance <https://ico.org.uk/for-organisations/foi/freedom-of-information-and-environmental-information-regulations/retention-and-destruction-of-information/> | After a request, intentional alteration, erasure, destruction, or concealment intended to prevent disclosure can be an offence within scope; ordinary lawful retention practice is not converted into indefinite keeping of everything. | A request or legal-release process must create a durable disposal barrier over responsive records, while routine schedules remain independently governed. Deletion history and request timing must be recoverable. | It does not create a blanket FOI legal hold before every request, decide exemptions, or authorize public release. | Statutory/ICO guidance update or matter-specific request. |
| **CPR Practice Direction 57AD, paras. 3-4**, disclosure and document preservation in the Business and Property Courts. Ministry of Justice. <https://www.justice.gov.uk/courts/procedure-rules/civil/rules/part-57a-business-and-property-courts/practice-direction-57ad-disclosure-in-the-business-and-property-courts> | The preservation duty includes documents otherwise deleted under a retention policy; relevant deletion processes are suspended; employees/former employees and agents/third parties may need notice; written confirmation is required. | Legal hold must cover deletion systems and third-party custody, identify classes, retain evidence of notice/confirmation, and aggregate scope across stores. | The practice direction is procedural and scope-specific. It does not define all UK public-sector holds or make this report legal advice. | CPR/PD amendment, court order, or litigation-scope change. |
| **Procurement Act 2023 c. 54, s.98**, record-keeping. Legislation.gov.uk. <https://www.legislation.gov.uk/ukpga/2023/54/section/98> | Contracting authorities retain records sufficient to explain material decisions and communications within the statutory scheme. | Procurement-dependent authority needs durable decision chronology, communications, contract term, options, audit/records rights, and affected-system inventory. | It does not set PolicyOS's retention period, appoint a supplier, or prove a particular procurement record sufficient. | Statutory/regulatory amendment, commencement guidance update, or different procurement regime. |
| **Civil Contingencies Act 2004 c. 36, s.2** and **Emergency Preparedness, Chapter 6: Business Continuity Management**, Cabinet Office. <https://www.legislation.gov.uk/ukpga/2004/36/section/2> and <https://www.gov.uk/government/publications/emergency-preparedness> | Category 1 responders maintain plans to continue functions so far as reasonably practicable; official guidance covers business continuity arrangements, training, and exercising. | Public-sector continuity requires prioritized functions, trained execution, exercises, and evidence that plans work. Active-incident records deserve faster recovery than shadow work. | The duties do not apply automatically to every PolicyOS operator, do not establish the proposed RTO values, and do not absorb institutional-scale OPS-R12 scope. | Statutory/regulatory amendment, revised Chapter 6, or the ongoing 2026-2027 post-implementation review. |

### 3.1 Currentness note on UK continuity sources

The Cabinet Office opened a Civil Contingencies Act Call for Views on 2026-07-14 for the 2027
post-implementation review. The Act and existing guidance remain the inspected current sources, but
any implementation or legal conclusion must recheck the review outcome and revised guidance. This is
why the transfer is the principle of exercised, prioritized continuity, not a claim of permanent
wording or universal applicability.

## 4. Archival and long-term cryptographic sources

| Stable identifier and official source | Imported result | What transfers to government-record custody | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **ISO 14721:2025**, Space Data System Practices - Reference model for an Open Archival Information System (OAIS), Edition 3, published 2025-03. <https://www.iso.org/standard/87471.html> | An OAIS accepts organizational responsibility to preserve information and make it available to a designated community over technology, media, format, and knowledge-base change; functions include ingest, archival storage, data management, access, dissemination, and migration. | Preserve original content plus representation information, fixity, provenance, preservation planning, migration evidence, access routes, and organizational responsibility over a long horizon. | No claim of OAIS certification, no appointed archive, no mandatory vendor topology, no legal retention term, and no assumption that "open" means unrestricted public access. | ISO revision, preservation-horizon change, or designated-community change. |
| **PREMIS Data Dictionary for Preservation Metadata, Version 3.0**, Library of Congress. <https://www.loc.gov/standards/premis/v3/index.html> | Provides a practical preservation model centered on Objects, Events, Rights, and Agents. | Record preservation actions, fixity, rights basis, agents, migrations, failures, and custody changes as linked evidence rather than informal notes. | PREMIS is not adopted as the final PolicyOS schema or wire format and does not decide legal rights. | PREMIS version/errata update or implementation-design phase. |
| **RFC 4998**, Evidence Record Syntax, DOI `10.17487/RFC4998`. RFC Editor. <https://www.rfc-editor.org/info/rfc4998/> | Long-term proof for signed data can require archive timestamp and hash-tree renewal before algorithms, keys, or certificates lose adequate assurance. The RFC defines evidence-record syntax and processing. | Monitor cryptographic dependencies, renew evidence before weakness, retain original data and timestamp chains, and distinguish timestamp renewal from hash-tree renewal. | The RFC does not establish a government mandate, legal non-repudiation, PolicyOS trust policy, public-log profile, or complete verifier closure. It is an option pattern, not the selected wire format. | RFC status/errata change, cryptographic-policy change, or concrete implementation selection. |
| **RFC 6283**, Extensible Markup Language Evidence Record Syntax, DOI `10.17487/RFC6283`. RFC Editor. <https://www.rfc-editor.org/info/rfc6283/> | Provides an XML representation of evidence-record concepts. | Demonstrates that preservation semantics can survive representation change when the original evidence relation remains explicit. | No XML selection or PolicyOS serialization decision follows. | Concrete format selection or RFC status/errata change. |

## 5. Cross-jurisdiction synthesis

The U.S. and UK sources converge on several operational principles without being identical legal
regimes:

1. **Create and preserve adequate evidence.** Government decisions and material transactions require
   records sufficient to explain what happened, by whom, under what authority, and from what source.
2. **Disposition is governed.** Retention deadlines, authorized disposal, archives, holds, and
   litigation/disclosure duties must remain distinct and evidenced.
3. **A hold is scoped preservation, not validity.** It suspends destructive disposition over covered
   records, including third-party custody, but does not extend an expired authority or authorize use.
4. **Access and retention are related but not identical.** Freedom-of-information duties require
   trustworthy records and prevent obstructive destruction, but do not automatically require keeping
   everything forever or publishing restricted evidence.
5. **Procurement rights expire and records outlive service.** Contract term, audit rights, exit,
   records custody, and survival clauses need watched evidence; continued technical service is not
   renewal.
6. **Continuity must be exercised.** Plans and runbooks are inputs. Measured exercises, after-action
   evidence, remediation, and retest establish operational confidence.
7. **Long-term verification is an institutional service.** It requires fixity, representation
   information, cryptographic renewal, verifier closure, access routes, and succession evidence, not
   one permanent algorithm or one storage provider.

The sources do **not** converge on one retention period, one hold authority, one archive, one
procurement rule, or one legal effect. Those remain deployment-specific institutional decisions.

## 6. Conflicts and adjudication

### 6.1 NARA freeze FAQ versus current eCFR numbering

The NARA FAQ explains the operational distinction between agency hold and records-center freeze but
cites historical regulatory numbering. Current eCFR Part 1226 controls the regulation citation.
Transfer the operational distinction; do not repeat the obsolete number as current law.

### 6.2 FOI access versus disposal

FOI regimes support access to existing records and prohibit obstructive destruction in defined
circumstances. Records schedules and archival law separately govern normal retention/disposal. The
selected design therefore creates a request/hold disposal barrier when evidence requires it but does
not infer an indefinite retention duty from FOI alone.

### 6.3 Preservation access versus unrestricted publication

OAIS access is for a designated community and explicitly does not mean unrestricted access. Public
verification may expose some evidence openly, make some obtainable through a competent records
process, and keep some restricted. INT-R7's evidence-obtainability dimension and PAO-R36's public
change semantics remain separate from archive custody.

## 7. Transfer conclusion

The transferable result is a custody discipline: adequate records, governed disposition, scoped
holds, preserved originals, migration and renewal evidence, exercised continuity, independent
recovery, and separately reportable historical/current/public dimensions. The non-transferable
result is every jurisdictional conclusion, retention number, appointment, authority grant, or claim
that PolicyOS already meets those duties.
