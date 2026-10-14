# Academic Gold Set

This directory holds seed scaffolding for the academic causal-claims pipeline;
it is not a versioned, rubric-conformant evaluation gold set.

Files:

- `guidelines.md`: annotation rubric for claim-level labels. The file does not
  declare a rubric version.
- `claim_gold.jsonl`: three seed claim rows in the repository tree as inventoried
  on 2026-10-14. This is a complete row count for this file, not a claim about
  other candidate pools.
- `claim_gold_split.json`: suite `claim_gold`, version `1.0`, with selection and
  holdout IDs. This split version does not version the annotation rubric.

Notes:

- These rows are intentionally small seed data, not complete examples for the
  current rubric. All three omit the rubric-required `title`, `paper_abstract`,
  `claim_text`, `direction`, and `supporting_spans` fields. They also use
  `design_family=ols` and `support_status=insufficient`; the rubric's permitted
  values are `ols_cross_sectional` and `insufficient_evidence` respectively.
- Do not treat the current rows as a calibrated benchmark or as evidence that
  annotation/data validation has passed. The seed set is intended to be expanded
  and adjudicated by human annotators against a versioned rubric.
- Use `python polisyos-tools data build-academic-gold-candidates --snapshot-root <snapshot>` to generate candidate pools from a snapshot before manual labeling.
- `Causal Claims in Economics` should be treated as a silver candidate source, not as gold.
