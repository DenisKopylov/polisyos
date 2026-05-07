# Merge Governance

Owner: `@platform-owners`  
Backup owner: `@tools-owners`  
Source of truth: `architecture/control_plane_supply_chain.toml`,
`docs/reference/{quality-gates.md,ownership.md}`, repository-root
`.github/{CODEOWNERS,repository-rulesets/main.yml,PULL_REQUEST_TEMPLATE.md,labels.yml}`,
and the current root workflow inventory under `.github/workflows/*.yml`

This page describes the repo-tracked part of the merge contract for `main`.

Important boundary: GitHub evaluates CODEOWNERS, rulesets, PR templates,
labels, and workflows from the outer repository root, not from
`policy-engine/`. Those files are intentionally repo-control-plane files.
Whether `.github/repository-rulesets/main.yml` is actually applied in the live
GitHub UI is still operational evidence; the repository file records the
intended ruleset, not proof of application.

For the current manual GitHub-UI checklist, see
[Apply GitHub Governance Manually](../how-to/apply-github-governance.md).

## Repo-Tracked Controls

The repository itself currently versions these merge-governance surfaces:

- default-branch ruleset intent in `.github/repository-rulesets/main.yml`;
- enforceable personal-repo reviewer routing in `.github/CODEOWNERS`;
- active control-plane owner mappings and supply-chain controls in
  `architecture/control_plane_supply_chain.toml`;
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
this repository as live-applied state:

- proof that `.github/repository-rulesets/main.yml` is applied to `main`;
- the exact live required-check contexts selected by GitHub, especially after
  job-name changes;
- merge queue enablement, currently disabled in the tracked ruleset contract;
- any reviewer-routing rules configured only in GitHub settings.

When you need to verify or update those settings, treat GitHub as the manual
application surface and reconcile it against the repo-tracked contract files
above.

## Reviewer Routing With CODEOWNERS

`.github/CODEOWNERS` currently maps owned paths to `@DenisKopylov`, because
this is a personal repository without provisioned organization team slugs. The
logical owner model still lives in [Ownership](ownership.md), and the active
Phase 2.8 CODEOWNERS projection lives in
`architecture/control_plane_supply_chain.toml`.

Use these sources in order:

- `.github/CODEOWNERS` for current enforceable reviewer routing;
- `architecture/control_plane_supply_chain.toml` for active logical-owner to
  CODEOWNERS projection and path-prefix cleanup enforcement;
- [Ownership](ownership.md) for subsystem and shared-surface escalation;
- the nearest package `README.md` for boundary-specific reviewer hints;
- [Quality Gates](quality-gates.md) for category-specific review expectations.

Changes to shared control-plane paths should still request `@platform-owners`
attention explicitly. That includes:

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

If you are configuring or auditing GitHub manually, reconcile the UI against
`.github/repository-rulesets/main.yml` and the active control-plane contract.
The intended posture is:

- require pull requests for `main`;
- require at least one approval;
- require code-owner review;
- dismiss stale approvals on push;
- require approval of the most recent push;
- require conversations to be resolved before merge;
- require the fast PR check tier named in the ruleset;
- protect `main` from force-push and branch deletion through GitHub-side
  ruleset settings;
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

Merge queue is explicitly disabled in `.github/repository-rulesets/main.yml`
with a personal-repository rationale. Enabling it later requires a control-plane
contract update plus merge_group-compatible workflow contexts.

## Signatures Policy

- `signatures.yml` is the repo-tracked regression surface for artifact-signing
  behavior and private-key hygiene;

- `build-and-push.yml` is the repo-tracked SBOM/signing bundle for manual build
  dispatches;

- signed release tags are required by the ruleset artifact;
- commit-signature enforcement on `main` remains recommended but not enforced
  until contributor key management and automation signing posture are
  standardized.

This keeps provenance anchored in versioned tests and build steps without
pretending that GitHub-side application proof is tracked in-repo when it is not.
