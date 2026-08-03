---
title: INT-R9 — Proving-Ground Contamination Census
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-first-promotion-protocol
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - repository-grounded contamination classification of the thirteen canonical proving-ground cases at the pinned commit
  - reconciliation of the thirteen-case proving-ground denominator with the fifteen adjudication manifests
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
research_only: true
---

# INT-R9 — Proving-Ground Contamination Census

## 1. Census rule

For INT-R9, **contamination** means prior access by an implementation author, case selector,
criteria author, evaluator author, or their tools to information that can rationally affect
case choice, bindings, criteria, stopping, thresholds, or expected output. Exact string
leakage is only one form. Public source packs, expected claim identifiers, gold cards,
reviewer votes, labels, prior slice use, and end-to-end debugging all count, with different
severity.

This is an exposure census, not an accusation that any contributor optimized against an
answer. The risk exists even when all contributors acted honestly: the repository makes
many outcome-relevant choices visible, and the current architecture has been developed
through repeated contact with some cases.

The corpus README names **13 real cases across 12 domains** and says their annotations are
evaluation authority only, not runtime or claim authority
([`policy-engine/docs/research/universal-policy-design/outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md)).
The adjudication README names **15 committed manifests**: the same 13 real cases plus
`housing-rent-stabilization-001` and `public-health-outreach-001`
([`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/README.md:1-52`](../../universal-policy-design/outcome-corpus/adjudications/README.md)).
Therefore:

- proving-ground denominator = **13 real cases**;
- adjudication-manifest denominator = **15**;
- the two synthetic manifests are calibration/adjudication fixtures, not additional
  proving-ground cases;
- all 15 may be public regression material;
- none of the 15 is a sealed holdout at this commit.

## 2. Contamination classes

| Class | Meaning | Consequence for INT-R9 |
| --- | --- | --- |
| `C0_unseen` | No outcome-relevant package, expectation, label, binding, or run visible to the implementation side before freeze. | Potential decisive holdout, subject to independent custody proof. |
| `C1_source_seen` | Case sources, seed claims, expected evidence families, or limitations are public. | Public regression only unless a distinct hidden expectation can still be proven independent. |
| `C2_answer_seen` | Expected claim IDs, gold cards, labels, or reviewer votes are implementation-visible. | Not a sealed holdout. A fresh answer key cannot retroactively erase exposure. |
| `C3_slice_development_seen` | The case appears in mechanism-growth, envelope-revision, or other development evidence. | Not adjacent-unseen evidence; heightened bespoke-binding review. |
| `C4_integrated_loop_seen` | The full composed loop was built, debugged, or repeatedly exercised against the case. | Ineligible as the decisive first-promotion case. Development/public-regression use only. |

Classes are cumulative: `C4` includes `C1`–`C3`; `C3` includes `C1`–`C2`.

## 3. Thirteen-case census

The adjudication files expose `expected_claim_ids`, `label`, `gold_card`,
`reviewer_votes`, reviewer-role metadata, and authority/calibration fields. The table
records only what the pinned tree supports. “No integrated-loop evidence found” does
**not** mean the case was never viewed by a person; it means no stronger repository claim
is made.

| Canonical case | Domain | Public expected answer at the pinned commit | Additional repository exposure | Highest class | INT-R9 disposition |
| --- | --- | --- | --- | --- | --- |
| `ua-msme-affordable-loans-2022` | MSME credit, Ukraine | `expected_claim_ids=[claim:wartime-credit-access-support]`; `label=limitation_required`; gold card and reviewer votes committed; role-only reviewers; calibration round null. [`.../adjudications/ua-msme-affordable-loans-2022.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/ua-msme-affordable-loans-2022.adjudication.json) | The constitution says this is the **only** case run through the full composed loop; all 12 others are per-slice only. It is also used in S12 envelope growth and S13 envelope revision/certified-delta records, and the N9 input defaults its governed-promotion reference to the ua-msme record. [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md); [`.../layer2_s14_universality_assurance_manifest.json:1-260`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json); [`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:130-180`](../../../../src/polisyos/runtime/quality/promotion_sequence.py) | `C4_integrated_loop_seen` | **Ineligible** as decisive first-promotion holdout and as adjacent-unseen case. Keep as development/public regression. |
| `berlin-rent-cap-2020` | Housing | `expected_claim_ids=[claim:berlin-rent-cap-tenant-relief]`; `label=false_pass`; gold card and votes committed; `deep-pilot-round-1`. [`.../adjudications/w11a_berlin_rent_cap_2020.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_berlin_rent_cap_2020.adjudication.json) | The tree establishes public corpus/adjudication and per-slice classification, but this census found no integrated-loop or S12/S13 development reference comparable to ua-msme. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `boston-operation-ceasefire-1996` | Public safety | `expected_claim_ids=[claim:ceasefire-reduced-youth-gun-violence]`; `label=limitation_required`; gold card and votes committed; `deep-pilot-round-1`. [`.../adjudications/w11a_boston_operation_ceasefire_1996.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_boston_operation_ceasefire_1996.adjudication.json) | Used in the S12 envelope-growth evidence set. [`.../layer2_s14_universality_assurance_manifest.json:170-245`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json) | `C3_slice_development_seen` | Public regression only; not sealed or adjacent unseen. |
| `eu-temporary-protection-ukraine-2022` | Migration | `expected_claim_ids=[claim:temporary-protection-immediate-rights]`; `label=semantic_pass`; gold card and votes committed; `deep-pilot-round-1`. [`.../adjudications/w11a_eu_temporary_protection_ukraine_2022.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_eu_temporary_protection_ukraine_2022.adjudication.json) | Used in the S13 envelope-revision evidence set. [`.../layer2_s14_universality_assurance_manifest.json:190-250`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json) | `C3_slice_development_seen` | Public regression only; not sealed or adjacent unseen. |
| `ghana-free-shs-2017` | Education access | `expected_claim_ids=[claim:free-shs-expands-access]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_ghana_free_shs_2017.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_ghana_free_shs_2017.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `india-aadhaar-dbt-2016` | Digital public service | `expected_claim_ids=[claim:aadhaar-dbt-targets-benefits]`; `label=semantic_pass`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_india_aadhaar_dbt_2016.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_india_aadhaar_dbt_2016.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `mexico-ssb-tax-2014` | Public health | `expected_claim_ids=[claim:ssb-tax-reduces-purchases]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_mexico_ssb_tax_2014.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_mexico_ssb_tax_2014.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `netherlands-room-for-the-river-2007` | Climate adaptation | `expected_claim_ids=[claim:room-for-river-reduces-flood-risk]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_netherlands_room_for_river_2007.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_netherlands_room_for_river_2007.adjudication.json) | Used in the S13 certified-envelope-delta evidence set. [`.../layer2_s14_universality_assurance_manifest.json:200-255`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json) | `C3_slice_development_seen` | Public regression only; not sealed or adjacent unseen. |
| `pakistan-ehsaas-emergency-cash-2020` | Social protection | `expected_claim_ids=[claim:ehsaas-rapid-social-protection]`; `label=semantic_pass`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_pakistan_ehsaas_cash_2020.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_pakistan_ehsaas_cash_2020.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `uk-levelling-up-fund-2021` | Infrastructure | `expected_claim_ids=[claim:luf-prioritises-local-infrastructure]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_uk_levelling_up_fund_2021.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_uk_levelling_up_fund_2021.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `uk-making-tax-digital-vat-2019` | Tax enforcement | `expected_claim_ids=[claim:mtd-improves-tax-compliance]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_uk_mtd_vat_2019.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_uk_mtd_vat_2019.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `uk-work-programme-2011` | Labour activation | `expected_claim_ids=[claim:work-programme-sustained-employment]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_uk_work_programme_2011.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_uk_work_programme_2011.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |
| `us-ppp-2020` | MSME emergency credit | `expected_claim_ids=[claim:ppp-emergency-payroll-support]`; `label=limitation_required`; gold card and votes committed; calibration round null. [`.../adjudications/w11a_us_ppp_2020.adjudication.json:1-170`](../../universal-policy-design/outcome-corpus/adjudications/w11a_us_ppp_2020.adjudication.json) | Public corpus/adjudication and per-slice classification; no integrated-loop evidence found. [`.../outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md); [`.../universal-policy-design-system-vision-and-organizing-rules.md:404-430`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) | `C2_answer_seen` | Public regression/calibration only; not sealed or adjacent unseen. |

### Name reconciliation

The human-facing task uses names without the repository's `w11a_` prefix and calls the
Pakistan case `pakistan-ehsaas-emergency-cash-2020`; the committed file names use
`w11a_*` and `w11a_pakistan_ehsaas_cash_2020`. These are aliases for census reporting,
not new identities. The canonical source rows and committed manifest names remain the
repository spellings ([`outcome-corpus/README.md:18-48`](../../universal-policy-design/outcome-corpus/README.md);
[`adjudications/README.md:29-52`](../../universal-policy-design/outcome-corpus/adjudications/README.md)).

## 4. The ua-msme dilemma — decision and cost

### Decision

`ua-msme-affordable-loans-2022` is **excluded from the decisive first-promotion
holdout**. It remains mandatory public regression material and may be used to prove that
the frozen implementation has not regressed, but its result cannot establish “the first
positive governed promotion without cherry-picking.”

### Why

1. The case was selected and developed long before this protocol.
2. It is the only full-loop case, so system shape and case tractability are entangled.
3. It appears in multiple development records.
4. N9 carries a ua-msme governed-promotion reference by default.
5. Its expected adjudication answer is public.

The letter of “do not choose after seeing this run” would therefore preserve a
substantive selection leak: years of prior case-conditioned engineering happened before
the formal run. Calling it unseen would be false.

### Cost

The decisive attempt must use a newly authored, independently held case that has never
completed the loop. It may refuse, dispute, or fail to converge. The project therefore
loses the easiest path to a positive headline and accepts the possibility that the first
protocol version yields **no promotion**.

### Evidence that could reopen the decision

Only a custody proof strong enough to defeat the facts above could reopen it—for example,
proof that the decisive expectation and all case-specific binding choices were generated
outside the implementation team, remained inaccessible before the code/configuration
freeze, and that prior ua-msme work could not affect the tested predicates. The pinned
repository supplies the opposite evidence. A fresh hidden label alone would not remove
case-selection and implementation contamination.

## 5. Reviewer and calibration exposure

The adjudication guide requires preserving reviewer role, expertise basis, conflicts,
and substantive disagreement; it also states that deep-pilot manifests overlap reviewers
for calibration and later manifests may be partially disjoint
([`adjudications/README.md:9-27`](../../universal-policy-design/outcome-corpus/adjudications/README.md)).
The committed manifests identify role-shaped reviewer IDs and declarations such as
`none_declared`, not accountable natural persons. Most have `calibration_round_id: null`;
three deep-pilot manifests record `deep-pilot-round-1`. This is useful public-regression
metadata, but it is not proof of independent adjudication for an irreversible first
promotion. INT-R9 therefore treats all existing reviewer topology as **development and
calibration exposure**, never as the independent panel required for the decisive run.

## 6. Public regression population

The public regression battery may use:

- all 13 real case packs and adjudications;
- both synthetic adjudications;
- ID-renumbered, delivery-order, wrong-scope, source-flip, and obligation-removal
  mutations whose expectations are public;
- the S14 assurance material only within its declared scope.

The S14 manifest itself limits its authority and bars production, recommendation,
publication, claim, closeout, and gold-label authority
([`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:1-340`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json)).
A green public battery can show regression conformance to named visible predicates; it
cannot supply the sealed evidence needed for INT-R9.

## 7. Decisive holdout requirement

Because every current real case is at least `C2_answer_seen`, the decisive holdout must
be **newly authored after this census and before candidate inspection**, with:

1. input package authored under a declared domain method;
2. expectation/evaluator package held separately;
3. commitment and access-log custody reused from S0-GAP-02;
4. no implementation-side access to the answer package before output freeze;
5. no prior case-specific code, configuration, binding, alias, or fixture;
6. a separately sealed adjacent case;
7. precommitted attempt ordering and stopping, so a failed case cannot be swapped for a
   successful public or unregistered case.

A new case is not automatically clean. It becomes `C0_unseen` only if custody evidence
supports the claim.

## 8. Census falsifier

This census is wrong if the auditor finds either:

- a current corpus case whose expected answer was not implementation-visible before the
  relevant freeze and whose case-selection and implementation history are demonstrably
  independent; or
- repository evidence that one of the cases classified only `C2` was in fact used for
  integrated-loop or case-specific development, which would raise, not lower, its class.

Until such evidence appears, the honest denominator is: **13 public real regression
cases, 2 public synthetic adjudication fixtures, 0 sealed decisive cases, 0 adjacent
unseen cases.**
