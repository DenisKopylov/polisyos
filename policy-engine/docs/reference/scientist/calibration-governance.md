# Calibration Governance
Related explanation: [Governance Model](../../explanation/governance-model.md).

Calibration governance extends the base validation pipeline with observation-family policy mapping, adversarial challenge suites, backtest matrices, stress scenarios, and leaderboard rollups.

## Module Map

| Module | Responsibility |
|--------|----------------|
| `backtest_matrix` | Execute standardized backtest suites across multiple runtime surfaces |
| `calibration` | Main calibration governance runner, family-level pass mapping, adversarial suites, lesson publication |
| `calibration_leaderboard` | Rank calibrated candidates with shared metrics |
| `calibration_validation` | Persist and reload validation bundles around calibration runs |
| `stress_scenarios` | Compare candidate robustness under macro and procurement shocks |

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

::: polisyos.scientist.governance.calibration

::: polisyos.scientist.governance.calibration_leaderboard

::: polisyos.scientist.governance.calibration_validation

::: polisyos.scientist.governance.stress_scenarios
