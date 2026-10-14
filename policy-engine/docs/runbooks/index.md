# Runbooks

Owner: `@platform-owners` (logical owner group; see [Ownership](../reference/ownership.md))
Source of truth: incident procedure in each linked runbook and the source contracts it cites
Coverage map: `architecture/runbook_coverage.toml` is marked `report_only`; it is not an operational readiness gate
Repository review: source inspection at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; index links and selected references checked. No operational command, service, deployment, or cleanup action was executed.

> This page routes to procedures; its contents do not establish that a local or
> cloud environment is provisioned, reachable, credentialed, healthy, or ready.
> E02 source, manifest, or evidence presence in the repository proves source
> presence only. Confirm current environment state from its own authorized
> inventory and evidence before treating a procedure as executable.

Use the linked runbook for the affected surface. Check its prerequisites and
environment-specific values before running commands. Runbooks are maintained
separately; an index review does not validate their commands or refresh their
environment evidence.

## Published Runbook Entry Points

| Runbook | When to use it | Logical owner |
| --- | --- | --- |
| [Dependency Upgrade Regression](dependency-upgrade-regression.md) | A dependency, lockfile, or toolchain change causes a regression. | `@platform-owners` |
| [Runtime API Outage](runtime-api-outage.md) | Runtime HTTP routes fail or degrade. | `@runtime-owners` |
| [CAS or OPA Outage](cas-opa-outage.md) | Runtime artifact access, integrity, or authorization dependencies fail. | `@runtime-owners` |
| [Broken Contract Generation](broken-contract-generation.md) | Schema, OpenAPI, or frontend contract generation or freshness fails. | `@platform-owners` |
| [Artifact Signing or SBOM Failure](artifact-signing-sbom-failure.md) | Signing, SBOM, or attestation evidence fails. | `@platform-owners` and security |
| [Key Rotation](key-rotation.md) | Signing-key or trust-store rotation is needed. | `@platform-owners` and security |
| [Canary Rollback or Failed Promotion](canary-rollback-or-promotion-failure.md) | A staged rollout or promotion is blocked or rolled back. | `@platform-owners` |
| [Migration Release Promotion](migration-release-promotion.md) | A breaking database, runtime-state, API, IR, or persisted-artifact migration blocks promotion. | `@platform-owners` |
| [Idempotency Incident](idempotency-incident.md) | Retry or replay produces duplicates, mismatches, or stuck pending state. | `@runtime-owners` |
| [Mutation Audit Investigation](mutation-audit-investigation.md) | An operator needs to trace a runtime mutation. | `@runtime-owners` |
| [Cache Rebuild Storm](cache-rebuild-storm.md) | Run, timeline, or lineage cache rebuilds cause latency or resource pressure. | `@runtime-owners` |
| [Fabric Quarantine/DLQ And Data-Plane Recovery](fabric-quarantine-dlq-and-data-plane-recovery.md) | Fabric quarantine, dead-letter, streaming checkpoint, or connector recovery is involved. | `@fabric-owners` |
| [Runtime Graceful Shutdown or Stuck Background Worker](runtime-graceful-shutdown-and-stuck-worker.md) | Shutdown, connection draining, or a background worker stalls. | `@runtime-owners` |
| [Replay or Restore Workflow](replay-or-restore.md) | A replay session, checkpoint, snapshot manifest, or retained archive needs recovery. | `@platform-owners` and affected owner |
| [Retained Artifact Recovery](retained-artifact-recovery.md) | A retained CI, benchmark, audit, snapshot, replay, or archive artifact needs recovery. | `@platform-owners` and affected owner |
| [Artifact Corruption Recovery](artifact-corruption-recovery.md) | Read-time integrity checks find a corrupt blob or manifest mismatch. | `@platform-owners` and affected owner |
| [Docs Publication Failure](docs-publication-failure.md) | A docs build, repository-tracked documentation gate, or Pages publication fails. | `@docs-owners` |
| [Benchmark Regression Triage](benchmark-regression-triage.md) | A benchmark comparison shows a quality, latency, or stability regression. | `@foundry-owners` |
| [Production Quality Canary](production-quality-canary.md) | A production-quality canary, scenario matrix, approval, override, replay, or provider review is involved. | `@platform-owners` and runtime |
| [Cloud Production Debugging](cloud-production-debugging.md) | Historical `2026-05-20` cloud setup and validation record; current resources are unverified and the commands require the page's revalidation prerequisites. | `@platform-owners` and runtime |
| [Production Quality Triage](production-quality-triage.md) | A PQL-001 through PQL-024 result needs triage by layer and next action. | `@platform-owners` |
| [Honest Diagnostics Operator Triage](honest-diagnostics.md) | Serious closeout fails on runtime references, diagnostics, source truth, phase barriers, semantic evidence, tenant scope, attestation, staleness, or partial state. | `@platform-owners` and runtime |
| [Policy Design Case Operator Triage](policy-design-case-operator-triage.md) | Policy Design Case closeout is missing case, intent, producer, evidence, governance, audit, or benchmarking support. | `@platform-owners` and runtime |
| [Policy Design Case Rollout And Rollback](policy-design-case-rollout-rollback.md) | Policy Design Case promotion, hold, rollback, kill-switch, or closeout evidence is involved. | `@platform-owners` and runtime |

For Policy Design Case reference paths and operator concepts, start at the
[Policy Design Case Operator Guide](../reference/policy-design-case-operator-guide.md).
For runtime and storage concepts, use the [Operations Reference](../reference/operations/index.md).

## Ownership And Support

Owner labels in runbooks name logical groups. They are not proof that an
organization team or on-call rotation is provisioned. The repository's current
reviewer mapping and escalation ownership are recorded in
[Ownership](../reference/ownership.md); supported branches,
support channels, and external-support limits are in `policy-engine/SUPPORT.md`.

## Postmortem Record

After an incident, retain a UTC timeline with detection, mitigation, and
recovery points; the affected scope; a remediation owner and due date; and a
link to the procedure that changed. Follow the specific surface policy for
handling raw runtime data and evidence; this index does not authorize promotion
or cleanup.
