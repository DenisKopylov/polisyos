# AD-E02-06 / B161: first assessment without erasing history

Status: G architecture selection for implementation, 2026-10-21. Select B from the author packet, with the concrete narrow transition below. This is not code acceptance or B161 closure. Historical B198 and accepted D04/AD01–03 remain unchanged.

## The selected relation

The initial permitted relation is **`unassessed_to_assessed_same_basis@1.0`**. It replaces one explicit unassessed placeholder with an actual assessment of that same uncertainty obligation. Initial production wiring covers the statistical component through the selected native-measure/relative-width profile below. L3/L4 model-tier values and measurement/transport defaults cannot ride this relation. It does not claim that later evidence is always better, that a smaller number is truer, or that a new posterior can generically replace an earlier risk.

The exact original B161 criterion permits this first assessment. It does not require a universal scientific law for monotonically decreasing uncertainty. Reject historical-max-only as the current result, global `min`, latest-write, stage-number ordering and automatic overwriting of already-assessed values. Keep the historical maximum as a separately named historical diagnostic.

An actual assessed value of 1.0 is not unknown. A typed unassessed predecessor is required; neither `level==1` nor strings such as `static_rule`/`not_assessed` prove that state. A migration adapter can classify a legacy observation only from its admitted producer operation and contract; arbitrary legacy envelopes remain routing-only and cannot activate this relation.

## Scope, state and owner

Reuse `scientist/methods/search/uncertainty.py`, its CAS artifacts, the funnel ticket/current projection, and existing owned runtime selection. Do not build a new truth engine, risk scheduler or event store.

Extend `SearchUncertaintyBasis` and `SearchUncertaintyObservation` with explicit **2.0** variants; v1.0 remains readable as routing-only. The new fields form this semantic contract (strict, immutable models; no free-form metadata replacement):

| Part | Required meaning |
|---|---|
| Stable scope | Exact subject/candidate view; semantic quantity/estimand, treatment contrast, population, outcome, unit representation, uncertainty component and obligation ID |
| Frozen input basis | Complete role-qualified selected scientific inputs, model/graph, rule/profile and procedure/config/selection refs; owner-derived dependency inventory |
| State | `unassessed` with reason and no numeric assessment, or `assessed` with source-result ref, native measure, optional qualified routing score and profile |
| Origin | Actual producer/run/attempt/implementation refs reconciled with the selected owned attempt; not a producer-provided name |
| Time | Target/valid epoch, source observation interval, computation/admission times; explicit as-of mode, with live currentness separately established or unavailable |
| Relation | Specific predecessor observation ref, successor observation ref, exact relation-profile ref and source-qualified verification result |

The semantic quantity is not its changing numerical estimate. Do not demand equality of earlier/later result bytes or overload existing `value_ref` to mean both quantity identity and a numeric output. Bind a stable quantity/obligation ref and separate result refs in v2.0. New result artifacts are consequences of computation, not changes to the frozen scientific inputs. Dependency completeness is derived from the actual selected executable plan/config/source graph or independently reconciled against it; a producer-supplied list/hash is insufficient. Bind the complete role-qualified set, not merely every member of a supplied subset.

Persist the relation as `polisyos.scientist.SearchUncertaintyRefinement` version `1.0` under the existing uncertainty owner: predecessor ref, successor ref, scope/basis ref, relation profile ref, selected attempt/verification ref and expected ticket generation. Dependencies are acyclic: basis → observations → refinement → bounded current projection. No successor observation contains the hash of its enclosing refinement. The current projection is selected through the existing ticket revision mechanism, not a second ledger.

For this first relation, all material input selections remain equal. A changed dataset/model/profile/valid epoch is a **new basis**. The system can start its own current projection with visible predecessor lineage, but it cannot silently supersede the old projection or claim this same-basis refinement. More general evidence updates/transport/calibration laws are future profile extensions only when substantively justified.

At task admission the owner creates the explicit unassessed obligation for the selected scope. This replaces an implicit placeholder convention with a real producer operation. The later method owner produces a content-bound assessment. Search admission verifies both and produces the relation. A caller cannot supply a smaller envelope and ask the orchestrator to trust it.

## An implementable first score profile

B161's state transition need not wait for an outside institution to define an internal routing convention. Select the existing nonzero-effect computation, under an honest name:

**`relative_interval_halfwidth_routing@1.0`**, candidate search scheduling only.

For a validated interval `[L,U]` and point estimate `theta` of the same quantity, let `w=U-L`. If `theta` is finite and nonzero, `L,U` are finite and ordered, and their units/estimand/basis match, compute `raw_ratio = w / (2*abs(theta))`, `score = min(1, raw_ratio)`. Retain `theta,L,U,w`, the uncapped ratio or an explicit overflow indication, interval semantics, and the selected profile. Saturation is disclosed; it is not hidden clipping of invalid input. Use a numerically stable evaluation so intermediate overflow cannot yield a spurious zero.

This is a **relative imprecision routing score**: larger means wider relative interval. It is not a probability of error, a calibrated risk, a confidence level, evidence of causality, or a measure of model/transport/legal uncertainty. It may order candidate work; by itself it cannot prune/stop a candidate, certify completeness or satisfy promotion/admissibility/authority. Existing resource budgets still govern execution, with deferred work visible. Ranking requires the same selected quantity/scale, interval level/semantics (pointwise versus simultaneous included), target sampling and model-conditional profile. Different alpha, sampling regimes or conditionality are incomparable unless a separate explicit comparison profile supports them. No cross-unit or cross-quantity total order is implied. A genuine native zero-width interval with nonzero theta has score zero; it still carries its original assumptions and identification limits.

For `theta=0`, retain the assessed native interval/point but mark this relative score unavailable (`zero_reference_scale`), including when width is zero. `assessment_state=assessed` is independent of `routing_score=unavailable`; this does not turn an existing native assessment back into unknown. Near-zero effects retain the raw quantities and the declared saturation/instability limitation; no hidden epsilon is introduced. Missing, malformed, nonfinite or negative width is unavailable/invalid, never numeric confidence. An interval supplied only as a label or `ci_width` field is insufficient: its actual producer, target and interval semantics must be resolved. A dimensionful or differently scoped native measure may be retained without this score.

The quantity must also have a bound zero/reference-scale meaning for this ratio. A treatment-effect contrast can retain its no-effect zero under an admitted multiplicative unit conversion; a generic level with an arbitrary additive origin cannot. If the quantity definition or unit transform does not establish that condition, retain the native assessment with `reference_scale_not_established`, not a fabricated relative score. Comparing numbers expressed in the same named unit alone is insufficient.

Example, **constructed arithmetic discriminator**: point 2 and interval [1.8,2.2] yield score 0.1 within numeric tolerance. A prior typed unassessed placeholder is replaced only for this obligation. A separate active comparable constraint with score 0.8 remains 0.8; another unknown component stays unknown. This is not an empirical uncertainty or independence demonstration.

Reuse the actual interval-producing owner (including an admitted AD04 outcome where applicable), not a new pseudo-bootstrap. The initial profile does not supply a missing CI law: it can transform a supported model-conditional interval for candidate routing, carrying that condition forward. An HTE point-only result cannot manufacture a statistical score. Existing L3/L4 CI-width code is the implementation starting point, not proof of correct provenance or a license to keep its misleading bootstrap labels/defaults.

## Composition and concurrency

Maintain three separate views:

1. **History:** immutable observations and decisions; the legacy conservative maximum is explicitly historical and may include an unknown placeholder. It is never described as current knowledge.
2. **Current per obligation:** only an admitted first-assessment edge can replace its named unassessed predecessor. Already-assessed observations are not lowered by this profile.
3. **Active constraints/disagreement:** independent or otherwise separate risks remain active. They do not need a statistical independence claim merely to remain visible. A maximum over compatible scores is a worst-component routing summary, not a joint probability. Incompatible scales remain separate; do not average them into apparent certainty.

Unknown components remain unknown. An invalid observation is recorded as an intake failure for its own obligation and does not erase valid unrelated assessments. If a relevant scheduled attempt is incomplete, expose incomplete coverage instead of reporting the whole current set complete.

The existing ticket/owned state revision fences updates. Bind the relation to the expected predecessor and generation. Duplicate identical delivery is idempotent. Two distinct same-generation successors are retained and produce a contested current component unless an already selected, independently justified producer-selection policy resolves them. A transaction/CAS winner is only a storage winner, not evidence superiority. Late arrival must not silently overwrite or disappear; record the conflict and recompute the view. Do not pick the smaller score or newer timestamp.

If a conflict arrives after a first projection was served, increment the owned revision and invalidate that projection for current reads; retain it only as an honest earlier as-of view. A cache cannot preserve the earlier uncontested state after reconciling the conflict event.

A replay reconstructs the same as-of projection from pinned admitted observations, relation policy and generation. "Current" must say whether it means current knowledge about this frozen task epoch or a live-world claim. The former needs the task's selected basis; the latter needs actual live currentness. Without that evidence, keep the live projection unavailable while allowing the qualified as-of view. Fresh public read does not rerun simulations or scan full sample arrays. The admission worker performs substantive source verification and persists a bounded projection; reads check selected refs, state revision, compatible verifier/rule and current access. Expired/inapplicable currentness invalidates the live claim while preserving an honest historical as-of result.

## Minimum producer/consumer/surface footprint

- Existing uncertainty models/writers/readers and source-bound observation producer; actual L3/L4 method-result bridge in `search/stages.py` and funnel adapters. Do not stop at the current uninvoked persistence helper.
- `funnel/orchestrator.py` current composition, `funnel/types.py` ticket/outcome and score semantics; existing persistence/lifecycle fence for the ticket. Preserve ordinary `final_result` versus current/historical distinctions.
- SearchController, work-packet/VOI, judge and decision-packet consumers that use uncertainty must select the intended projection. Candidate scheduling may consume a named routing score; authority/promotion must not treat it as empirical assurance.
- Existing public DTO/API/export/dashboard surfaces: show native assessment, score meaning, scope, current/historical states, active constraints, limitations and provenance. Generated/schema/readme companions are part of the same delivery.

Readers-first migration, then the real producer and relation writer, then current consumers. Preserve v1 bytes and historical behavior for explicit replay. Default current routes must use v2 or report unavailable; an alias to legacy `merge_max` is not migration. Do not backfill typed unknown state or valid-time authority from old strings.

## Acceptance and adversarial signals

- Real producer → selected CAS basis/assessment → relation admission → persisted current projection → fresh funnel consumer/API: typed unassessed → 0.1, history still includes 1, active separate 0.8 retained, another component unknown.
- Replace predecessor with an actual assessed 1.0, keeping all display labels: refinement refuses. An assessed 0.9 cannot be reduced to 0.1 through this first-assessment relation.
- Change subject/population/estimand/unit, one material input, method/profile/rule, quantity identity or valid epoch independently. Each mismatched edge is withheld without losing the new candidate artifact.
- Forge the basis/result/relation together and recompute all hashes: lacking an owned producer attempt or valid dependency inventory still refuses.
- Remove the relation or producer invocation while retaining markers and finite numbers: current refinement disappears. Remove only history preservation or independent-constraint retention: the end-to-end discriminator fails.
- Zero, near-zero, legitimate zero width, malformed width, saturation, mismatched units, arbitrary additive reference shifts and point-only HTE each preserve the specified measure/score distinction. No NaN/Inf enters a score.
- Opposite arrival order of two successors, duplicate delivery, stale ticket revision, replay-as-of and late retry cannot silently select favorable evidence or erase disagreement.
- Remove live-currentness evidence with a valid as-of assessment unchanged: the as-of view remains and the live view is unavailable. Change interval alpha/semantics or sampling profile: no silent numeric ranking under the old comparison profile.

No runtime result is claimed here. Missing parts remain `producer_missing`/`bridge_missing`/`verification_missing`/`surface_missing` until the actual chain is built and reviewed. This decision resolves the first-assessment relation and routing convention; it does not provide real-world calibration, live source currentness, external permissions or a general assessed-to-assessed updating law.

## Research and pattern pass

[Microsoft's event-sourcing guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) supports retaining events separately from materialized views and checking concurrent revisions; it also warns about the cost of adopting a whole new event-sourced architecture. We use the existing owner and persistence. [W3C PROV-DM revision/derivation](https://www.w3.org/TR/prov-dm/) motivates explicit predecessor/result lineage; it does not decide scientific superiority.

P04/P08/P10/P14/P27/P29/P31/P32/P37/P38/P40: distinguish knowledge state from numeric proxy; content-binding from scientific support; history from current; separate constraints from a joint probability. The decisive counterexample is a genuine assessed 1.0 versus an unassessed placeholder displayed as 1.0. The numeric proxy alone cannot distinguish them. No universal scientific refinement contract is introduced.
