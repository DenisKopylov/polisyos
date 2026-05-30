# Governance (`polisyos.scientist.governance`)

## Purpose

`polisyos.scientist.governance` is the Scientist governance and accountability
layer: pre/post-flight checks, pass registry and pipeline execution, backtest
and calibration review, human oversight, continuous governance, stress
scenarios, leaderboard rollups, and audit-friendly governance artifacts used
before or after decision publication.

## Where to Start

- Stable package facade: [`__init__.py`](__init__.py)
- Pre/post-flight entrypoints: [`preflight.py`](preflight.py) and [`postflight.py`](postflight.py)
- Pass registry and pipeline semantics: [`pass_registry.py`](pass_registry.py), [`pass_entrypoints.py`](pass_entrypoints.py), and [`pipeline.py`](pipeline.py)
- Builtin pass implementations: [`passes/`](passes/)
- Continuous governance lifecycle: [`continuous/`](continuous/)
- Human review and oversight: [`human_review/`](human_review/)
- Calibration and accountability surfaces: [`calibration.py`](calibration.py), [`calibration_validation.py`](calibration_validation.py), [`calibration_leaderboard.py`](calibration_leaderboard.py), [`accountability.py`](accountability.py), and [`stress_scenarios.py`](stress_scenarios.py)

## Public Entrypoints

- `preflight_checks(...)` and `postflight_checks(...)` in [`preflight.py`](preflight.py) and [`postflight.py`](postflight.py)
- `ValidationProfile` re-exported through [`__init__.py`](__init__.py) from shared core governance profiles
- Registry and pipeline surfaces in [`pass_registry.py`](pass_registry.py) and [`pipeline.py`](pipeline.py)
- Calibration surfaces in [`calibration.py`](calibration.py), [`calibration_validation.py`](calibration_validation.py), and [`calibration_leaderboard.py`](calibration_leaderboard.py)
- Accountability/report surfaces in [`accountability.py`](accountability.py) and [`report.py`](report.py)
- Stress and backtest surfaces in [`backtest_matrix.py`](backtest_matrix.py) and [`stress_scenarios.py`](stress_scenarios.py)
- Continuous governance public contracts in [`continuous/`](continuous/) for monitor events, drift detectors, lifecycle bridges, decision validity reports, reissue packets, incidents, and withdrawals
- Human review public contracts in [`human_review/`](human_review/) for review packets, decisions, queue state, oversight policy, VOI escalation, and advisory review-effectiveness measurement

## Depends On / Depended On By

- Depends on: shared core governance profiles, observation-layer contracts, Scientist backtesting/kernel helpers, and runtime artifact/report persistence
- Depended on by: governance builtin nodes, search rollout logic, workflow launchers, and decision publication surfaces linked from [`../nodes/README.md`](../nodes/README.md) and [`../workflows/README.md`](../workflows/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.governance import ValidationProfile, preflight_checks, CalibrationValidationRunner; print(ValidationProfile.__name__, callable(preflight_checks), CalibrationValidationRunner.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/governance -q`
- Continuous governance tests: `uv run pytest tests/unit/scientist/governance/continuous -q`
- Human review tests: `uv run pytest tests/unit/scientist/governance/human_review -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/governance/test_pass_registry.py tests/unit/scientist/governance/test_validation_pipeline.py tests/unit/scientist/governance/test_accountability.py -q
```

## Reference Docs

- Governance registry reference: [`../../../../docs/reference/scientist/governance-passes.md`](../../../../docs/reference/scientist/governance-passes.md)
- Calibration governance reference: [`../../../../docs/reference/scientist/calibration-governance.md`](../../../../docs/reference/scientist/calibration-governance.md)
- Accountability artifact reference: [`../../../../docs/reference/scientist/governance-accountability.md`](../../../../docs/reference/scientist/governance-accountability.md)
- Contributor how-to: [`../../../../docs/how-to/write-governance-pass.md`](../../../../docs/how-to/write-governance-pass.md)
- Cross-package navigation: [`../README.md`](../README.md), [`../search/README.md`](../search/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-05-24
