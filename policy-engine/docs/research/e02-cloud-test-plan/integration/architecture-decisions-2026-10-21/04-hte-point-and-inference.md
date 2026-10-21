# AD-E02-04: computed HTE point, conditional interval, and refusal

Status: G architecture selection for implementation, 2026-10-21. Choose option 1 from the author packet, with the target/provenance qualifications and migration below. This does not accept the implementation or adjudicate B31, V4/V7 or any other finding. AD01–03 are preserved.

## Decision

Keep a usable **computed candidate point** when interval inference is unavailable. Introduce one discriminated HTE outcome slot with point-only, interval-bearing and refusal variants. Never manufacture an ATE CI from CATE dispersion, substitute missing within-row uncertainty with zero, or widen a native interval with the current unqualified guard on this new path.

Choose a small first inference profile that can be implemented with the current backend: **the exact EconML native interval for the mean effect over explicitly selected evaluation rows**, qualified as backend/model-conditional. Do not call it a validated population-ATE interval merely because the API class is `PopulationSummaryResults`. Independent causal identification, population sampling/transport, empirical coverage and publication authority remain separate claims.

Reject discarding every computed point, a generic CausalEffectReport status expansion, nullable success slots, NaN/sentinel bounds, and a universal fallback interval. A genuinely supported method-specific bootstrap may later receive a registered profile; this decision does not select a generic bootstrap or impose Bayesian-only inference.

## Contract and exact semantic split

Extend `ir/analytics/hte.py` and existing registries/persistence. Allocate the first persisted contract **`polisyos.ir.HTEOutcome`, version `1.0`**. The earlier author's `HTEOutcomeV2` is an illustrative proposal, not a deployed v1 predecessor; do not invent that history. Use new breaking method ABI versions for the four final shared-extractor families. Preserve old explicit method versions and artifact bytes for historical replay.

The selected successor identities are `causal.hte.causal_forest@2.0.0`, `causal.hte.double_ml@2.0.0`, `causal.hte.meta_learner@2.0.0` and `causal.hte.forest_dr@2.0.0`. They replace the output ABI, not the scientific method's name or original execution identity. Preserve the current serial ForestDR constraint (`n_jobs=1`) in its successor; this decision does not reopen AD02 or authorize another scheduler/inner fanout. Check for concurrent version allocation before writing; a collision requires an explicit compatible successor mapping, never overwriting an existing identity.

One required `hte_outcome` slot contains exactly one of:

| Variant | Required value | Meaning |
|---|---|---|
| `point_estimate` | `HTEPointEstimate` plus typed inference disposition/reasons | A computation produced a point for this declared target; no usable interval under the selected profile |
| `interval_estimate` | The same point semantics, immutable `HTEResult` v1 ref and `ATEInferenceBasis` ref | A selected native procedure produced the exact recorded conditional interval; no automatic causal/coverage/publication authority |
| `refusal` | Typed stage/reason and diagnostic refs | No usable admitted computation for the requested point/target; no numeric placeholder |

`HTEPointEstimate` and `ATEInferenceBasis` are new strict owner models, each version `1.0`, in the same HTE module, with existing registry/ArtifactRef conventions. The point can be embedded in the outcome and basis capture rather than allocated a second CAS object without a consumer need. No parallel governance ledger or generic inference service.

Every variant includes method FQN/version/ABI, frozen pre-output invocation/attempt anchor, source implementation/backend profile, input selection and purpose. Keep **requested target/guarantee** and **computed target/guarantee** in separate typed fields, plus a strict relation/disposition: exact request satisfied within its stated candidate scope, or `requested_claim_not_satisfied` with specific limitations. A selected-row result never fills a population-target field by adjacency. Point-bearing variants additionally carry:

- Point value and native target: outcome/contrast (including T0/T1), selected covariate rows/order and any weights, preprocessing/model profile, fit data versus evaluation data relation, selected estimator and selection procedure/data reuse.
- Quantity/unit relation: resolved binding where available; otherwise an explicit unknown binding tied to the source outcome representation. Unknown unit is a candidate limitation and cannot become a unit-qualified policy metric. AD01 remains the owner of that metric relation.
- Fit/evaluation counts separately; CATE values or bounded refs with exact row identities. Descriptive dispersion is distinct from standard error. Paired per-row intervals/SEs retain their own support/absence state.
- Observation/target time, execution and capture times, valid scope and limitations. A computed timestamp never establishes live source currentness.

Extra fields are forbidden. Absence and invalid-present inference are distinct. A point-only outcome has no primary ATE CI fields and no ATE p-value implying an unavailable test. An optional diagnostic artifact can retain rejected native output, but the primary result cannot present it as an admitted interval.

Do not also require the old independent `causal_effect_report`/`hte_result` pair on the new ABI. It would make the point-only branch impossible. A finite-interval compatibility report may be derived from the admitted branch; never synthesize `SUCCESS`, `NUMERICAL_FAILURE` or `ASSUMPTION_FAILED` for a legitimate point-only result. Existing generic report decoding remains unchanged.

## Initial inference profile and its limits

Select **`econml_native_mean_over_selected_x@1.0`** in the existing HTE method/profile owner. Its content-bound definition pins:

1. Supported EconML distribution/version and implementation digest, concrete estimator/fit-inference configuration and extraction protocol. The initial researched protocol is **EconML 0.17.0**, matching the supplied runtime receipt. Reconcile the installed distribution against that selection; another version needs an explicit compatibility entry, not a floating dependency. Each concrete estimator/inference implementation/configuration is a separate accepted entry under this profile family; membership is not inherited across all four wrappers. Method name or a discovered callable is not sufficient.
2. A single declared outcome and treatment contrast, a fixed uniform average over the exact supplied X rows, and source-bound fit/evaluation relationship (`same_rows`, disjoint or explicitly defined overlap). Nonuniform weighting, another treatment axis or superpopulation targets require another defined profile.
3. Actual `ate_inference(X, T0, T1)` and `conf_int_mean(alpha=...)` results, requested alpha with `0 < alpha < 1`, unrounded native point/bounds and relevant native uncertainty fields. Admission enforces `HTEPointEstimate.value == HTEResultV1.ate == native.mean_point == selected aggregate effect` under the pinned numerical comparison rule. Mismatch is not repaired by recentering. Bounds in the admitted result equal the captured native bounds without a widening/recentering transform.
4. The **native uncertainty route**: backend-provided mean SE where available, or the backend's documented conservative mean-SE procedure. Preserve which was used. EconML's own conservative aggregation is different from PolicyOS's current CATE-dispersion/zero-substitution guard. Neither `std_point` nor percentiles across CATE predictions is the SE/CI of their mean.
5. A claim boundary: `backend_conditional_interval`; target-row frame, model assumptions and empirical-assumption status are visible. `population_sampling_coverage`, `causal_identification`, `transport_validity` and `empirical_calibration` remain unestablished unless independently supplied and admitted by their existing owners.

The profile author must inspect the pinned backend implementation and reference method documentation/theory, distinguishing a conditional model assumption from a checkable execution predicate. Specify why the SE procedure and normal approximation apply to this concrete estimator/configuration and fixed-row target. A conservative SE bound alone does not establish nominal coverage. Model assumptions may remain explicit conditional premises in candidate work; checkable invocation/config/input predicates must actually be recomputed. Unsupported method-law entries stay point-only, with native raw output diagnostic. This is ordinary internal scientific/engineering work; no outside issuer is needed to document what the backend computes. It does not permit a package label to substitute for such inspection.

The mathematical distinction is concrete. For a fixed frame of m prediction errors with covariance matrix Sigma and true marginal standard deviations s_i, Cauchy–Schwarz gives `Var(mean error) <= (mean s_i)^2 <= mean(s_i^2)`. This bounds dependence without assuming independent rows; it neither estimates the s_i nor proves centering, negligible bias or a normal approximation. Substituting estimated backend SEs therefore yields a conditional/asymptotic procedure, not a distribution-free guarantee. An independent-row `sqrt(sum(s_i^2))/m` shortcut and a CATE-dispersion shortcut are both outside this profile. The runtime records the native procedure, while its documented assumptions remain attached to the candidate result.

Each initial entry must state its actual estimator/inference class, fit options, mean-SE route, reference law and target/data-reuse conditions. Start with the concrete configurations already exercised by the supplied repaired-adapter receipt; those receipts establish execution only. An entry with unsupported method conditions remains point-only while other entries can ship. This is bounded profile qualification, not a new G approval round for every method name.

A native `PopulationSummaryResults` output can thus be retained with its honest bounded meaning before a population-ATE claim is justified. If the request explicitly requires a population confidence guarantee, the overall requested claim remains limited even while this conditional interval is visible. Consumers may not silently treat the two claims as equivalent.

Keep **estimator** and **estimand** separate as well. The observed point is the mean of fitted CATE predictions. A qualified conditional interval concerns the corresponding mean of underlying conditional effects at the selected X frame under the named model/identification premises; it is not uncertainty about the arithmetic mean of already stored prediction bytes. If that inferential target/law is unsupported for the selected configuration, only the computed point is admitted. Neither interpretation by itself establishes a population sampling or transport guarantee.

Post-fit selection is binding. For selected S/T/X or a subgroup chosen using the same outcomes, absent a selection-valid procedure the result is point-only on the qualified path; an ordinary backend interval is a diagnostic, not a nominal post-selection interval. A fixed preselected estimator may use the native profile if the other conditions hold. Do not fix data reuse by renaming the method or relabeling training rows as an independent evaluation sample.

Initial representability also requires the unchanged strict HTEResult v1 shape: finite ordered bounds containing its point, consistent dimensions and sample fields. This is a boundary of this first schema/profile, not a theorem that all valid intervals contain their point. A later supported asymmetric/bias-corrected procedure that violates this legacy shape requires a new payload version, not clamping. Newly produced `subgroup_effects` with inferred CI/significance are empty unless separately supported; existing CATE-bin percentiles may be preserved only as descriptive diagnostics with that name. Feature importance is model descriptive, not causal evidence.

## Acyclic persistence and actual origin

Use this order of dependencies (each later object references earlier objects):

`frozen intent/input/profile → owned fit/capture → native result → inference basis → outcome → admitted projection`.

The existing Runtime owner creates a stable **pre-output attempt anchor** containing frozen intent/fence. Outcomes reference that anchor. The **later** output/verification association references anchor and outcome; it is a later event/projection or an existing mutable owned index, never the same content-addressed anchor. This preserves `outcome→anchor` and `association→outcome` without a cycle. Raw HTEResult v1 on the new path has no self-CAS ID or backlink to a containing outcome/basis. The basis may reference the result and native capture; the result must not reference the basis. A verification receipt is a later independent object referencing the outcome/basis, never a receipt whose hash the same basis must contain. This avoids impossible content-hash cycles.

`ATEInferenceBasis` binds selected profile, invocation/fit, exact input/evaluation-target refs, method/backend/executable identity, operation/config/alpha, native scalar/vector capture refs, unchanged interval-result ref, numeric representation rule and capture provenance. Persist the minimal sufficient native fields, not a serialized Python estimator. Large vectors use existing CAS refs; GET does not deserialize an estimator or refit.

Admission resolves actual bytes, checks schema/kind/media/profile, recomputes target/input closure, shape and numerical equality, and reconciles the capture with the **owned selected attempt**. A self-consistent forged result/basis with recomputed hashes fails that origin check. Hash integrity alone is not independent execution evidence. Existing trusted runtime provenance is sufficient inside that trust boundary; do not invent cryptographic attestation for every local method call.

Substantive verification runs in the existing admitted worker. The existing owned evaluation/run record atomically binds the verified projection to the result/fence and verifier revision. Late verification cannot qualify another winning attempt. Fresh readers consume the bounded projection and check current selection/access/policy compatibility, not refit the model or scan all CATE values on each GET.

## Failure semantics

| Observation | Outcome / action |
|---|---|
| Valid computed point; inference explicitly disabled or unsupported | `point_estimate`, `inference_not_requested` or `inference_unsupported` |
| Valid point; native mean interval unavailable under the selected protocol | `point_estimate`, `inference_unavailable`; never insert zero variance |
| Valid point independently captured; inference attempt errors or returns malformed/foreign values | `point_estimate` with `inference_failed`/`inference_invalid`, failed inference diagnostic retained; not a successful inference run |
| Point/target/origin invalid, fit failed, missing required backend, or error prevents validating the point | `refusal`; preserve diagnostics, no finite proxy |
| Supported interval computed but requested population/selection/authority claim unsupported | Show the bounded conditional result where valid; requested stronger claim remains limited/unavailable |

Known protocol absence is distinguished from unexpected exceptions. Do not blanket-catch backend errors and emit apparent normal absence. Optional SHAP/feature diagnostics can fail independently; they do not fabricate an interval or erase an otherwise correctly captured point. Selection-invalid intervals follow the specific point-only rule above.

## Migration and full footprint

Cover the four final producers sharing the extractor: CATE, DML, selected S/T/X, ForestDR. The internal S/T/X scoring call consumes pointwise effects only and is not a fifth persisted producer. CausalBCF is outside this stated denominator unless an actual source census establishes a shared contract change.

- IR HTE models/refs/registry/persistence/public exports and serialization schema.
- Foundry method signatures, registration/version selection, output-slot coercion, shared extractor and four final producers. The new branch bypasses `_guarded_ate_standard_error`, `robust_standard_error(cate)` fallback and the fixed 1.96 widening entirely.
- Scientist `run_causal_evaluation.py`, orchestration output protocol, decision-packet outcome sections, existing Runtime attempt/verification association and AD01 measured-output consumer. HTE-specific readers must dispatch on the discriminant; a generic numeric dictionary is not compatibility.
- Public DTO/API/schema/generated clients/browser/export; refusal and point-only display must be visible, not an omitted section. Packaging and relevant current-version docs are mandatory companions.

Deploy readers → producers/versioned writers → associations/admission → ordinary current consumers/default selection. Existing pinned old ABI runs remain explicit historical/compatibility executions. On current qualification routes, an old finite HTEResult without basis cannot act as a successful replacement for a new point-only outcome. Surface it as legacy/unqualified. Migrate all default current selectors in the same finished slice; leaving the new contract unused is not delivery.

Do not rewrite old artifacts or add inferred basis refs. A later inference is a new attempt/artifact with lineage. A historical replay preserves original behavior but cannot retain contemporary qualified-publication meaning merely through the old `SUCCESS` string. Legacy guard removal is for the new version, not silent reinterpretation of old ABI results.

## Deciding signals

1. Actual supported backend with fixed selected method and no available mean inference → persisted point-only → fresh Scientist/decision packet/HTTP reader; no fabricated bounds or disappearing result section.
2. Actual native profile → raw capture, owned attempt and exact conditional interval → fresh reader. Verify alpha other than 0.05; mean SE versus cross-row dispersion; one outcome/contrast, row identity, fit/evaluation reuse and unit-binding state.
3. Remove inference availability with points unchanged; preserve all method/profile labels. The primary result changes variant. Remove the origin association with bytes/hashes intact: qualified admission fails.
4. Independently mutate profile, input/target, alpha, native bounds, result bounds, selected fit/attempt or numerical-representation policy. Also forge the entire CAS graph coherently; it still cannot acquire an owned execution origin.
5. Native narrow interval versus broader legacy guard: new result equals the native interval, not the guard. Missing row uncertainty remains missing. A supplied conservative native procedure is not mislabeled as the local fallback.
6. Post-selection, unsupported population target, missing profile, malformed inference, interval not representable by v1 and unknown unit each retain their distinct limitations. No p-value/CI is promoted through metadata or a legacy alias.
7. All four final producers plus the independent point-only scoring consumer; installed public readers, required slots, API/generated surface; cold GET with heavy methods forbidden. Removal of producer/bridge or discriminant handling must fail the real path.

These checks are future implementation obligations, UNRUN here. The newer adapter/ForestDR receipt reports scoped runtime success on `80f7c18f…`; this supersedes the early packet's adapter-failure narrative for that exact test scope, but does not resolve this outcome contract or scientific guarantees.

## External basis and pattern pass

[EconML PopulationSummaryResults](https://www.pywhy.org/EconML/_autosummary/econml.inference.PopulationSummaryResults.html) distinguishes mean estimates, their uncertainty and across-row dispersion. The public documentation served at research time identifies version 0.16.0; use the [tagged 0.17.0 inference source](https://raw.githubusercontent.com/py-why/EconML/v0.17.0/econml/inference/_inference.py) and [tagged effect/ATE source](https://raw.githubusercontent.com/py-why/EconML/v0.17.0/econml/_cate_estimator.py) for the selected extraction protocol, reconciling their relevant bytes with the actual installed distribution. These references justify protocol distinctions; they do not certify that installation, causal assumptions or actual coverage. The covariance bound above is an independent mathematical explanation of why dependent predictions and heterogeneity must not be interchanged.

Genuine external dependencies are actual data/provenance, target sampling/transport evidence, relevant empirical calibration and permissions. Documenting and implementing a versioned conditional backend protocol is not an external dependency. P04/P05/P07/P08/P10/P14/P27/P29/P31/P32/P37/P38/P40: preserve point versus interval availability, separate identity/origin/inference/authority, close all shared final producers, and test semantic removal rather than field presence. New result/bridge/surface remain incomplete until implemented; B31's source-owned same-estimand/unit separation remains an independent criterion.
