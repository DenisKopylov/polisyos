# W11.C Expert Adjudication Labels

This directory stores repo-owned expert adjudication label manifests for the
universal outcome corpus. The contract is `C30`: structural validity is only a
candidate signal until expert labels judge interpretation, scope, legal
competence, causal support, method fit, time-role alignment, participation
attribution, independence, and public truthfulness.

## Annotation Guide

- Use the labels `semantic_pass`, `limitation_required`, `contested`,
  `unsupported`, `false_pass`, `fabricated_unverifiable`, and
  `reviewer_disagreement`.
- Preserve reviewer role, expertise basis, conflicts, and disagreement
  category. Substantive disagreement must stay visible as reviewer votes; do
  not collapse it into a hidden gold label.
- For every rejected structural pass, include the C30 gold-card fields:
  `claim_id`, `dimension_id`, `evidence_ref`, `context_ref`, `failure_mode`,
  `why_structural_checks_missed_it`, `status_should_have_been`, and
  `required_surface_change`.
- Deep-pilot manifests use overlapping reviewers for calibration. Later
  manifests may use partial-disjoint review while still recording reviewer
  metadata and any substantive disagreement.

Pattern pass: W11.C primarily guards `P10` structural-only validation and
`P15` speculation laundering, with `P05` authority boundary protection. These
manifests are benchmark/evaluation artifacts only; they do not mint claim,
legal, evidence, or closeout authority.

Committed manifests:

- `housing-rent-stabilization-001.adjudication.json`
- `public-health-outreach-001.adjudication.json`
- `ua-msme-affordable-loans-2022.adjudication.json`
- `w11a_berlin_rent_cap_2020.adjudication.json`
- `w11a_boston_operation_ceasefire_1996.adjudication.json`
- `w11a_eu_temporary_protection_ukraine_2022.adjudication.json`
- `w11a_ghana_free_shs_2017.adjudication.json`
- `w11a_india_aadhaar_dbt_2016.adjudication.json`
- `w11a_mexico_ssb_tax_2014.adjudication.json`
- `w11a_netherlands_room_for_river_2007.adjudication.json`
- `w11a_pakistan_ehsaas_cash_2020.adjudication.json`
- `w11a_uk_levelling_up_fund_2021.adjudication.json`
- `w11a_uk_mtd_vat_2019.adjudication.json`
- `w11a_uk_work_programme_2011.adjudication.json`
- `w11a_us_ppp_2020.adjudication.json`
