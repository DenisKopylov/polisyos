# Repository SOTA Phase 4 Generated, Frontend, Data, And Ops Discipline

Status: implemented as report-only discipline on 2026-05-03.

## Scope

Phase 4 closes non-Python governance gaps without moving source topology:

- tracked generated clients, types, lockfiles, reports, schema outputs, SBOMs,
  frontend outputs, data fixtures, local data, runtime state, and ops baselines
  are registered or explicitly ignored;
- frontend workspaces have owners, build/test commands, schema drift commands,
  and generated-output ignore rules;
- product-root `data/` contains allowlisted committed data and ignored local
  medallion/policy-engine-local data;
- `.polisyos/` runtime state is ignored, retention-classed, and cleanable;
- observability, security, release, runtime, and migration baselines are
  captured under `ops/`.

## Evidence

| Area | Evidence |
| --- | --- |
| Generated registry | `architecture/generated_artifacts.toml` plus regenerated `docs/reference/generated-artifacts.md` |
| Frontend contract | `architecture/frontend_workspaces.toml` and `docs/reference/frontend/workspace-contract.md` |
| Data policy | `architecture/data_policy.toml` and `docs/reference/data-lake-policy.md` |
| Runtime state | `architecture/local_runtime_state.toml` and `docs/reference/local-runtime-state.md` |
| Ops baselines | `architecture/ops_baselines.toml` and `docs/reference/operations/ops-baselines.md` |
| Security/release configs | `ops/security/secrets-baseline.toml`, `ops/release/*.toml` |
| OTel/runtime configs | `ops/observability/otel/baseline.yaml`, `ops/runtime/runtime-contracts.toml` |
| Migration contract | `ops/migrations/migration-contracts.toml` |
| Acceptance test | `tests/tools/test_repository_sota_phase4_discipline.py` |

## Acceptance Notes

- Generated artifacts are reproducible through registered commands or
  explicitly marked `local_ignored` / `manual_review`.
- Frontend generated outputs are ignored unless promoted to a registered
  committed baseline.
- Local data and `.polisyos/` runtime state are ignored and documented with
  cleanup commands.
- Release, security, observability, runtime, and migration checks have
  report-only baseline configs ready for Phase 5 enforcement.
