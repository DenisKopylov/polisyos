# Apply GitHub Governance Manually

This guide covers the GitHub settings that are not versioned in the local
repository.

Use it whenever you need to reconcile the live GitHub repository with the
repo-tracked docs and workflow inventory.

## Inputs

- repository admin or equivalent settings access in GitHub;
- current repo checkout with the live `.github/workflows/*.yml` files and docs;
- a reason to reconcile labels, rulesets, reviewer routing, or required checks.

## Output

- GitHub repository settings aligned with the repo-tracked governance docs and
  current workflow inventory;

- a reviewable record of which settings are still manual rather than
  version-controlled.

## Commands

Use local commands to collect the repo-tracked source of truth before changing
the GitHub UI:

```bash
cd policy-engine
rg --files ../.github/workflows
sed -n '1,200p' ../.github/labels.yml
sed -n '1,220p' ../.github/CODEOWNERS
sed -n '1,220p' ../.github/repository-rulesets/main.yml
sed -n '1,200p' docs/reference/merge-governance.md
sed -n '1,200p' docs/reference/quality-gates.md
sed -n '1,200p' docs/reference/ownership.md
sed -n '1,220p' architecture/control_plane_supply_chain.toml
```

## Before You Start

You need repository admin access, or a custom role with permission to edit
repository settings, branch protection, labels, and merge rules.

The current repo-tracked inputs are:

- labels: repository-root `.github/labels.yml`
- reviewer and change taxonomy prompts:
  repository-root `.github/PULL_REQUEST_TEMPLATE.md`
- merge-governance narrative: `docs/reference/merge-governance.md`
- local/CI gate inventory: `docs/reference/quality-gates.md`
- owner routing: `docs/reference/ownership.md`
- active workflow inventory: repository-root `.github/workflows/*.yml`
- CODEOWNERS routing: repository-root `.github/CODEOWNERS`
- default-branch ruleset intent:
  repository-root `.github/repository-rulesets/main.yml`
- active control-plane target contract:
  `policy-engine/architecture/control_plane_supply_chain.toml`

The repository now versions CODEOWNERS and ruleset intent. GitHub-side
application of that ruleset is still manual evidence: after changing the file,
verify the UI or export the ruleset from GitHub.

## 1. Create or Update Labels

GitHub does not automatically create labels from `.github/labels.yml`, so add
or update them in the UI when the file changes.

Path in GitHub UI:

1. Open the repository main page.
2. Click **Issues** or **Pull requests**.
3. Click **Labels**.
4. Click **New label**.
5. Copy the `name`, `color`, and `description` from `.github/labels.yml`.
6. Save the label.
7. Repeat until the full set exists.

Verification:

- open the Labels list and confirm every label from `.github/labels.yml`
  exists exactly once;

- open any test PR and confirm the labels are selectable.

## 2. Review the Active Workflow Inventory

Before configuring required checks, verify which workflows actually exist under
`.github/workflows/`.

As of this docs refresh, the active inventory includes:

- `abi.yml`
- `ci.yml`
- `core-runtime-long-soak.yml`
- `core-runtime-release-gate.yml`
- `docs-pages.yml`
- `fabric-remediation.yml`
- `frontend-nightly.yml`
- `frontend-quality.yml`
- `release.yml`

Product-local templates under `policy-engine/ops/ci/templates/workflows/` are
reference/template material unless they are promoted to the repository-root
`.github/workflows/` control plane.

## 3. Configure Branch Protection Manually

Path in GitHub UI:

1. Open the repository main page.
2. Click **Settings**.
3. Open the branch-protection or rulesets section for `main`.

Recommended posture, matching the tracked ruleset intent:

- require pull requests before merging;
- require at least one approval;
- require code-owner review;
- dismiss stale approvals on push;
- require approval of the most recent push;
- require conversation resolution before merge;
- block force-push and branch deletion on the protected default branch.

These are operational settings. Keep them aligned with
`.github/repository-rulesets/main.yml` and
`docs/reference/merge-governance.md`; treat the repository files as intended
state and the GitHub UI as applied-state evidence.

## 4. Choose Required Checks from Current Workflows

GitHub requires exact check-context names, and those names come from live
workflow runs rather than from filenames alone.

Recommended process:

1. Open recent successful runs for the workflows you want to require.
2. Copy the exact check names shown by GitHub.
3. Add only those live check names to branch protection.
4. Recheck them whenever workflow job names change.

The tracked ruleset currently names `Fast PR / Gate` and `Standard PR / Gate`
as the fast PR tier. If job names change, update the ruleset file and this
guide before changing the GitHub UI.

## 5. Reviewer Routing

Reviewer routing should follow:

1. `.github/CODEOWNERS` for current enforceable reviewer routing
2. `architecture/control_plane_supply_chain.toml` for target logical-owner
   projection and personal-repo exceptions
3. `docs/reference/ownership.md`
4. the nearest package `README.md`
5. the shared-surface guidance in `docs/reference/quality-gates.md`

For shared control-plane changes such as `.github/workflows/**`, `mkdocs.yml`,
release ledgers, or shared reference pages, request `@platform-owners`
attention explicitly.

## 6. Merge Queue and Signatures

- Merge queue is disabled in `.github/repository-rulesets/main.yml`. If you
  enable it in GitHub, update the tracked contract first and add
  merge_group-compatible required checks.

- `signatures.yml` and `build-and-push.yml` are the repo-tracked signing and
  SBOM surfaces.

- Signed release tags are required by the tracked ruleset. Commit-signature
  enforcement on `main` remains recommended but is not enforced until key
  management and automation signing posture are standardized.

## 7. Post-Setup Verification Checklist

After saving the ruleset, verify all of the following:

- the GitHub settings page shows the intended protections for `main`;
- the required-check list contains only contexts from workflows that currently
  exist;

- labels from `.github/labels.yml` are available and can be applied;
- a sample PR routes reviewers according to `.github/CODEOWNERS`;
- a sample PR shows the expected blocking rules in the merge box;
- release tag/signing expectations match `.github/repository-rulesets/main.yml`.

## 8. Drift-Control Rule

When governance policy changes in the repo:

1. update `.github/labels.yml`, workflow files, and/or the relevant governance
   docs;
2. update `.github/CODEOWNERS`, `.github/repository-rulesets/main.yml`, or
   `architecture/control_plane_supply_chain.toml` when ownership, protection,
   or supply-chain posture changes;
3. update the relevant docs page;
4. apply the same change in GitHub UI;
5. verify the live repository state still matches the repo-tracked source of
   truth.

## Rollback

- revert the GitHub UI change if it contradicts the repo-tracked docs or blocks
  the current workflow inventory;

- if the mistake is really in the repo-tracked source of truth, update docs and
  workflow files first, then re-apply the GitHub setting intentionally;

- when unsure, prefer restoring the previous live setting over leaving the repo
  in a half-synchronized governance state.

## Troubleshooting

- If a required check never appears in branch protection, copy the exact check
  context from a recent workflow run instead of guessing from the YAML filename.

- If reviewer routing feels ambiguous, escalate to
  `docs/reference/ownership.md` before inventing ad hoc code-owner rules.

- If labels drift repeatedly, treat `.github/labels.yml` as the canonical list
  and reconcile the UI in one pass instead of editing labels PR by PR.

## References

- GitHub Docs: [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- GitHub Docs: [Managing labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels)
- GitHub Docs: [Merging a pull request with a merge queue](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue?tool=webui)
- GitHub Docs: [About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)
- GitHub Docs: [Signing tags](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-tags)
