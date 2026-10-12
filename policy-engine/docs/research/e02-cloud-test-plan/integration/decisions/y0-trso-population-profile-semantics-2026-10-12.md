# Y0 TRSO population-profile semantics (open decision)

**Status:** open; this proposal does not decide what evidence or authority a production transport claim requires.

## Question

Y0 0.2.11's `identify_target_outcomes()` requires source-population outcome and intervention sets. `SelectionDiagram` carries graph nodes and selection nodes, but no population-indexed observed-variable declarations or data references. What canonical contract should bind those inputs to a PolicyOS transport query without treating diagram structure or a caller assertion as evidence?

## Options

1. **Optional request profile (proposed bridge).** Add strict `surrogate_data_profile` to the existing registered method parameters. Each row supplies `population_id`, observed `outcomes`, and `interventions`. Missing/null/malformed input remains typed and distinct. This is the smallest compatible path to call Y0 TRSO; it proves only that the caller made a declaration and that the declared names are in the admitted graph.
2. **Typed persisted profile artifact.** Define a versioned population-data profile with population identity, dataset refs, observation-window semantics, and resolver/verifier ownership. The method accepts its typed ref and verifies selected current content before invoking TRSO. This provides a route to evidence binding but requires an artifact, producer, lifecycle invalidation, and verifier contract that are not in this proposal.
3. **Extend the graph/selection-diagram contract.** Add population-indexed data availability as a graph-adjacent input. This may be convenient for callers, but it risks conflating structural mechanism shifts with dataset observability and still needs independent source verification.
4. **Add a population-indexed estimand IR.** Preserve `PopulationProbability` and its intervention population in a typed AST rather than retaining only the exact formula string plus typed quantity partitions. This is a separate schema and downstream compiler/consumer migration.

## Impact and migration

The request-profile option adds one optional parameter to the registered v1/v2 method signatures and does not change `SelectionDiagram`, `TransportabilityResult`, `TransportFormula`, or `EstimandAST` schemas. Direct ID continues through the direct Y0 API without a profile. Existing callers that select Y0/TRSO for a query with selection nodes and provide no profile now receive `y0_surrogate_data_profile_absent`; explicit null and malformed values have their own limitations. No profile is inferred from S-nodes, variable names, or context values.

A future persisted-profile decision would require profile acquisition, exact source identity, observation-time/epoch binding, content selection, independent verification, invalidation/reissue, and API/audit projection. A future typed population-indexed AST would require compiler support for population-specific quantity resolution and compatibility reads for existing formula-only results.

## Authority and time boundary

For the request-profile option, `profile_declaration` is `consumer_asserted`; graph-name membership is recomputed against the admitted graph. Source or target data existence, currentness, provenance, authenticity, and institutional authority are `not_established`. A successful Y0 expression is a mathematical identification result under the graph and caller profile, not proof that those populations' data exist or support an estimate. It does not make a result gate-eligible, publishable, or a current institutional claim. No causal or transport law is selected here, and no S-node is interpreted as an observed outcome/intervention declaration.

## Bouned prototype evidence

A pure controlled API probe on locked Y0 0.2.11 called `identify_outcomes()` on X→M→Y and returned a Sum/Product expression. A second call to `identify_target_outcomes()` on the same graph with one declared source population (outcome Y, intervention X) returned a TRSO expression containing both target (`pi*`) and source (`pi1`) probability quantities. The candidate adapter preserves the returned LaTeX and y0 serialization, selected profile digest, operation, and package version. These fixtures establish API use and typed projection only; they establish no external graph truth, data availability, currentness, or authority. The existing typed `EstimandAST` cannot retain population-indexed Y0 leaves.

## Remaining decision

Choose whether request-only profiles are acceptable for non-authoritative mathematical candidate generation, or whether Y0/TRSO should remain limited until a persisted verified profile contract exists. Decide separately whether the population-indexed expression needs a first-class IR AST before downstream compilation. Keep closure_ids empty until both decisions and their producer/consumer boundaries are accepted.
