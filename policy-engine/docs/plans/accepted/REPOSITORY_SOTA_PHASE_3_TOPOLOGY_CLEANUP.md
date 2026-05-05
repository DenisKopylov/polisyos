---
title: Repository SOTA Phase 3 Final Topology Cleanup
status: report
owner: team-polisyos
created: 2026-05-02
last_verified: 2026-05-03
stability: migration-evidence
---

# Repository SOTA Phase 3 Final Topology Cleanup

This note records the clean-cut Phase 3 closeout against
`REPOSITORY_SOTA_PLAN.md`. The final topology no longer treats product-root
legacy paths or duplicate top-level `tools/*` namespaces as active surfaces.

## Move Summary

| Surface | Final home | Owner | Evidence |
| --- | --- | --- | --- |
| Active GitHub control plane | repository-root `.github/` | `team-platform` | root workflows and CODEOWNERS |
| Product workflow templates | `ops/ci/templates/` | `team-platform` | `ops/ci/templates/**` |
| Cloud deploy assets | `ops/cloud/deploy/assets/` and `tools/ops/cloud/` | `team-ops` | `.gitignore`, cloud tool tests |
| GCP helpers | `ops/cloud/gcp/` | `team-ops` | command registry and GCP package helper |
| Docker/compose assets | `ops/docker/` | `team-ops` | `ops/docker/academic-doc-infra.compose.yml`, `ops/docker/observability.compose.yml` |
| Observability assets | `ops/observability/{grafana,prometheus,otel,slo}` | `team-observability` | `architecture/ops_baselines.toml` |
| Policy-as-code | `ops/policy/` | `team-security` | `ops/policy/policies/**` |
| Duplicate tools namespaces | `tools/{devx,ops,quality,research,...}` | owning tool teams | command registry |
| Tests topology | `tests/{architecture,unit,property,e2e,golden,...}` | owning package teams | physical test tree |
| Top-level docs | `docs/{README,index,style-guide,key-rotation}.md` only | `team-docs` | strict docs-root test |

## Clean-Cut Retirements

The following product-root surfaces were removed after their canonical targets
existed:

- `policy-engine/.github`
- `policy-engine/cloud_deploy`
- `policy-engine/deploy`
- `policy-engine/docker`
- `policy-engine/gcp`
- `policy-engine/scripts`

The following duplicate top-level tool namespaces were removed from the active
`tools/` surface:

- `tools/benchmarks`
- `tools/calibration`
- `tools/cloud`
- `tools/data`
- `tools/diagnostics`
- `tools/lint`
- `tools/release`
- `tools/runtime`
- `tools/testing`
- `tools/ukraine_data`
- `tools/validation`
- `tools/workspace`

Compatibility is now through canonical CLI commands and documentation, not
product-root wrapper directories.

## Local-State Policy

Local cloud deploy assets live under `policy-engine/ops/cloud/deploy/assets/`
and remain ignored. Local bulk data lives under product-root ignored data
paths, including `data/policy-engine-local/`; committed `data/` content is
allowlisted for tiny fixtures, manifests, registries, and gold examples only.

## Acceptance Evidence

Phase 3 final acceptance is enforced by
`tests/architecture/test_repository_sota_phase3_topology_cleanup.py`:

- topology status is `final`;
- denied loose files are checked before git-ignore exemptions;
- product-root legacy directories are absent and absent from
  `architecture/topology.toml`;
- duplicate top-level `tools/*` namespaces are absent;
- tests use the final physical taxonomy;
- ops uses the final nested layout;
- docs root markdown is allowlisted.
