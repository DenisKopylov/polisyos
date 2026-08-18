---
title: PAO-R36 - Anchor and Citation Verification
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_pass_ii_external_source_verification
  - pao_r36_internal_anchor_verification
  - pao_r36_transfer_limit_dispositions
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 anchor and citation verification

## 1. Method

Every row in the external ledger at
`policy-engine/docs/research/policy-operations/pao-r36/external-primary-source-and-transfer-ledger.md:25-70`
was checked against the named official publication, official legislation database, standards-owner
record, or source DOI. Stable identifiers rather than mutable page prose control the verification.
Where a direct official endpoint rate-limited an anonymous request, the stable identifier, official
metadata, and a second official publication from the same authority were cross-checked; no result is
upgraded to legal sufficiency.

The audit asks four questions for each row:

1. does the identifier resolve to the named source;
2. does the source establish the source-regime proposition;
3. is the PolicyOS transfer no stronger than that proposition; and
4. does the “does not transfer” column prevent jurisdictional or institutional laundering?

## 2. External primary-source ledger verification

| ID | Stable source checked | Source proposition verified | Transfer verdict |
| --- | --- | --- | --- |
| EU-01 | TFEU Article 296, CELEX `12016E296`, ELI `eli/treaty/tfeu_2016/art_296/oj` | Union legal acts state reasons and refer to the Treaty-prescribed proposal/initiative/opinion basis. | **Supported.** The transfer is only a reasons-bearing correction-notice design rule; the row expressly refuses to make PolicyOS an EU institution or settle sufficient reasons. |
| EU-02 | Charter Article 41, CELEX `12012P041` | Good administration includes impartial/fair handling, hearing before an adverse individual measure, file access subject to legitimate confidentiality, reasons, and language correspondence. | **Supported.** PAO-R36 transfers only the need for an adverse-impact/affected-party decision and expressly refuses a universal hearing, notice, or remedy rule. |
| EU-03 | Council Regulation No 1, CELEX `31958R0001`, consolidated `01958R0001-20130701` | The regulation enumerates official/working languages and language rules for institutional communications and the Official Journal. | **Supported only in part.** It supports governed enumeration of authoritative languages. It does **not** establish language-invariant semantic identity; that is a PAO-R36/INT-R6 requirement. `PAO-R36-II-004`. |
| EU-04 | Directive (EU) 2016/2102, CELEX `32016L2102` | Public-sector websites/mobile applications are subject to accessibility duties, accessibility statements, and feedback mechanisms. | **Supported only after narrowing.** It supports accessibility of the notice, links, status, and any otherwise-required recourse. It does not create substantive recourse. `PAO-R36-II-002`. |
| EU-05 | Council Regulation 354/83, CELEX `31983R0354` | The regulation governs permanent historical archives and public access after current administrative use, subject to exceptions. | **Supported.** The transfer is preservation/current-authority separation; retention, restrictions, and legal hold remain excluded. |
| EU-06 | ESS Guidelines on Revision Policy for PEEIs, product `KS-RA-13-016`, DOI `10.2785/42763` | The guidelines harmonize transparent revision policies and distinguish routine, major, and non-scheduled revisions; Eurostat also publishes reasons, schedules, metadata, and quality analysis. | **Supported and carefully bounded.** Policy, classification, vintages, reasons, and revision analysis transfer; signer authority, individual effect, and legal significance do not. `PAO-R36-II-001`. |
| US-01 | 44 U.S.C. § 3101, Pub. L. 90-620, 82 Stat. 1297 | Federal agencies must make and preserve adequate and proper records documenting organization, functions, policies, decisions, procedures, and essential transactions, including effects on persons' rights. | **Supported.** The row transfers preservation of original/correction/reasons/version-used and expressly refuses federal-agency status or retention/legal-hold conclusions. |
| US-02 | 5 U.S.C. § 553(c) | Informal rulemaking concludes with a concise general statement of basis and purpose. | **Supported as an analogue.** It supports a reasons-bearing notice, not a claim that APA rulemaking governs PolicyOS. |
| US-03 | NARA Office of the Federal Register Document Drafting Handbook; 1 C.F.R. § 18.13(a) | For specified pre-publication corrections, the original submission and authorized correction instruction are retained; substantial electronic changes may require a newly signed submission. | **Supported.** The no-mutation/original-plus-authorized-successor transfer is bounded; OFR forms, roles, and timing do not transfer. |
| US-04 | NARA “Correcting the Federal Register and CFR”; 1 C.F.R. § 18.15 | Agency-originated substantive errors are corrected through an authorized corrective document in the publication-of-record system. | **Supported.** It justifies a separate durable notice, not a PolicyOS venue, threshold, or deadline. |
| US-05 | Federal Register publication system; 44 U.S.C. § 4101; 1 C.F.R. § 5.10 | The official electronic Federal Register has durable citation and preserved editions under the statutory publication system. | **Supported.** It supports distinguishing publication of record from convenience projections and does not appoint a PolicyOS publication-of-record surface. |
| US-06 | 29 U.S.C. § 794d | Federal electronic and information technology is subject to accessibility requirements. | **Supported.** The transfer is channel accessibility—not compliance, a technical standard choice, or a substantive notification duty. |
| UK-01 | Code of Practice for Statistics, Edition 3.0, Standard 3.9 | Revisions/corrections are transparent, governed by a published policy, and state their nature and scale. | **Supported.** The row explicitly refuses to convert “as soon as possible” into a recovery objective or universal deadline. |
| UK-02 | ONS Revisions Policy and Correction of Errors Policy, updated 9 August 2024 | ONS separates revisions from errors and adds a dated explanation to the affected release when errors are corrected. | **Supported.** The transfer that the affected record itself disclose what/why/when is sound; ONS materiality/UI practice is excluded. |
| UK-03 | ONS real-time datasets and revision triangles | ONS publishes successive vintages and provides tools/analysis for revisions across releases. | **Supported.** Version retrieval and comparative monitoring transfer; signatures, currentness, and legal effect do not. |
| UK-04 | ONS Consumer Price Inflation Revisions and Correction of Errors Policy, December 2025 | Published RPI values generally are not revised because of significant financial/legal uses, while qualifying errors are still publicly notified and explained. | **Supported.** It is a strong analogue for an old version retaining legal/operational significance; RPI-specific thresholds and non-revision rules do not transfer. |
| UK-05 | The Gazette, “Removing notices after they have been published” | Published notices generally remain part of the official record; narrow redaction/removal pathways address exceptional safety/privacy circumstances. | **Supported.** Additive correction and separately governed safety redaction transfer; no absolute anti-redaction rule or Gazette appointment follows. |
| UK-06 | Gazette notices `4418985`, `4891030`, `4900924` | The cited correction/replacement notices identify earlier publications, corrected propositions, dates/reasons, and—where applicable—objection routes. | **Supported as publication examples.** The specific statutory procedures do not generalize. |
| UK-07 | Public Records Act 1958 s.3 and UK National Archives digitisation guidance | Public records and their custody/context are safeguarded; digitisation does not by itself erase the original record, and lawful disposition remains separately governed. | **Supported.** Distinct original/successor records and provenance transfer; PolicyOS public-record status and retention do not. |
| UK-08 | Public Sector Bodies (Websites and Mobile Applications) (No. 2) Accessibility Regulations 2018, SI `2018/952` | Covered public-sector websites/apps require accessible content, an accessibility statement, and feedback/enforcement routes. | **Supported only after narrowing.** Accessibility is a completion dimension for content already required by another source; it is not the source of substantive recourse. `PAO-R36-II-002`. |
| STD-01 | ISO 15489-1:2016 | Records management covers creation/capture/management of records, metadata, responsibilities, controls, monitoring, and records processes over time. | **Supported.** The transfer is lifecycle discipline, not a correction protocol or public-notice duty. |
| STD-02 | ISO 14721:2025, OAIS Reference Model, edition 3 | OAIS defines preservation responsibilities, information packages/functions, access, migration, and a designated community. | **Supported.** It justifies bounded archive-set/designated-community claims, not currentness authority, vendor selection, or certification. |
| STD-03 | PREMIS Data Dictionary for Preservation Metadata, version 3.0 | PREMIS represents preservation objects, events, agents, rights, and relationships. | **Supported.** Explicit correction/preservation relations transfer; no serialization or authority rule is adopted. |
| SCH-01 | COPE Retraction Guidelines, DOI `10.24318/cope.2019.1.4` | The current DOI record describes retained, conspicuous, bidirectionally linked retraction notices rather than silent disappearance. | **Transfer supported; citation needs edition pin.** The DOI now resolves to Version 3, August 2025. The PAO row names no edition/date and could be read as the 2019 edition embedded in the DOI string. `PAO-R36-II-003`. |

## 3. Statistical-agency over-transfer test

The statistical analogue is the strongest external part of the research, not its weakest. The PAO
ledger transfers five mature practices:

1. a published revision/correction policy;
2. planned/routine/unplanned classification;
3. explicit reasons, scope, timing, and user information;
4. preserved vintages/real-time datasets; and
5. revision analysis, including triangles where useful.

It expressly refuses to transfer signer authority, legal sufficiency, currentness ownership,
individual administrative effect, or the legal significance of a superseded version
(`external-primary-source-and-transfer-ledger.md:38, 51-55`). That boundary is correct. The ONS RPI
example is used as an existence proof that old releases can remain significant, not as a rule that
PolicyOS must never revise a value. No material over-transfer was found.

### `PAO-R36-II-001` — commendation — statistical revision practice is transferred honestly

The closest mature analogue is treated seriously while its authority limits remain explicit. The
revision-policy claims survive consolidation.

## 4. External-source findings

### `PAO-R36-II-002` — minor — accessibility does not create substantive recourse

Rows EU-04 and UK-08 at
`policy-engine/docs/research/policy-operations/pao-r36/external-primary-source-and-transfer-ledger.md:36,58`
say that “recourse” belongs in the controlled accessible-surface set or is a completion dimension.
The cited accessibility regimes support making a required route accessible and supplying statutory
feedback/accessibility-statement mechanisms. They do not establish the underlying administrative
recourse obligation. Revise the transfer to “any otherwise-required recourse/feedback route must be
accessible.”

### `PAO-R36-II-003` — minor — the COPE DOI needs an edition/date

The DOI `10.24318/cope.2019.1.4` currently resolves to **Retraction Guidelines, Version 3, August
2025**. The substantive transfer remains right, but the source ledger should pin the edition/date so
a future DOI update cannot silently change the cited text.

### `PAO-R36-II-004` — minor — Regulation No 1 does not establish semantic identity

Regulation No 1 establishes a governed institutional language regime. The requirement that one
correction have a language-invariant semantic identity is a PAO-R36 interface obligation to INT-R6,
not a proposition established by the Regulation. Narrow the source transfer accordingly.

### `PAO-R36-II-005` — commendation — jurisdiction-specific duties are not laundered

Every legal/publication row has a non-transfer column. The synthesis at
`external-primary-source-and-transfer-ledger.md:64-70` expressly excludes competence, deadlines,
legal effect, hearing/notification sufficiency, venue, retention, and remedy. No source is cited as if
it directly imposes a legal duty on PolicyOS.

## 5. Internal anchor verification

| Internal anchor | Audited use | Verification |
| --- | --- | --- |
| `PV-K01` | Separately report current authority and bind it to authenticated `as_of`. | Correctly cited by finding ID and carried into currentness/feed/notice requirements. |
| `PV-K02` | Preserve historical authenticity while current authority changes append-only. | Correctly consumed; no re-litigation found. F02/F03/F09 make violations observable. |
| `PV-K04` | Notice may compress but must not amplify truth, authority, currency, certainty, or permission. | Correctly consumed in the protected-query notice contract and F06. |
| `S0-K08` | Correction appends; history is not rewritten. | Correctly consumed in successor identity, archive preservation, and incident repair. |
| `INT-K05` | No parent/parallel confidence ledger; future composition stays with the same owner. | Correctly used only as an owner-discipline analogy. It is not misrepresented as the correction rule itself. |
| GY-N12 | Sole epoch/currentness/current-head/reissue owner. | Correctly declared undelivered and consumed by interface; no second currentness owner is proposed. |
| INT-R7 | Signature/key-status/history/currentness distinctions. | Substantive use is correct, but citations should include terminal controlling §18 (`int-r7/public-verification-profile.md:620-760`) rather than relying only on earlier rows. |
| P35/P36 | Complete denominators; cite findings, not adjacent prose. | The research is strong on frozen denominators and finding IDs, except for the unresolved `supersede` census and the non-terminal INT-R7 citations. |

## 6. Citation conclusion

The source foundation is fit for consolidation after three minor citation-transfer corrections. No
external source is used to establish a duty PolicyOS actually has, a legally sufficient notice, a
retention period, a publication venue, or a remedy. The main statistical-agency transfer is careful
and should survive revision unchanged.
