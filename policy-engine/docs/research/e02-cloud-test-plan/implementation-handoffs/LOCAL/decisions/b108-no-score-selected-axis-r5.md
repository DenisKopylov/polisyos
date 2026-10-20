# B108 R5 selected-axis admission and configured-source evaluation

Status: author candidate for independent G review. No formal acceptance or closure is asserted.

## Property and P40 bucket

This is the same B108 score-availability/admission class, one level deeper under P40. R4 bound objective rules and rejected contradictory fiscal aliases, but independent review showed that vector consumers still required an unrelated scalar aggregate, and producer/replay paths disagreed on whether a null primary alias permits a valid alternate. R5 widens the mechanism to the configured objective quantity: one source evaluator plus one consumer-selected admission predicate.

A candidate's execution feasibility and score availability are separate. Successful execution and Stage A pass do not establish a scalar score. A scalar consumer requires a recomputed scalar assessment bound to its selected rule and value. A multi-objective consumer requires every configured axis and rule, and no extra axes; it does not require an unrelated scalar aggregate. Missing, invalid, or rule-mismatched selected inputs remain unranked and excluded from numeric training.

## Reuse-first alternatives

1. **Keep `Evaluation.is_valid` as the universal objective gate.** It depends on a scalar assessment. A valid selected GDP-only or multi-axis evaluation with no unrelated aggregate is incorrectly dropped by MO training, Pareto, and hypervolume. Rejected.
2. **Patch each reader's fiscal/null parser or add a local MO exception.** That repeats producer/replay semantics and leaves the next score reader open. Rejected under P40.
3. **Reuse one configured source evaluator and the existing selected-rule check (candidate).** Producer evaluation, scalar metric evaluation, and persisted source reconciliation enter `_evaluate_configured_objective_source`. It resolves the selected source operands once and evaluates the existing rule. `_evaluation_matches_selected_objectives` independently checks successful execution, the exact selected axis set, rule/direction/source agreement, and scalar-carrier agreement only for scalar consumers. Transfer and hierarchy use their persisted/configured rule maps; MO uses its selected axis map. This changes only availability/admission, not scientific authority.
4. **Add a new score authority artifact or objective framework.** Rejected: existing `ObjectiveScoreAssessment`, `ObjectiveValue`, and configured objective rule are the source of truth; another artifact would add a new writer, bridge, and migration without closing a different property.

## Fiscal source semantics and limits

Under the original B108 fallback contract, a null fiscal alias means that alias is absent. A valid non-null alternate may supply the selected value. A malformed non-null value is invalid even when another alias is valid. When both balance and deficit groups contain values, the existing transforms are reconciled; a conflict is invalid rather than silently preferred. A measured zero remains available. The evaluator adds no unit conversion, precedence, imputation, weights, calibration, legal authority, or production-currentness claim. Numeric agreement cannot establish that two externally supplied aliases use comparable units; that limitation remains explicit for G.

## Persistence, migration, and consumers

Transfer schema 4 continues to bind exact selected names, directions, and canonical rule specs. A schema-4 vector row may carry valid per-objective assessments with `scalar_score: null`; it is admitted only when the consumer's complete selected basis recomputes. A single-axis scalar consumer additionally requires its scalar score and scalar assessment to equal the selected axis. Schema 3 rows without selected-rule identity remain diagnostic-only; they are not rebound from their own assessments.

The shared selected-basis predicate covers MO training, objective-vector construction, Pareto and hypervolume, transfer registration/restore/sort, scalar warm-start and Benchmark projection, hierarchical candidate-only transfer, and Bayesian scalar training. The scalar Bayesian adapter derives its selected metric rule from the generator's configured metric and source direction; callers cannot inject an independent rule string. Its independent source-profile verifier reconstructs rows from the selected BenchmarkEvaluation split and replays that same rule before fitting. The typed MethodJob run profile binds the actual configured unit into the objective compatibility fingerprint before warm-start or candidate fitting; changing metric, direction, rule, or declared unit prevents profile reuse. An absent unit is retained as unknown and does not imply a conversion or measurement authority; reported MethodJob units must equal the selected run unit before the score can be admitted. Bayesian checkpoint metadata carries the exact selected binding and rejects continuation data from another binding.

Direct BayesianOptimizer use without a configured selection remains a generic numeric candidate-search contract: successful finite caller-supplied values may guide candidate exploration, but that route has no configured objective claim and cannot produce a reusable configured native-GP profile. Configured policy search always supplies its selected metric rule, so missing, legacy, or self-labeled rows cannot enter its scalar training or warm-start corpus. The generator's SearchMethodRunProfile must match the constructor binding.

Hierarchical transfer also reconciles its RunFingerprint objective names, directions, and rules with the current selected ObjectiveStack before reevaluating the candidate. Existing public exports are preserved; the public-surface inventory refresh remains with the root owner.

## Verification and falsifiers

The candidate adds controls for: GDP-only MO selection with no scalar aggregate; exact axis-set rejection; no-score candidate removal while a valid sibling remains rankable; selected GDP and employment objectives through transfer CAS write, fresh read, and MO training-vector construction with no scalar aggregate; selected-rule mismatch refusal at transfer; custom labels accepted only when the selected configured rule matches; null primary plus valid alternate; all-null unavailable; malformed primary and alternate invalid; cross-group conflicts invalid; true zero valid; source mutation rejected; and Bayesian scalar selection with both maximize/minimize normalization, a same-label GDP assessment rejected by the selected fiscal rule, custom metric labels retained, caller-supplied rule injection rejected, actual MethodJob run-profile unit mutation rejected, reported-output unit mismatch refused at the MethodJob→BenchmarkEvaluation boundary, and source mutation after admission rejected.

Native Ruff and formatter checks are source-only and must be rerun on the final candidate. The focused objective-availability and Bayesian generator/source-verifier module replays, filesystem CAS integration test, canonical public-surface regeneration, installed consumers, and composed closeout replay are UNRUN pending independent R5 review and the root's serialized runtime slot. `closure_ids` is empty; `B108` remains a proposal for G adjudication.

## G decision requested

Confirm the scalar-versus-vector admission boundary and null-as-absent fiscal fallback semantics, or identify the existing repository contract that should replace either. If unit-aware alias reconciliation is required, name the typed unit/context source and owner; this candidate does not infer it from a key name or a numeric coincidence.
