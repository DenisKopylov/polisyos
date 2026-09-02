# Debt Group A — drift detection and actionable measurement

Date: 2026-09-02  
Branch: `codex/debt-group-a-drift-detection`  
Base: `fac07ffc6`

This journal is append-only. `docs/plans/active/` was read for the five binding
closure signals and is not edited by this task.

## Provisioning receipt

- The provisioned worktree had neither `.venv` nor `node_modules`. Offline `uv sync`
  could not resolve uncached `jaxlib==0.8.2`, so the empty environment was preserved
  under ignored `_build/.tmp/debt-a2-empty-venv` and `.venv` was linked to the main
  checkout's Python 3.14 lock environment. This is a tooling non-receipt, not a
  product verdict.
- `corepack pnpm install --frozen-lockfile --ignore-scripts` completed from the
  frozen lockfile. All comparisons in this task use that same Python environment,
  local `node_modules`, and the provisioned read-only `production_data` link.
- Runtime invocations pin `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
  `PYTHONHASHSEED=0`, `JAX_PLATFORMS=cpu`, and `PYTHONPATH=src:.`.

## Seam 2 — owner-validator timeout classification and measured ceiling

Pattern pass: P37/P38 apply to the failure classifier. The property is whether the
owner rejected the source; the old implementation tested whether the child returned
a receipt before a stopwatch expired. Those predicates diverge when a healthy child
crosses 120 seconds.

Positive control before RED:

- Exact node
  `tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py::test_real_owner_artifact_reaches_available_domain_projection`
  passed unchanged. `/usr/bin/time -p` reported `real 216.91`, `user 180.49`,
  `sys 8.38`; the node returned an available owner-admitted packet. This whole-node
  time is context only, not substituted for the child measurement.
- The debt-register measurement at `docs/plans/active/DEBT-REGISTER.md:324` records
  the healthy serialized owner-validator child at 92 seconds. The committed timing
  catalog now admits that literal as `owner-validator:default`, labels its regime
  `serialized`, and derives the executable ceiling as `2 × 92 = 184` seconds.

Accepted RED:

- Two exact nodes failed: the timeout test because
  `OwnerValidationTimeoutError` did not exist, and the budget test because the
  `owner-validator:default` measurement lane did not exist.

Implementation and GREEN:

- `subprocess.TimeoutExpired` is no longer converted to
  `ProjectionSourceValidation(status="failed")`. It raises the typed operational
  `OwnerValidationTimeoutError`, carrying the projection id and the 184-second
  measured ceiling. `OSError` and completed owner-validator failures retain their
  existing fail-closed governance paths.
- The DS17 OpenAPI example propagates that typed timeout unchanged. Its exception
  says `timed out` and cannot say `owner-admitted`; no second resolution is needed
  to learn which clock failed.
- Three focused behavioral nodes passed. The two focused timing-catalog tests also
  passed, including the source-excerpt binding for the 92-second sample. Targeted
  Ruff and `git diff --check` passed.

