# ADR-0020: Robustness Modes (Sensitivity + Stress Test) (Phase 13)

## Status
Proposed

## Context

Phase 13 adds robustness analysis capabilities:

1. Sensitivity analysis (Morris/Sobol/FAST) to rank influential parameters.
2. Stress/adversarial testing to discover worst-case behavior and vulnerabilities.

The project already has:

- DoE placeholders (`SensitivityPlan`)
- Search controller with flexible objective/stopping abstractions
- CAS-backed artifact flow and DecisionPacket assembly

but no production-ready robustness engine.

## Decision

1. Expand `scientist.doe.designs` with:
   - `ParameterSpec`
   - `SensitivityPlan` guardrails (`estimated_runs`, `max_estimated_runs`, failure policy)
   - `SensitivityResult`
   - `AdversarialPlan`
2. Add SALib-backed modules:
   - `scientist.doe.sampling`
   - `scientist.doe.analysis`
3. Add stress reporting contract:
   - `scientist.doe.stress_report` (`StressTestReport`, `Vulnerability`)
4. Extend search integrations:
   - `SensitivityAwareCandidateGenerator`
   - adversarial objective wrapper (`NegatedCompositeObjective`)
   - stress orchestrator (`run_stress_test`)
5. Add CLI entries:
   - `polisyos scientist sensitivity run --config ...`
   - `polisyos scientist stress-test --config ...`

Artifacts:

- `scientist.sensitivity_result`
- `scientist.stress_test_report`

Typed refs added to `core.contracts.scientist`:

- `SensitivityResultRef`
- `StressTestReportRef`

## Key Design Notes

- Large sensitivity batches are blocked by default unless explicitly overridden.
- Failed simulation runs are handled by explicit policy:
  `fail_fast | drop_failed | impute_baseline`.
- Stress mode supports both "stop at first vulnerability" and "collect risk landscape".

## Consequences

### Positive

- Robustness becomes first-class in Scientist outputs and DecisionPacket.
- Reuses existing Search infrastructure instead of introducing another optimizer stack.
- Enables predictable compute behavior via DoE guardrails.

### Negative

- Optional dependency on SALib/scipy for full sensitivity functionality.
- Sobol analysis cost remains high for large parameter sets.

## Alternatives Considered

1. Build custom Morris/Sobol implementation: rejected (validation and maintenance burden).
2. Separate stress optimizer subsystem: rejected (duplicates Search logic).

