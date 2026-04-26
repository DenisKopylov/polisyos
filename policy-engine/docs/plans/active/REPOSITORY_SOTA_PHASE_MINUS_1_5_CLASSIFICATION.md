---
title: Repository SOTA Phase -1.5 Classification
status: active
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-04-24
stability: snapshot
---

# Repository SOTA Phase -1.5 Classification

This is the conservative Phase -1.5 classification for
`REPOSITORY_SOTA_PLAN.md`. The scope is intentionally narrow while the Lex NPA
corpus run is active: classify loose files, tighten ignore coverage for
local-only artifacts, and defer physical moves that could affect active or
queued cloud work.

No protected Lex/cloud files or production output layouts were moved, rewritten,
or deleted.

## Ignore-Rule Changes

Safe root ignore coverage added on 2026-04-24:

| Pattern | Reason |
| ------- | ------ |
| `.venv-*/` | Covers local environment variants such as `.venv-spatial-tests/`. |
| `/logs/` | Keeps root logs local-only if created. |
| `/out/` | Keeps root build outputs local-only if created. |
| `/dist/` | Keeps root build outputs local-only if created. |
| `/site/` | Keeps root documentation builds local-only if created. |
| `/benchmark-results/` | Keeps root benchmark output local-only if created. |
| `/*.polisyos-audit.tar.gz` | Keeps root audit bundles local-only if created. |
| `/=*` | Covers accidental shell redirection artifacts such as `=2.5.0`. |

Existing product-root ignore coverage already handles:

- `.venv/`, `.venv_codex/`, `.tmp_c7_venv/`, `.tmp_c7_smoke/`, `.uv-cache/`
- `logs/`, `runs/`, `tmp/`, `out/`, `dist/`, `site/`, `benchmark-results/`
- `*.duckdb`, `*.kuzu`
- `*.polisyos-audit.tar.gz`
- `all_1000_policy_topics.csv`, `env_example.txt`, and `/=*`
- `production_data/`

## Classification

| Surface | Current classification | Phase -1.5 action |
| ------- | ---------------------- | ----------------- |
| Root reports: `compileall.txt`, `import_gate.txt`, `ruff_stats.txt`, `summary.json`, `test_collect.txt`, `stale_sources_missing_paths.txt` | Local reports | Already ignored at repo root; no move during overlay. |
| Root topic CSV: `topics.csv` | Local topic artifact | Already covered by root `*.csv`; do not move during overlay. |
| Root topic directory: `relevant_topics_domain_files/` | Local topic artifact | Already ignored; do not move during overlay. |
| Root scripts: `filter_topics.py`, `organize_relevant_topics.py` | Tracked legacy topic helpers | Already deny-listed by topology; defer move/class split to `tools/research` or `tools/workspace`. |
| Root historical spec: `scm-implementation-spec-v3.md` | Tracked historical spec | Already deny-listed by topology; defer archive/ADR replacement review. |
| Root env variant: `.venv-spatial-tests/` | Local virtualenv | Now ignored by `.venv-*/`; no deletion performed. |
| Product accidental file: `=2.5.0` | Local accidental shell artifact | Already ignored by product-root `/=*`; no deletion performed. |
| Product audit bundles: `audit_R_recover_*.polisyos-audit.tar.gz` | Local audit bundles | Already ignored by product-root pattern; defer archive/delete cleanup. |
| Product `all_1000_policy_topics.csv` | Local topic artifact | Already ignored; defer fixture/source classification. |
| Product local outputs: `runs/`, `logs/`, `out/`, `dist/`, `site/`, `benchmark-results/`, `tmp/` | Local outputs | Already ignored; no deletion performed. |
| Root future outputs: `logs/`, `out/`, `dist/`, `site/`, `benchmark-results/` | Local outputs | Now ignored if created. |
| `data/data_lex` and `data/lex_knowledge` | Freeze-protected local Lex data | Do not move, delete, normalize, or rewrite during Lex production freeze. |
| `tools/cloud/**` and `tools/ops/cloud/**` | Freeze-protected cloud execution surfaces | No wrapper removal or path tightening during overlay. |

## Deferred Cleanup

These items remain intentionally unresolved until the overlay allows stronger
actions:

1. Move or archive tracked root topic helpers only after confirming they are not
   referenced by active or queued Lex preparation workflows.
2. Archive or replace `scm-implementation-spec-v3.md` with curated historical
   docs and ADR/reference links.
3. Decide whether `topics.csv`, `all_1000_policy_topics.csv`, and
   `relevant_topics_domain_files/` are fixtures, ignored local data, or
   manifest-backed source inputs.
4. Delete or archive ignored audit bundles only after confirming they are not
   needed for active review.
5. Keep `data/data_lex`, `data/lex_knowledge`, cloud deploy assets, and
   sharded output roots frozen until Queue 2 and Queue 3 Waves 1-5 complete and
   pass merge/QC.

## Overlay Safety Check

Phase -1.5 did not change:

- `src/polisyos/lex/batch/**`
- `src/polisyos/batch_common/**`
- `src/polisyos/batch_snapshot/**`
- `tools/ops/cloud/**`
- `tools/cloud/**`
- `tools/ops/ukraine_data/pre_shard_lex_corpus.py`
- `tools/ukraine_data/pre_shard_lex_corpus.py`
