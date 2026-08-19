---
title: "INT-R8 external primary-source and transfer ledger"
research_id: INT-R8
artifact_role: source-and-transfer-ledger
status: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
prepared_at: 2026-08-04
source_as_of: 2026-08-04
amended_after_audit: research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2
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

# INT-R8 external primary-source and transfer ledger

## 0. Controlling amendment notice

This source ledger executes R3 and R12. It preserves the audited source corpus and transfer limits,
corrects two mutable-source custody defects, and adds deterministic quantitative-information-flow
families that the audited version omitted.

No source below establishes that PolicyOS complies with a jurisdiction, that any institution is
competent to publish, or that any numerical disclosure value is presently justified.

## 1. Source-selection and version-custody rule

Priority remains:

1. enacted or officially consolidated law;
2. official tribunal, agency, or statistical-institute practice;
3. primary peer-reviewed or official technical literature.

For mutable web guidance, this ledger records an `as_of` date and narrows the proposition to what
was independently readable on that date. A living page is not silently represented as a frozen
historical edition.

Resolution vocabulary:

- `stable` — statute, DOI, CELEX, arXiv, Federal Register ID, or official fixed file path;
- `living_as_of_2026-08-04` — official page/download whose proposition was checked as of that date;
- `historical_edition_not_pinned` — the old edition named in v1 cannot be reproduced from a stable
  identifier and is not used as current evidence; and
- `candidate_future_model` — mathematically real, but no PolicyOS model or owner is established.

## 2. Public-administration, access, reasons, and accessibility sources

| ID | Stable identifier / custody | Proposition used | Transfer to INT-R8 | Non-transfer boundary |
|---|---|---|---|---|
| US-APA-557 | 5 U.S.C. § 557(c)(3)(A), official U.S. Code; `stable` | Covered formal adjudication decisions state findings/conclusions and reasons or basis on material issues. | Material findings and reasons are candidate mandatory semantics. | Not a universal duty for every PolicyOS record. |
| US-FOIA-552 | 5 U.S.C. § 552(b), final paragraph; `stable` | Reasonably segregable material is released after exempt deletion; amount/place of deletion is generally indicated unless that indication harms the protected interest. | Supports typed omission and the rule that a manifest may itself need safe coarsening. | No direct FOIA applicability or requirement to expose self-disclosing metadata. |
| US-PWA-2010 | Plain Writing Act, Pub. L. 111-274, 124 Stat. 2861, GovInfo `PLAW-111publ274`; `stable` | Covered federal documents use clear communication the public can understand and use. | Supports faithful plain-language condensation. | Readability does not authorize loss of basis, limitations, dissent, or negative outcomes. |
| AU-ADJR-1977 | Administrative Decisions (Judicial Review) Act 1977 (Cth), Federal Register `C2004A01697`, s 13; `stable` | A qualifying requester may obtain material factual findings, evidence/material references, and reasons, subject to exceptions. | Supports reasons and contestability as load-bearing. | Not a universal reasons format or legal-sufficiency finding. |
| AU-FOI-1982 | Freedom of Information Act 1982 (Cth), Federal Register `C2004A02562`; `stable` | Official access, exemption, review, and complaint structures coexist. | Supports layered access plus honest visible summary. | Access control/exemption does not itself prove compression parity. |
| NSW-MHRT-PD-G2 | NSW MHRT official file `files/mhrt/pdf/GeneralNo2-Dissenting Opinions.pdf`, official index last-modified 2025-03-24, checked 2026-08-04; `living_as_of_2026-08-04` | The Tribunal maintains a formal General No. 2 practice direction dedicated to dissenting opinions. | Supports treating dissent as a formally governed decision artifact rather than informal noise. | V1's exact three-member/material-matter/signed-and-dated wording is not relied upon here without a content digest or fixed edition text; no universal identity/publication rule follows. |
| EU-WAD-2016 | Directive (EU) 2016/2102, CELEX `32016L2102`, ELI `dir/2016/2102/oj`; `stable` | Public-sector websites and apps are subject to accessibility requirements and monitoring/statement duties. | Critical caveats must survive accessible and alternate representations. | The Directive does not define PolicyOS semantic parity. |
| EUIPO-BOA-SUMMARY | EUIPO Boards of Appeal official decisions/overview page, checked 2026-08-04; `living_as_of_2026-08-04` | Selected summaries are informational and may not reproduce exact wording; case references lead to decisions. | Supports explicit summary status and authoritative pointer. | A pointer/notice does not cure materially misleading visible prose. |

## 3. Statistical disclosure-control sources

| ID | Stable identifier / custody | Proposition used | Transfer to INT-R8 | Non-transfer boundary |
|---|---|---|---|---|
| UK-ONS-SDC | ONS official “Statistical disclosure control” policy page, checked 2026-08-04; `living_as_of_2026-08-04` | Outputs for publication or specific recipients are checked for disclosure risk and controlled as required; assessment is contextual. | Every audience view/version/export is a release event and prior outputs matter. | No exhaustive theorem for narrative policy records. |
| UK-ONS-SRS-CURRENT | ONS “Supporting your research project” / output, ingest and transfer guidance plus current related `SRS Output Checking Guidance Document`, checked 2026-08-04; `living_as_of_2026-08-04` | Material leaving the SRS is an output request subject to checking; request files are retained for stated periods. | Supports prospective actual-output review and custody of release requests. | The audited “12 June 2023” edition is not treated as the current fixed edition. Risk classes or thresholds must be cited to a pinned edition before exact import. |
| UK-ONS-SRS-2023-HIST | V1 label “SRS Output Checking Guidance Document, 12 June 2023”; `historical_edition_not_pinned` | Historical proposition only: an official guidance edition existed. | Preserved as audit history. | It is not current authority and supplies no exact quoted rule until an official archive/digest is bound. |
| AU-ABS-DATALAB | ABS DataLab Clearance official guidance, checked 2026-08-04; `living_as_of_2026-08-04` | Outputs require ABS approval before leaving DataLab; users apply output rules and provide evidence. | Supports pre-release checking of actual candidate output. | Not a numerical PolicyOS budget. |
| AU-ABS-OUTPUT-RULES | ABS DataLab Output Rules / detailed examples, checked 2026-08-04; `living_as_of_2026-08-04` | Official examples use contributor thresholds and differencing/secondary-disclosure checks. | Supplies rule-of-N and cumulative-output comparators. | The number 10 is not imported as a universal threshold or legal guarantee. |

### R12 disposition

The mutable ONS and NSW items now have explicit custody:

- the current ONS proposition is tied to the living official page/download as of 2026-08-04;
- the former 12 June 2023 label is marked historical and unpinned rather than silently current;
- the NSW item is tied to the official file path and index modification date; and
- the NSW proposition is narrowed to the existence and subject of the formal dissent practice
  direction. Exact internal wording requires a fixed byte digest or edition before stronger use.

## 4. Differential privacy and quantitative-information-flow sources

| ID | Stable identifier | Primary proposition used | INT-R8 disposition |
|---|---|---|---|
| NIST-DP-800-226 | NIST SP 800-226 (2025), DOI `10.6028/NIST.SP.800-226` | DP guarantees depend on correctly specified neighboring inputs, mechanisms, parameters, implementation, and threat assumptions. | Premise-audit source; no DP label by analogy. |
| DP-COMPOSITION-2015 | Kairouz, Oh, Viswanath, PMLR 37:1376-1385; arXiv `1311.0776` | Composition characterizes privacy degradation for mechanisms already satisfying local DP guarantees, including adaptive interaction under its premises. | Valid theorem family; current PolicyOS editorial projection has no local DP contract/accountant. |
| MAX-LEAKAGE-2020 | Issa, Wagner, Kamath, DOI `10.1109/TIT.2019.2962804`; arXiv `1807.07878` | Maximal leakage measures multiplicative guessing improvement through a channel. | Demonstrates that a numerical leakage framework is not excluded by deterministic channel semantics alone. No current PolicyOS secret/channel model exists. |
| QIF-MINENTROPY-2009 | Geoffrey Smith, “On the Foundations of Quantitative Information Flow,” FoSSaCS 2009, DOI `10.1007/978-3-642-00596-1_21` | Min-entropy vulnerability/leakage quantifies adversarial guessing under a declared secret distribution and channel. | Candidate deterministic or probabilistic QIF model; no canonical PolicyOS prior/support/channel. |
| QIF-GLEAKAGE-2012 | Alvim, Chatzikokolakis, Palamidessi, Smith, IEEE CSF 2012, DOI `10.1109/CSF.2012.26`, HAL `hal-00734044v1` | Generalized gain functions model different adversary benefits and induce g-leakage/capacity relations. | Shows that the gain function is a load-bearing model choice. PolicyOS has no competent canonical gain package. |
| MAX-ALPHA-2019 | Liao, Kosut, Sankar, Calmon, IEEE TIT 65(12):8043-8066, DOI `10.1109/TIT.2019.2935768`; arXiv `1809.09231` | Maximal-alpha leakage interpolates information-leakage objectives, has data processing and sub-additivity supporting a weak composition result. | Candidate numerical family for deterministic or randomized channels under its assumptions; no local value or applicable composition owner exists in PolicyOS. |
| STAT-MAX-LEAKAGE-2026 | Wang, Lin, Fanti, “Statistic Maximal Leakage,” Entropy 28(7):819, DOI `10.3390/e28070819`; arXiv `2411.18531` | Measures leakage about a specified statistic, has composition/post-processing properties, and analyzes efficient computation for deterministic release mechanisms. | Direct counterexample to “determinism makes numerical leakage impossible.” It does not define the statistic, prior/support, channel, or owner for PolicyOS. |

## 5. Corrected R3 theorem and transfer test

### 5.1 What is established

The repository cannot currently issue a canonical numerical disclosure-composition claim because
no established source contract supplies the complete premises of any surveyed quantitative model:

- declared protected secret or statistic;
- release channel, including side channels and history;
- support or prior assumptions where required;
- adversary gain/loss objective;
- local leakage or privacy guarantee valid for the actual release mechanism;
- prospective allocation or acceptance rule;
- composition theorem applicable to the history-selected sequence;
- canonical owner able to reproduce membership, chronology, model versions, local values, and
  aggregate result; and
- authority boundary preventing the number from becoming a compliance or publication claim.

Therefore the controlling conclusion is:

> No canonical numerical disclosure-composition claim is justified for the current PolicyOS
> release path under any model established in the repository.

### 5.2 What is not established

The amendment withdraws the broader claim that randomization is necessary for every numerical
leakage framework. Randomization is a defining premise of differential privacy's probabilistic
comparison. It is not an eliminating property for maximal leakage, maximal-alpha leakage,
statistic maximal leakage, min-entropy leakage, or generalized-gain QIF.

No new number is issued. These families become specified future research doors, not current
capabilities.

## 6. Comparative-model transfer ledger

| Imported family | Transfers now | Does not transfer now | What would settle future use |
|---|---|---|---|
| DP | Neighbor/mechanism/local-guarantee/accountant premise checklist | Epsilon/delta for editorial projections | A bounded statistical release contract with tested local DP guarantees and adaptive accountant. |
| Maximal leakage | Explicit secret/channel/guessing objective and view-synergy analysis | Current scalar or universal legal/privacy meaning | Canonical secret/channel/support model, local computation, composition semantics, and owner. |
| Maximal-alpha leakage | Tunable adversary objective, data processing, model-specific weak composition | Automatic summation or one alpha for heterogeneous harms | Competently selected alpha/loss semantics, local channel values, and applicable composition rule. |
| Statistic maximal leakage | A named protected statistic can be analyzed even for deterministic release | Treating every policy-record harm as one statistic | A canonical statistic family, prior/support semantics, deterministic channel model, and owner. |
| Min-entropy leakage | Worst-case guessing vulnerability under declared distribution/channel | Distribution-free exact reconstruction or universal risk score | Justified prior/support and channel; otherwise retain exact consistency-set Boolean analysis. |
| Generalized-gain leakage | Explicitly model what the adversary values | One self-evident gain function for citizens, insiders, reviewers, or institutions | Competent gain-package governance and separate reporting for heterogeneous harms. |
| Exact consistency sets | Distribution-free exact uniqueness/non-uniqueness test | Approximate/high-confidence leakage or protection against unknown auxiliary data | Finite/decidable model or proved-conservative abstraction, protected predicates, and declared release family. |

## 7. Legal and administrative transfer ledger

| Imported result | Transfers | Does not transfer |
|---|---|---|
| Material findings/reasons | Preserve basis needed for understanding and challenge | Universal legal duty or sufficiency result |
| Segregability/deletion indication | Safe typed omission rather than silent deletion | Self-disclosing omission metadata or direct statutory applicability |
| Formal dissent practice | Preserve existence and material effect of dissent where governed | Universal publication of identity, wording, or outcome effect |
| Plain language/accessibility | Faithful shorter language and visible caveats across representations | Permission to delete qualifiers for readability |
| Summary plus full-decision pointer | Explicitly label summary and bind current authoritative record | Pointer as cure for false or materially broadened prose |
| Output checking | Check each actual view/version/export and accumulated prior releases | Cell rules as narrative reasons or universal scalar budget |

## 8. Source conflicts and adjudication

### Deletion indication versus confidentiality

The FOIA source contains its own exception where indication would harm the protected interest.
INT-R8 therefore requires a safe semantic-class/effect notice, not either silent deletion or a
manifest that becomes an oracle.

### Plain language versus full reasons

Faithful condensation is allowed. Truth-changing qualifiers, material counterpositions, denied
uses, and negative outcomes remain mandatory. Accessibility is evaluated on the actual rendered
representation, not merely source text.

### Statistical thresholds versus cumulative inference

A local threshold can pass while differencing across releases fails. The transferable rule is
actual-output and prior-output review, not one number.

### DP versus deterministic QIF

DP does not transfer because its mechanism premises are absent. Deterministic QIF is not rejected;
it remains unavailable because PolicyOS has not established its secret/channel/gain/composition
model or owner.

## 9. Stable-reference checklist

A future verifier should resolve at least:

- 5 U.S.C. §§ 552 and 557;
- GovInfo `PLAW-111publ274`;
- Federal Register `C2004A01697` and `C2004A02562`;
- NSW MHRT official `GeneralNo2-Dissenting Opinions.pdf` plus a future content digest;
- CELEX `32016L2102` / ELI `dir/2016/2102/oj`;
- ONS SDC and SRS output/transfer living pages with an explicit as-of date;
- ABS DataLab clearance/output-rules pages with an explicit as-of date;
- DOI `10.6028/NIST.SP.800-226`;
- arXiv `1311.0776` / PMLR 37;
- DOI `10.1109/TIT.2019.2962804`;
- DOI `10.1007/978-3-642-00596-1_21`;
- DOI `10.1109/CSF.2012.26`;
- DOI `10.1109/TIT.2019.2935768`; and
- DOI `10.3390/e28070819` / arXiv `2411.18531`.

## 10. Source-ledger standing

The external grounding remains `accepted_narrow_scope`. The legal and administrative domain
argument is preserved. The numerical refusal is narrowed to models actually established in the
repository. No source authorizes a scalar, implementation, publication, or compliance claim.
