# Run-Cost Proportionality Ledger

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/quality/cost_gate.py`, `src/polisyos/runtime/quality/scorecard.py`, `schemas/runtime_quality/policy_design_run_cost_proportionality_ledger_v1.schema.json`, and `tests/unit/runtime/quality/**`

Wave 30 closes the Policy Design Case evidence-production cost loop. Serious
runtime closeout must either emit a run-cost proportionality ledger inside
`quality_evidence/policy_design_case.json` or emit a typed run-cost blocker.

The ledger schema is
`policyos.runtime.policy_design_case.run_cost_proportionality_ledger.v1`.
The committed JSON Schema lives at
`schemas/runtime_quality/policy_design_run_cost_proportionality_ledger_v1.schema.json`.

## Ledger Inputs

The runtime producer projects the ledger from the same evidence surfaces that
feed the scorecard:

| Ledger field | Source evidence |
| --- | --- |
| `runtime_performance_budget` | canary performance budget and run performance summary |
| `foundry_cost_model` | Foundry method report cost fields |
| `scientist_budget` | Policy Design Case and synthesis run-cost evidence |
| `doe_search_budget` | multiverse, specification-curve, and search-budget case records |
| `provider_cost` | provider model quality ledger or LLM model variants |
| `elapsed_time_budget` | performance budget or runtime timestamps |
| `human_review_burden` | human review calibration report |
| `evidence_depth_budget` | authority level, public impact, heterogeneity, independent evidence count, and stopping rule |

Every component cites a runtime artifact ref. Local file paths are not valid
authority evidence for this contract.

## Evidence-Depth Rule

The evidence-depth budget is proportional to:

- authority level,
- public impact,
- observed heterogeneity,
- effective independent evidence count,
- stopping rule and stopping decision.

A stopped run with too little independent evidence fails closed unless the case
contains a valid typed blocker. High-cost low-impact runs also require explicit
proportionality evidence or a typed blocker.

## Scorecard Gate

The scorecard gate is `policy_design_wave30_run_cost_proportionality`. It
validates existing case records first. If a serious scorecard call receives
runtime/source evidence but no ledger, it attempts to project the ledger from
the quality context and validates the projected record. Producer bundles should
persist the projected record in `policy_design_case.json` so benchmarking can
compare evidence quality and evidence-production cost together.

Typed run-cost blocker records use `status: blocked`, `code`, `message`,
`evidence_ref`, and `runtime_event_ref`. They are the only acceptable substitute
for a missing ledger at the Wave 30 exit fence.
