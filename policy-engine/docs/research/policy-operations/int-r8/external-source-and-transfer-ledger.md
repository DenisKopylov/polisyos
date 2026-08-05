---
title: "INT-R8 external primary-source and transfer ledger"
research_id: INT-R8
artifact_role: source-and-transfer-ledger
status: accepted_narrow_scope
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
prepared_at: 2026-08-04
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

## 1. Scope and source-selection rule

This ledger grounds INT-R8 in official law, official administrative/statistical practice and primary mathematical literature. It does not conclude that PolicyOS complies with any jurisdiction or that an institution is competent to issue a governed result.

Source priority was:

1. enacted law or official consolidated legislation;
2. official tribunal/agency practice direction or release rule;
3. official statistical-institute guidance;
4. primary peer-reviewed or official technical publication.

Secondary commentary was used only to locate primary material and is not relied on for the recommendations.

## 2. Primary source ledger

### 2.1 United States — reasons, disclosure and plain language

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| US-APA-557 | **5 U.S.C. § 557(c)(3)(A)** | An agency decision in the covered formal-adjudication setting must include findings and conclusions, and the reasons or basis, on all material issues of fact, law or discretion presented on the record. | “Material reasons” and material issues are not optional explanatory garnish. Compression that removes a basis necessary to understand or challenge the result is blocked. Scope is limited to the statute's covered setting; it is not treated as a universal global rule. |
| US-FOIA-552 | **5 U.S.C. § 552(b), final paragraph (segregability/deletion indication)** | A reasonably segregable portion must be provided after exempt portions are deleted; the amount of information deleted and the place of deletion generally must be indicated unless doing so would harm the protected interest. | Supports redaction-with-manifest and the important qualification that even omission metadata may be too revealing. Transfers as design logic, not a determination that a PolicyOS release is legally subject to FOIA. |
| US-PWA-2010 | **Plain Writing Act of 2010, Pub. L. 111-274, 124 Stat. 2861** | Covered federal documents should use clear communication that the public can understand and use. | Supports shorter/plain-language rendering, but not semantic deletion. Accessibility/readability and reasons fidelity must be jointly satisfied. |

Canonical official locations: U.S. House Office of the Law Revision Counsel for 5 U.S.C. §§ 552 and 557; GovInfo package `PLAW-111publ274` for the Plain Writing Act.

### 2.2 Australia — reasons, access and dissent

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| AU-ADJR-1977 | **Administrative Decisions (Judicial Review) Act 1977 (Cth), Act No. 59 of 1977, Federal Register ID C2004A01697, s 13** | A person entitled to seek review may request a written statement of findings on material questions of fact, reference to evidence/material, and reasons, subject to statutory exceptions. | Reinforces that findings, evidence basis and reasons are contestability infrastructure. A public summary may be shorter, but cannot silently replace the actual basis with a favorable conclusion. |
| AU-FOI-1982 | **Freedom of Information Act 1982 (Cth), Act No. 3 of 1982, Federal Register ID C2004A02562** | Establishes an official-access regime with exemptions, review and publication structures. | Supports a layered model: lawful withholding and public access coexist. Access control/exemption does not justify an unreceipted misleading summary. No legal-coverage conclusion is drawn for PolicyOS. |
| NSW-MHRT-PD-G2 | **NSW Mental Health Review Tribunal, Practice Direction General No. 2 — Dissenting Opinions** | For a three-member panel, a dissent on a material matter relevant to determination is formally recorded; the dissenting member's reasons are signed and dated. | Directly supports retaining the existence and material subject of dissent and preserving its custody. It does not imply that every committee in every jurisdiction must publish personal identity or full confidential text. |

### 2.3 European Union — accessible official communication and decision summaries

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| EU-WAD-2016 | **Directive (EU) 2016/2102, CELEX 32016L2102, ELI `dir/2016/2102/oj`** | Public-sector websites and mobile applications are subject to accessibility requirements and related monitoring/statement mechanisms. | Accessibility is part of the release contract. Critical caveats cannot live only in inaccessible hover/collapse behavior. The Directive does not prescribe PolicyOS claim semantics. |
| EUIPO-BOA-SUMMARY | **EUIPO Boards of Appeal, official “Decisions / Overview of Boards of Appeal decisions” publication page** | The official page states that selected summaries are for information and do not necessarily reproduce the exact wording; case references link to the decisions. | Strong comparator for “summary plus authoritative full decision pointer and explicit non-equivalence notice.” The pointer/notice layer is adopted, but it cannot cure material broadening in the summary. |

### 2.4 United Kingdom — official statistical disclosure control

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| UK-ONS-SDC | **Office for National Statistics, “Statistical disclosure control” official policy page** | ONS states that statistical outputs for general publication or specific recipients are checked for disclosure risk and controlled as required. | Supports treating every output as a release event and checking recipient-specific outputs, not just public tables. It does not supply a theorem for narrative policy records. |
| UK-ONS-SRS-2023 | **ONS Secure Research Service, “SRS Output Checking Guidance Document,” Statistical Disclosure Control work strand, 12 June 2023** | Classifies outputs by disclosure risk and assigns output-checking burdens; release can be withheld or adjusted when checks identify risk. | Supplies a practical fail-closed release discipline and differentiates low/high-risk outputs. Thresholds/rules remain context-specific and cannot become PolicyOS-wide safe-loss rules. |

### 2.5 Australia — DataLab output checking and the rule of N

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| AU-ABS-DATALAB | **Australian Bureau of Statistics, DataLab User Guide — DataLab Clearance** | ABS must approve and clear DataLab outputs before they leave the environment; users apply output rules, provide evidence and request only what is needed. | Direct support for prospectively checking the actual release and minimizing accumulated outputs. This is procedural, not a numeric PolicyOS budget. |
| AU-ABS-OUTPUT-RULES | **ABS “DataLab Output Rules — Detailed Examples” official workbook** | Official examples require underlying counts to evidence contributor thresholds (including examples using at least 10 contributors) and treat differencing across tables. | Supplies the required “rule of N” comparator and secondary-disclosure lesson. The number 10 is not imported as a universal PolicyOS threshold; it is a domain-specific example of a fixed, evidenced local rule. |

### 2.6 Differential privacy and information leakage

| ID | Stable identifier | Primary proposition used | INT-R8 relevance |
|---|---|---|---|
| NIST-DP-800-226 | **NIST SP 800-226 (2025), DOI 10.6028/NIST.SP.800-226** | Differential privacy is a mathematical framework whose guarantee depends on correctly specified and implemented mechanisms, parameters and threat assumptions; the publication emphasizes evaluation hazards in practice. | Supports the premise audit. It does not license epsilon language for deterministic curated summaries. |
| DP-COMPOSITION-2015 | **Kairouz, Oh & Viswanath, “The Composition Theorem for Differential Privacy,” PMLR 37 (2015), pp. 1376-1385; arXiv:1311.0776** | Characterizes privacy degradation when composing mechanisms that already satisfy differential-privacy guarantees. | The theorem transfers only after local mechanism guarantees and their parameters exist. Those premises are absent for the current editorial projection. |
| MAX-LEAKAGE-2020 | **Issa, Wagner & Kamath, “An Operational Approach to Information Leakage,” IEEE Transactions on Information Theory 66(3):1625-1639 (2020), DOI 10.1109/TIT.2019.2962804; arXiv:1807.07878** | Defines maximal leakage through multiplicative improvement in guessing an adversarially chosen function of a secret after observing output. | Supplies a useful adversary/gain lens and motivates cross-view synergy analysis. A numerical value requires a declared channel/distribution and is therefore not issued here. |

## 3. Required comparative-model survey

### 3.1 Decision table

| Model | Guarantee it can supply | Property that eliminates it as the sole answer | Disposition in selected design |
|---|---|---|---|
| 1. National-statistical-institute SDC | Suppression/perturbation/thresholds, output checking, differencing review, release minimization | Cell/contributor rules do not capture legal reasons, dissent, denied uses, authority/status or narrative scope; thresholds are dataset/output-specific | **Adopt as release-discipline and attack layer**, not universal semantic rule or scalar budget. |
| 2. Differential privacy | Formal per-mechanism privacy and composition when adjacency, randomization and local guarantees hold | Curated editorial projections are not established DP mechanisms; no adjacency, randomization, local guarantee or accountant exists | **Reject as current general composition theorem**; retain as future narrow candidate for defined statistical mechanisms. |
| 3. Information-theoretic leakage | Formal inference/guessing measures and view synergy under a declared channel/distribution | No justified distribution or single secret/gain function; one number would hide heterogeneous harms | **Adopt consistency-set exact reconstruction now; retain leakage measures as diagnostic research**, not budget. |
| 4. Access control / need-to-know | Reduces ordinary audience access | Roles overlap, delegation/collusion/copying/export exist; content can leak across authorized views; access does not preserve semantic parity | **Adopt as perimeter layer only**. |
| 5. Redaction with manifest | Makes removal detectable and supplies typed reasons | Manifest can itself leak; it does not test joint/temporal reconstruction; IDs alone do not classify materiality | **Adopt as canonical base**, extended by `CompressionLossReceipt` and transcript checks. |
| 6. Provenance completeness / full-record pointer | Supports audit, currentness, correction and authorized access to full reasoning | Pointer does not cure a misleading visible claim and may be inaccessible to affected readers | **Adopt as binding/currentness layer**, never as sole parity guarantee. |
| 7. Administrative-law reasons-giving | Identifies material findings, evidence/reasons and contestability as non-optional decision content | Duties vary by jurisdiction/procedure; may permit confidentiality and do not define privacy composition | **Adopt as materiality/contestability layer**, bounded by source scope. |
| 8. Unstructured editorial summarization without receipt | Low cost, readable prose | Silent loss is unobservable; no complete inventory, materiality test, denied-use monotonicity, reconstruction check or fail-closed verdict | **Reject completely** as governed publication basis. This is the negative comparator. |

### 3.2 Selected composition of layers

The recommendation is not one model. It is a layered contract:

1. **Administrative reasons/dissent practice** defines classes of load-bearing content whose loss can defeat understanding and contestability.
2. **Existing redaction-with-manifest substrate** records typed removal and prevents silent claim-ID omission.
3. **Compression-loss semantic verifier** decides whether shortening preserves truth conditions, scope, negative state, limitations, denied uses and material counterpositions.
4. **Access control** limits who receives each canonical projection.
5. **SDC-style output checking** treats every view/export/version as a release and checks differencing/secondary disclosure.
6. **Consistency-set transcript analysis** tests exact joint and temporal reconstruction without inventing a probability model.
7. **Provenance/currentness pointer** connects the summary to the authoritative revision and correction state.
8. **INT-R7 proof** will bind those contents and history; INT-R8 does not choose how.
9. **No-number procedural composition** proves only that every actual prefix was prospectively checked under a declared rule family.

## 4. Transfer ledger

### 4.1 Legal and administrative imports

| Imported result | Transfers to PolicyOS | Does not transfer |
|---|---|---|
| Findings/reasons on material issues (US APA; AU ADJR) | A summary must preserve the actual material basis and enough evidence/counterposition structure for understanding and challenge | Universal legal duty, sufficiency finding or competence conclusion for every PolicyOS record |
| Segregability and indication of deletion (US FOIA) | Remove protected detail while disclosing safe typed omission; do not silently erase | Requirement to reveal omission metadata when that metadata would expose the protected interest; direct statutory applicability |
| Formal dissent custody (NSW MHRT) | Preserve existence, affected material issue, reasons custody and signed/dated status where relevant | Universal publication of identity/full dissent; treating dissent as automatically outcome-determinative |
| Plain writing/accessibility (US PWA; EU Directive 2016/2102) | Shorter accessible language and visible critical caveats across UI/print/accessibility tree | Permission to omit qualifiers, reasons, denied uses or negative states for readability |
| Official summary plus full decision link (EUIPO) | Clearly label summary as summary, provide authoritative pointer and case/currentness reference | Treat pointer as cure for materially misleading prose |

### 4.2 Statistical-confidentiality imports

| Imported result | Transfers to PolicyOS | Does not transfer |
|---|---|---|
| Every output is checked (ONS/ABS) | Every audience view, revision, screenshot and export is a disclosure event; check actual candidate before release | A presumption that passing one view means future views are safe |
| Request/release only what is needed (ABS) | Minimize projections and optional metadata; accumulated outputs are part of threat model | Automatic deletion of material reasons/limitations under “minimization” |
| Contributor threshold/rule of N | Fixed local threshold must be evidenced and checked; underlying counts may be required for the checker | The number 10 as a universal threshold; narrative/legal confidentiality guarantee |
| Differencing/secondary disclosure | Compare proposed output with prior outputs and other audience releases | A claim that all inference risks are covered by table differencing |
| Output checker may adjust/withhold | `blocked_material_omission` is a valid release refusal; safety is not a formatting suggestion | Authority to publish after an editor informally adjusts prose without rerunning the full gate |

### 4.3 Privacy-theoretic imports

| Imported result | Transfers to PolicyOS | Does not transfer |
|---|---|---|
| DP composition theorem | Premise template: define mechanism, local guarantee, prospective parameter, history-selected validity and canonical accountant | Any current epsilon/delta budget for deterministic editorial summaries |
| NIST DP evaluation guidance | Mechanism assumptions and implementation reality must be audited; labels are not guarantees | Treating “DP-inspired,” “anytime-valid” or “privacy-aware” as theorem satisfaction |
| Maximal leakage | Specify adversary objective; analyze whether combined views improve guessing; use data processing/composition properties only with valid channel model | A canonical scalar without probability/channel/gain assumptions; equivalence to legal/materiality harm |
| Consistency-set reconstruction (INT-R8 formalization) | Distribution-free exact reconstruction test for finite/symbolic models | Proof against every unknown auxiliary source or future attack |

## 5. Domain findings that drive the minimum retained set

The source families converge on five non-generic public-administration requirements:

1. **Reasons and material findings:** a conclusion without its material basis can be unreviewable even when every retained number is accurate.
2. **Counterevidence and dissent:** a majority result and a unanimous result are not interchangeable; confidentiality can justify detail removal, not fabricated consensus.
3. **Conditionality and denied use:** “only under this basis” and “may not be used for X” are part of the claim's meaning.
4. **Negative governed results:** refusal/exhaustion/dispute are outcomes, not empty slots to be hidden for a cleaner narrative.
5. **Accessible visible caveats:** a condition available only in a linked full record, hover state or inaccessible control can disappear in the citizen's actual artifact.

These findings explain why generic information retention, token counts or compression ratios are not acceptable materiality measures.

## 6. Source conflicts and adjudication

### 6.1 “Indicate deletion” versus confidentiality of the indication

FOIA's deletion-indication structure contains its own safety qualification: the amount/location need not be indicated when doing so would harm the protected interest. INT-R8 therefore rejects both extremes:

- silent untyped omission; and
- a manifest so specific that it reconstructs the secret.

The selected rule is a safe typed semantic-class/effect notice with affected public claims, tested as part of the transcript.

### 6.2 Plain language versus exact reasons

Plain-language law/practice favors understandable documents; reasons-giving favors material completeness. There is no necessary conflict. INT-R8 permits faithful condensation and normalized language but blocks loss of a truth-changing qualifier, counterposition or negative state.

### 6.3 Statistical threshold versus cumulative inference

A local contributor threshold may pass while multiple tables fail through differencing. Official output-checking practice resolves the conflict in favor of transcript/context review. INT-R8 follows that direction and refuses to treat the rule of N as a composition theorem.

### 6.4 DP theorem versus editorial practice

The mathematics is not disputed. The mechanism premise fails. The result is not “DP is unsuitable”; it is “DP composition is unavailable until the release is actually defined and enforced as a qualifying mechanism.”

## 7. Stable-reference checklist for a future audit

An independent auditor should be able to resolve at least:

- `5 U.S.C. 557(c)(3)(A)` and `5 U.S.C. 552(b)` through the U.S. Code;
- `PLAW-111publ274` through GovInfo;
- `C2004A01697`, s 13, and `C2004A02562` through Australia's Federal Register of Legislation;
- NSW MHRT Practice Direction General No. 2 through the Tribunal's official publications;
- `CELEX:32016L2102` / ELI `dir/2016/2102/oj` through EUR-Lex;
- ONS SDC policy and SRS Output Checking Guidance (12 June 2023) through ONS;
- ABS DataLab Clearance and detailed output rules through ABS;
- DOI `10.6028/NIST.SP.800-226`;
- PMLR volume 37 `kairouz15` / arXiv `1311.0776`;
- DOI `10.1109/TIT.2019.2962804` / arXiv `1807.07878`.

A later webpage update must not be allowed to silently change the proposition attributed to a stable statute, document edition or paper.

## 8. Result standing

**`accepted_narrow_scope`.** The selected layered model is source-grounded across the United States, Australia, the European Union and the United Kingdom, plus primary privacy literature. Every import has an explicit non-transfer boundary. No source supports a current numeric disclosure budget for PolicyOS editorial projections.
