# Support Policy

This repository supports contributors, operators, and evaluators differently
depending on whether they are working on the supported branch and supported
surface.

## Support Boundaries

| Audience | Supported | Not supported |
|---|---|---|
| Internal maintainers and operators | Contributor workflow, release path, runtime operations, docs, and repository automation on supported branches | Ad hoc support for stale branches kept alive only locally |
| External evaluators and bug reporters | Best-effort help for reproducible bugs and documentation issues on supported branches | Custom deployment help, private environment debugging, bespoke feature work |
| Forks and downstream private patches | Best-effort pointers only | Branch-specific fixes for unmerged local changes |

Supported branch policy follows [SECURITY.md](SECURITY.md): `main` and the most
recent supported tag are in scope; historical tags and side branches are not.

## Support Channels

- Non-sensitive bugs and documentation issues: public GitHub issue or pull
  request.
- Contributor workflow failures: public issue or PR discussion with the exact
  command, error output, and affected branch or commit.
- Security reports: private disclosure only, following [SECURITY.md](SECURITY.md).
- Internal operational outages: email `skvidvard167m@gmail.com` with the
  subject prefix `[incident]`.

## Response Modes

| Request type | Mode | Initial target |
|---|---|---|
| Internal Sev-1 outage or release blocker | Incident coordination | within 4 business hours |
| Internal Sev-2 degradation or broken engineering path | Priority maintenance | within 1 business day |
| External reproducible bug or docs defect | Best-effort async support | within 5 business days |
| Feature request or roadmap question | Product triage | best effort, no SLA |
| Security or vulnerability report | Private security handling | see [SECURITY.md](SECURITY.md) |

## Expected Handling

- Incident-mode requests focus on stabilization, rollback, blast-radius
  assessment, and next-update ownership.
- Standard support requests focus on reproduction, affected supported surface,
  and the smallest actionable fix or workaround.
- Requests that only affect unsupported tags, abandoned branches, or private
  forks may be closed with an upgrade recommendation instead of a patch.

## What Support Does Not Mean

- No guarantee of custom consulting, migrations for private forks, or managed
  production operations.
- No support promise for internal-only or experimental surfaces beyond
  best-effort maintainer judgment.
- No public handling of confidential incidents, credential exposure, or
  vulnerabilities.
