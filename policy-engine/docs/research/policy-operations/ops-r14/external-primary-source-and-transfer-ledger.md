---
id: OPS-R14-EXTERNAL-LEDGER
artifact_kind: research_source_and_transfer_ledger
status: research_only
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
repository_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
audited_head: 3a694212aa47c4c2d8a631f8edc4ba8f7e15dce7
audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
source_review_date: 2026-08-06
amendment_date: 2026-08-08
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
or assert that PolicyOS is within any source's legal scope. Applicability, competent authority, and
the contents of a particular instrument are `institutionally_supplied` predicates under P37; OPS-R14
cannot use an unverified declaration of any of them to return a positive authority or gate result.
They must be admitted and resolved by the canonical institutional/legal process before implementation
or use in a real matter.

The review date is 2026-08-06. A source is rechecked on amendment, supersession, material guidance
update, jurisdiction change, contract change, or before any implementation relies on it.

## 2. United States federal sources

| Stable identifier and official source | Imported result | What transfers to government-record custody | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **44 U.S.C. 3101**, Records management by agency heads. Office of the Law Revision Counsel. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title44-section3101&num=0&edition=prelim> | Agency heads must make and preserve adequate and proper documentation of organization, functions, policies, decisions, procedures, and essential transactions. | Custody must preserve evidence needed to reconstruct an authority-bearing act, not only its final display. Decision chronology, source, role, and supporting evidence are part of recovery closure. | It does not establish that PolicyOS is a U.S. federal agency, set retention periods, or specify software architecture. | Amendment to Title 44 or deployment-jurisdiction change. |
| **44 U.S.C. 3105**, Safeguards. Office of the Law Revision Counsel. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title44-section3105&num=0&edition=prelim> | Agencies establish safeguards against removal/loss and notify the Archivist of unlawful removal/destruction. | Recovery must detect missing evidence and preserve a durable incident trail; silent loss is not acceptable closeout. | It does not define project incident roles, sanctions, or cross-border duties. | Statutory or relevant NARA-rule change. |
| **36 C.F.R. Part 1226**, Implementing disposition. eCFR. <https://www.ecfr.gov/current/title-36/chapter-XII/subchapter-B/part-1226> | Current federal rules govern authorized disposition, withdrawal of disposal authority, and temporary extension under special circumstances. | A hold/freeze can suspend disposition while the underlying schedule and passed deadline remain facts; release requires renewed disposal evaluation. | No retention term, PolicyOS hold authority, schema, or universal litigation rule is adopted. | eCFR/NARA change or non-federal deployment. |
| **NARA FRC Freeze Process Overview / FAQ**. <https://www.archives.gov/frc/arcis/freeze-faq> | Distinguishes an agency litigation hold from an FRC freeze and explains suspension for covered records outside agency physical custody. | A hold must reach third-party/separate custody domains; tagging only the primary store is insufficient. | Operational guidance, not a universal legal-hold rule; current eCFR controls over historical numbering. | Page/rule/arrangement change. |
| **Fed. R. Civ. P. 37(e)**, current U.S. Courts rules page. <https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-civil-procedure> | Preservation consequences concern ESI that should have been preserved in anticipation/conduct of litigation and reasonable preservation steps. | Drill evidence should show destructive processes were suspended for in-scope material and loss was detected, scoped, and reported. | It does not impose indefinite hold on every record, decide anticipation, or apply outside procedural scope. | Rule/case/matter-specific change. |
| **5 U.S.C. 552**, FOIA. Office of the Law Revision Counsel. <https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section552&num=0&edition=prelim> | Federal agencies provide access to existing agency records subject to statute and exemptions. | Evidence obtainability is a custody dimension; a competent access route may be needed without open publication. | Not a blanket schedule or publication authority; applicability/exemptions are undecided here. | Statute/agency rule/matter change. |
| **FAR 4.805**, current FAC 2026-01 effective 2026-03-13. Acquisition.gov. <https://www.acquisition.gov/far/4.805> | Contract files cover all media; alternate-media conversion must reproduce originals completely, accurately, and clearly and protect data from alteration. Investigations/litigation can extend retention. | Durable procurement records, complete/accurate format migration including signatures, transformation provenance, and visible investigation/hold interaction transfer. **Instrument-specific inference:** an audit right, exit duty, option, or survival clause is watched only when its existence, scope, term, and effect are proved from the admitted contract, statute, or agreement. | FAR 4.805 does not itself create a universal audit right, exit obligation, or survival clause; no FAR retention number, vendor/custodian, or legal-sufficiency conclusion is imported. | FAC/NARA/instrument/regime change. |
| **FEMA FCD-1 (2017)**, FEA `FCD-1`. FEMA guidance catalogue. <https://www.fema.gov/about/reports-and-data/guidance> | Federal executive continuity framework and plan elements emphasize planning, training, testing, assessment, and engagement. | Recovery objectives must be exercised and measured; continuity evidence includes exercises, after-action findings, and improvement closure. | No automatic application, PolicyOS custody-class definition, or OPS-R12 absorption. | Replacement FCD/guidance/scope change. |
| **NIST SP 800-34 Rev. 1**, DOI `10.6028/NIST.SP.800-34r1`. <https://doi.org/10.6028/NIST.SP.800-34r1> | Contingency priorities and strategies derive from impact and require testing, training, and exercises. | Custody classes need differentiated measured objectives and exercised paths; backup configuration is not recovery evidence. | No legal retention, public authority, or binding PolicyOS RPO/RTO. | Revision or architecture change. |
| **NIST SP 800-184**, DOI `10.6028/NIST.SP.800-184`. <https://doi.org/10.6028/NIST.SP.800-184> | Recovery planning includes playbooks, testing, metrics, improvement, and coordination. | Retain outcomes, failure injections, playbook execution, lessons, remediation, and retest. | No legal-hold authority, signed-record semantics, or government mandate for PolicyOS. | Revision or threat/architecture change. |

## 3. United Kingdom sources

| Stable identifier and official source | Imported result | What transfers to government-record custody | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **Public Records Act 1958 c.51 s.3**, legislation.gov.uk. <https://www.legislation.gov.uk/ukpga/1958/51/section/3> | Public-record bodies have duties around selection, preservation, transfer, and authorized disposal within scope. | Distinguish preservation, transfer, and disposal authority; organization change must not orphan records or erase provenance. | No universal applicability/period or appointment of The National Archives. | Legislative/transfer-policy/scope change. |
| **FOIA 2000 s.46 Code of Practice** (2021), ISBN `978-1-5286-2517-3`. <https://www.gov.uk/government/publications/code-of-practice-on-the-management-of-records-issued-under-section-46-the-freedom-of-information-act-2000> | Public-authority records-management practice supports reliable creation, keeping, access, and disposal. | Public access depends on trustworthy records management, metadata, disposal control, and continuity—not only a request endpoint. | Guidance, not a universal schedule or proof of compliance. | New Code/statute/guidance/scope change. |
| **FOIA 2000 s.77** and ICO guidance. <https://www.legislation.gov.uk/ukpga/2000/36/section/77> and <https://ico.org.uk/for-organisations/foi/freedom-of-information-and-environmental-information-regulations/retention-and-destruction-of-information/> | Intentional alteration, erasure, destruction, or concealment after a request to prevent disclosure can be an offence within scope; lawful ordinary retention is not converted into indefinite keeping. | A request/legal-release process can create a durable disposal barrier over responsive records; deletion history and request timing must be recoverable. | No pre-request blanket hold, exemption decision, or publication authority. | Statute/guidance/matter change. |
| **CPR PD 57AD paras.3–4**. <https://www.justice.gov.uk/courts/procedure-rules/civil/rules/part-57a-business-and-property-courts/practice-direction-57ad-disclosure-in-the-business-and-property-courts> | Preservation includes documents otherwise deleted under policy; deletion processes are suspended; employees/former employees and agents/third parties may need notice/confirmation. | Holds cover deletion systems and third-party custody, identify classes, retain notice/confirmation evidence, and aggregate scope. | Procedural and scope-specific; not all UK public-sector holds or legal advice. | PD/order/litigation-scope change. |
| **Procurement Act 2023 c.54 s.98**, legislation.gov.uk. <https://www.legislation.gov.uk/ukpga/2023/54/section/98> | Contracting authorities retain records sufficient to explain material decisions and communications within the statutory scheme. | Durable decision chronology and communications transfer. **Instrument-specific inference:** contract term, options, audit/records rights, exit duties, and survival clauses enter the watched-dependency set only when the admitted instrument or applicable rule actually establishes them. | Section 98 does not itself create universal audit rights, exit duties, or survival effects; it sets no PolicyOS retention period, supplier appointment, or sufficiency conclusion. | Statute/regulation/instrument/regime change. |
| **Civil Contingencies Act 2004 s.2** and **Emergency Preparedness Ch.6**. <https://www.legislation.gov.uk/ukpga/2004/36/section/2> and <https://www.gov.uk/government/publications/emergency-preparedness> | Category 1 responders maintain continuity plans so far as reasonably practicable; guidance covers arrangements, training, and exercise. | Public-sector continuity requires prioritized functions, trained execution, exercises, and evidence that plans work. | No automatic application, proposed-RTO authority, or OPS-R12 absorption. | Statute/guidance/review/scope change. |

### 3.1 Currentness note on UK continuity sources

The Cabinet Office opened a Civil Contingencies Act Call for Views on 2026-07-14 for the 2027 post-
implementation review. The inspected Act/guidance remain the source, but any implementation or legal
conclusion must recheck the outcome. The transfer is exercised, prioritized continuity—not permanent
wording or universal applicability.

## 4. Archival and long-term cryptographic sources

| Stable identifier and official source | Imported result | What transfers | What does not transfer | Recheck trigger |
| --- | --- | --- | --- | --- |
| **ISO 14721:2025**, OAIS Edition 3. <https://www.iso.org/standard/87471.html> | An OAIS accepts organizational responsibility to preserve information and make it available to a designated community across technology/media/format/knowledge change. | Originals, representation information, fixity, provenance, planning, migration evidence, access routes, and organizational responsibility. | No certification, archive/vendor topology, legal period, or inference that “open” means unrestricted public. | Revision/horizon/community change. |
| **PREMIS Data Dictionary 3.0**, Library of Congress. <https://www.loc.gov/standards/premis/v3/index.html> | Practical preservation model centered on Objects, Events, Rights, and Agents. | Link preservation actions, fixity, rights basis, agents, migrations, failures, and custody changes. | Not adopted as PolicyOS schema/wire and does not decide rights. | Version/errata/design phase. |
| **RFC 4998**, DOI `10.17487/RFC4998`. <https://www.rfc-editor.org/info/rfc4998/> | Long-term proof can require archive timestamp and hash-tree renewal before algorithm/key/certificate assurance weakens. | Monitor dependencies, renew evidence before weakness, retain originals/timestamp chains, distinguish renewal types. | No government mandate, legal non-repudiation, trust policy, public-log profile, or selected wire. | RFC/errata/policy/selection change. |
| **RFC 6283**, DOI `10.17487/RFC6283`. <https://www.rfc-editor.org/info/rfc6283/> | XML representation of evidence-record concepts. | Shows preservation relations can survive representation change when evidence remains explicit. | No XML or serialization selection. | Selection/RFC change. |

## 5. Cross-jurisdiction synthesis

The U.S. and UK sources converge on operating principles without becoming one legal regime:

1. **Create and preserve adequate evidence.** Decisions and material transactions need records of
   what happened, by whom, under what authority, and from what evidence.
2. **Disposition is governed.** Retention deadlines, disposal, archives, holds, litigation,
   disclosure, and procurement records remain distinct and evidenced.
3. **A hold is scoped preservation, not validity.** It suspends destructive disposition over covered
   records, including third-party custody, without extending authority or authorizing use.
4. **Access and retention differ.** FOI duties require trustworthy records and can prohibit
   obstructive destruction, but do not require keeping everything forever or publishing restricted
   evidence.
5. **Procurement records outlive service; other rights are instrument-specific.** Durable procurement
   chronology survives as required by the applicable regime. Contract term, options, audit rights,
   exit duties, records rights, and survival clauses are watched only when the admitted contract,
   statute, or agreement proves that they exist and defines their scope/effect. Continued technical
   service cannot establish renewal.
6. **Continuity must be exercised.** Plans/runbooks are inputs; measured exercises, after-action
   evidence, remediation, and retest establish operational confidence.
7. **Long-term verification is an institutional service.** It requires fixity, representation
   information, cryptographic renewal, verifier closure, access routes, and succession—not one
   algorithm or provider.

The sources do **not** converge on one retention period, hold authority, archive, procurement rule,
audit right, exit duty, survival effect, or legal consequence. Those remain deployment- and
instrument-specific institutional decisions.

## 6. Conflicts and adjudication

### 6.1 NARA freeze FAQ versus current eCFR numbering

The FAQ supplies the operational distinction between agency hold and records-center freeze but cites
historical numbering. Current eCFR Part 1226 controls the regulation citation. Transfer the
distinction, not the obsolete number.

### 6.2 FOI access versus disposal

FOI supports access to existing records and prohibits obstructive destruction in defined
circumstances. Schedules/archival law separately govern ordinary retention. A request/hold barrier is
created only when admitted evidence requires it; no indefinite duty is inferred from FOI alone.

### 6.3 Preservation access versus unrestricted publication

OAIS access is for a designated community, not necessarily unrestricted access. Public verification
may be open, obtainable through a competent process, restricted, or unavailable. INT-R7 obtainability
and PAO-R36 public-change semantics remain separate from archive custody.

### 6.4 Procurement record duty versus instrument-specific rights

FAR 4.805 and Procurement Act s.98 support durable contract files and decision/communication records.
They do not by themselves establish that a particular audit right, exit obligation, option, or
survival clause exists or outlives service. Those propositions must be read from and content-bound to
the admitted instrument or applicable rule; until then they are institutionally supplied and
non-positive under P37.

## 7. Transfer conclusion and standing

The transferable result is a custody discipline: adequate records, governed disposition, scoped
holds, preserved originals, migration/renewal evidence, exercised continuity, independent recovery,
and separately reportable historical/current/public dimensions. The non-transferable result is every
jurisdictional conclusion, period, appointment, authority grant, instrument-specific right, or claim
that PolicyOS already meets those duties.

**Research standing:** `accepted_narrow_scope`.  
**Capability standing:** `NO_GO`.  
**First-public-signature gate standing:** `NO_GO`.
