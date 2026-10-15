# Platform Changelog

Related how-to: [Release, Versioning, and Deprecation Policy](../how-to/release-policy.md).

Owner: `@platform-owners`
Source of truth: this page's dated entries for historical summaries. Linked
reference pages and repository-tracked artifacts describe the documented
contracts. Release notes remain the publish-time artifact for a specific release.

> Operator-facing summary of notable platform-contract changes. This page is not
> a substitute for release notes; it is the durable "what changed in the
> platform model" view.

The 2026-04-12 entry is a historical repository summary. Present-tense wording
describes the contract recorded for that date; it does not verify today's
runtime, deployment, or publication state.

## 2026-04-12

### Runtime lifecycle and API maturity

Related references: [REST API](api/index.md) and [Observability
Topology](operations/observability-topology.md).

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

Related references: [CAS and Storage](operations/cas-storage.md) and [Artifact
Corruption Recovery](../runbooks/artifact-corruption-recovery.md).

- Runtime services now consume a backend-neutral storage boundary instead of
  binding directly to `FileSystemCAS`.

- Read-time integrity verification is enforced before artifact payloads are
  returned.

- Manifest creation and runtime artifact logging now use batched or atomic
  paths to reduce duplicate or write-amplified behavior.

### Runtime write-path hardening

Related references: [Control Plane API](api/control.md) and [Observability
Topology](operations/observability-topology.md).

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
