# Repository Topology

Freshness: 2026-05-03

Owner: `@platform-owners`
Backup owner: `@docs-owners`
Source of truth:

- `architecture/topology.toml`
- `architecture/repository_sota_gates.toml`
- `architecture/data_policy.toml`
- `architecture/local_runtime_state.toml`
- `tests/architecture/test_repository_sota_phase3_topology_cleanup.py`
- `tests/architecture/test_repository_public_polish.py`
- `docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md`

PolicyOS uses a collapsed product-root workspace: this `policy-engine/`
directory is the only product/workspace root modeled by
`architecture/topology.toml`. The outer Git repository root is a
repo-control-plane shell for GitHub-native files such as `.github/`, root
`.gitignore`, and Renovate configuration; ignored editor/agent state may exist
locally but is not product workspace state. Active GitHub workflows live only
at the outer repository-root `.github/`, product workflow templates live under
`ops/ci/templates/`, and product-root legacy surfaces such as `.github/`,
`cloud_deploy/`, `deploy/`, `docker/`, `gcp/`, and `scripts/` are forbidden
paths inside `policy-engine/`.

## Product Root

| Path | Use |
| --- | --- |
| `architecture/` | Machine-readable repository contracts, exceptions, and gate registries. |
| `src/polisyos/` | Product Python packages and public facades. |
| `tests/` | Physical test taxonomy described below. |
| `tools/` | Canonical local, CI, research, ops, and validation commands. |
| `ops/` | Runtime, cloud, CI templates, deployment, observability, security, release, and migration configuration. |
| `docs/` | Published docs, lifecycle-managed plans, ADRs, runbooks, and archived evidence. |
| `schemas/` | JSON Schema and generated-schema source contracts. |
| `frontend/` | Frontend workspaces and generated-client consumers. |
| `data/` | Committed fixtures, tiny examples, contracts, manifests, and registry entries only. |
| `design/` | Product-level design concepts and implementation handoff assets. |
| `.polisyos/` | Ignored local runtime state, caches, temporary outputs, and operator scratch state. |

## Tools

Active top-level tool namespaces are limited to:

- `tools/lib`
- `tools/devx`
- `tools/ci`
- `tools/ops`
- `tools/quality`
- `tools/research`
- `tools/design`

Facade files at `tools/cli.py` and `tools/registry.py` remain the public CLI
boundary. Phase 1D compatibility shims may remain until 2026-09-01 under:

- `tools/architecture`
- `tools/connectors`
- `tools/foundry`
- `tools/migrations`
- `tools/demos`

Deprecated compatibility code may exist only under `tools/archive/` with a
registered owner, reason, target, and sunset rule. New commands should be
registered in `tools.registry` and exposed through `polisyos-tools` rather than
through product-root shell scripts.

## Tests

The physical test taxonomy is:

| Path | Use |
| --- | --- |
| `tests/architecture` | Repository contracts, topology, import/public-surface policy, closeout gates. |
| `tests/unit/<package>` | Unit tests mirroring `src/polisyos/<package>`. |
| `tests/property` | Hypothesis, invariants, and property-style contract checks. |
| `tests/contract` | Cross-package contract fixtures and compatibility evidence. |
| `tests/integration` | Multi-component integration coverage. |
| `tests/e2e` | End-to-end product flows. |
| `tests/golden` | Golden, replay, and differential baselines. |
| `tests/performance` | Benchmarks and performance regressions. |
| `tests/tools` | Tooling behavior and command integration. |
| `tests/lint` | Lint policy tests. |
| `tests/fixtures` | Reusable committed fixture material. |
| `tests/unit/data_forge` | Data Forge fixture and artifact behavior. |

## Ops

`ops/` is the only product-root home for operational configuration:

| Path | Use |
| --- | --- |
| `ops/cloud/gcp` | GCP-specific cloud configuration and deployment assets. |
| `ops/cloud/helm` | Helm charts and values. |
| `ops/cloud/terraform` | Terraform modules and environment contracts. |
| `ops/docker` | Container build/runtime assets. |
| `ops/deploy` | Deployment manifests and release handoff material. |
| `ops/observability/grafana` | Dashboards. |
| `ops/observability/prometheus` | Prometheus rules and scrape policy. |
| `ops/observability/otel` | OpenTelemetry baselines. |
| `ops/observability/slo` | SLO and error-budget configuration. |
| `ops/policy` | OPA/Rego policy and policy-test material. |
| `ops/release` | Release fragments, commit policy, signing, and release contracts. |
| `ops/runtime` | Runtime API and service contract material. |
| `ops/migrations` | Migration forward/rollback contracts. |
| `ops/security` | Secrets, dependency, SBOM, and security baseline configuration. |

## Docs

Published docs use Diataxis-style homes:

| Path | Use |
| --- | --- |
| `docs/index.md` | Public handbook landing page. |
| `docs/reference/` | Stable factual reference, inventories, and contracts. |
| `docs/how-to/` | Task-oriented operational guides. |
| `docs/runbooks/` | Incident and rollback procedures. |
| `docs/tutorials/` | Learning paths. |
| `docs/explanation/` | Architecture rationale. |
| `docs/adr/` | Accepted decisions and supersession notes. |
| `docs/plans/active/` | Work that is still under review or implementation. |
| `docs/plans/accepted/` | Approved plans with active implementation or accepted closeout evidence. |
| `docs/archive/plans/` and `docs/archive/reports/` | Historical plans, reports, and baseline evidence. |

The top-level `docs/` directory remains minimal and allowlisted. New audits,
plans, handoffs, and closeout evidence should not land in the docs root.

## Local State

Bulk data and local runtime outputs stay outside committed product state:

- `data/` is allowlist-committed: tiny reviewed fixtures and registry entries
  may be tracked, while local bulk outputs under `data/policy-engine-local/`
  remain ignored;
- `.polisyos/` under `policy-engine/` is the only canonical local runtime
  state root and is governed by `architecture/local_runtime_state.toml`;
- generated outputs must either be registered in
  `architecture/generated_artifacts.toml` or ignored by the documented local
  output policy.

## Validation

Use these gates when topology, docs, tools, ops, data, or generated-artifact
surfaces change:

```bash
uv run pytest tests/architecture/test_repository_sota_phase3_topology_cleanup.py -q
uv run pytest tests/architecture/test_repository_public_polish.py -q
uv run polisyos-tools workspace repository-sota-closeout --contract-only
uv run polisyos-tools workspace repository-sota-closeout
uv run polisyos-tools docs --output docs/reference/tools.md --check
uv run mkdocs build --strict
```
