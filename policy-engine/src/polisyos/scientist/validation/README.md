# Validation (`polisyos.scientist.validation`)

## Purpose

`polisyos.scientist.validation` owns Scientist decision-grade validation:
metric diagnostics, fairness audits, phase publication preflight, decision
validity, verified-policy contracts, reliability scoring, and proof-carrying
verification.

## Where to Start

- Stable package facade: [`__init__.py`](__init__.py)
- Decision lifecycle validity: [`decision_validity.py`](decision_validity.py)
- Verified policy models and services: [`policy_verified/`](policy_verified/)
- IC and implementation-conformance verification: [`verification/`](verification/)
- Metric and fairness validation: [`metrics.py`](metrics.py), [`benchmarks.py`](benchmarks.py), and [`fairness_audit.py`](fairness_audit.py)

## Compatibility

The old first-level packages `polisyos.scientist.decision_validity`,
`polisyos.scientist.reliability_scorecard`, `policy_verified`, and
`verification` were removed after reaching zero non-compat callers. New code
should import from this validation hub.

## Common Commands

Run from the repository root (`policy-engine/`).

- Import smoke: `uv run python -c "from polisyos.scientist.validation import DecisionValidityService, PolicyRequestFrame, verify_incentive_compatibility; print(DecisionValidityService.__name__, PolicyRequestFrame.__name__, callable(verify_incentive_compatibility))"`
- Focused validation tests: `uv run pytest tests/unit/scientist/validation tests/unit/scientist/governance/test_ic_verification.py tests/unit/scientist/governance/test_ic_conformance.py -q`

## Last Updated

- Last updated: 2026-05-05
