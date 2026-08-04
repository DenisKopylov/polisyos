---
title: INT-R9 — Proving-Ground Contamination Census
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
bound_int_r10_commit: research/int-r10-revision@a334f7d844733bfd17f1857a4cb56fbf219378ef
bound_int_r1_amendment_commit: research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0
authoritative_for:
  - repository-grounded contamination classification of the thirteen canonical proving-ground cases at the pinned baseline
  - reconciliation of the thirteen-case proving-ground denominator with the fifteen adjudication manifests
  - exact fifteen-manifest calibration, topology, authority-level, and answer-bearing-field census
  - research-only eligibility decisions for public regression, decisive sealed holdout, and adjacent unseen evaluation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner assignment
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - legal compliance conclusion
  - proof that a newly authored pool is free of upstream tractability judgment
  - a sequence-level numeric false-promotion claim
research_only: true
---

# INT-R9 — Proving-Ground Contamination Census

## 1. Census rule

For INT-R9, **contamination** is prior access by implementation authors, case selectors, criteria or evaluator authors, adjudicators, their tools, or shared development processes to information that can rationally affect case choice, bindings, criteria, stopping, thresholds, interpretation, or expected output. Literal answer leakage is only one class. Public source packs, expected claim IDs, labels, gold-card contents or null patterns, votes, rationales, prior slice use, and end-to-end debugging all matter.

This is an exposure census, not an allegation of intentional tuning. Honest development can still make a case unsuitable as one-time evidence.

The outcome-corpus README identifies **13 real cases across 12 domains** and limits annotation authority (`policy-engine/docs/research/universal-policy-design/outcome-corpus/README.md:1-48`). The adjudication README lists **15 manifests**, adding two synthetic cases (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/README.md:1-52`).

```text
proving-ground denominator = 13 real cases
adjudication-manifest denominator = 15
synthetic calibration fixtures = 2
sealed decisive cases at the pinned baseline = 0
adjacent unseen cases at the pinned baseline = 0
```

## 2. Exposure classes

| Class | Meaning | INT-R9 consequence |
| --- | --- | --- |
| `C0_unseen` | No outcome-relevant input, answer, binding, case-selection, or run exposure before the relevant freeze, supported by custody evidence. | Potential decisive or adjacent evidence, subject to all other requirements. |
| `C1_source_seen` | Sources, seed claims, evidence families, or limitations are public. | Public regression unless a distinct answer and selection history remain independently held. |
| `C2_answer_seen` | Expected IDs, labels, votes, rationales, non-null gold cards, or equivalent answer-bearing structures are visible. | Not a sealed holdout. Null gold card does not reverse other answer exposure. |
| `C3_slice_development_seen` | Case appears in mechanism growth, envelope revision, or other development evidence. | Not adjacent-unseen evidence; heightened bespoke-binding review. |
| `C4_integrated_loop_seen` | Full composed loop was built, debugged, or repeatedly exercised against the case. | Ineligible as decisive first-promotion or adjacent case. |

The classes are cumulative. “No stronger repository exposure found” is not proof that no person or model ever saw the case.

## 3. Corrected thirteen-case census

Every adjudication anchor below uses the exact existing range `:1-120`, verified at `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`. The former uniform `:1-170` ranges overran EOF and are retired.

| Canonical case | Domain | Public answer/development exposure | Highest class | INT-R9 use |
| --- | --- | --- | --- | --- |
| `ua-msme-affordable-loans-2022` | MSME credit, Ukraine | `expected_claim_ids=[claim:wartime-credit-access-support]`; `label=limitation_required`; non-null cards and votes; `authority_level=governed`; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/ua-msme-affordable-loans-2022.adjudication.json:1-120`). It is the only full-loop case; all twelve others are per-slice (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`), appears in S12/S13 evidence (`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:170-255`), and is named by the N9 default (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:130-180`). | `C4_integrated_loop_seen` | **Ineligible** as primary and adjacent. Public regression/development only. |
| `berlin-rent-cap-2020` | housing | `expected_claim_ids=[claim:berlin-rent-cap-tenant-relief]`; `label=false_pass`; non-null card and votes; governed; `deep-pilot-round-1` (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_berlin_rent_cap_2020.adjudication.json:1-120`). No integrated-loop evidence found beyond the public corpus/per-slice baseline (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `boston-operation-ceasefire-1996` | public safety | `expected_claim_ids=[claim:ceasefire-reduced-youth-gun-violence]`; `label=limitation_required`; non-null card and votes; research; `deep-pilot-round-1` (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_boston_operation_ceasefire_1996.adjudication.json:1-120`). Used in S12 envelope-growth evidence (`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:170-245`). | `C3_slice_development_seen` | Public regression only. |
| `eu-temporary-protection-ukraine-2022` | migration | `expected_claim_ids=[claim:temporary-protection-immediate-rights]`; `label=semantic_pass`; votes visible; `gold_card=null`; production; `deep-pilot-round-1` (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_eu_temporary_protection_ukraine_2022.adjudication.json:1-120`). Used in S13 envelope-revision evidence (`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:190-250`). | `C3_slice_development_seen` | Public regression only. |
| `ghana-free-shs-2017` | education access | `expected_claim_ids=[claim:free-shs-expands-access]`; `label=limitation_required`; non-null card and votes; research; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_ghana_free_shs_2017.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `india-aadhaar-dbt-2016` | digital public service | `expected_claim_ids=[claim:aadhaar-dbt-targets-benefits]`; `label=semantic_pass`; votes visible; `gold_card=null`; production; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_india_aadhaar_dbt_2016.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `mexico-ssb-tax-2014` | public health | `expected_claim_ids=[claim:ssb-tax-reduces-purchases]`; `label=limitation_required`; non-null card and votes; research; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_mexico_ssb_tax_2014.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `netherlands-room-for-the-river-2007` | climate adaptation | `expected_claim_ids=[claim:room-for-river-reduces-flood-risk]`; `label=limitation_required`; non-null card and votes; research; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_netherlands_room_for_river_2007.adjudication.json:1-120`). Used in S13 certified-envelope-delta evidence (`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:200-255`). | `C3_slice_development_seen` | Public regression only. |
| `pakistan-ehsaas-emergency-cash-2020` | social protection | Repository alias `w11a_pakistan_ehsaas_cash_2020`; `expected_claim_ids=[claim:ehsaas-rapid-social-protection]`; `label=semantic_pass`; votes visible; `gold_card=null`; production; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_pakistan_ehsaas_cash_2020.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `uk-levelling-up-fund-2021` | infrastructure | `expected_claim_ids=[claim:luf-prioritises-local-infrastructure]`; `label=limitation_required`; non-null card and votes; governed; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_uk_levelling_up_fund_2021.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `uk-making-tax-digital-vat-2019` | tax enforcement | `expected_claim_ids=[claim:mtd-improves-tax-compliance]`; `label=limitation_required`; non-null card and votes; governed; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_uk_mtd_vat_2019.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `uk-work-programme-2011` | labour activation | `expected_claim_ids=[claim:work-programme-sustained-employment]`; `label=limitation_required`; non-null card and votes; governed; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_uk_work_programme_2011.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |
| `us-ppp-2020` | MSME emergency credit | `expected_claim_ids=[claim:ppp-emergency-payroll-support]`; `label=limitation_required`; non-null card and votes; production; calibration null (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/w11a_us_ppp_2020.adjudication.json:1-120`). No integrated-loop evidence found (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`). | `C2_answer_seen` | Public regression/calibration only. |

All table anchors above are full repository paths with exact ranges present at the pinned baseline.

## 4. Programmatic fifteen-manifest enumeration

The amendment enumeration operated on the exact manifest roster from `adjudications/README.md:29-52` and extracted:

```text
manifest filename
case role (real/synthetic)
authority_level
reviewer_topology.topology_mode
reviewer_topology.calibration_round_id
whether any adjudication gold_card is null
whether expected_claim_ids, label, and reviewer_votes are present
```

Exact output:

| # | Manifest | Role | Topology | Calibration | Authority | Null card present |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `housing-rent-stabilization-001.adjudication.json` | synthetic | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | yes, one semantic-pass adjudication |
| 2 | `public-health-outreach-001.adjudication.json` | synthetic | `partial_disjoint` | `null` | `production` | no |
| 3 | `ua-msme-affordable-loans-2022.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no |
| 4 | `w11a_berlin_rent_cap_2020.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | no |
| 5 | `w11a_boston_operation_ceasefire_1996.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `research` | no |
| 6 | `w11a_eu_temporary_protection_ukraine_2022.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `production` | yes |
| 7 | `w11a_ghana_free_shs_2017.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no |
| 8 | `w11a_india_aadhaar_dbt_2016.adjudication.json` | real | `partial_disjoint` | `null` | `production` | yes |
| 9 | `w11a_mexico_ssb_tax_2014.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no |
| 10 | `w11a_netherlands_room_for_river_2007.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no |
| 11 | `w11a_pakistan_ehsaas_cash_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | yes |
| 12 | `w11a_uk_levelling_up_fund_2021.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no |
| 13 | `w11a_uk_mtd_vat_2019.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no |
| 14 | `w11a_uk_work_programme_2011.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no |
| 15 | `w11a_us_ppp_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | no |

Set-level results:

```text
calibration_round_id values = {null, "deep-pilot-round-1"}
  deep-pilot-round-1: 4
  null: 11

topology_mode values = {"deep_pilot_overlap", "partial_disjoint"}
  deep_pilot_overlap: 4
  partial_disjoint: 11

authority_level values = {"production", "governed", "research"}
  production: 5
  governed: 6
  research: 4

all 15 expose expected_claim_ids: yes
all 15 expose adjudication labels: yes
all 15 expose reviewer_votes: yes
all adjudications have non-null gold_card: no
```

These facts correct the original prompt's sampled generalizations and the original INT-R9's incomplete “three deep-pilot manifests” statement. They do not cure the independence problem: reviewer IDs remain role-shaped, conflicts remain `none_declared`, and no named-person signature, employment/funding, reporting-line, or first-promotion access evidence exists.

## 5. ua-msme decision and the price paid

### 5.1 Why it stays excluded

The contamination evidence is cumulative:

- public expected answer;
- only full-loop case;
- S12/S13 development use;
- current N9 default reference; and
- long prior engineering contact.

A hidden new answer cannot undo implementation and selection history. ua-msme therefore remains barred from both primary and adjacent roles.

### 5.2 Cost

The decisive attempt must use a newly authored case that may expose missing bridges, refuse, or never converge. The protocol accepts **no promotion** as a complete outcome and prohibits falling back to ua-msme for a favorable headline.

### 5.3 Reopening evidence

Reopening would require a custody and causal-isolation proof that prior ua-msme work could not influence the tested predicates, binding, configuration, source choice, criteria, or implementation behavior. The pinned tree supplies contrary evidence. This is a high bar because the contamination is substantive; it is not written merely to be impossible.

## 6. New-case independence: exact claim and residual

A newly authored pool can establish, with evidence:

1. answer secrecy;
2. implementation-side non-access;
3. separation of implementation, case/answer authorship, eligibility review, custody, and adjudication roles; and
4. non-discretionary selection and order **within the committed pool**.

It cannot by those facts alone establish:

- that pool authors did not choose tractable mechanisms;
- that the pool is representative of policy space;
- that case and answer authors do not share substantive priors;
- that a language model had no prior source exposure; or
- that upstream topic judgment was independent of known system strengths.

If one case unit authors both inputs and answers, custody may keep answers hidden but pool-level tractability bias remains. Public wording must call the pool purposive unless an external frame and independent construction evidence support more.

## 7. Reviewer exposure and independence standing

Public manifests are useful calibration material. They are not decisive independent adjudication. The four deep-pilot manifests overlap roles for calibration; the eleven partial-disjoint manifests have null round IDs. Authority metadata is heterogeneous. None of that creates accountable human identity or proves independence.

A future panel must supply corroborating evidence for contribution history, authorship, access, line management, employment, funding, compensation, and outcome incentives. Informal network and reputational ties remain declared residuals. Same-network friendliness receives an explicit conflict disposition; it is not an automatic pass.

## 8. Public regression population

The public battery may use:

- all 13 real packs and adjudications;
- both synthetic adjudications;
- public ID, delivery-order, wrong-scope, source-flip, obligation-removal, and accounting characterizations;
- S14 assurance material only inside its stated boundary.

S14 itself bars production, recommendation, publication, claim, closeout, and gold-label authority (`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:1-340`). A green public battery shows regression conformance to named visible predicates, never sealed first-promotion evidence.

## 9. Decisive holdout requirement

Because all current real cases are at least `C2_answer_seen`, any decisive case must be newly authored and independently held with:

- separate input and expectation/evaluator packages;
- S0-GAP-02 custody, or an expressly governed canonical supersession;
- no implementation-side answer access before output freeze;
- no prior case-specific code/configuration/binding/alias/fixture;
- separately sealed adjacent case;
- precommitted selection/order/stopping;
- disclosed purposive-pool boundary; and
- named evidence-backed human adjudication.

A case becomes `C0_unseen` only through custody evidence. Newness is not enough.

## 10. Census falsifiers and final denominator

This census should be revised if an auditor finds:

- a current case with demonstrably independent answer, selection, and implementation history; or
- stronger development/integrated exposure for a case currently classified only `C2`.

The first would lower a class only with affirmative evidence; the second would raise it. Until then:

```text
13 public real regression cases
+ 2 public synthetic calibration fixtures
+ 0 sealed decisive cases
+ 0 adjacent unseen cases
```
