# Platform Changelog

Related how-to: [Release, Versioning, and Deprecation Policy](../how-to/release-policy.md).

Owner: `@platform-owners`
Source of truth: operator-facing contract changes captured in `docs/reference/**`, `docs/how-to/release-policy.md`, and the repo-tracked artifacts or workflows cited in each dated entry

> Operator-facing summary of notable platform-contract changes. This page is not
> a substitute for release notes; it is the durable "what changed in the
> platform model" view.

## 2026-04-12

### Runtime lifecycle and API maturity

- Runtime now starts and stops through an explicit typed container rather than
  ad-hoc `app.state` wiring.

- Health payloads expose lifecycle state and dependency graph snapshots.
- `/api/v1/*` responses emit version/deprecation metadata suitable for client
  contract review.

- Artifact resources now expose cache validators and support raw-download or
  negotiated content paths.

- Batch endpoints were added for runs and artifacts to reduce operator-facing
  N+1 retrieval.

### Storage and integrity hardening

- Runtime services now consume a backend-neutral storage boundary instead of
  binding directly to `FileSystemCAS`.

- Read-time integrity verification is enforced before artifact payloads are
  returned.

- Manifest creation and runtime artifact logging now use batched or atomic
  paths to reduce duplicate or write-amplified behavior.

### Runtime write-path hardening

- `X-Idempotency-Key` is now supported on side-effecting runtime control paths.
- Per-tenant rate limiting and live-stream budgets are enforced at the runtime
  perimeter.

- Mutation and data-access audit trails are now part of the runtime operating
  model.

## Changelog Rules

- record operator-visible platform-contract changes, not every internal refactor;
- link each entry to the relevant ADR, migration guide, or runbook when the
  change affects rollout or incident response;

- keep release notes as the authoritative publish-time artifact and use this
  page as the durable operator summary.
