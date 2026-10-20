# B108 R7 — selected score source projection and terminal completion

Status: author candidate for independent review; no formal closure claimed.

## Same-class review findings

The R6 review found two B108/P40 escapes in the selected-score source/admission invariant. `PredictiveVOIScheduler.observe_stage_result` first recomputed a score from its complete source, then projected `source_field_names` by looking up each full string as a top-level key. For a valid source such as `simulation_results.gdp_change = 0.0` plus `metric_units.gdp_change = "fixture-unit"`, that projection dropped the nested unit map; `VOIObservation` then rejected the otherwise valid assessment when it replayed the persisted basis. Separately, `FunnelOrchestrator.advance` required an available selected score for `terminal_action="complete"` only when an assessment object existed. A stage with no assessment/value and `NOT_ESTABLISHED` could therefore set the direct `FunnelOutcome.final_action` to `complete`, while a later compatibility projection showed `DEFER`.

These are the same B108 basis/admission class, not independent instance defects. R7 widens the shared path projection to preserve exact selected source paths through the root, `simulation_results`, and `metrics` envelopes, including nested mappings. VOI admission replays the projection before persisting it; a projection that cannot reproduce the assessment demotes the sample to `NOT_ESTABLISHED`. For selected policy-vector channels, the projection retains only the selected vector channel plus its declared simulation source paths.

The terminal action gate now requires `AVAILABLE` from the source-recomputed selected assessment for every `complete` action, irrespective of whether an assessment was supplied. Missing or unavailable basis defers; invalid/conflicting basis rejects; a source-bound genuine zero remains available. Candidate-only continuation remains distinct from terminal recommendation.

## Contract choices

R7 reuses `ObjectiveScoreAssessment.source_field_names` as the projection source of truth and extends its interpretation to nested mapping paths. This keeps persistence bounded to selected operands and preserves the source shape required by existing recomputation. Retaining the entire simulation payload was considered and rejected because unrelated inputs would be copied into VOI history. A one-off `metric_units` special case was rejected because future selected nested fields would repeat the same defect.

The direct `BayesianOptimizer` API without a configured selected objective remains a generic candidate-only API per the independent R6 source-call census. It must not produce policy admission, ranking, promotion, or publication. Product constructors in `BayesianCandidateGenerator`, source-profile verification, and multi-objective policy-vector search bind their selected configuration. This exclusion is bounded to standalone callers and tests; it is not an alternative policy-score authority.

## Discriminators and verification

The added VOI cases keep a zero GDP score, a nested selected unit, a result envelope, and unrelated payload; the snapshot retains only the selected basis and survives validation. Removing or changing the nested unit demotes the persisted score. A malformed selected unit remains `INVALID` through round-trip instead of being reinterpreted as absent. A policy-vector VOI control retains only its selected channel and source paths, including the nested selected unit, and survives snapshot replay. Funnel tests retain the existing unavailable-score and valid-zero routes and add a stage that supplies `complete` with no score assessment/value while leaving an `APPROVE` feedback marker; the direct outcome and compatibility projection must defer.

The R7 RAW candidate has not run runtime tests, persistence suites, an installed wheel, or a rebuilt sdist. Those checks require independent review and the composed runtime slot. The selected policy-vector production unit source remains unavailable, so those policy-vector scores stay unscored. No authority, unit conversion, measurement quality, calibration, causal validity, production currentness, or publication claim is introduced. `closure_ids` remains empty; `B108` is an author proposal for G.
