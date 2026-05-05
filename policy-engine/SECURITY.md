# Security Policy

This repository treats security reports as private coordination work, not as
public issue traffic.

## Reporting a Vulnerability

- Do not open a public GitHub issue for a suspected vulnerability.
- Send the report to `skvidvard167m@gmail.com`.
- Use the subject prefix `[security]`.
- Include the affected commit, tag, or branch, the impacted surface, expected
  impact, reproduction steps, and any proof-of-concept material needed for
  validation.

If GitHub private vulnerability reporting is enabled for this repository, that
channel is also acceptable. Email remains the fallback source of truth.

## Response Targets

| Report type | Initial acknowledgement | Triage target | Ongoing updates |
|---|---|---|---|
| Confirmed vulnerability | within 2 business days | severity + next step within 5 business days | every 5 business days until fix or containment |
| Suspected actively exploited issue | same-day best effort | mitigation plan within 24 hours of confirmation | daily while active |
| Credential leak / signing-key exposure | same-day best effort | rotation / containment starts immediately after confirmation | daily while active |

Business-day targets are intentionally used because the repository is currently
maintained from a personal-owner setup rather than a staffed 24x7 rotation.

## Supported Branches and Versions

| Surface | Status | Notes |
|---|---|---|
| `main` | Supported | Security fixes and mitigations land here first. |
| Latest tagged release on the default line | Supported | Best-effort support when a published artifact or deployed environment depends on it. |
| Historical tags, feature branches, personal forks | Not supported | Upgrade to `main` or the latest supported tag before requesting a fix. |

Until dedicated `release/*` branches exist, `main` is the only continuously
supported engineering branch.

## Response Mode

- Security vulnerabilities are triaged privately, reproduced, severity-ranked,
  fixed, and disclosed only after a patch, mitigation, or documented
  containment exists.
- Operational outages with a security dimension are handled in incident mode:
  stabilize the system first, preserve evidence, then complete remediation and
  disclosure follow-up.
- Secret, token, signing-key, or workflow-credential exposures trigger
  immediate containment, credential rotation, and artifact trust review.

## What to Expect from Us

- We will confirm whether the report is in scope and reproducible.
- We may request a reduced reproduction or private validation details.
- We will coordinate disclosure timing when a fix requires a release,
  migration, or token rotation window.
- We will explicitly say when a finding is out of support scope or not
  reproducible on a supported branch.
