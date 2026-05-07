---
title: Repository Root Topology Decision Brief
status: active
owner: team-polisyos
created: 2026-05-05
last_verified: 2026-05-05
stability: inventory
related:
  - ../archive/2026-05-07-repository-best-in-class-remediation-master-plan.md
  - ../../adr/0146-product-root-decision.md
  - ../../adr/0096-canonical-product-root-and-workspace-boundary.md
  - ../../adr/0111-workspace-root-boundary-sota-contract.md
  - ../../reference/repository-topology.md
---

# Repository Root Topology Decision Brief

Phase 0.2 inventory and Phase 1.1 decision brief for the best-in-class
repository remediation program.

This brief records current outer-root state, command assumptions, cleanup
candidates, the Renovate placement decision input, and the accepted Phase 1.1
product-root decision. It does not move files, rewrite CI, edit CODEOWNERS, or
clean residue.

## Phase 1.1 Decision

ADR-0146 selects **Option B: keep the outer Git root as an explicit repository
wrapper and GitHub control plane, with `policy-engine/` as the effective product
root for all product workflows**.

Option A, physically moving the Git root to `policy-engine/`, is deferred to a
dedicated repository migration window and is not selected for this remediation
wave. Option C remains rejected because it preserves root drift.

Decision details for Wave 2:

- `policy-engine/` is the selected product root for source, docs, tests, tools,
  ops, release inputs, package manifests, local runtime-state contracts, and
  documented product commands.
- The outer Git root is allow-listed only for repository control plane:
  `.github/**`, `.gitignore`, `.gitattributes`, optional outer editor metadata
  such as `.editorconfig`, and the `policy-engine/` product root.
- Renovate placement is `.github/renovate.json`; the outer-root
  `renovate.json` transition was retired on 2026-05-07.
- Wrong-root `_cache/ruff/**`, `tmp/phase3a_*`, and future wrong-root residue
  are cleanup candidates, not product state.
- The outer root README remains absent. A future root README, if needed for the
  GitHub landing page, must be a minimal gateway pointer to
  `policy-engine/README.md`.
- Rollback covers path/workflow/Renovate/ignore/docs/control-plane contract
  changes only. It must not bundle source package moves or JavaScript workspace
  relocation.

## Executive Inventory

- Tracked files outside `policy-engine/`: 19.
- Non-ignored untracked files outside `policy-engine/`: 0.
- Ignored files outside `policy-engine/`: 210.
- Current product root: `policy-engine/`.
- Current outer root role: GitHub control plane plus Git ignore/repo metadata,
  with local ignored residue.
- Current root README: absent. The product README at `policy-engine/README.md`
  explicitly tells contributors to `cd polisyos/policy-engine`.
- Current `.github/renovate.json`: canonical dependency automation config in
  the GitHub control plane.

Evidence commands used on 2026-05-05:

```bash
git ls-files | awk '$0 !~ /^policy-engine(\/|$)/ {print}'
git ls-files -o --exclude-standard | awk '$0 !~ /^policy-engine(\/|$)/ {print}'
git ls-files -o -i --exclude-standard | awk '$0 !~ /^policy-engine(\/|$)/ {print}'
git check-ignore -v .DS_Store .claude/settings.json .claude/launch.json \
  .cursor/plans _cache/ruff/CACHEDIR.TAG tmp/phase3a_cloud_runner_20260503.sh
```

## Tracked Outer-Root Paths

| Path | Classification | Current placement | Expected future placement |
| --- | --- | --- | --- |
| `.editorconfig` | editor/local metadata | Outer root, duplicated by `policy-engine/.editorconfig`. | Keep only if outer-root metadata needs editor policy; otherwise product style should live in `policy-engine/.editorconfig`. |
| `.gitattributes` | Git control plane | Outer root. | Keep at outer root because Git attributes apply repository-wide. |
| `.github/CODEOWNERS` | GitHub control plane | Outer root. | Keep at outer root while GitHub evaluates CODEOWNERS from repository root. |
| `.github/PULL_REQUEST_TEMPLATE.md` | GitHub control plane | Outer root. | Keep under `.github/`. |
| `.github/actions/setup-policy-engine-python/action.yml` | GitHub control plane | Outer root composite action; default `working-directory` is `policy-engine`. | Keep under `.github/actions/`; maintain product-root default. |
| `.github/actions/setup-runtime-dashboard/action.yml` | GitHub control plane | Outer root composite action; default `working-directory` is `policy-engine/apps/runtime-dashboard`. | Keep under `.github/actions/`; maintain product/dashboard-root default. |
| `.github/labels.yml` | GitHub control plane | Outer root label manifest. | Keep under `.github/`. |
| `.github/repository-rulesets/main.yml` | GitHub control plane | Outer root ruleset source; protects `.github/**` and selected `policy-engine/**` control docs. | Keep under `.github/` or another explicit control-plane registry chosen by Phase 1.1. |
| `.github/workflows/abi.yml` | GitHub control plane | Outer root workflow. Some jobs run from outer root for workflow governance; product jobs use `working-directory: policy-engine`. | Keep at outer root; keep product work rooted in `policy-engine`. |
| `.github/workflows/ci.yml` | GitHub control plane | Outer root workflow. Jobs use `policy-engine` or `policy-engine/apps/runtime-dashboard` working directories. | Keep at outer root; keep product work rooted in `policy-engine`. |
| `.github/workflows/core-runtime-long-soak.yml` | GitHub control plane | Outer root workflow; job default is `policy-engine`. | Keep at outer root; keep product work rooted in `policy-engine`. |
| `.github/workflows/core-runtime-release-gate.yml` | GitHub control plane | Outer root workflow; path filters are `policy-engine/**`; most jobs default to `policy-engine`. | Keep at outer root; keep path filters explicit until any root move. |
| `.github/workflows/docs-pages.yml` | GitHub control plane | Outer root Pages workflow; builds from `policy-engine`, uploads `policy-engine/_build/site`. | Keep at outer root; keep docs build rooted in `policy-engine`. |
| `.github/workflows/fabric-remediation.yml` | GitHub control plane | Outer root workflow; triggers and artifacts are prefixed with `policy-engine/`; jobs default to `policy-engine`. | Keep at outer root; keep product work rooted in `policy-engine`. |
| `.github/workflows/frontend-nightly.yml` | GitHub control plane | Outer root workflow. Workflow/action freshness and repository SBOM run from outer root; benchmark/frontend jobs use product/dashboard roots. | Keep at outer root; explicitly document any whole-repo audit jobs as control-plane exceptions. |
| `.github/workflows/frontend-quality.yml` | GitHub control plane | Outer root archived workflow with explanatory echo-only job. | Keep or delete in a later cleanup phase after archive policy decision. |
| `.github/workflows/release.yml` | GitHub control plane | Outer root workflow. Prepare/notes/SBOM/sign/publish jobs call `policy-engine/...`; build/canary jobs use `policy-engine`. | Keep at outer root; keep release logic under `policy-engine`. |
| `.gitignore` | Git control plane and ignore policy | Outer root ignore file; product-local ignore also exists at `policy-engine/.gitignore`. | Keep at outer root for outer residue and Git-wide ignores; product-specific ignores stay under `policy-engine/.gitignore`. |
| `.github/renovate.json` | dependency automation config with control-plane behavior | GitHub control-plane file; package rules point at existing `policy-engine/**` manifests and GitHub Actions. | Keep at `.github/renovate.json`; reintroducing root `renovate.json` requires a new ADR. |

## Ignored Outer-Root Residue

`git ls-files -o -i --exclude-standard` found 210 ignored files outside
`policy-engine/` and no non-ignored untracked files outside `policy-engine/`.

| Path | Files | Size | Ignore source | Classification | Cleanup candidate |
| --- | ---: | ---: | --- | --- | --- |
| `.DS_Store` | 1 | 6 KB | `.gitignore:73` | ignored local residue | Delete in cleanup; no retention value. |
| `.claude/launch.json`, `.claude/settings*.json` | 3 | 44 KB | `.gitignore:78`, `.gitignore:80` | editor/agent local metadata | Keep ignored or delete locally; do not promote to product root. |
| `.cursor/plans/` | 0 | 0 B | `.gitignore:81` | editor/local metadata | Delete empty directory or keep ignored; no product role. |
| `_cache/ruff/**` | 146 | 628 KB | nested `_cache/ruff/.gitignore` | wrong-root cache residue | Delete after confirming no running command owns it; future cache root should be under `policy-engine/_cache/` or another declared product-local cache. |
| `tmp/phase3a_*` and `tmp/.DS_Store` | 60 | 32 MB | `.gitignore:54` | wrong-root scratch/test residue | Preserve any evidence needed by active closeout reports, then delete in cleanup. Future scratch should use product-local `_build/.tmp`, `.polisyos/`, or a declared temp root. |

Notable residue details:

- `_cache/ruff/0.14.10` contains 144 hashed Ruff cache files plus
  `CACHEDIR.TAG` and a nested `.gitignore`.
- `tmp/phase3a_fullsuite_12core_20260504`,
  `tmp/phase3a_fullsuite_analysis_20260503`,
  `tmp/phase3a_fullsuite_clean_20260503`, and
  `tmp/phase3a_fullsuite_corrected_20260503` contain logs, JUnit XML,
  summaries, runner metadata, and timing files.
- Root `.gitignore` ignores `/tmp/` but does not explicitly ignore `/_cache/`;
  `_cache/ruff` is ignored by its own nested ignore file. A future cleanup
  phase should make the wrong-root `_cache` policy explicit before deleting it.

## Command And Working-Directory Assumptions

| Surface | Current assumption | Root decision implication |
| --- | --- | --- |
| `policy-engine/README.md` | Quickstart clones the outer repo and immediately `cd`s into `polisyos/policy-engine`; it calls `python3 -m tools.cli workspace bootstrap`, `doctor`, and `verify` from product root. | Product contributor commands already assume `policy-engine` as the working root. |
| Outer root README | No tracked `README.md` exists at the outer root, although CODEOWNERS has a placeholder owner rule for `/README.md`. | Phase 1.1 must decide whether to keep the outer root README absent or add a minimal gateway README. |
| `policy-engine/CONTRIBUTING.md` | Shows `polisyos-tools workspace bootstrap`, `doctor`, `verify`, and `ci-parity`; manual frontend setup uses `cd apps/runtime-dashboard` relative to product root. | Contributor docs are product-root oriented; a future outer README must not duplicate product instructions as if outer root were the product root. |
| `tools.lib.imports.repo_root_from` | Infers product root using `pyproject.toml`, `tools`, and `src` sentinels. | Product tools are intentionally anchored to `policy-engine`, not the outer Git root. |
| `tools/devx/workspace/_common.py` | Defines `PRODUCT_ROOT` from `repo_root_from(__file__)`, `GIT_ROOT` from `git rev-parse`, and frontend roots under `PRODUCT_ROOT/frontend`. | Tooling can distinguish product root from outer Git root; future root gates should reuse this split instead of hardcoding. |
| `workspace bootstrap`, `doctor`, `verify` | Run `uv`, pytest, generated-contract checks, and frontend npm commands with `cwd=PRODUCT_ROOT` or `cwd=FRONTEND_ROOT`. | No command move is needed for Phase 0.2; Phase 1.1 can codify this as the product command contract. |
| `workspace acceptance-audit` | Uses `PRODUCT_ROOT` for product evidence and `WORKSPACE_ROOT = PRODUCT_ROOT.parent` for `.github/CODEOWNERS`. | Acceptance audit already models the split root and should be updated only after the root decision. |
| `workspace repository-sota-closeout` | Uses `REPO_ROOT = repo_root_from(__file__)` for product contracts and `WORKSPACE_ROOT = REPO_ROOT.parent` for GitHub control-plane checks. | Existing closeout gates know about the outer root but currently encode accepted SOTA assumptions that Phase 1.1 will revisit. |
| `check_docs_gate.normalize_changed_paths` | Strips the `policy-engine/` prefix from Git-tracked paths because the product root lives inside a larger checkout. | Path normalization must remain until any physical root move completes. |
| `check_phase7_ratchet.py` | `--repo-root` means outer workspace root containing `policy-engine/`; package detection uses `policy-engine/src/polisyos/`. | CI governance jobs that inspect changed paths still assume outer-root Git paths. |
| `check_workflow_policy.py` | Runs from the outer root and scans `.github/workflows` plus `.github/actions`; product legacy path checks mention `policy-engine/...`. | Workflow policy is control-plane automation and stays outer-root aware. |
| Runtime curated data lookup | `src/polisyos/runtime/http/services/control.py` tries both `data/curated` and `policy-engine/data/curated`. | This is a compatibility smell for mixed cwd habits; Phase 1.1 or later cleanup should choose one product-root contract. |
| Cloud deployment scripts | `tools/ops_runners/cloud/deploy/*.sh` and pipeline runners default remote product roots to `/opt/polisyos/policy-engine` or `POLISYOS_REPO_ROOT`. | Deployment automation assumes the product directory name is `policy-engine`; any physical move must include explicit remote path migration. |
| Hardcoded local evidence paths | Some generated/archive docs and `tools/ops_runners/data/build_expert_review_bundle.py` reference `/Users/deniskopylov/polisyos/policy-engine`. | These are cleanup candidates for later portability work, not root topology moves. |

## CI Working-Directory Inventory

| Workflow or action | Outer-root assumption | Product-root assumption |
| --- | --- | --- |
| `.github/actions/setup-policy-engine-python/action.yml` | Composite action must live under outer `.github/actions`. | Default `working-directory: policy-engine`; runs workspace bootstrap or `uv sync` there. |
| `.github/actions/setup-runtime-dashboard/action.yml` | Composite action must live under outer `.github/actions`; Node cache path is `policy-engine/apps/runtime-dashboard/package-lock.json`. | Default `working-directory: policy-engine/apps/runtime-dashboard`. |
| `.github/workflows/abi.yml` | Workflow governance, actionlint, dependency review, and Phase 7 ratchet inspect outer-root paths. | Python quality, docs quality, and ABI jobs default to `policy-engine`; ABI path filters use `policy-engine/...`. |
| `.github/workflows/ci.yml` | Workflow file lives at outer root. | Runtime, frontend, performance, integration, and economics jobs use `policy-engine` or dashboard root working directories. |
| `.github/workflows/core-runtime-long-soak.yml` | Workflow file lives at outer root. | Job default is `policy-engine`; uploaded reports are under `policy-engine/_build/.tmp`. |
| `.github/workflows/core-runtime-release-gate.yml` | Trigger path filters are outer Git paths with `policy-engine/` prefixes. | Most jobs default to `policy-engine`; evidence artifacts are uploaded from `policy-engine/**`. |
| `.github/workflows/docs-pages.yml` | GitHub Pages workflow must live at outer root. | Build runs from `policy-engine`; site artifact is `policy-engine/_build/site`. |
| `.github/workflows/fabric-remediation.yml` | Trigger path filters are outer Git paths with `policy-engine/` prefixes. | Jobs default to `policy-engine`; evidence artifacts are under `policy-engine/_build/.tmp`. |
| `.github/workflows/frontend-nightly.yml` | Workflow audit, action freshness, repository SBOM (`syft dir:.`), OpenSSF Scorecard, and upload paths are outer-root control-plane jobs. | Benchmark, runtime fixture, dashboard, Lighthouse, and npm audit jobs use `policy-engine` or dashboard root. |
| `.github/workflows/frontend-quality.yml` | Archived control-plane file only. | No active product commands. |
| `.github/workflows/release.yml` | Prepare, release notes, SBOM/vulnerability evaluation, signing, attestation, and publish jobs call `policy-engine/...` from outer root. | Build and canary jobs default to `policy-engine`; dashboard build uses dashboard root. |

## Renovate Placement

Current state:

- `.github/renovate.json` is tracked in the GitHub control plane and owned by
  `.github/CODEOWNERS`.
- Its package rules target `policy-engine/pyproject.toml`,
  `policy-engine/uv.lock`, and
  `policy-engine/apps/runtime-dashboard/package.json`,
  `policy-engine/apps/runtime-reference-shell/package.json`,
  `policy-engine/packages/cli/package.json`, and
  `policy-engine/packages/runtime-api-client/package.json`.
- It also manages GitHub Actions, which are correctly outer-root control-plane
  files.

Decision input:

- Renovate's repository config default is root `renovate.json`, but Renovate
  also supports `.github/renovate.json` as an alternative configuration
  location. See the official Renovate onboarding docs:
  <https://docs.renovatebot.com/getting-started/installing-onboarding/#configuration-location>.
- Canonical placement for the current split-root model is
  `.github/renovate.json`. That keeps dependency automation in the GitHub
  control plane and removes loose outer-root product-looking files.
- Fallback placement is retired. Reintroducing root `renovate.json` requires a
  new ADR and a fail-closed control-plane contract update.

## Cleanup Candidates For Later Phases

| Candidate | Reason | Later-phase action |
| --- | --- | --- |
| `_cache/ruff/**` | Wrong-root cache residue and currently ignored only by nested ignore file. | Delete after retention check; add explicit wrong-root cache policy or gate. |
| `tmp/phase3a_*` | Wrong-root scratch/test evidence residue. | Promote any required evidence to `policy-engine/docs/archive/reports/**`, then delete. |
| `.DS_Store` and `tmp/.DS_Store` | Editor residue. | Delete in cleanup; no retention. |
| `.cursor/plans/` | Empty ignored editor directory. | Delete or leave ignored locally. |
| `.claude/*.json` | Local agent/editor state. | Keep ignored or delete locally; never commit. |
| Root `.editorconfig` | Duplicate product-local editor policy. | Decide whether outer-root metadata still needs it after Phase 1.1. |
| Root `renovate.json` | Loose outer-root config creates a false product-root signal. | Retired on 2026-05-07; gate fails if it reappears. |
| Hardcoded product-root absolute paths | Portability and local-machine coupling. | Replace with product-root-relative defaults in a later tools/docs cleanup phase. |

## Wave 1 Decision Inputs

Phase 1.1 should decide:

1. Whether the target topology is a physical root move or a formal split-root
   wrapper with `policy-engine/` as effective product root.
2. Whether the outer root README remains absent or becomes a minimal gateway.
3. Whether root `.editorconfig` is retained for control-plane files.
4. Whether any future Renovate fallback is justified by a new ADR; default is
   no root `renovate.json`.
5. Whether wrong-root `_cache/` should become an explicitly denied outer-root
   path before cleanup.
6. Which current CI jobs are legitimate outer-root control-plane audits:
   workflow policy, action freshness, dependency review, repository SBOM,
   Scorecard, release signing/attestation, and publish.
7. How remote deployment roots such as `/opt/polisyos/policy-engine` are
   migrated if a physical root move is later selected.

## Acceptance Check

- Every tracked file outside `policy-engine/` is inventoried above.
- Ignored outer-root residue is inventoried by path class, count, size, ignore
  source, and cleanup candidate.
- Product command assumptions, CI working directories, workspace doctor
  assumptions, root README state, and automation paths are inventoried.
- Current placement for `.github/renovate.json` and the retired root fallback
  are recorded.
- No physical Git-root move is attempted by this decision brief.
