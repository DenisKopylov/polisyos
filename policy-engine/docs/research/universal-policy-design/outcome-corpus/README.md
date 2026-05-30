# Universal Outcome Corpus

Wave: W11.A Universal Outcome Corpus Sourcing

This directory is the repo-owned source surface for real policy cases used by
the universal Policy Design Case outcome track. Each case is a Markdown file
with YAML frontmatter shaped by the Annotation Protocol Draft in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`.

W11.A began as a sourcing pass, not expert adjudication. The files now carry
source-grounded seed claims, W11.B claim/evidence decomposition annotations,
expected evidence families, raw source refs, known limitation labels, and a
W11.C adjudication status pointer. Strict C30 adjudication manifests live under
`adjudications/`; machine-loadable W11.D fixtures live under
`tests/fixtures/universal-corpus/`. These corpus annotations remain evaluation
authority only and must not be treated as runtime claim, legal, evidence,
method, participation, closeout, or projection authority.

## Coverage

| Case | Domain | Authority level | Jurisdiction authority | Policy time |
| --- | --- | --- | --- | --- |
| `w11a_us_ppp_2020` | `msme_credit_grant` | `production` | `national` | `2020-03 to 2021-05` |
| `ua-msme-affordable-loans-2022` | `msme_credit_grant` | `governed` | `national` | `2022-2024` |
| `w11a_mexico_ssb_tax_2014` | `public_health_intervention` | `research` | `national` | `2014-01 onward` |
| `w11a_berlin_rent_cap_2020` | `housing_rent_control` | `governed` | `subnational` | `2020-02 to 2021-04` |
| `w11a_uk_mtd_vat_2019` | `tax_enforcement` | `governed` | `national` | `2019-04 onward` |
| `w11a_ghana_free_shs_2017` | `education_access` | `research` | `national` | `2017-09 onward` |
| `w11a_netherlands_room_for_river_2007` | `climate_adaptation` | `research` | `national` | `2007-01 to 2019-01` |
| `w11a_uk_work_programme_2011` | `labour_activation` | `governed` | `national` | `2011-06 to 2017-03` |
| `w11a_eu_temporary_protection_ukraine_2022` | `migration_displacement` | `production` | `supranational` | `2022-03 to 2027-03` |
| `w11a_boston_operation_ceasefire_1996` | `public_safety` | `research` | `local` | `1996-05 to 2000 evaluation window` |
| `w11a_india_aadhaar_dbt_2016` | `digital_public_service` | `production` | `national` | `2016-09 onward` |
| `w11a_uk_levelling_up_fund_2021` | `infrastructure_prioritisation` | `governed` | `national` | `2021-22 to 2025-26` |
| `w11a_pakistan_ehsaas_cash_2020` | `social_protection_targeting` | `production` | `national` | `2020-04 to 2020-10` |

Coverage totals:

- 13 real cases.
- 12 domains.
- 3 PolicyOS authority levels: `research`, `governed`, `production`.
- 4 jurisdiction authority levels: `local`, `subnational`, `national`,
  `supranational`.

## Pattern Pass

- Relevant patterns: `P01`, `P02`, `P03`, `P05`, `P10`, `P13`, `P14`, `P15`.
- Existing anti-pattern avoided: W11.A-C close `artifact_missing` for the
  universal outcome corpus, per-case decomposition annotations, and expert
  adjudication labels by keeping sourced cases and C30 manifests under
  repo-owned paths instead of a local research folder.
- Target correct pattern: source refs are explicit, expected evidence families
  are named, adjudication status is visible, and every case remains limited to
  evaluation authority while W11.E/W11.F measure compiler/runtime behavior.
- Missing capability labels after W11 source surfaces: none for W11.A-C source
  artifacts; the earlier `consumer_missing` and `verification_missing` labels
  are closed by W11.D-F loader/tool suites, and `semantic_test_missing` is
  closed by W11.C adjudication coverage plus W11.E truthfulness measurement.
- Acceptance signal: `uv run pytest tests/repo_quality/tools/test_w11a_universal_outcome_corpus_sourcing.py tests/repo_quality/tools/test_universal_corpus_annotations.py tests/repo_quality/tools/test_expert_adjudication_labels.py -q`.

## Transformation Notes

The `references` lists are deliberately source-indexed because W11.B loaders
must be able to reject ungrounded claim refs. `raw_source_refs` duplicates the
web-facing URLs for the W11.A negative test: a case without a raw source ref or
redacted hash cannot enter the corpus.
