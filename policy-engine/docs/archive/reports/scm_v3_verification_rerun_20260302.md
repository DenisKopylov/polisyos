# SCM v3 Full Verification Rerun (2026-03-02)

- Generated (UTC): 2026-03-02T18:43:41Z
- Workspace: /Users/deniskopylov/polisyos/policy-engine
- Base run log: docs/reports/_logs_rerun_20260302_203535

## Summary

- Structured checks from rerun `run_status.tsv` (well-formed rows):
  - PASS: **66**
  - FAIL: **0**
  - BLOCKED: **0**
- Result: **no blockers in phase/law/SL execution checks from this rerun**.

## Environment sync (full-run profile)

Executed:

- `uv sync --group dev --extra causal --extra causal-discovery --extra kuzu --extra analytics --extra sensitivity --extra academic-skg`
- `uv sync --group dev --extra causal --extra causal-discovery --extra kuzu --extra analytics --extra sensitivity --extra academic-skg --extra multi-tenant`

Installed critical optional deps used in phase verification: `kuzu`, `tigramite`, `fastapi`.

## Post-sync targeted rechecks

- `tests/ir/test_causal_graph_kuzu.py` -> PASS (`....`)
- `tests/foundry/methods/catalog/causal/test_pcmci_discovery.py` -> PASS (`.....`)
- `tests/foundry/methods/catalog/causal/test_transport_check.py` + `tests/scientist/governance/test_transportability_required_pass.py` -> PASS (`............`)
- `tests/runtime/http/test_timeline_api.py::test_run_lineage_endpoint_returns_dependency_graph` -> PASS (`.`)

## Backlog B readiness verdict

- **B.1 DAGMA (LOW): READY** - discovery contracts/registry are green and extension point is present under `causal.discovery`.
- **B.2 Phase 12b y0 (MEDIUM): READY** - simplified transportability baseline and Law T gating checks are green.
- **B.3 orjson serialization (LOW): READY** - codebase has many `model_dump/json.dumps` hot paths; optimization can be added without contract change.
- **B.4 JAX CI vectorization (MEDIUM): READY** - discovery baseline passes with `tigramite`; JAX runtime is already in project dependencies.
- **B.5 Transport loop caching (HIGH): READY** - clear insertion point exists in `TransportabilityResolutionLoop` for deterministic per-run memoization.

## Notes

- Existing files `docs/reports/scm_v3_verification_matrix.md` and `docs/reports/scm_v3_verification_evidence.json` were generated before this rerun and should be treated as historical baseline.
