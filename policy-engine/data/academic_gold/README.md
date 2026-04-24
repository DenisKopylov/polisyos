# Academic Gold Set

This directory holds the repository-tracked gold-set scaffolding for the academic causal-claims pipeline.

Files:

- `guidelines.md`: annotation rubric for screen-level and claim-level labels.
- `screen_gold.jsonl`: manually curated screening gold examples.
- `claim_gold.jsonl`: manually curated claim extraction/adjudication gold examples.

Notes:

- The files are intentionally small seed sets in git. They are meant to be expanded by human annotators.
- Use `python scripts/build_academic_gold_candidates.py --snapshot-root <snapshot>` to generate candidate pools from a snapshot before manual labeling.
- `Causal Claims in Economics` should be treated as a silver candidate source, not as gold.
