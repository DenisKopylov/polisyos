---
title: Calibration Ledger
status: active
owner: team-policyos-runtime
last_verified: 2026-05-22
stability: experimental
related:
  - ../../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
  - ../../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
  - ../../reference/policy-design-case-failure-patterns.md
  - ../../../src/polisyos/runtime/quality/calibration_ledger.py
---

# Calibration Ledger

The W2.E calibration ledger is the runtime-owned schema for longitudinal
calibration history. It records realized-outcome calibration entries keyed by
domain, method family, jurisdiction, data class, evidence mode, authority
level, provider, claim family, and group slice.

The ledger's output is `policyos.runtime.calibration_ledger.v1`. Its influence
records use `policyos.runtime.historical_prior_influence.v1`.

## Authority Boundary

Historical calibration can influence future routing, review depth, uncertainty
posture, evidence budget, provider/model selection, and authority caps.

Historical calibration cannot:

- satisfy current-run claim evidence;
- refute current-run evidence;
- mint legal, data, method, or participation authority;
- hide current-run deficits;
- replace current-run producer output, typed blockers, limitations, or
  accepted deficits.

The claim registry enforces this by failing rows that place
`historical-prior-influence:*` or calibration-ledger refs in claim evidence
slots.

## Sparse History

Sparse history is transparent and non-blocking. Insufficient or thin history
may warn, require deeper review, widen uncertainty, or request extra evidence,
but it cannot automatically block a claim or backfill missing evidence.

Mature blocking requires governed config: `maturity = mature_governed`,
`blocking_enabled = true`, `policy_ref`, and `longitudinal_evidence_ref`.
Even then, the effect is a scoped future authority/routing control, not
current-run evidence closure.

## Runtime Contract

Use `build_calibration_ledger(...)` from
`polisyos.runtime.quality.calibration_ledger` to produce the ledger, then
`persist_calibration_ledger(...)` to write the CAS artifact and optional
evidence-bundle `calibration_ledger.json` surface.

Use `calibration_influence_for_scope(...)` to read the future influence record
for a target scope. The returned influence record always declares
`claim_evidence_admissible = false` and `current_run_evidence_effect = none`.

W5.C consumers use `calibration_behavior_scorecard_gates(...)` and
`calibration_behavior_deficit_records(...)` to apply the influence record to
future posture:

- sparse or thin history emits owned review posture without a closeout block;
- readiness-capped history emits a status-deficit readiness cap;
- mature scoped blocks fail scorecard/readiness only when
  `policy_design_case.calibration_mature_history_gates` is enabled through
  governed consumer policy;
- provider/model routing gates are exposed on the provider-quality surface but
  remain historical-prior influence, never claim evidence.

## Verification

Focused coverage:

```bash
uv run pytest tests/unit/runtime/quality/test_calibration_ledger.py -q
```

This test pack covers sparse-history transparency, mature governed scoped
blocks, persistence surfaces, and the anti-laundering claim-registry firewall.
