# Repository SOTA Phase 5 Closeout

Freshness: 2026-05-03
Owner: `team-architecture`
Source of truth: `architecture/gates/repository_sota.toml`,
`tools/devx/workspace/repository_sota_closeout.py`,
`architecture/shims.toml`,
`architecture/exceptions/complexity.toml`, and
`architecture/baselines/ops.toml`

Public reference: `docs/reference/repository-topology.md`

## Status

Repository SOTA Phase 5 promotes the repository policy layer from documented
intent to fail-closed practice and records the final clean-cut topology. The
closeout command is:

```bash
uv run polisyos-tools workspace repository-sota-closeout
```

The lighter pre-commit and fast-CI contract command is:

```bash
uv run polisyos-tools workspace repository-sota-closeout --contract-only
```

## Final Topology

The implemented topology keeps active GitHub workflows at the repository root
and product workflow templates under `ops/ci/templates/`. Product-root
`.github`, `cloud_deploy`, `deploy`, `docker`, `gcp`, and `scripts` have been
removed. Domain code is routed through the layered package model and Data Forge
owns build-time artifact surfaces.

Duplicate top-level `tools/*` namespaces have been retired from the active
surface. Canonical commands live under `tools/devx`, `tools/ops`,
`tools/quality`, `tools/research`, `tools/architecture`, `tools/ci`,
`tools/connectors`, `tools/data_forge`, `tools/foundry`, `tools/migrations`,
`tools/demos`, `tools/lib`, and `tools/archive`.

Local data and runtime state are governed by `architecture/policies/data.toml`
and `architecture/local_runtime_state.toml`. Committed generated artifacts,
frontend clients, SBOM policy, operational baselines, and release policy are
registered under `architecture/generated_artifacts.toml`,
`architecture/frontend_workspaces.toml`, and `architecture/baselines/ops.toml`.

## Fail-Closed Gates

| Gate | Contract | Enforcement |
| --- | --- | --- |
| Topology and loose files | `architecture/topology.toml` | `tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py` |
| Import policy | `architecture/imports/policy.toml`, `architecture/imports/exceptions.toml` | `tools/quality/lint/lint_imports.py` |
| Public surface | `architecture/public_surface/contract.toml` | `polisyos-tools architecture guardrails check` |
| Generated drift | `architecture/generated_artifacts.toml` | `polisyos-tools architecture guardrails check --run-generated-checks` |
| Docs freshness | `architecture/exceptions/docs_freshness.toml` | `polisyos-tools workspace repository-sota-closeout` |
| Public polish | `docs/reference/repository-topology.md` | `pytest tests/repo_quality/architecture/test_repository_public_polish.py` |
| Shim audit | `architecture/shims.toml` | `polisyos-tools workspace repository-sota-closeout --contract-only` |
| Complexity exceptions | `architecture/exceptions/complexity.toml` | `polisyos-tools workspace repository-sota-closeout --contract-only` |
| Security and dependencies | `ops/security/*.toml` | `polisyos-tools workspace repository-sota-closeout --contract-only` |
| SBOM | `ops/security/sbom.toml` | `polisyos-tools workspace repository-sota-closeout --contract-only` |
| Commit policy | `ops/release/commit-policy.toml` | `polisyos-tools workspace repository-sota-closeout --contract-only` |
| Command registry | `tools.registry`, `docs/reference/tools.md` | `polisyos-tools docs --output docs/reference/tools.md --check` |

## Remaining Exceptions

Remaining import and complexity exceptions are explicit and reviewable:

- Import exceptions remain in `architecture/imports/exceptions.toml` with owner, reason,
  source glob, and expiry.
- Complexity exceptions remain in `architecture/exceptions/complexity.toml`
  with concrete source paths, owner, reason, remediation, and expiry.
- Docs freshness uses `architecture/exceptions/docs_freshness.toml` as a
  time-bounded baseline while historical published-doc metadata debt is burned
  down.

## Retired Shims

Clean-cut topology shims were retired on 2026-05-03 because their source paths
no longer exist:

- `nested-github-to-root-github`
- `root-cloud-deploy-to-ops-cloud`
- `root-deploy-to-ops-deploy`
- `root-docker-to-ops-docker`
- `root-gcp-to-ops-cloud-gcp`
- duplicate `tools/*` namespace shims for benchmarks, calibration, cloud, data,
  diagnostics, lint, release, runtime, testing, Ukraine data, validation, and
  workspace.

`architecture/shims.toml` now contains only shims whose source path
physically exists or whose file-relocation evidence is still reviewable.

## CI And Pre-Commit Wiring

Fail-closed wiring is present in:

- `.github/workflows/abi.yml`
- `policy-engine/.pre-commit-config.yaml`
- `ops/ci/templates/workflows/arch.yml`

The root fast PR workflow runs the contract-only closeout gate in Python
quality and the docs-freshness baseline in docs quality. The reusable
architecture template runs the full closeout command after generated and
frontend drift checks.

## Follow-Up Backlog

| Follow-up | Owner | Due |
| --- | --- | --- |
| Burn down the docs freshness baseline and set `expected_violation_count = 0`. | `team-docs` | 2026-06-30 |
| Remove import exceptions whose expiry dates arrive in July 2026. | owning package teams | 2026-07-30 |
| Add generated ADR index validation after ADR front matter is normalized. | `team-architecture` | 2026-09-01 |
