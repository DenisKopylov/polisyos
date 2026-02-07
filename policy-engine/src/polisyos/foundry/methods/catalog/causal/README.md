# Causal Method Catalog

Phase 12 causal inference methods implemented on NUMPY backend:

- `synthetic_control` (`SyntheticControlMethod`)
- `difference_in_differences` (`DifferenceInDifferences`)
- `regression_discontinuity` (`RegressionDiscontinuity`)
- `structural_time_series` (`StructuralTimeSeries`)
- `causal_forest` (`CausalForestEstimator`, optional `econml`)
- `double_ml` (`DoubleMachineLearning`, optional `econml`)
- `meta_learner` (`MetaLearnerEstimator`, optional `econml`)
- `policy_tree` (`OptimalPolicyLearner`, optional `econml`)

Key contracts:

- Input data models:
  - `PanelObservationalData`
  - `HTEObservationalData`
  - `RDDObservationalData`
- Output model:
  - `polisyos.ir.causal.CausalEffectReport`
- Optional uncertainty integration:
  - `CausalEffectReport.to_uncertainty_envelope()`

All methods:

- run via `MethodDispatcher` + `NumpyRunner`
- declare `DeterminismTier.STATISTICAL`
- expose static assumptions in `MethodMetadata.assumptions`
- expose dynamic diagnostics in report payload.
