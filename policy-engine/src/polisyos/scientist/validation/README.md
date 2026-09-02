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

## Epoch-validity owner intake

`DecisionValidityService` admits an epoch transition only through its configured verifier. It
reconciles the complete owner target denominator, persists the complete pending freeze before the
first packet mutation, resumes idempotently after a crash, and exposes completed evidence only by
content-bound receipt ref. Generic dependency events cannot admit or clear semantic-epoch state.
The production composition has no epoch-transition signing authority, so positive signed
transition issuance remains absent; an explicitly appointed test verifier proves the intake
mechanism without promoting that retained institutional gap.

Scientist can also persist and exact-read a strict semantic-epoch impact snapshot from the same
nullable owner walk used by the legacy denominator resolver. Strict materialization refuses a
missing or non-CAS owner artifact id without changing legacy resolver behavior. A lazy write-once
owner index is available for reconciliation admission bindings and creates no directory until a
sidecar-aware admission writes its first binding. When an explicit Runtime reader is configured,
first admission validates the exact sidecar and freezes its handle before the unchanged v1 pending
batch; restart replay resolves only that frozen handle and never consults the live owner index.
The literal `None` default preserves legacy admission, and no production reader is appointed yet.

## Common Commands

Run from the repository root (`policy-engine/`).

- Import smoke: `uv run python -c "from polisyos.scientist.validation import DecisionValidityService, PolicyRequestFrame, verify_incentive_compatibility; print(DecisionValidityService.__name__, PolicyRequestFrame.__name__, callable(verify_incentive_compatibility))"`
- Focused validation tests: `uv run pytest tests/unit/scientist/validation tests/unit/scientist/governance/test_ic_verification.py tests/unit/scientist/governance/test_ic_conformance.py -q`

## Last Updated

- Last updated: 2026-05-05
