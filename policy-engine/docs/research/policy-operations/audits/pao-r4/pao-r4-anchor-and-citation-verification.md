---
title: PAO-R4 independent audit — anchor and citation verification
audit_id: PAO-R4
artifact_role: anchor-and-citation-verification
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent verification of PAO-R4 internal anchors
  - independent Pass II verification of cited primary sources and transfer limits
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 anchor and citation verification

## 1. Scope and method

Every internal claim was checked at the pinned repository commit. Every external source in
`external-primary-source-and-transfer-ledger.md` was opened at its stable identifier or official
publication page. This file verifies existence, cited proposition, scope/currentness, and the
honesty of the transfer limit. It does not assess or declare compliance.

## 2. Internal anchor verification

| Finding/anchor | Audited use | Independent result |
|---|---|---|
| **Individual-decision firewall** ruling | PolicyOS owns the firewall; individual determination remains external | **Verified.** `policyos-identity-and-custody-boundary.md:123-139@1a7a2d05ebba22fae80e9934329e4b880806588e` assigns OWN to the firewall and states that the individual decision is never PolicyOS's. |
| Binding anti-roles | No case-system, court, notification, payment, or CRM design | **Verified.** `policyos-identity-and-custody-boundary.md:88-91@1a7a2d05ebba22fae80e9934329e4b880806588e`. |
| **`S0-K05`** | no authority by observation, transport, or projection | **Verified by finding ID.** The primary report uses the ratified finding rather than inventing a new authority rule. |
| **`S0-K07`** | projection cannot mint authority | **Verified by finding ID.** The export/projection contract stays non-authoritative. |
| **`S0-K11`** | protected actions need equivalent action-specific protection | **Verified by finding ID.** The research correctly treats a generic human click as insufficient. |
| **`PV-K04`** | projection may reduce detail but denied uses do not shrink | **Verified by finding ID.** The report explicitly says the law already exists and builds its monotone-denial rule on it (`pao-r4-individual-decision-firewall.md:71-80@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). |
| **`INT-K02`** | a `delta` is inseparable from declared obligation set and assumptions | **Verified by finding ID.** The report transfers the broader principle that a bounded population claim loses meaning if its basis is stripped; it does not claim `INT-K02` itself governs every non-`delta` claim. |
| **`P35`** | full-set denominator discipline | **Verified by finding ID.** Pass I nevertheless finds one application error and one incomplete positive-token pass. |
| **`P36`** | finding, not adjacent prose, carries warrant | **Verified by finding ID.** The report generally names the kernel findings it uses. |

### Internal-anchor conclusion

The ratified-kernel inheritance is one of the strongest parts of PAO-R4. In particular, the work does
**not** present denied-use monotonicity as its own discovery. It correctly says `PV-K04` already
ratified the property and then instantiates it for individual-use vocabulary.

## 3. European Union sources

| Identifier | Existence and proposition | Transfer-limit audit | Verdict |
|---|---|---|---|
| Regulation (EU) 2016/679, **CELEX 32016R0679**, Articles 4(4), 13(2)(f), 14(2)(g), 15(1)(h), 22; Recital 71 | Exists. Article 22 is limited to decisions based solely on automated processing that produce legal or similarly significant effects, subject to stated exceptions and safeguards. Profiling and information duties are real. | The ledger expressly declines territorial/material scope, exceptions, lawful bases, controller roles, and compliance. Honest. | **Verified.** |
| CJEU **C-634/21**, **ECLI:EU:C:2023:957** | Exists, judgment 7 December 2023. The Court treated automated establishment of a probability value as Article-22 decision-making where a third party draws strongly on it in the contractual decision. | The ledger correctly transfers upstream material reliance, not a universal GDPR definition. | **Verified.** |
| Charter **2012/C 326/02**, Article 41(2)(a)-(c) | Exists. Article 41 covers hearing, file access subject to confidentiality, and reasons, and textually binds institutions, bodies, offices, and agencies of the Union. | The ledger expressly refuses institutional/direct-effect/remedy transfer and keeps individual reasons external. | **Verified.** |
| Regulation (EU) 2024/1689, **CELEX 32024R1689**, Article 86 | Exists. Under its conditions, a person affected by a deployer's decision based on high-risk AI may obtain a clear and meaningful explanation of the AI system's role and main elements of the decision. | The ledger refuses high-risk classification and compliance. Honest. | **Verified.** |

### EU line-difference audit

The work accurately names that GDPR Article 22 is narrower than PAO-R4 along two axes: sole
automation and formal/significant decision scope. The engineering trigger “material contribution” is
broader **on those axes**. That does not prove the PAO-R4 package is globally “not weaker”: GDPR,
the Charter, and the AI Act also include institutional duties, rights, exceptions, remedies,
competence, and procedural protections that PAO-R4 deliberately leaves outside its firewall.

## 4. Canada sources

| Identifier | Existence and proposition | Currentness/transfer audit | Verdict |
|---|---|---|---|
| Treasury Board Directive on Automated Decision-Making, page identifier **`id=32592`** | Exists. It covers production automated decision systems making or supporting federal administrative decisions and includes AIA, notice, meaningful explanation, documentation, testing, monitoring, data governance, peer review, training, intervention and recourse measures. | The proposition is supported and the scope limit is honest. The page is mutable and was modified **24 June 2025**, with transition provisions. The ledger gives no version/date or archived instrument identifier. | **Substance verified; stable-version requirement not met.** |
| Government of Canada Algorithmic Impact Assessment | Exists. The current tool organizes questions about project, decision, data, impact and mitigation, and drives Directive requirements. | The page/tool is mutable. The ledger gives no release, archive, questionnaire version, or retrieval date. It correctly refuses to import scoring weights. | **Substance verified; stable-version requirement not met.** |

The omission matters because the commission required stable identifiers and because the Directive
itself records replaced versions. The transfer need not be withdrawn; it must be pinned to the
version actually read.

## 5. United States sources

| Identifier | Existence and proposition | Currentness/transfer audit | Verdict |
|---|---|---|---|
| **5 U.S.C. § 555(e)** | Exists. It requires prompt notice of denial of a written application, petition or request and, subject to the stated exceptions, a brief statement of grounds. | The ledger preserves scope, exceptions, remedies and sufficiency limits and does not design reasons. | **Verified.** |
| **Los Angeles Department of Water & Power v. Manhart, 435 U.S. 702 (1978)** | Exists. In the Title VII context, the Court states that even a true class generalization is insufficient to disqualify an individual to whom it does not apply. | The ledger expressly confines the holding and transfers only the individual-versus-class principle. | **Verified.** |
| OMB **M-24-10**, 28 March 2024 | Exists and supports the quoted minimum-practice proposition for rights- and safety-impacting AI. | **Currentness defect:** OMB M-25-21, dated 3 April 2025, expressly “rescinds and replaces” M-24-10. The ledger describes M-24-10 without saying it is historical/superseded. | **Historical proposition verified; current-regime implication not safe.** |

M-24-10 remains usable as historical comparative practice, but a 2026 ledger must either label it
superseded or use M-25-21 for current federal policy. This is especially important because the two
memoranda use different categories and requirements.

## 6. Statistical sources

| Identifier | Existence/proposition | Verdict |
|---|---|---|
| Robinson, **DOI 10.2307/2087176** | Exists. The ecological-versus-individual association warning is the source's central proposition. | **Verified.** |
| Meehl & Rosen, **DOI 10.1037/h0048070**, PMID 14371890 | Exists. The source is specifically about antecedent/base probability and efficiency of signs/cut scores in individual classification. | **Verified.** |
| Dawid, **DOI 10.1080/01621459.1982.10477856** | Exists. Calibration is defined across a sequence/subset of forecasts. The PAO-R4 statement that calibration alone does not make a probability an observed individual fact is a defensible inference, not a theorem quoted from the paper. | **Verified with inference label required.** |

The statistical trio is well chosen, but it supports non-entailment and conditionality—not a blanket
ban on every use of statistical evidence in an individual procedure.

## 7. Pass-II and Pass-VIII findings

### `PAO-R4-II-001` — material — “PAO-R4 is not weaker” is not established

**Evidence:** `external-primary-source-and-transfer-ledger.md:40-45,92-98@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

The broader material-contribution trigger is demonstrably no narrower on reliance/finality. It does
not dominate the cited regimes' rights, remedies, hearing, explanation, competent-review, exception,
and institutional-duty structures. The claim must be narrowed to the dimension actually compared.

### `PAO-R4-II-002` — material — two mutable Canadian sources are not version-pinned and M-24-10 is superseded

**Evidence:** `external-primary-source-and-transfer-ledger.md:47-73@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`; Directive page `id=32592`, modified 24 June 2025; OMB M-25-21, 3 April 2025, opening paragraph.

The propositions remain usable, but the ledger fails the commission's stable-source/currentness bar.
It must name the Directive/AIA version read and label M-24-10 historical and rescinded, or substitute
the current memorandum with a new transfer analysis.

### `PAO-R4-II-003` — commendation — every regime carries an explicit non-compliance transfer limit

**Evidence:** `external-primary-source-and-transfer-ledger.md:20-26,28-98@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

No table silently declares PolicyOS compliant. Each row names what does not transfer, and the final
section repeats that jurisdiction-specific sufficiency remains external.

### `PAO-R4-II-004` — commendation — the legal propositions are substantively used rather than name-checked

The sources support concrete design distinctions: upstream reliance, individual grounds versus
population explanation, pre-use assessment, operational monitoring, and class-versus-individual
treatment. Except for currentness and the global “not weaker” sentence, the representations are
accurate and bounded.

### `PAO-R4-VIII-001` — commendation — `PV-K04` is inherited, not re-authored

**Evidence:** `pao-r4-individual-decision-firewall.md:71-80,168-177@a27c3da9942b03881dbee1005a8a1e44e5ac44b4` and F-04 in
`falsifier-suite.md:134-163@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

The work correctly makes denied-use union a concrete firewall invariant while preserving the
ratified finding as the source of authority.

### `PAO-R4-VIII-002` — commendation — the remaining ratified-kernel and anti-role boundaries hold

`S0-K05`, `S0-K07`, `S0-K11`, `INT-K02`, the identity ruling, and the anti-roles are used within
their findings. The correction contact is an interface obligation only; no correction mechanism is
designed.
