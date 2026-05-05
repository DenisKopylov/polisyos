# Operate the CI/CD Platform

This guide documents the current repo-tracked CI/CD surface. It intentionally
describes only workflows, commands, and evidence paths that exist in the
repository today.

## Inputs

- a repo change that touches workflows, docs-sensitive surfaces, release gates,
  or platform evidence;

- the current checkout of `.github/workflows/**`, docs, and workspace tooling;
- intent to validate or operate the active CI/CD platform rather than historical
  workflows.

## Output

- a verified understanding of which workflows and local commands are canonical
  today;

- a minimal operating path for local parity, GitHub governance reconciliation,
  and release/security evidence.

## Commands

```bash
cd policy-engine
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
uv run polisyos-tools workspace ci-parity --skip-browser
uv run polisyos-tools docs --output docs/reference/tools.md
```

## 1. Workflow Inventory

The maintained GitHub-executed automation surface is the repository-root
inventory under `.github/workflows/`; reusable product templates live under
`policy-engine/ops/ci/templates/workflows/`.

| Workflow file                                          | Status | Tier                   | Trigger                              | Purpose                                                                                                      |
| ------------------------------------------------------ | ------ | ---------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `.github/workflows/abi.yml`                            | active | PR gate                | pull request on ABI-visible paths    | ABI snapshot generation, semantic diff, docs quality, public-surface docstring quality, and fast tests       |
| `.github/workflows/ci.yml`                             | active | PR gate                | pull request and push                | Runtime HTTP, frontend contracts/smoke, integration, and test-economics surfaces                             |
| `.github/workflows/core-runtime-long-soak.yml`         | active | scheduled/manual soak  | schedule, manual                     | Core-runtime long-soak evidence                                                                              |
| `.github/workflows/core-runtime-release-gate.yml`      | active | release-grade gate     | runtime/docs paths, push, manual     | Core-runtime contracts, docs, mutation subset, benchmarks, and release-review evidence                       |
| `.github/workflows/docs-pages.yml`                     | active | docs publication       | manual and successful docs gate      | Strict docs build before Pages publication                                                                   |
| `.github/workflows/fabric-remediation.yml`             | active | subsystem remediation  | Fabric remediation paths, manual     | Fabric connector/data-plane/schema-governance remediation gates                                              |
| `.github/workflows/frontend-nightly.yml`               | active | nightly frontend       | schedule, manual, frontend paths     | Broader frontend quality and nightly coverage                                                                |
| `.github/workflows/frontend-quality.yml`               | active | archival notice        | manual                               | Documents the archived frontend-quality workflow state                                                       |
| `.github/workflows/release.yml`                        | active | release orchestration  | release tags, manual                 | Release packaging, dashboard artifact, SBOM, and canary evidence                                             |
| `ops/ci/templates/workflows/{arch,perf,replay,...}.yml` | template | reusable product specs | not GitHub-executed from this path   | Retained product workflow specs and generated-artifact references                                            |

Historical workflow names that are absent from the repository-root workflow
inventory should not be used as current automation anchors. Template workflows
are factual repo artifacts, but they are not active GitHub Actions until they
are intentionally promoted to the root `.github/workflows/` surface.

Operational rule:

- If a CI/CD control matters, it should either exist in the active root
  workflow inventory above, be documented as a reusable template, or be
  documented as a canonical local command.

- If a workflow file is absent, docs should not describe it as current policy.

## 2. Local Parity Before a PR

Before opening a PR that changes docs-sensitive surfaces, start with the D6
docs drift gate:

```bash
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
```

This command is path-aware: it dispatches strict MkDocs, docs accuracy,
semantic docstrings, public-surface drift, schema reference drift, Runtime API
contract drift, and the required impact-note/runbook evidence rules only for
the surfaces touched by your change.

If your worktree already contains unrelated local changes, repeat
`--changed-path <repo-relative-path>` to scope the gate to the change set you
are validating.

If the PR is broader than docs drift alone, finish with the CI-like umbrella
path:

```bash
uv run polisyos-tools workspace ci-parity --skip-browser
```

For tool-registry or CLI changes, refresh the generated tools reference after
the gate tells you it drifted:

```bash
uv run polisyos-tools docs --output docs/reference/tools.md
```

The backend parity lane includes docs accuracy, strict MkDocs build, semantic
docstring quality, schema drift, runtime contract drift, and the fast platform
gate unless explicit skip flags are used.

## 3. Manual GitHub Settings

Required checks, branch protection, approval counts, and merge queue settings
are currently operational/manual truth in GitHub rather than repo-tracked
files.

Use [Apply GitHub Governance Manually](apply-github-governance.md) when you
need to reconcile the live repository settings with the repo-tracked workflow
inventory and docs.

## 4. Release, Build, and Security Surfaces

The current repo-tracked release/build/security surfaces are:

- `.github/workflows/release.yml` for release packaging, dashboard artifact,
  SBOM, and canary evidence;

- `ops/ci/templates/workflows/build-and-push.yml` for the reusable manual image
  build/SBOM/signing template;

- `ops/ci/templates/workflows/signatures.yml` for the reusable
  artifact-signing regression template;
- `docs/reference/operations/core-runtime-closeout.md` plus
  `polisyos-tools workspace core-runtime-closeout` /
  `core-runtime-long-soak` for core-runtime closeout evidence;

- `docs/reference/operations/platform-acceptance-audit.md` plus
  `polisyos-tools workspace acceptance-audit` for cross-surface platform
  acceptance.

Release/build evidence is currently split across root release workflows,
template workflow specs, and the closeout commands/docs rather than one
monolithic release workflow.

## 5. Docs and Benchmark Surfaces

- `.github/workflows/abi.yml` runs the current docs quality gate for PRs and
  pushes; `.github/workflows/docs-pages.yml` handles docs publication.

- `ops/ci/templates/workflows/perf.yml` is the reusable performance-evidence
  template: benchmark regression comparison, overhead checks, and Scientist
  reliability artifacts.

- Local benchmark truth still comes from `polisyos-tools benchmarks ...` and the
  published benchmark/how-to/reference docs, not from workflow-template names
  alone.

## 6. Workflow Security Posture

- Prefer read-only default `GITHUB_TOKEN` posture in GitHub settings.
- Keep top-level workflow permissions minimal and escalate writes only where a
  job truly needs them.

- Pin third-party actions to specific major versions or SHAs as the owning
  workflow policy requires.

- Keep PR-triggered workflows on `pull_request` unless a separately reviewed
  exception is needed.

- Enable secret scanning and push protection in GitHub settings; those are live
  platform controls, not repo-tracked files.

## 7. Rule of Thumb

If you need to answer “which workflow matters now?”, start from the table in
this page and the files that actually exist under `.github/workflows/`, not
from old filenames, historical plans, or tribal memory.

## Rollback / Handoff

- if a platform change introduces governance or docs drift, restore the previous
  repo-tracked workflow/doc state before retrying the CI/CD change;

- if the live GitHub settings diverge from the repo inventory, hand off through
  [Apply GitHub Governance Manually](apply-github-governance.md) instead of
  documenting an unverified setting as current truth;

- if release evidence is incomplete, stop at the evidence gap rather than
  widening the rollout on assumption alone.

## Troubleshooting

- If a workflow is mentioned in docs but absent from `.github/workflows/`,
  treat the doc as stale until the inventory is updated.

- If a local parity command feels too broad, start with the path-aware docs gate
  and add only the subsystem checks the diff actually triggered.

- If repo-tracked policy and GitHub UI disagree, the docs should describe the
  repo truth and explicitly mark the live setting as manual until reconciled.
