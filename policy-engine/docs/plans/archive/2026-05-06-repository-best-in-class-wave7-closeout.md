# Repository Best-In-Class Wave 7 Closeout

Status: accepted final closeout
Owner: team-polisyos
Date: 2026-05-06
Superseded plan: [Repository Best-In-Class Remediation Master Plan](2026-05-07-repository-best-in-class-remediation-master-plan.md)

Wave 7 is the accepted final repository-layout remediation window. The final
closeout gates are green, Scientist repo-quality gates now verify the canonical
Scientist topology, directory-health documentation coverage is closed, platform
acceptance has no manual pending checks, and the phase PR ledger is recorded
below. No blocker exception remains for Wave 7 acceptance.

## Evidence Summary

| Area | Result | Evidence |
| --- | --- | --- |
| Python toolchain | Pass | `uv run python --version` reported Python 3.14.0. |
| JS toolchain | Pass | `corepack pnpm --version` reported 10.33.2. Direct `pnpm` is not required. |
| JS install | Pass | `corepack pnpm install --frozen-lockfile`. |
| JS build | Pass | `corepack pnpm -r --workspace-concurrency=1 --if-present run build`. |
| JS tests | Pass | `corepack pnpm -r --workspace-concurrency=1 --if-present run test`. |
| Workspace doctor | Pass | `uv run python -m tools.devx.workspace.doctor`; direct script invocation is not the required interface. |
| Contract tests | Pass | `uv run pytest tests/contract -q`. |
| Full repo-quality suite | Pass | `uv run pytest tests/repo_quality -q`; Scientist gates have 0 canonical-topology failures. |
| Root structure gate | Pass | `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json`. |
| Decomposition preflight | Pass | `uv run python tools/quality/validation/decomposition_preflight.py gate --output-json _build/.tmp/wave7-closeout/decomposition-preflight.json`. |
| Architecture report-only contracts | Pass | `uv run python tools/quality/validation/architecture_report_only_contracts.py --report all --json-output _build/.tmp/wave7-closeout/architecture-contracts-all.json --fail-on-contract-errors`. |
| Repository SOTA closeout | Pass | `uv run polisyos-tools workspace repository-sota-closeout --skip-generated-checks --output-json _build/.tmp/wave7-closeout/repository-sota-closeout-skip-generated.json`. |
| Directory health | Pass | `uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/wave7-closeout/directory-health.json --markdown-output _build/.tmp/wave7-closeout/directory-health.md --fail-on-regression`. |
| Test ratchets | Pass | `uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/wave7-closeout/test-ratchets.json --fail-on-regression`. |
| Stale overrides | Pass | `uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/wave7-closeout/dead-overrides.json`. |
| Platform acceptance audit | Pass | `uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/wave7-closeout/platform-acceptance.json --summary _build/.tmp/wave7-closeout/platform-acceptance.md`; manual pending = 0. |
| Control-plane supply chain | Pass | `uv run python tools/quality/validation/control_plane_supply_chain_contracts.py --output-json _build/.tmp/wave7-closeout/control-plane-supply-chain.json --crosswalk-json _build/.tmp/wave7-closeout/supply-chain-control-crosswalk.json --strict-current-codeowners`. |
| Operability release gates | Pass | `uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/wave7-closeout/operability-release-gates.json --fail-closed`. |
| Compatibility release gates | Pass | `uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/wave7-closeout/compatibility-release-gates.json --fail-on-contract-errors`. |
| Docs lifecycle | Pass | `uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .`. |

## Before And After Metrics

| Metric | Before | Wave 7 after | Evidence |
| --- | --- | --- | --- |
| Root policy violations | Phase 0.1 baseline: 19 tracked outer-root paths, 210 ignored outer-root files, 0 non-ignored untracked files. | 0 root policy findings in fail-closed structure and repository SOTA closeout gates. | `repository_structure_phase0.py`, `repository-sota-closeout-skip-generated.json`. |
| Root facade violations | Phase 0.1 baseline: 80 non-facade root files across 10 package roots; Fabric 25, IR 19. | 0 root facade findings after registered Python re-export shims are counted as shim policy, not loose roots. | `decomposition-preflight.json`, `architecture/shims.toml`. |
| Shim count and days to sunset | Phase 0.1 baseline: 53 shims; next sunset 2026-07-01, 57 days from 2026-05-05. | 89 registered shims; next sunset 2026-07-01, 56 days from 2026-05-06. | `architecture/shims.toml`. |
| Mirror-test ratios | Phase 0.1 baseline: 28.6 percent weighted strict mirror ratio; 5 pytest-collectable data-like tests; Fabric, Lex, and Data Forge missing dedicated property tests. | Ratchet report passes with 0 floor regressions, 0 property regressions, and only accepted time-boxed mirror-ratchet exceptions. | `test-ratchets.json`, `architecture/test_ratchets.toml`. |
| Module-size debt | Phase 0.1 baseline: 45 modules above 2,000 lines, 7 seeded high-debt modules, largest module 10,231 lines. | 18 active module-size budgets; 0 contract errors. Remaining module-size work is report-only budget debt, not unowned layout ambiguity. | `architecture-contracts-all.json`, `architecture/module_size_budget.toml`. |
| SLO/runbook coverage | Phase 0.1 baseline: 6 SLO files with 12 objectives and runbook links; 46 alerts with 3 direct `runbook_url` annotations; 8 dashboards. | Operability gates pass with 14 components, 8 public-stable components, 14 observability contracts, and 46 mapped component/central/Prometheus alerts. | `operability-release-gates.json`. |
| Stale override count | Phase 0.1 baseline: 88 missing mypy override modules, 0 stale concrete Ruff ignore paths, 19 import exceptions expiring within 60 days. | 1,045 overrides tracked; 824 mypy, 221 Ruff, 0 stale mypy, 0 stale Ruff, 0 missing metadata, 0 findings. | `dead-overrides.json`. |
| Generated-artifact freshness | Phase 0.1 baseline: 22 generated-artifact families; 6 automated, 12 manual-review, 4 ignored-by-policy. | Generated checks have 0 contract errors; compatibility release gates report 6 generated families and 4 promotion checks. | `architecture-contracts-all.json`, `compatibility-release-gates.json`. |
| CODEOWNERS coverage | Phase 0.1 baseline: CODEOWNERS and ruleset artifacts present; path families covered; GitHub-side enforcement not proven by repository files. | Strict current CODEOWNERS control-plane check passes with 0 blockers and 0 findings; supply-chain crosswalk records 4 controls, 4 release artifact contracts, and 3 release phase gates. | `control-plane-supply-chain.json`, `supply-chain-control-crosswalk.json`. |
| Directory-health coverage | Phase 0.1 baseline: 23 product-root top-level dirs, 6 workspace-root dirs, 20 high-volume subtrees, 11 asset/residue categories inventoried. | Directory health passes with 0 findings, 0 contract errors, 0 regressions, 100% high-volume subtree documentation coverage, 0 undocumented high-volume subtrees, and 0 undocumented frontend subtrees. | `directory-health.json`, `directory-health.md`. |

## Phase PR Ledger

No merged phase PR URLs exist for this program. This is not an exception: remote
git evidence confirms the repository exposes no pull-request refs while
`origin/main` is readable at commit `7acba2e4e1b3c113e0d428786ed6e80db93ebdce`.
The final closeout branch is `codex/wave7-final-closeout` and is not counted as
a merged phase PR at artifact time.

| Phase/wave | PR URL | Merge date | Owner | Evidence |
| --- | --- | --- | --- | --- |
| Wave 0 baseline and inventories | None; no merged phase PR found. | N/A | team-polisyos | `git ls-remote origin 'refs/pull/*/head'` returned 0 refs; `git log` shows direct main history. |
| Wave 1 foundation contracts | None; no merged phase PR found. | N/A | team-architecture | Same remote pull-ref evidence; phase state is represented by repository contracts and master ledger rows. |
| Wave 2 root, JS, lifecycle, docs movement | None; no merged phase PR found. | N/A | team-platform, team-frontend, team-docs | Same remote pull-ref evidence; phase state is represented by direct repository history. |
| Wave 3 facade and tooling lanes | None; no merged phase PR found. | N/A | team-fabric, team-ir, team-devx | Same remote pull-ref evidence; phase state is represented by direct repository history. |
| Wave 4 Foundry, Scientist, frontend, ops lanes | None; no merged phase PR found. | N/A | team-foundry, team-scientist, team-frontend, team-ops | Same remote pull-ref evidence; phase state is represented by direct repository history. |
| Wave 5 extension, mirror, module-size, release lanes | None; no merged phase PR found. | N/A | team-architecture, team-quality, team-ops | Same remote pull-ref evidence; phase state is represented by direct repository history. |
| Wave 6 integration gates and directory closure | None; no merged phase PR found. | N/A | team-polisyos | Same remote pull-ref evidence; final gate ledgers live under `architecture/` and `_build/.tmp/wave7-closeout/`. |
| Wave 7 final closeout | None merged at artifact time. | N/A | team-polisyos | Current branch: `codex/wave7-final-closeout`; remote main HEAD: `7acba2e4e1b3c113e0d428786ed6e80db93ebdce`. |

## Exceptions

### Blocker Exceptions

None.

### Accepted Ratchet Exceptions

| Exception | Owner | Rationale | Sunset |
| --- | --- | --- | --- |
| Fabric strict mirror exception | team-fabric | Fabric package reshaping increased the strict mirror denominator; loose mirror and property ratchets remain non-regressing. | 2026-06-15 |
| Foundry mirror exceptions | team-foundry, team-quality | Foundry source denominator reshaping and strict-path expansion need first-level mirror normalization while property coverage remains stable. | 2026-06-15 |
| IR mirror exception | team-quality | IR denominator growth remains explicitly owned while contract and property coverage stay active. | 2026-06-15 |
| Lex strict mirror exception | team-lex | Lex/Data Forge legal-batch topology needs strict mirror normalization while loose mirror and property ratchets remain covered. | 2026-06-15 |
| Runtime loose mirror exception | team-runtime | Runtime HTTP behavior is normalized through cross-module behavior tests while module mirror files catch up. | 2026-06-15 |
| Scientist strict mirror exception | team-scientist | Scientist first-level shim files remain while taxonomy and mirror contracts converge; this is a mirror-ratchet exception only, not a repo-quality gate blocker. | 2026-06-15 |

No structural ambiguity remains outside the accepted, time-boxed ratchet
exceptions above.

## Contributor Notes

- Treat `policy-engine/` as the product root; future scratch data belongs under
  product-local `_build/.tmp`, `.polisyos/`, or another declared temp root.
- Use `corepack pnpm ...` for JS workspace commands in environments where
  standalone `pnpm` is not installed.
- Use `uv run python -m tools.devx.workspace.doctor` or
  `uv run polisyos-tools workspace doctor` for root coherence; direct script
  invocation is not a supported closeout command.
- Root-level Python re-export files are allowed only when registered in
  `architecture/shims.toml` as explicit compatibility shims.

## Operator Notes

- Local `.polisyos` artifact residue is normalized under
  `.polisyos/cas/_cache/artifacts`; outer workspace `_cache` and `tmp` residue
  should not be reintroduced.
- Operability and compatibility release gates pass against the current release
  contracts; manual platform evidence is now recorded in
  `docs/archive/reports/platform-acceptance.manual.toml`.
- CODEOWNERS and ruleset coverage are verified by the strict current
  control-plane supply-chain check.

## Compatibility And Directory Notes

- Compatibility shims are time-boxed through `architecture/shims.toml`; earliest
  sunset is 2026-07-01.
- Scientist repo-quality gates now target canonical paths such as
  `orchestration/engine`, `orchestration/orchestrator`, `evidence/claims`,
  `evidence/provenance`, and `methods/research_dag`.
- Directory health is closed by local owner docs for all high-volume subtrees
  and the frontend shared subtree; new high-volume directories need README,
  AUTHORING, or index coverage before merge.
