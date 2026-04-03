# Apply Phase 1 Governance in GitHub UI

This guide covers the Phase 1 steps that cannot be enforced from the local
repository alone:

- creating the repository labels from `.github/labels.yml`;
- applying the default-branch ruleset from `.github/repository-rulesets/main.yml`;
- verifying that live GitHub settings match the repo-tracked governance policy.

Use this guide after merging the Phase 1 governance files into `main`.

## Before You Start

You need repository admin access, or a custom role with permission to edit
repository rules and labels.

Repository source of truth:

- labels: `.github/labels.yml`
- branch ruleset: `.github/repository-rulesets/main.yml`
- merge policy narrative: `docs/reference/merge-governance.md`
- PR taxonomy: `.github/PULL_REQUEST_TEMPLATE.md`

## 1. Create the Phase 1 Labels

GitHub does not automatically create labels from `.github/labels.yml`, so add
them once in the UI.

Path in GitHub UI:

1. Open the repository main page.
2. Click **Issues** or **Pull requests**.
3. Click **Labels**.
4. Click **New label**.
5. Copy the `name`, `color`, and `description` from `.github/labels.yml`.
6. Save the label.
7. Repeat until the full set exists.

Labels to create:

### Kind labels

- `kind:architecture`
- `kind:contract-schema`
- `kind:runtime-behavior`
- `kind:frontend`
- `kind:docs`
- `kind:ops-security`
- `kind:dependency-upgrade`

### Compatibility labels

- `compat:breaking`
- `compat:additive`
- `compat:internal`

### Release labels

- `release:breaking`
- `release:feature`
- `release:fix`
- `release:docs`
- `release:ops`
- `release:security`
- `release:none`

Verification:

- open the Labels list and confirm every label from `.github/labels.yml`
  exists exactly once;
- open any test PR and confirm the labels are selectable.

## 2. Create the Default-Branch Ruleset

Path in GitHub UI:

1. Open the repository main page.
2. Click **Settings**.
3. In the left sidebar, click **Rules**, then **Rulesets**.
4. Click **New ruleset**.
5. Click **New branch ruleset**.

Use these values:

- **Ruleset name**: `main-merge-governance`
- **Enforcement status**: `Active`
- **Target branches**: include `main`

## 3. Configure Pull Request Rules

Under branch protections, enable:

- **Require a pull request before merging**
- **Required approvals**: `1`
- **Require review from code owners**
- **Dismiss stale pull request approvals when new commits are pushed**
- **Require approval of the most recent reviewable push**
- **Require conversation resolution before merging**

Do not add bypass actors unless there is a reviewed exception. If bypass is
required, prefer pull-request-only bypass over unrestricted direct push bypass.

## 4. Configure Required Status Checks

Still inside the same ruleset:

1. Enable **Require status checks before merging**.
2. Enable **Require branches to be up to date before merging**.
3. Add these exact checks:
   - `Fast PR / Gate`
   - `Standard PR / Gate`

Do not require these on the branch ruleset:

- `Docs Pages / Deploy`
- any Nightly workflow
- any Release workflow
- `Frontend Quality (Archived)`

The repository intentionally protects `main` through the two aggregated gate
checks rather than dozens of individual job contexts.

## 5. Merge Queue Decision

Leave merge queue disabled for now.

Rationale:

- the current repository is hosted as a personal repository
  (`DenisKopylov/polisyos`), and GitHub documents merge queue for eligible
  organization-owned repositories rather than this hosting model;
- the current repository volume does not justify queueing yet;
- the active PR workflows do not currently declare `merge_group` triggers;
- enabling merge queue before the workflow contract supports it would weaken,
  not strengthen, governance.

Record that decision by ensuring the live ruleset matches the rationale in
`.github/repository-rulesets/main.yml` and
`docs/reference/merge-governance.md`.

## 6. Signed Commits and Signed Tags

Do not enable **Require signed commits** on `main` yet.

Current Phase 1 policy is:

- release-critical tags should be signed;
- verified commit signatures on `main` are recommended but not yet enforced.

That split is intentional because tag signing is part of release provenance,
while commit-signing enforcement would currently create contributor friction
before key management is standardized.

## 7. CODEOWNERS Self-Protection

No extra UI path mapping is needed beyond enabling code-owner review in the
ruleset, because `.github/CODEOWNERS` already marks these paths as owned:

- `.github/**`
- `.github/CODEOWNERS`
- `SECURITY.md`
- `SUPPORT.md`
- `CODE_OF_CONDUCT.md`

Verification:

1. Open a test PR that changes one of those files.
2. Confirm GitHub requests the CODEOWNER reviewer.
3. Confirm the PR cannot merge without satisfying the required review rules.

## 8. Post-Setup Verification Checklist

After saving the ruleset, verify all of the following:

- the repository rulesets page shows an active ruleset targeting `main`;
- the ruleset displays required pull requests and code-owner review;
- the ruleset displays stale-review dismissal and most-recent-push approval;
- the required check list contains `Fast PR / Gate` and `Standard PR / Gate`;
- a sample PR shows the expected blocking rules in the merge box;
- labels from `.github/labels.yml` are available and can be applied.

## 9. Drift-Control Rule

When governance policy changes in the repo:

1. update `.github/labels.yml` and/or `.github/repository-rulesets/main.yml`;
2. update the relevant docs page;
3. apply the same change in GitHub UI;
4. verify the live repository state still matches the repo-tracked source of
   truth.

## References

- GitHub Docs: [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- GitHub Docs: [Managing labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels)
- GitHub Docs: [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- GitHub Docs: [Merging a pull request with a merge queue](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue?tool=webui)
- GitHub Docs: [About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)
- GitHub Docs: [Signing tags](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-tags)
