# ADR-0075: EconML/CATE: heterogeneous effects via DML, Causal Forests (Phases 2/11)

## Status
Proposed

## Date
2026-02-28

## Context
Phases 2 and 11 require estimation of heterogeneous treatment effects (HTEs) to answer
the policy question "for whom does the intervention work best?" Average treatment
effects (ATEs) mask critical distributional variation: a universal basic income may
raise mean welfare while harming a vulnerable subgroup. DoWhy's `estimate_effect`
supports a limited set of HTE estimators, but Microsoft's EconML library provides a
comprehensive suite purpose-built for conditional average treatment effects (CATEs):
Double Machine Learning (DML), Causal Forests, Doubly Robust Learners, and
Meta-Learners (S/T/X).

## Decision
1. Add `econml` as a required dependency (it already shares the DoWhy ecosystem and
   is co-maintained by Microsoft Research).
2. Register four new catalog entries under `foundry/methods/catalog/causal/`:
   `dml_cate`, `causal_forest_cate`, `dr_learner_cate`, and `metalearner_cate`.
3. Each entry implements the `CausalEstimatorProtocol` and returns an `HTEResult` IR
   artifact containing CATE point estimates, confidence intervals, and SHAP-based
   feature importance for effect modifiers.
4. The `CausalEvaluationNode` selects the HTE estimator when the `ProblemFrame`
   specifies `effect_modifier_variables` (non-empty list).
5. Governance pass `SensitivityPass` is extended to run `EconML.refute_estimate` with
   the placebo and subset refuters on HTE outputs.

## Consequences
### Positive
- Enables subgroup-level policy targeting, directly supporting equity analysis.
- EconML's DML handles high-dimensional confounders with any scikit-learn model.
- Tight integration with DoWhy's causal graph ensures identification is checked before
  estimation.
### Negative
- EconML pulls in scikit-learn, scipy, and lightgbm as transitive dependencies,
  increasing install size.
- CATE confidence intervals from Causal Forests require honest splitting, which halves
  effective sample size.
- HTE results are harder to communicate to non-technical policy stakeholders than ATEs.
