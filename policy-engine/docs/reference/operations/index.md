# Operations Reference

Owner: `@platform-owners` (logical owner group; see [`../ownership.md`](../ownership.md))
Source of truth: the child references below and the operational contracts, configuration, source, or procedure named by each page
Repository review: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; repository sources inspected, no runtime, CI, deployment, or network command executed.

This index routes operators to the repository-owned contracts and procedures
for runtime, storage, observability, retention, and handoff.

> A checked-in contract, workflow, Helm chart, component bundle, or runbook is
> evidence that a repository source exists. It does not show that a service,
> alert, storage backend, cloud resource, credential, or data copy is present
> or healthy in an environment. E02 source presence is not runtime readiness;
> establish current environment state using authorized environment evidence.

## Start Here

| Need | Start with | Canonical source or boundary |
| --- | --- | --- |
| Runtime HTTP or control-plane issue | [Runtime API Outage](../../runbooks/runtime-api-outage.md), [Deploy Runtime](../../how-to/deploy-runtime.md), [Control Plane API](../api/control.md) | Runtime factory and routes are in `src/polisyos/runtime/http/`; the selected app profile and environment determine the effective service configuration. |
| CAS or artifact-storage issue | [CAS or OPA Outage](../../runbooks/cas-opa-outage.md), [CAS and Storage](cas-storage.md), [Artifact Corruption Recovery](../../runbooks/artifact-corruption-recovery.md) | `src/polisyos/core/artifacts/`, `src/polisyos/runtime/http/dependencies.py`, and `src/polisyos/fabric/storage/`; backend values are documented in [Configuration](../configuration.md). |
| Local `.polisyos` state or cleanup | [Local Runtime State](../local-runtime-state.md), [Retained Artifact Recovery](../../runbooks/retained-artifact-recovery.md) | `architecture/local_runtime_state.toml`, `architecture/runtime_state_layout.toml`, and `tools/ops_runners/runtime/runtime_state_cleanup.py`. |
| CI, docs validation, or publication | [Operate the CI/CD Platform](../../how-to/operate-ci-cd-platform.md), [Docs Publication Failure](../../runbooks/docs-publication-failure.md) | Repository-declared workflow files are under root `.github/workflows/`. `ops/ci/templates/workflows/` contains reusable product templates and is not itself the GitHub-executed workflow inventory. |
| Runtime metrics, alerts, or SLO definitions | [Observability Topology](observability-topology.md), [SLO and Error Budget Policy](slo-error-budget.md) | Repo-owned configuration is under `ops/components/**` and `ops/observability/**`. The runtime component README labels its SLO and alert mapping as draft; configuration presence does not establish deployed telemetry or SLO attainment. |
| Release or cross-surface acceptance | [Platform Acceptance Audit](platform-acceptance-audit.md), [Core Runtime Closeout](core-runtime-closeout.md), [Release Policy](../../how-to/release-policy.md) | Required evidence and commands are named by those procedures; a source artifact alone is not an acceptance result. |
| Environment-specific production debugging | [Production Quality Canary](../../runbooks/production-quality-canary.md), [Local Production Debugging](../../runbooks/local-production-debugging.md), [Cloud Production Debugging](../../runbooks/cloud-production-debugging.md) | The local (`2026-05-19`) and cloud (`2026-05-20`) setup notes are historical receipts; no current host, container, data, or credential state is established. Read their source-backed revalidation prerequisites before reuse. |

## Reference Pages

| Page | Purpose |
| --- | --- |
| [Platform Architecture Diagrams](platform-architecture-diagrams.md) | Request path, control-plane lifecycle, CAS/integrity flow, and observability map. |
| [CAS and Storage](cas-storage.md) | Runtime artifact-store contract, backend selection, local layout, and guards. |
| [Infrastructure Split-Compute Note (2026-04-04 source snapshot)](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/operations/infrastructure-split-compute.md) | Historical target-design and cost snapshot; source gaps and deployment assumptions require revalidation before reuse. |
| [SLO and Error Budget Policy](slo-error-budget.md) | Reliability vocabulary, SLO policy, error-budget response, and freeze policy. |
| [Ops Baselines](ops-baselines.md) | Repository baseline configuration map; external scanner, billing, and service states are not established by source presence. |
| [Observability Topology](observability-topology.md) | Signal taxonomy, dashboards and alerts, ownership, and correlation boundaries. |
| [Retention and Recovery Policy](retention-and-recovery.md) | Retention classes and recovery expectations; local `.polisyos` slots are specified separately by the local-state contract. |
| [Handoff and Platform Review](handoff-and-platform-review.md) | Handoff template, retirement review, and platform review. |
| [Platform Acceptance Audit](platform-acceptance-audit.md) | Acceptance evidence map, contributor-path rehearsal, and manual evidence expectations. |
| [Core Runtime Closeout](core-runtime-closeout.md) | Core-runtime closeout evidence and remaining gaps. |
| [Repository Topology](../repository-topology.md) | Product root, ops, tools, tests, docs lifecycle, data, and local-state placement. |
| [Scientist Reliability Scorecard](../scientist/reliability-scorecard.md) | Scientist release evidence and workflow scenarios. |

For scenario procedures, begin at the [Runbooks index](../../runbooks/index.md). For
ownership semantics and support scope, see [Ownership](../ownership.md) and
`policy-engine/SUPPORT.md`.

## CI and Runtime Command Status

The following commands are documented and registered in repository tooling or
repo-tracked workflow definitions. They were **not executed during this review**:

```bash
cd policy-engine
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
uv run polisyos-tools validation check-docs-accuracy --repo-root .
uv run polisyos-tools workspace ci-parity --skip-browser
```

Provision the supported `uv` environment as described in `CONTRIBUTING.md`.
The docs gate also needs its selected base ref to resolve in local Git;
`workspace ci-parity` has the broader contributor-toolchain prerequisites. The
repo-declared docs PR gate is `.github/workflows/abi.yml`, and the repository
publication workflow is `.github/workflows/docs-pages.yml`; the local procedure is
`docs/how-to/operate-ci-cd-platform.md`. These files establish configured
automation only, not a successful CI run or a published site.

Runtime launch instructions and required extras are in
[Deploy Runtime](../../how-to/deploy-runtime.md). They describe an application
entrypoint, not a provisioned service or a production deployment. Deployment
manifests under `ops/cloud/helm/` likewise describe repository configuration;
they do not confirm that a cluster has applied it.
