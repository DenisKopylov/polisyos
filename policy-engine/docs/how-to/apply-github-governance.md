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
rg --files .github/workflows
sed -n '1,200p' .github/labels.yml
sed -n '1,200p' docs/reference/merge-governance.md
sed -n '1,200p' docs/reference/quality-gates.md
sed -n '1,200p' docs/reference/ownership.md
```

## Before You Start

You need repository admin access, or a custom role with permission to edit
repository settings, branch protection, labels, and merge rules.

The current repo-tracked inputs are:

- labels: `.github/labels.yml`
- reviewer and change taxonomy prompts: `.github/PULL_REQUEST_TEMPLATE.md`
- merge-governance narrative: `docs/reference/merge-governance.md`
- local/CI gate inventory: `docs/reference/quality-gates.md`
- owner routing: `docs/reference/ownership.md`
- active workflow inventory: `.github/workflows/*.yml`

There is no repo-tracked `.github/repository-rulesets/main.yml` or
`.github/CODEOWNERS` file in this checkout, so those parts of GitHub
governance are manual today.

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
- `arch.yml`
- `arch-freeze.yml`
- `build-and-push.yml`
- `causal-phases.yml`
- `docs.yml`
- `foundry-release-gate.yml`
- `perf.yml`
- `replay.yml`
- `signatures.yml`

Do not create required checks for absent historical files such as `ci.yml`,
`frontend-nightly.yml`, `release.yml`, or `docs-pages.yml`.

## 3. Configure Branch Protection Manually

Path in GitHub UI:

1. Open the repository main page.
2. Click **Settings**.
3. Open the branch-protection or rulesets section for `main`.

Recommended posture:

- require pull requests before merging;
- require at least one approval;
- require conversation resolution before merge;
- enable stale-approval dismissal if that matches your team's review posture.

These are operational settings. Keep them aligned with
`docs/reference/merge-governance.md`, but do not treat them as repo-tracked
facts unless the repository starts versioning them.

## 4. Choose Required Checks from Current Workflows

GitHub requires exact check-context names, and those names come from live
workflow runs rather than from filenames alone.

Recommended process:

1. Open recent successful runs for the workflows you want to require.
2. Copy the exact check names shown by GitHub.
3. Add only those live check names to branch protection.
4. Recheck them whenever workflow job names change.

The repository does not currently version a canonical required-check allowlist,
so this remains manual.

## 5. Reviewer Routing

Because there is no repo-tracked `.github/CODEOWNERS` file here, reviewer
routing should follow:

1. `docs/reference/ownership.md`
2. the nearest package `README.md`
3. the shared-surface guidance in `docs/reference/quality-gates.md`

For shared control-plane changes such as `.github/workflows/**`, `mkdocs.yml`,
release ledgers, or shared reference pages, request `@platform-owners`
attention explicitly.

## 6. Merge Queue and Signatures

- Merge queue is not part of the repo-tracked contract today. If you enable it
  in GitHub, treat that as a manual operational decision.
- `signatures.yml` and `build-and-push.yml` are the repo-tracked signing and
  SBOM surfaces.
- Commit-signature enforcement on `main`, if you use it, is a manual GitHub
  setting rather than a versioned repository rule.

## 7. Post-Setup Verification Checklist

After saving the ruleset, verify all of the following:

- the GitHub settings page shows the intended protections for `main`;
- the required-check list contains only contexts from workflows that currently
  exist;
- labels from `.github/labels.yml` are available and can be applied;
- a sample PR routes reviewers according to `docs/reference/ownership.md`;
- a sample PR shows the expected blocking rules in the merge box;
- labels from `.github/labels.yml` are available and can be applied.

## 8. Drift-Control Rule

When governance policy changes in the repo:

1. update `.github/labels.yml`, workflow files, and/or the relevant governance
   docs;
2. update the relevant docs page;
3. apply the same change in GitHub UI;
4. verify the live repository state still matches the repo-tracked source of
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
