# Operate the CI/CD Platform

Owner: `@platform-owners`
Source of truth: `.github/workflows/`, `policy-engine/ops/ci/templates/workflows/`, and the referenced local workspace tools. Live GitHub settings are managed separately.
Repository source reviewed: `47e1e59b569a5b922611f71a7f53fb6320abea4c` on 2026-10-14; workflow-file and trigger inspection only. GitHub settings and workflow run state were not queried.

This guide documents the repository-declared CI/CD surface at that source
snapshot. It describes workflows, commands, and evidence paths found in source;
it does not establish that a workflow is enabled in GitHub or has a recent
successful run.

## Inputs

- a repo change that touches workflows, docs-sensitive surfaces, release gates,
  or platform evidence;

- the current checkout of `.github/workflows/**`, docs, and workspace tooling;
- intent to validate repo-tracked workflow definitions or reconcile live
  platform settings.

## Output

- a source-backed understanding of which workflow definitions and local
  commands are canonical at the reviewed pin;

- a minimal operating path for local parity, GitHub governance reconciliation,
  and release/security evidence.

## Commands

```bash
cd policy-engine
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
uv run polisyos-tools workspace ci-parity --skip-browser
uv run polisyos-tools docs --output docs/reference/tools.md
```

Run from `policy-engine/` with the contributor baseline from
`CONTRIBUTING.md` (Python 3.14.x, Node 22.x, and uv 0.9.21). The docs profile
provides `lint + docs`; use the documented workspace bootstrap and doctor before
the local docs or parity commands. The docs gate also requires its selected
base ref to resolve locally. The commands and workflow definitions below were
inspected at the pinned source snapshot; they were not run here. No GitHub
settings, workflow run, Pages deployment, or live URL was queried.

## 1. Workflow Inventory

The repo-tracked workflow definitions are under `.github/workflows/`; reusable product templates live under
`policy-engine/ops/ci/templates/workflows/`.

The repo-tracked workflows define jobs named `Fast PR / Gate` and
`Standard PR / Gate`. Whether the live GitHub default-branch ruleset requires
those checks is a manual platform setting and was not verified here; keep the
job names stable when changing the workflows or local command wrappers.

| Workflow file                                           | Source state    | Tier                     | Trigger                                     | Purpose                                                                                |
| ------------------------------------------------------- | --------------- | ------------------------ | ------------------------------------------- | -------------------------------------------------------------------------------------- |
| `.github/workflows/abi.yml`                             | repo-defined    | PR gate                  | every pull request; push to `main`          | Workflow governance, dependency review, ABI/schema drift, docs quality, and fast tests |
| `.github/workflows/ci.yml`                              | repo-defined    | PR gate                  | every pull request; push to `main`          | Runtime HTTP, frontend contracts/smoke, integration, and test-economics surfaces       |
| `.github/workflows/core-runtime-long-soak.yml`          | repo-defined    | scheduled/manual soak    | schedule; manual dispatch                   | Core-runtime long-soak evidence                                                        |
| `.github/workflows/core-runtime-release-gate.yml`       | repo-defined    | release-grade gate       | selected PR/push paths; manual dispatch     | Core-runtime contracts, docs, mutation subset, benchmarks, and release-review evidence |
| `.github/workflows/docs-pages.yml`                      | repo-defined    | docs publication         | manual; successful `PR Fast` push on `main` | Strict docs build and conditional Pages publication                                    |
| `.github/workflows/fabric-remediation.yml`              | repo-defined    | subsystem remediation    | Fabric paths; manual dispatch               | Fabric connector/data-plane/schema-governance remediation gates                        |
| `.github/workflows/frontend-nightly.yml`                | repo-defined    | nightly frontend         | schedule; manual dispatch                   | Broader frontend quality and nightly coverage                                          |
| `.github/workflows/frontend-quality.yml`                | archival notice | archived workflow record | manual                                      | Documents the archived frontend-quality workflow state                                 |
| `.github/workflows/release.yml`                         | repo-defined    | release orchestration    | `v*` tag; manual dispatch with tag          | Release packaging, dashboard artifact, SBOM, and canary evidence                       |
| `ops/ci/templates/workflows/{arch,perf,replay,...}.yml` | template        | reusable product specs   | not GitHub-executed from this path          | Retained product workflow specs and generated-artifact references                      |

Historical workflow names that are absent from the repository-root workflow
inventory should not be used as current automation anchors. Template workflows
are factual repo artifacts, but they are not active GitHub Actions until they
are intentionally promoted to the root `.github/workflows/` surface.

“Repo-defined” means that source declares a workflow and its triggers at the
reviewed pin. It does not prove GitHub registration, enablement, current branch
protection, or recent execution. The `frontend-quality.yml` entry is retained
as an archival notice, not an active quality workflow.

Operational rule:

- If a CI/CD control matters, it should either exist in the repo-tracked root
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

## 4. Docs Publication and Run Evidence

The checked-in Pages flow is declared in `.github/workflows/docs-pages.yml`:
`PR Fast` runs the docs gate for pull requests and pushes to `main`; the Pages
workflow listens for its completion, but builds and deploys on that event only
when it was a successful `push` run on `main`. That path checks out the
completed run's head SHA. Manual `workflow_dispatch` bypasses the main-push
condition and checks out `github.sha` for the dispatched run; both paths use
`uv run python -m mkdocs build --strict` and pass the Pages artifact from the
build job to deploy. The source does not configure a PR preview or an
in-workflow approval hold. The `github-pages` environment may have external
protection rules, but those live settings were not queried.

On an actual run, use the `github-pages` environment and the deployment step's
`page_url` output to identify the published address. The workflow source does
not establish that Pages is enabled, that a deployment succeeded, or which URL
is currently live. Check the current repository Pages settings and run output
before deciding whether an older URL is still valid or should be changed. The
Pages upload is a build-to-deploy handoff; this workflow does not set a
long-lived diagnostic-artifact retention period for it.

For a verification receipt, record the exact repository commit SHA, workflow
run URL and event/ref (for Actions), job/step, command, outcome, and the
artifact name when an upload step exists. For a local run, record the supported
environment versions, exact command, exit status, and output path; hash a
retained file with `shasum -a 256 <path>`. Link the Actions run and its
downloadable artifact while they are available rather than linking a runner's
`_build/.tmp` path. Local ignored logs are not reviewer-accessible receipts.

Selected examples in the checked-in workflows: `workflow-policy-summary` and
`abi-schema-report` in `.github/workflows/abi.yml` declare 14-day retention.
`.github/workflows/ci.yml` declares 14 days for its uploaded JUnit/economics
reports; its Playwright accessibility and smoke artifacts are uploaded only on
failure and also declare 14 days. The Scientist Phase 0/1 evidence and
release-review bundle in `.github/workflows/core-runtime-release-gate.yml`
declare 30 days. This is not a complete inventory of workflow artifacts or
live platform retention settings. These are workflow settings, not evidence
that an artifact exists for a particular run; confirm the upload step succeeded
and download needed evidence before expiry.
The Pages artifact is a separate deployment handoff, not one of these retained
diagnostic uploads.

If a check failed, link the exact failed run and job, inspect its log and any
artifact the workflow actually uploaded, and route the underlying change to its
source owner. If it was not run, state `UNRUN` with the missing prerequisite;
if an upload is absent or expired, state that the evidence is unavailable.
Neither case is a pass. Workflow and platform questions belong with the
`@platform-owners` named above; generated-family questions go to the family
`owner` / `approval_owner` in `architecture/generated_artifacts.toml`. Do not
turn an ignored local report into a claim about a prior CI run.

## 5. Release, Build, and Security Surfaces

The repo-declared release/build/security surfaces are:

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

- dependency review and the Scheduled action freshness audit, backed by
  `frontend-nightly.yml`, Renovate, and `tools/ci/check_action_freshness.py`,
  for dependency freshness governance.

Release/build evidence is currently split across root release workflows,
template workflow specs, and the closeout commands/docs rather than one
monolithic release workflow.

## 6. Docs and Benchmark Surfaces

- `.github/workflows/abi.yml` declares the path-aware docs quality gate for
  pull requests and pushes to `main`; `.github/workflows/docs-pages.yml`
  declares the conditional Pages publication path described above.

- `ops/ci/templates/workflows/perf.yml` is the reusable performance-evidence
  template: benchmark regression comparison, overhead checks, and Scientist
  reliability artifacts.

- Local benchmark truth still comes from `polisyos-tools benchmarks ...` and the
  published benchmark/how-to/reference docs, not from workflow-template names
  alone.

## 7. Workflow Security Posture

- GitHub-hosted runners are the default trust model for repo-tracked workflows;
  use OIDC for cloud identity handoff instead of long-lived deploy credentials.

- Prefer read-only default `GITHUB_TOKEN` posture in GitHub settings.
- Keep top-level workflow permissions minimal and escalate writes only where a
  job truly needs them.

- Pin third-party actions to specific major versions or SHAs as the owning
  workflow policy requires.

- Keep PR-triggered workflows on `pull_request` unless a separately reviewed
  exception is needed.

- Enable secret scanning and push protection in GitHub settings; those are live
  platform controls, not repo-tracked files.

## 8. Rule of Thumb

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
