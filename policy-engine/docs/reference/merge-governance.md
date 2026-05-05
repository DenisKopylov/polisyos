# Merge Governance

Owner: `@platform-owners`  
Backup owner: `@tools-owners`  
Source of truth: `docs/reference/{quality-gates.md,ownership.md}`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/labels.yml`, and the current root workflow inventory under `.github/workflows/*.yml`

This page describes the repo-tracked part of the merge contract for `main`.

Important boundary: this repository does not currently version a
`.github/repository-rulesets/main.yml` file or a `.github/CODEOWNERS` file
under `policy-engine/`. Any enforcement that exists only in the GitHub UI is
therefore operational/manual truth rather than a repo-tracked contract.

For the current manual GitHub-UI checklist, see
[Apply GitHub Governance Manually](../how-to/apply-github-governance.md).

## Repo-Tracked Controls

The repository itself currently versions these merge-governance surfaces:

- PR taxonomy and reviewer prompts in `.github/PULL_REQUEST_TEMPLATE.md`;
- label vocabulary in `.github/labels.yml`;
- owner routing in [Ownership](ownership.md);
- published gate inventory in [Quality Gates](quality-gates.md);
- local and CI validation commands referenced from those pages;
- the actual workflow files present under repository-root `.github/workflows/`;
- reusable product workflow templates under `policy-engine/ops/ci/templates/workflows/`.

Those files are the factual control plane that reviewers can audit from a
checkout without relying on out-of-band GitHub settings.

## What Is Manual Today

The following settings may still exist in GitHub, but they are not versioned in
this repository today:

- required status-check selections;
- branch-protection toggles such as “require pull request before merging”;
- approval count and stale-review behavior;
- merge queue enablement;
- reviewer-routing rules configured only in GitHub.

When you need to verify or update those settings, treat GitHub as the manual
source of truth and reconcile it against the repo-tracked pages above.

## Reviewer Routing Without CODEOWNERS

Because there is no repo-tracked `.github/CODEOWNERS` file in this checkout,
review routing is documented instead of auto-derived.

Use these sources in order:

- [Ownership](ownership.md) for subsystem and shared-surface owners;
- the nearest package `README.md` for boundary-specific reviewer hints;
- [Quality Gates](quality-gates.md) for category-specific review expectations.

Changes to shared control-plane paths should request `@platform-owners`
attention explicitly even without CODEOWNERS automation. That includes:

- `.github/workflows/**`
- `policy-engine/ops/ci/templates/workflows/**`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/labels.yml`
- `mkdocs.yml`
- shared pages under `docs/reference/**`
- release ledgers and closeout manifests under `release/**`

## Current Workflow Reality

The current repo-tracked workflow inventory is the one listed in
[Quality Gates](quality-gates.md). In particular:

- repository-root `.github/workflows/abi.yml`, `.github/workflows/ci.yml`,
  `.github/workflows/core-runtime-release-gate.yml`, `.github/workflows/docs-pages.yml`,
  `.github/workflows/fabric-remediation.yml`, `.github/workflows/frontend-nightly.yml`,
  `.github/workflows/frontend-quality.yml`, and `.github/workflows/release.yml` are
  active and factual;

- product-local templates such as `arch.yml`, `perf.yml`, `replay.yml`,
  `signatures.yml`, and `foundry-release-gate.yml` live under
  `policy-engine/ops/ci/templates/workflows/` and are not active GitHub
  workflows unless copied or promoted intentionally.

## Recommended Manual Branch-Protection Posture

If you are configuring GitHub manually, the documented posture is:

- require pull requests for `main`;
- require at least one approval;
- require conversations to be resolved before merge;
- choose required-check contexts only from workflows that currently exist in
  `.github/workflows/`;

- avoid selecting historical or otherwise absent check contexts.

Because the exact GitHub check-context names are produced by live workflow runs,
capture them from the GitHub UI rather than hardcoding them into this page.

## Tools and Docs Drift Expectations

Tools and docs changes are mergeable only when the generated and validated
surfaces agree with the registry and manifests:

- command-metadata changes regenerate `docs/reference/tools.md`;
- generated-reference changes regenerate the affected published pages;
- docs changes keep `check-docs-accuracy` and strict MkDocs green unless a
  tracked exception is explicitly recorded.

## Merge Queue

Merge queue is not part of the repo-tracked contract today. If it is enabled in
GitHub later, that remains an operational/manual decision until the repository
starts versioning the relevant policy and workflow context.

## Signatures Policy

- `signatures.yml` is the repo-tracked regression surface for artifact-signing
  behavior and private-key hygiene;

- `build-and-push.yml` is the repo-tracked SBOM/signing bundle for manual build
  dispatches;

- commit-signature enforcement on `main`, if enabled in GitHub, is currently a
  manual platform setting rather than a versioned repo contract.

This keeps provenance anchored in versioned tests and build steps without
pretending that live GitHub enforcement is tracked in-repo when it is not.
