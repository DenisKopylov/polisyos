# Calibration Governance
Related explanation: [Governance Model](../../explanation/governance-model.md).

Calibration governance extends the base validation pipeline with observation-family policy mapping, adversarial challenge suites, backtest matrices, stress scenarios, and leaderboard rollups.

## Module Map

| Module | Responsibility |
|--------|----------------|
| `accountability` | Unified calibration/fairness/risk artifact with threshold registry and escalation policy |
| `backtest_matrix` | Execute standardized backtest suites across multiple runtime surfaces |
| `calibration` | Main calibration governance runner, family-level pass mapping, adversarial suites, lesson publication |
| `calibration_leaderboard` | Rank calibrated candidates with shared metrics |
| `calibration_validation` | Persist and reload validation bundles around calibration runs |
| `stress_scenarios` | Compare candidate robustness under macro and procurement shocks |

## WS-3B Accountability Surface

Calibration validation now emits a first-class governance accountability
artifact alongside the replay bundle. That artifact keeps the following claims
audit-visible on the default path:

- Brier score, log score, reliability bins, and ENCE
- calibration-by-group and fairness-aware calibration gaps
- equalized odds, intersectional slices, and counterfactual fairness summary
- adaptive threshold selection with fairness-accuracy frontier
- CVaR / tail-risk drift and human-escalation triggers

Reference: [governance-accountability.md](governance-accountability.md)

## Backtest Kinds

| Kind | Semantics |
|------|-----------|
| `MACRO` | Aggregate macro backtests over system-wide indicators |
| `CELL` | Cell-level spatial or sectoral outcome replay |
| `STRATEGIC_AGENT` | Agent behavior under strategic-response assumptions |
| `HOUSEHOLD` | Household distribution and welfare replay |
| `DISTRESS` | Distress and failure-signal replay for downside control |

## Stress Scenario Kinds

| Kind | Semantics |
|------|-----------|
| `BUDGET_CONTRACTION` | Tests resilience when public budget room shrinks |
| `PROCUREMENT_SHOCK` | Tests procurement graph disruptions and supplier stress |
| `WAGE_SUBSIDY` | Tests labor-support intervention sensitivity |
| `FX` | Tests exchange-rate movement against imported-cost channels |
| `TRADE_DISRUPTION` | Tests supply and demand dislocation from trade breaks |
| `REIMBURSEMENT_TARIFF` | Tests tariff / reimbursement rule changes against fiscal exposure |

## API Reference

::: polisyos.scientist.governance.backtest_matrix

::: polisyos.scientist.governance.accountability

::: polisyos.scientist.governance.calibration

::: polisyos.scientist.governance.calibration_leaderboard

::: polisyos.scientist.governance.calibration_validation

::: polisyos.scientist.governance.stress_scenarios
