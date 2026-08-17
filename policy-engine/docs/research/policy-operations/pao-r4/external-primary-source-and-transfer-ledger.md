---
title: PAO-R4 external primary-source and transfer ledger
research_id: PAO-R4
artifact_role: external-source-ledger
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_verification_date: 2026-08-08
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - amended primary-source and stable-snapshot ledger for PAO-R4
  - bounded transfer and non-transfer statements
  - currentness correction for Canada and United States federal AI instruments
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# External primary-source and transfer ledger

## 1. Use rule

This ledger imports boundary principles, not compliance conclusions. Every source binds only its own
scope, definitions, institutions, exceptions, competence, procedures, and remedies. Nothing here
establishes that PolicyOS, an export, or a future implementation is lawful, sufficient, high-risk,
covered, compliant, or permitted in any jurisdiction.

PAO-R4's engineering trigger is **observable consultation or invocation in a protected individual
action inside a declared governed boundary**. It is **not narrower on the material-reliance /
formal-finality trigger** than comparators limited to sole automation or a formally final decision.
That is a single-axis comparison. It does not claim to equal or dominate the cited regimes' full
rights, duties, remedies, hearing, explanation, competence, lawful-basis, or review structures.

## 2. Source pinning convention

| Source kind | Stable pin used here |
|---|---|
| legislation/regulation | official identifier and article/section, such as CELEX or U.S. Code |
| judgment | case number, court and ECLI/reporter citation |
| mutable policy instrument | official instrument ID plus version/date and official archive/version chain |
| open questionnaire/tool | official page plus content-addressed public source snapshot |
| memorandum | memorandum number, date, official OMB index and official PDF |
| scholarly work | DOI |

Retrieval date is `2026-08-08`. A retrieval date is not substituted for a version identifier.

## 3. European Union

| Stable identifier | Primary proposition used | Transfer to PAO-R4 | What does not transfer |
|---|---|---|---|
| Regulation (EU) 2016/679, **CELEX 32016R0679**, Articles 4(4), 13(2)(f), 14(2)(g), 15(1)(h), 22; Recital 71 | Profiling evaluates personal aspects. Article 22 concerns stated solely automated decisions with legal or similarly significant effects, subject to safeguards and exceptions. Information duties concern the existence, logic, significance, and consequences of covered processing. | Keep empirical/model output distinct from the protected individual act; make the system's actual role visible; do not treat ceremonial human involvement as proof of independence. | GDPR scope, lawful bases, controller/processor roles, exceptions, rights, remedies, and compliance conclusions do not transfer. PAO-R4's consultation trigger is deliberately broader only on reliance/formal finality. |
| CJEU, **C-634/21, SCHUFA Holding (Scoring), ECLI:EU:C:2023:957**, judgment of 7 December 2023 | An upstream probability value can fall within Article 22 where a third party draws strongly on it in establishing, implementing, or terminating a contractual relationship. | Formal separation between producer and final decider does not remove the boundary when downstream reliance is material. The consumer-use gate must observe consultation/reliance, not only the final actor. | The judgment's GDPR interpretation is not converted into a universal definition for every policy domain, and no compliance inference follows. |
| Charter of Fundamental Rights of the European Union, **2012/C 326/02**, Article 41(2)(a)-(c) | Within its scope, good administration includes hearing, access to the file subject to legitimate confidentiality, and reasons. | A population explanation is not an individual reason. Actual grounds, facts, hearing and review remain external case-procedure duties; PolicyOS may require bounded evidence that its empirical artifact was not substituted for them. | Institutional/personal scope, direct effect, remedies and legal sufficiency do not transfer. |
| Regulation (EU) 2024/1689, **CELEX 32024R1689**, Article 86 | Under the Regulation's stated conditions, an affected person may obtain a clear and meaningful explanation of the high-risk AI system's role and main elements in a decision. | Returning evidence should distinguish the artifact's role from the external rule, case facts and final act. | PAO-R4 does not classify any system as high-risk, decide Article 86 applicability, or claim compliance. |

### EU transfer conclusion

The durable transfer is role visibility: an upstream score or model cannot escape the engineering
boundary merely because another actor formally decides. PAO-R4 is not narrower on that specific
material-reliance/formal-finality axis. No broader legal dominance comparison is made.

## 4. Canada — federal public administration

### 4.1 Versioned source record

| Source | Version/date pin | Archive/snapshot pin |
|---|---|---|
| Treasury Board of Canada Secretariat, **Directive on Automated Decision-Making**, policy instrument **`id=32592`** | Fourth-review amended instrument, **date modified 2025-06-24**; effective-date section retains 2019/2020 commencement and gives pre-24-June-2025 systems a transition to 2026-06-24 | The official instrument page's archive chain identifies replaced versions dated **2021-03-24** and **2023-04-24**. The 2025-06-24 version is additionally corroborated by the official Government of Canada progress entry “Updates to the Directive on Automated Decision-Making (June 24, 2025).” URL: `https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592` |
| Treasury Board of Canada Secretariat, **Algorithmic Impact Assessment tool** | Tool version supporting the fourth Directive review, publicly announced **2025-06-24** | Content-addressed questionnaire snapshot: `canada-ca/aia-eia-js@a10e7f8c0cc7efdf582cd8455122c18ed2425bf6` (2025-06-16), following version-field commit `055fcc8c574913f7dcb1d041fad565d158ae93a4` (2025-06-02). Official page: `https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/algorithmic-impact-assessment.html` |

The official AIA page is mutable and, at retrieval, describes a later 65-risk-question / 41-mitigation-
question tool. PAO-R4 cites the content-addressed June 2025 questionnaire snapshot for the version
contemporaneous with the fourth Directive review, not the mutable page as an immutable denominator.

### 4.2 Transfer table

| Stable source record | Primary proposition used | Transfer to PAO-R4 | What does not transfer |
|---|---|---|---|
| Directive `id=32592`, version 2025-06-24 | The Directive governs stated federal administrative decisions made or supported by automated decision systems and uses impact-scaled requirements including assessment, transparency, testing, monitoring, intervention, explanation, recourse and reporting. | Treat decision support, not only fully automated final acts, as boundary-relevant. Require pre-use classification and evidence-bearing operational safeguards. | Departmental scope, impact levels, exceptions, prescribed controls, transition rules, approval process and compliance assessment do not transfer. |
| AIA fourth-review snapshot `a10e7f8c...` | The questionnaire collects project, system, algorithm, decision, impact, data, consultation and mitigation information to determine impact and required safeguards. | Purpose, decision/action context, data/model role and mitigation premises must be made visible before use; declarations remain premises subject to `P37`, not self-proving gates. | Questionnaire questions, weights, score, impact level and federal publication process are not adopted as PolicyOS contracts. |

### Canada transfer conclusion

The transferable result is pre-use classification plus operational safeguards for systems that make
or support administrative decisions. PAO-R4 adds a stricter evidence proposition of its own: a
voluntary or unreconciled return channel cannot establish complete non-use. That is an engineering
identifiability conclusion, not a claim that the Canadian instruments require the same firewall.

## 5. United States

| Stable identifier | Primary proposition used | Transfer to PAO-R4 | What does not transfer |
|---|---|---|---|
| Administrative Procedure Act, **5 U.S.C. § 555(e)** | Subject to its exceptions, prompt notice of denial of a written application, petition or request includes a brief statement of grounds. | An empirical population statistic cannot silently substitute for the actual grounds of an individual denial. Returning evidence must distinguish empirical consultation from the external case reason. | Agency/proceeding scope, exceptions, remedies and sufficiency standards do not transfer; PAO-R4 does not draft reasons. |
| **Los Angeles Department of Water & Power v. Manhart, 435 U.S. 702 (1978)** | In the Title VII context, even a true class generalization does not justify treating an individual as though it necessarily describes that person. | Supports the empirical class-E non-entailment and the refusal to fill a person's fact/determination slot from a group average. | The Title VII holding and protected-class doctrine are not generalized into universal law or a compliance conclusion. It does not prohibit competent normative rule application or every use of statistical evidence in a lawful procedure. |
| OMB **M-25-21**, “Accelerating Federal Use of AI through Innovation, Governance, and Public Trust,” **3 April 2025**, official OMB memoranda index and official 25-page PDF | M-25-21 expressly **rescinds and replaces M-24-10**. It directs covered agencies to accelerate responsible AI use while applying minimum risk-management practices to high-impact AI, including governance, inventory, impact determination, testing/monitoring and independent review/risk acceptance in its stated scope. | Public-sector AI accountability depends on operational role, monitoring and risk evidence, not a model card or declared purpose alone. The high-impact/consultation idea supports separating candidate computation from protected-action authority. | Agency scope, high-impact definition, exclusions, governance roles, deadlines, waivers, inventories, risk-acceptance process and legal obligations do not become PolicyOS rules. |
| OMB **M-24-10**, **28 March 2024** | Historical predecessor concerning federal agency AI governance and rights-/safety-impacting uses. | Retained only as historical provenance for the original PAO-R4 citation. | It is not cited as current policy: M-25-21 states that it rescinds and replaces M-24-10. |

### United States transfer conclusion

The durable transfer is the distinction between general evidence and actual individual grounds, plus
operational governance for consequential uses. PAO-R4 does not decide whether statistical evidence is
legally admissible or sufficient in any U.S. programme.

## 6. Statistical and semantic sources

| Stable identifier | Proposition used | Transfer | Non-transfer |
|---|---|---|---|
| W. S. Robinson, “Ecological Correlations and the Behavior of Individuals,” **DOI 10.2307/2087176** (1950) | Aggregate correlations can differ from individual-level relationships; cross-level inference is not generally valid. | A class-E aggregate relation does not establish the corresponding relation for a person. | The paper does not prove every aggregate use invalid, define a case procedure, or set an anonymization threshold. |
| P. E. Meehl and A. Rosen, “Antecedent probability and the efficiency of psychometric signs, patterns, or cutting scores,” **DOI 10.1037/h0048070** (1955) | Predictive value depends on antecedent/base rates and test characteristics; the same sign can imply different posterior values in different populations. | Individual prediction is reference-class conditional, and a score stripped of its selection/population basis changes meaning. | No diagnostic threshold, normative rule, or administrative decision rule is imported. |
| A. P. Dawid, “The Well-Calibrated Bayesian,” **DOI 10.1080/01621459.1982.10477856** (1982) | Calibration is defined over sequences/subsets of probabilistic forecasts. | **Auditor-confirmed inference, not a quoted theorem:** calibration across forecasts does not by itself turn one forecast probability into an observed fact about the individual. | PAO-R4 does not adopt Dawid's framework as its prediction architecture or claim any model is calibrated. |

## 7. Cross-regime transfer matrix

| Boundary property | EU | Canada | United States | PAO-R4 bounded rule |
|---|---|---|---|---|
| Upstream material role can matter without formal finality | C-634/21 | Directive covers stated support of administrative decisions | M-25-21 addresses high-impact use and operational governance in scope | Instrumented consultation in a protected action triggers the gate. |
| Human presence is not self-proving | Article 22 safeguards in scope | Impact-scaled intervention/recourse requirements | M-25-21 operational governance and risk acceptance in scope | A human click does not cure consultation of a denied E/X artifact. |
| Individual grounds differ from population explanation | Charter Article 41; GDPR/AI Act information duties in scope | Explanation/procedural-fairness measures | 5 U.S.C. § 555(e) | `individual_reason_generation` remains denied for E; actual reasons are external. |
| Statistical generalization is not an individual fact | profiling/decision structure | decision/data context assessed | Manhart in Title VII scope | `P_E ∧ C_B(x) ⊭ F_x` absent pointwise recoverability and a separate individual procedure. |
| Monitoring/reporting must be operational | accountability/safeguards in scope | Directive monitoring/reporting | M-25-21 inventories, monitoring and risk practices | Complete non-use requires mandatory independently reconciled evidence; voluntary silence cannot prove it. |
| Normative rule can apply to a person | legal rules remain external to model statistics | programme authority and law remain departmental | governing law remains agency-specific | G may travel as rule-level input; executability is not refusal, and PolicyOS gains no case authority. |

## 8. Final transfer limitation

The sources establish that the model/policy-to-person transition is legally and institutionally
significant and commonly accompanied by safeguards. They do not establish PAO-R4's legal sufficiency,
future compliance, permission to export, competence of a rule authority, truth of case facts, or
ownership of the individual procedure. Jurisdiction-specific counsel, competent administrative
owners and the external case system remain separate prerequisites.
