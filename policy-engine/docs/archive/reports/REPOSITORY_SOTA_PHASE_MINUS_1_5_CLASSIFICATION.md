---
title: Repository SOTA Phase -1.5 Classification
status: report
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-05-02
stability: snapshot
---

# Repository SOTA Phase -1.5 Classification

This is the refreshed Phase -1.5 amnesty and classification report for
`REPOSITORY_SOTA_PLAN.md`.

Phase -1.5 classifies loose files and local outputs, extends ignore coverage,
and performs only unambiguous cleanup. It does not delete active source,
fixtures, contracts, migration evidence, Data Forge domain work, production
artifacts, or generated-schema candidates.

## Actions Performed

| Surface | Action | Target / result |
| ------- | ------ | --------------- |
| Root reports | Moved | `.polisyos/reports/repository-sota-phase-minus-1-5/` |
| Product audit bundles | Moved | `policy-engine/.polisyos/audits/repository-sota-phase-minus-1-5/` |
| Historical root spec | Moved | `policy-engine/docs/archive/specs/scm-implementation-spec-v3.md` |
| Root topic helper scripts | Moved | `policy-engine/tools/research/filter_topics.py` and `policy-engine/tools/research/organize_relevant_topics.py` |
| Product `env_example.txt` | Removed | `policy-engine/.env.example` is the canonical safe local example |
| Accidental shell artifact | Removed | `policy-engine/=2.5.0` |
| `.DS_Store` files | Removed | Repository-wide accidental OS metadata cleanup |
| Frontend local outputs | Ignore rules extended | explicit `runtime-dashboard` local output rules in `policy-engine/.gitignore` |

Moved root reports:

- `compileall.txt`
- `import_gate.txt`
- `ruff_stats.txt`
- `summary.json`
- `test_collect.txt`
- `stale_sources_missing_paths.txt`

Moved product audit bundles:

- 19 `audit_R_recover_*.polisyos-audit.tar.gz` files were moved under
  `policy-engine/.polisyos/audits/repository-sota-phase-minus-1-5/`.

## Ignore-Rule Changes

Root ignore coverage already handled the current local root artifacts:

| Pattern | Coverage |
| ------- | -------- |
| `/data/` | Local data lake |
| `/relevant_topics_domain_files/` | Local topic directory |
| `*.csv` | Local CSV/topic exports |
| `scm-implementation-spec-v3.md` | Prevents the archived spec from reappearing at repo root |
| `.venv-*/` | Local environment variants such as `.venv-spatial-tests/` |
| `/.tmp/`, `/tmp/`, `/runs/`, `/logs/`, `/out/`, `/dist/`, `/site/`, `/benchmark-results/` | Local run/build outputs |
| `/*.polisyos-audit.tar.gz` | Root audit bundles |
| `/=*` | Accidental shell redirection artifacts |
| root report files | Validation and lint scratch reports |

Product-root ignore coverage already handled local state, audit bundles, local
data, product-root outputs, accidental CSVs, and `production_data/`.

Additional product-root ignore coverage added on 2026-05-02:

| Pattern | Reason |
| ------- | ------ |
| `frontend/runtime-dashboard/coverage/` | Local test coverage output |
| `frontend/runtime-dashboard/playwright-report/` | Local Playwright report output |
| `frontend/runtime-dashboard/test-results/` | Local Playwright/Vitest test output |
| `frontend/runtime-dashboard/storybook-static/` | Local Storybook build output |
| `frontend/runtime-dashboard/output/` | Local dashboard output captures |
| `frontend/runtime-dashboard/.tmp/` | Local dashboard scratch output |

## Classification

| Surface | Classification | Phase -1.5 result |
| ------- | -------------- | ----------------- |
| Root reports: `compileall.txt`, `import_gate.txt`, `ruff_stats.txt`, `summary.json`, `test_collect.txt`, `stale_sources_missing_paths.txt` | Local reports | Moved to `.polisyos/reports/repository-sota-phase-minus-1-5/`. |
| Root topic CSV: `topics.csv` | Local topic artifact | Kept ignored by root `*.csv`; fixture/source decision deferred. |
| Root topic directory: `relevant_topics_domain_files/` | Local topic artifact | Kept ignored by root path rule; fixture/source decision deferred. |
| Root topic helpers: `filter_topics.py`, `organize_relevant_topics.py` | Durable research helpers | Moved to `policy-engine/tools/research/` per existing migration shim targets. |
| Historical root spec: `scm-implementation-spec-v3.md` | Durable historical spec | Archived under `policy-engine/docs/archive/specs/`. |
| Root virtualenv: `.venv/` | Local virtualenv | Kept ignored by `.venv/`; not deleted. |
| Root env variant: `.venv-spatial-tests/` | Local virtualenv | Kept ignored by `.venv-*/`; not deleted. |
| Product accidental file: `=2.5.0` | Accidental shell artifact | Removed after classification. |
| Product accidental metadata: `.DS_Store` | Accidental OS metadata | Removed repository-wide after classification. |
| Product `env_example.txt` | Obsolete environment example | Removed after confirming `policy-engine/.env.example` is canonical in docs and tooling. |
| Product audit bundles: `audit_R_recover_*.polisyos-audit.tar.gz` | Local audit bundles | Moved to `policy-engine/.polisyos/audits/repository-sota-phase-minus-1-5/`. |
| Product `all_1000_policy_topics.csv` | Local topic artifact | Kept ignored; fixture/source decision deferred. |
| Product local outputs: `runs/`, `logs/`, `out/`, `dist/`, `site/`, `benchmark-results/`, `tmp/` | Local outputs | Kept ignored; no deletion performed. |
| Product scratch envs: `.venv/`, `.venv_codex/`, `.tmp_c7_venv/`, `.tmp_c7_smoke/` | Local environments/scratch | Kept ignored; no deletion performed. |
| Frontend outputs: `node_modules/`, `dist/`, `coverage/`, `playwright-report/`, `test-results/`, `storybook-static/`, `output/`, `.tmp/` | Local generated outputs | Kept ignored with explicit dashboard patterns. |
| `policy-engine/production_data/` | Large local runtime data | Kept ignored/local; not moved or deleted. |
| Data Forge schema candidates | Potential committed contracts | Not touched; remain for Phase 0/Phase 4 registration decisions. |

## Product-Root Non-Amnesty Candidates

The following product-root entries are not local-output amnesty items. They are
tracked or intentional product-root surfaces that should be normalized in Phase
0 topology/contracts rather than moved or ignored during Phase -1.5.

| Surface | Classification | Phase -1.5 result |
| ------- | -------------- | ----------------- |
| `.basedpyright/baseline.json` | Quality baseline | Kept; Phase 0 should register or explicitly allow this topology path. |
| `.markdownlint-cli2.jsonc` | Docs style config | Kept; Phase 0 should register or explicitly allow this topology path. |
| `.taplo.toml` | TOML formatter/config policy | Kept; Phase 0 should register or explicitly allow this topology path. |
| `.yamllint` | YAML lint config | Kept; Phase 0 should register or explicitly allow this topology path. |
| `.cursor/rules/design-system.mdc` | Tooling/design-system rule | Kept; Phase 0 should decide whether this is committed tooling policy or local editor state. |
| `CHANGELOG-DESIGN.md` | Design changelog | Kept; Phase 0/docs lifecycle should classify it as design docs or changelog material. |
| `packages/cli/**` | Frontend/tooling package | Kept; Phase 0/frontend workspace contract should register the `packages/` topology. |

## Archive, Fixture, And Manifest Decisions

| Surface | Decision |
| ------- | -------- |
| `policy-engine/docs/archive/specs/scm-implementation-spec-v3.md` | Historical spec archived as durable documentation. |
| `topics.csv` | Local data for now; do not promote until fixture/source-of-truth decision is made. |
| `relevant_topics_domain_files/` | Local data for now; do not promote until manifest or fixture decision is made. |
| `policy-engine/all_1000_policy_topics.csv` | Local data for now; do not promote until Data Forge input/fixture decision is made. |
| `policy-engine/production_data/*` | Local runtime data; requires retention, PII, and artifact-governance classification before any promotion. |
| Durable fixtures/manifests | No unambiguous durable fixture or manifest promotion was identified in Phase -1.5; bulky/derived topic data remains ignored local data. |

## Compatibility And Evidence Notes

- `policy-engine/tools/research/filter_topics.py` and
  `policy-engine/tools/research/organize_relevant_topics.py` match the existing
  targets in `architecture/migration_shims.toml`.
- Both moved topic helper scripts passed Python bytecode compilation.
- `env_example.txt` was removed only after confirming `.env.example` is the
  canonical example referenced by docs and workspace tooling.
- Audit bundles were preserved under ignored local state instead of deleted.
- No active source, fixture, contract, migration evidence, Data Forge schema
  candidate, or production data artifact was deleted.
- Root/product-root topology comparison after cleanup reported no unclassified
  repo-root entries; remaining product-root topology candidates are listed in
  the non-amnesty table above for Phase 0.

## Plan Coverage Matrix

| Plan item | Implementation evidence |
| --------- | ----------------------- |
| Classify audit bundles | Classified as local audit bundles and moved to `policy-engine/.polisyos/audits/repository-sota-phase-minus-1-5/`. |
| Classify root reports | Classified as local reports and moved to `.polisyos/reports/repository-sota-phase-minus-1-5/`. |
| Classify accidental files | Classified `.DS_Store`, `=2.5.0`, and `env_example.txt`; removed only after classification. |
| Classify scratch virtualenvs | Classified root and product-root virtualenv/scratch envs; kept ignored and not deleted. |
| Classify local outputs | Classified root, product-root, and frontend local outputs; kept ignored. |
| Classify historical specs | Archived `scm-implementation-spec-v3.md` under `docs/archive/specs/`. |
| Classify topic artifacts | Kept `topics.csv`, `relevant_topics_domain_files/`, and `all_1000_policy_topics.csv` as ignored local data pending fixture/manifest decision. |
| Classify temporary run products | Kept `runs/`, `tmp/`, reports, frontend reports, and audit bundles in ignored local state. |
| Extend ignore rules | Added explicit frontend local-output ignore patterns to `policy-engine/.gitignore`; existing root/product rules cover other local state. |
| Move durable docs/specs | Moved the historical SCM implementation spec to the archive specs lifecycle home. |
| Relocate durable fixtures/manifests or keep bulky derived data local | No durable fixture/manifest promotion was unambiguous; bulky/derived topic and production data remains ignored local data. |

## Deferred Items

These surfaces remain intentionally classified but unresolved:

1. Decide whether `topics.csv`, `all_1000_policy_topics.csv`, and
   `relevant_topics_domain_files/` become fixtures, ignored local data, or
   manifest-backed Data Forge inputs.
2. Decide whether root-level topic helper compatibility wrappers are still
   needed. Root wrappers would reintroduce root loose files, so this phase leaves
   the moved tools as the canonical implementation.
3. Decide whether any product-root local virtualenvs should be deleted later.
   They are ignored and local, but deletion is not required for this phase.
4. Decide whether `policy-engine/production_data/*` needs a retention manifest,
   release artifact registration, or local-only cleanup policy.

## Acceptance Evidence

Phase -1.5 acceptance status:

1. Root reports were moved to ignored local report state.
2. Root tracked topic helper scripts were moved to canonical
   `policy-engine/tools/research/` targets.
3. The historical root spec was archived under `docs/archive/specs/`.
4. Root topic artifacts remain ignored local data pending fixture/manifest
   classification.
5. Product audit bundles were preserved under ignored local audit state.
6. Accidental files were removed only after this classification was established.
7. Ignore rules were extended for frontend local generated outputs.
8. Root loose files are now either allowed by topology, moved to a canonical
   home, or ignored as local state.
9. No active source, fixture, contract, or migration evidence was deleted.
