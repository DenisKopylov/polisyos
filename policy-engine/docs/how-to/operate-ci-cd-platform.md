# Operate the CI/CD Platform

> Canonical workflow inventory, required checks, release policy, and supply-chain governance for Phase 3.

## 1. Workflow Inventory

Package-level GitHub Actions workflows are **not** part of the active PolicyOS platform today.
The maintained workflow surface is root-only under `.github/workflows/`.

| Workflow file | Status | Tier | Trigger | Purpose |
|---|---|---|---|---|
| `.github/workflows/abi.yml` | canonical | Fast PR | pull request, push to `main` | workflow governance, dependency review, python/docs quality, ABI drift |
| `.github/workflows/ci.yml` | canonical | Standard PR | pull request, push to `main` | runtime HTTP, frontend quality, contract drift, smoke, integration |
| `.github/workflows/frontend-nightly.yml` | canonical | Nightly | schedule, manual | benchmark contours, bundle/lighthouse, dependency and action audits, Scorecard |
| `.github/workflows/release.yml` | canonical | Release | tags `v*`, manual | reproducible artifacts, release notes, signatures, SBOM/vuln gate, canary, attestations |
| `.github/workflows/docs-pages.yml` | canonical | Publish | `PR Fast` success on `main`, manual | strict MkDocs build and GitHub Pages deployment |
| `.github/workflows/frontend-quality.yml` | archival | none | manual only | legacy duplicate surface kept only as an explicit archive marker |

Operational rule:

- If a process matters for branch protection, releases, nightly platform assurance, or docs publish, it must live in one of the canonical workflows above.
- `frontend-quality.yml` must not be reactivated for PR or push triggers. Any new frontend gate belongs in `ci.yml` or `frontend-nightly.yml`.

## 2. Required Check Matrix

| Tier | Budget target | Workflow | Required gate | Scope |
|---|---:|---|---|---|
| Fast PR | `< 10 min` | `.github/workflows/abi.yml` | `Fast PR / Gate` | actionlint, workflow policy, dependency review, import/docs/schema drift, fast unit checks, ABI drift |
| Standard PR | `< 25 min` | `.github/workflows/ci.yml` | `Standard PR / Gate` | runtime HTTP, frontend quality/a11y, component smoke, contract drift, e2e smoke, integration |
| Nightly | `30-90 min` | `.github/workflows/frontend-nightly.yml` | none by branch protection | benchmark contours, platform cost/perf visibility, scheduled audits, Scorecard |
| Release | variable | `.github/workflows/release.yml` | environment gates + workflow success | release packaging, SBOM/vuln gate, canary, provenance attestations, publish |

Branch protection / ruleset mapping:

1. Require `Fast PR / Gate`.
2. Require `Standard PR / Gate`.
3. Do **not** require Nightly or Release checks on normal pull requests.
4. Keep `Docs Pages / Deploy` out of the required-check set; docs publish is a post-merge production path, not a PR admission gate.

If you are applying or re-checking the live repository settings manually, use
the UI checklist in [Apply Phase 1 Governance in GitHub UI](apply-github-governance.md).

This split is intentional: fast and slow lanes are independent workflows, so slower platform checks cannot accidentally block or serialize the fast confidence path.

## 3. Repository Security Posture

### Token, actions, and workflow policy

- Repository default `GITHUB_TOKEN` posture should be configured as read-only in GitHub settings.
- Workflows keep top-level permissions read-only and escalate writes only at the job that truly needs them.
- Third-party actions must be pinned to full commit SHAs.
- `actionlint` plus `policy-engine/tools/ci/check_workflow_policy.py` run in Fast PR and Nightly to prevent YAML drift, dead paths, unsafe `pull_request_target`, unpinned actions, and over-broad workflow permissions.
- Dependency review is part of the Fast PR tier and therefore part of the branch-protected PR policy.

### Secret scanning and untrusted PR handling

- GitHub secret scanning and push protection should be enabled in repository security settings.
- Untrusted PR metadata must not be interpolated directly inside `run:` blocks.
- PR-triggered workflows use `pull_request`, not `pull_request_target`, unless a separately reviewed exception is approved.

### Identity, runners, and provenance

- Cloud deployment/auth steps should use OIDC or another short-lived credential mechanism where the target supports it.
- GitHub-hosted runners are the default trust model.
- Any future self-hosted runner requires an owner, an isolation boundary, secret minimization, and an ephemeral / just-in-time story before it can be added to policy.
- Release artifacts are signed with Sigstore keyless signatures and release evidence is attested with GitHub artifact attestations so downstream automation can verify both signatures and provenance.

### Vulnerability exception policy

- Release-time vulnerability exceptions live in `release/cve-exceptions.toml`.
- Every exception must have a concrete rationale and `expires_on`.
- Expired exceptions fail the release gate until renewed or removed.
- Fresh SBOMs are generated at release time and during scheduled audits. Transitive dependency coverage is expected wherever the underlying scanner can discover it from the source tree or produced artifacts.

## 4. Release Policy

### Entry and versioning

- Releases are cut from tags in `vX.Y.Z` form, or from a manual dispatch carrying the same tag.
- `pyproject.toml` and `frontend/runtime-dashboard/package.json` must match that version exactly.
- Published release versions are immutable. If a release is wrong, ship `vX.Y.(Z+1)` rather than mutating the existing release.

### Release notes

- PRs add TOML fragments under `release-fragments/unreleased/`.
- Release prep freezes those entries into `release-fragments/releases/<version>/`.
- The release workflow renders notes only from that immutable versioned snapshot.
- The published notes follow Keep a Changelog sectioning and must include:
  - compatibility notes;
  - migration notes;
  - schema/runtime/API changes;
  - known limitations.

### Progressive delivery

- `release-canary` is the first runtime-bearing checkpoint.
- It launches a live runtime API from the installed release wheel in a fresh
  environment, verifies health/readiness endpoints, checks that the shipped
  dashboard bundle extracts cleanly, then runs runtime smoke and benchmark
  smoke against the same release candidate.
- Canary abort thresholds are:
  - SBOM / vulnerability policy violations;
  - failed live runtime canary probes;
  - failed runtime smoke checks;
  - failed benchmark smoke checks.
- Release artifacts are signed with Sigstore keyless signatures before publish.
- Promotion only happens after the `release-production` environment job is allowed to proceed.

### Evidence and retention

| Artifact | Retention |
|---|---:|
| PR debug evidence | 14 days |
| Nightly audit / benchmark evidence | 30 days |
| Release artifacts, notes, signatures, SBOM, vuln report, asset-size policy, canary evidence | 180 days in Actions artifacts, plus permanent GitHub Release assets where published |

## 5. Benchmark Platform

The benchmark platform is intentionally broader than `pytest-benchmark`.

| Taxonomy slice | Current path | Owner | Current ratchet |
|---|---|---|---|
| Unit microbench | `benchmarks/run_all_benchmarks.sh` circuits and `benchmarks/foundry/` tests | Foundry maintainers | nightly benchmark contour summaries must stay green |
| Workflow throughput | contour summaries from `tools/validation/run_benchmark_contours.sh` | Platform | release / nightly summaries must keep `passes_all=true` |
| Frontend bundle | `npm run check:bundle` | Runtime dashboard owners | bundle budgets must pass |
| Frontend lighthouse | `npm run lighthouse:ci` | Runtime dashboard owners | Lighthouse CI must pass configured budgets |
| Selected infra-cost checks | `release/artifact-size-policy.toml` plus release asset summaries | Platform | release artifacts must stay within repo-tracked size thresholds before widening budgets |

Policy for baselines:

1. New baselines must come with an owner and a reason they matter for runtime or cost.
2. Raising a threshold is a conscious ratchet change and should be called out in the PR summary and release fragment.
3. Retiring a baseline needs an explicit justification in docs or an ADR if it changes release posture.

## 6. SSDF / SLSA / Scorecard Crosswalk

| Control | Enforced in repo policy | Enforced by process / platform |
|---|---|---|
| Pinned third-party actions | yes, via workflow policy scanner + review | — |
| Read-only default token posture | partially, via workflow files | yes, repository settings must enforce default read-only |
| Dependency review on PRs | yes | — |
| Release-time SBOM generation | yes | — |
| Release-time vulnerability gating with expiring exceptions | yes | exception approvals still need human review |
| Signed release artifacts and provenance / attestations | yes | downstream verification is consumer process |
| Secret scanning / push protection | no | yes, GitHub security settings |
| Protected release checkpoints | partially, via environment jobs | yes, environment reviewer rules live in GitHub settings |
| OIDC for cloud deploy auth | no direct enforcement today | yes, required when future deployment jobs are added |
| OpenSSF Scorecard external lens | yes, scheduled workflow | triage of findings is an engineering process |
| Scheduled action freshness audit | yes, scheduled workflow | upgrade decisions remain an engineering process |

## 7. Legacy vs Canonical Rule of Thumb

If you need to answer “which workflow matters now?” the answer should come from the canonical table in this page, not from old filenames, tribal memory, or package-local experiments.
