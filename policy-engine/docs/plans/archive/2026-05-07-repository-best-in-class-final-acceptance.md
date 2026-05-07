---
title: Repository Best-In-Class Final Acceptance
status: accepted
last_verified: 2026-05-07
stability: final
owner: team-architecture
supersedes:
  - docs/plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md
---

# Repository Best-In-Class Final Acceptance

This report closes the repository best-in-class remediation program in a
verifiable committed-state shape. The active remediation master plan is archived
at `docs/plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md`.

## Dirty State Classification

The branch started from the current dirty workspace with 3246 worktree entries.
Those entries were classified as acceptance-owned remediation state because they
map to the root topology closure, JavaScript `apps/` and `packages/` workspace
conversion, package/source facade closure, architecture contract registries,
tests, docs lifecycle, runtime/ops/release contracts, and acceptance evidence.
No unrelated user-change bucket was identified for this closeout.

## Final State

| Area | Final state | Evidence |
| --- | --- | --- |
| Product root policy | Outer repository root is GitHub/Git control plane plus `policy-engine/`; root topology gates are fail-closed. | `architecture/topology.toml`, `_build/.tmp/final-acceptance/platform-acceptance.json` |
| Renovate policy | Canonical config is `.github/renovate.json`; outer-root `renovate.json` is retired. `matchFileNames` must resolve and the retired `policy-engine/frontend/runtime-dashboard/package.json` path is blocked. | `.github/renovate.json`, `architecture/control_plane_supply_chain.toml`, `_build/.tmp/final-acceptance/control-plane-supply-chain.json` |
| Docs lifecycle | Final remediation plan is archived; active plans containing accepted final closeout evidence now fail the docs lifecycle gate. | `tools/quality/validation/check_docs_lifecycle.py`, `tests/repo_quality/tools/test_docs_lifecycle.py` |
| Importable roots | Namespace-capable non-product roots are documented and fail if undocumented: `tools`, `tests`, `benchmarks`, `apps`, `examples`, `ops`, `schemas`. | `architecture/directory_contracts.toml`, `_build/.tmp/final-acceptance/package-import-gates.json` |
| Top-level schemas | Top-level `schemas/` is schema-only: no `.py`, no `__init__.py`, and no product Python package code. Python schema helpers live under `src/polisyos/schemas`. | `architecture/directory_contracts.toml`, `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py` |
| Root facade policy | Package-root `.py` files are allowed facades, registered shims, or dated root-file exceptions. New unregistered root implementation files fail closed. | `architecture/package_layout.toml`, `tools/quality/validation/check_package_import_gates.py` |
| Scientist topology | Canonical Scientist first-level count is 18 semantic roots against cap 18. Compatibility shim roots are separate debt: 31 registered roots, covered by shim policy and smoke imports. | `architecture/packages/scientist.toml`, `docs/reference/scientist/index.md` |
| God-module ratchet | Existing oversized modules cannot grow above committed `current_lines`; 18 active budgets remain dated report-only decomposition debt. | `architecture/module_size_budget.toml`, `_build/.tmp/final-acceptance/package-import-gates.json` |
| Release/operability | Operability release gate is fail-closed; compatibility release metadata remains report-only but contract errors are fail-on and target fail-closed no earlier than 2026-10-01. | `_build/.tmp/final-acceptance/operability-release-gates.json`, `_build/.tmp/final-acceptance/compatibility-release-gates.json` |

## Package Facade Exceptions

All package-root Python exceptions require `path`, `owner`, `sunset`, and
`reason`. The default sunset for newly accepted root-file exceptions is
2026-07-31.

| Owner | Exception count | Sunset |
| --- | ---: | --- |
| team-architecture | 8 | 2026-07-31 |
| team-core | 7 | 2026-07-31 |
| team-data-forge | 2 | 2026-07-31 |
| team-foundry | 2 | 2026-07-31 |
| team-lex | 8 | 2026-07-31 |
| team-runtime | 2 | 2026-07-31 |
| team-scholar | 6 | 2026-07-31 |
| team-scientist | 2 | 2026-07-31 |

Total: 37 registered root-file exceptions. The fail-closed gate is
`uv run python tools/quality/validation/check_package_import_gates.py --fail-closed`.

## Report-Only Transitions

Every remaining report-only program item has an owner, evidence location, and
dated target in `architecture/gates/report_only.toml`.

| Transition | Owner | Evidence | Target |
| --- | --- | --- | --- |
| Package contract schema | team-architecture | `architecture/packages/*.toml` | 2026-10-01 or later |
| Compatibility release gates | team-release | `architecture/compatibility_release_gates.toml` | 2026-10-01 or later |
| Package aggregate mirrors | team-architecture | `architecture/package_boundaries.toml` | 2026-10-01 or later |
| Module-size budget decomposition | team-architecture | `architecture/module_size_budget.toml` | 2026-10-01 or later |
| Generated artifact contracts | team-architecture | `architecture/generated_artifacts.toml` | 2026-10-01 or later |
| Extension points | team-architecture | `architecture/extension_points.toml` | 2026-10-01 or later |
| Runbook coverage contract mirror | team-architecture | `architecture/runbook_coverage.toml` | 2026-10-01 or later |
| Component observability contract mirror | team-architecture | `architecture/component_observability.toml` | 2026-10-01 or later |
| Runtime-state layout contract mirror | team-architecture | `architecture/runtime_state_layout.toml` | 2026-10-01 or later |
| Test ratchet contract mirror | team-quality | `architecture/test_ratchets.toml` | 2026-10-01 or later |
| Directory contract mirror | team-architecture | `architecture/directory_contracts.toml` | 2026-10-01 or later |
| Directory hygiene assets | team-quality | `architecture/asset_placement.toml` | 2026-10-01 or later |
| Static-analysis overrides | team-architecture | `architecture/static_analysis_overrides.toml` | 2026-10-01 or later |
| Dead static-analysis overrides | team-devx | `architecture/static_analysis_overrides.toml` | 2026-10-01 or later |

Fresh report-only evidence was written to
`_build/.tmp/final-acceptance/architecture-contracts-all.json` with
`contract_error_count = 0`.

## Command Evidence

All commands below were run from `/Users/deniskopylov/polisyos/policy-engine`
on 2026-05-07 unless noted.

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py --output-json _build/.tmp/final-acceptance/control-plane-supply-chain.json --crosswalk-json _build/.tmp/final-acceptance/supply-chain-control-crosswalk.json --strict-current-codeowners
uv run polisyos-tools workspace tool-configs --check
uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/final-acceptance/package-import-gates.json
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/final-acceptance/directory-health.json --markdown-output _build/.tmp/final-acceptance/directory-health.md --fail-on-regression
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/final-acceptance/test-ratchets.json --fail-on-regression
uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/final-acceptance/dead-overrides.json
uv run python tools/quality/validation/check_extension_examples.py
uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/final-acceptance/operability-release-gates.json --fail-closed
uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/final-acceptance/compatibility-release-gates.json --fail-on-contract-errors
uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/final-acceptance/platform-acceptance.json --summary _build/.tmp/final-acceptance/platform-acceptance.md
uv run polisyos-tools workspace acceptance-audit --json-output docs/archive/reports/platform-acceptance.json --summary docs/archive/reports/platform-acceptance.md
uv run python -m tools.devx.workspace.doctor
uv run pytest tests/contract -q
uv run pytest tests/repo_quality -q
uv run python tools/quality/validation/architecture_report_only_contracts.py --report all --json-output _build/.tmp/final-acceptance/architecture-contracts-all.json --fail-on-contract-errors
corepack pnpm install --frozen-lockfile
corepack pnpm -r --workspace-concurrency=1 --if-present run build
corepack pnpm -r --workspace-concurrency=1 --if-present run test
```

Final root evidence checks are run from `/Users/deniskopylov/polisyos`:

```bash
test ! -f renovate.json
test -f .github/renovate.json
git ls-files | awk '!/^policy-engine\// && !/^\.github\// && $0 !~ /^\.(editorconfig|gitattributes|gitignore)$/ {print; bad=1} END {exit bad}'
git ls-files policy-engine | rg '(^|/)(_build|_cache|__pycache__|node_modules|\.venv|\.polisyos|tmp)/|\.pyc$|\.DS_Store$|egg-info' && exit 1 || true
git status --porcelain=v1
```
